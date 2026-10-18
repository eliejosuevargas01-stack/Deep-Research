import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update

from app.core.config import settings
from app.db.database import AsyncSessionLocal, engine
from app.models import Base, Research, ResearchPoint, ResearchStatus
from app.routers.auth import router as auth_router
from app.routers.research import router as research_router, schedule, schedule_revision, schedule_scout, _running
from app.routers.settings import router as settings_router
from app.briefing.router import router as briefing_router
from app.investigation.router import router as investigation_router
from app.audit.router import router as audit_router

_investigation_running: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        scouting = list((await db.scalars(select(Research.id).where(Research.status.in_([ResearchStatus.BRIEFING, ResearchStatus.BRIEFING.value])))).all())
        # E001 (A-C8-06): literais legados "scouting", "revising", "approved" e
        # "in_progress" removidos — nunca casam com o enum unificado
        # (consultas mortas que sempre retornavam vazio). Sem estado de revisão
        # pendente separado: a retomada de revisões usa run_revision sob demanda.
        revising: list = []
        active: list = []
        # RN-11: resume investigations interrupted by restart (points stuck in SCRAPER_IN_PROGRESS)
        interrupted = list((await db.scalars(
            select(Research.id).where(
                Research.status.in_([ResearchStatus.SCRAPER, ResearchStatus.SCRAPER.value]),
                Research.id.in_(select(ResearchPoint.research_id).where(ResearchPoint.status == "SCRAPER_IN_PROGRESS")),
            )
        )).all())
    for research_id in scouting:
        schedule_scout(research_id)
    for research_id in revising:
        schedule_revision(research_id)
    for research_id in active:
        schedule(research_id)
    if interrupted:
        from app.investigation.service import InvestigationService
        investigation_service = InvestigationService(AsyncSessionLocal)
        for research_id in interrupted:
            task = asyncio.create_task(investigation_service.run_investigation(research_id))
            _investigation_running.add(task)
            task.add_done_callback(_investigation_running.discard)
    yield
    # Clean shutdown: cancel pending background tasks and dispose engine
    from app.routers.research import _running
    pending = set(_running) | set(_investigation_running)
    for task in pending:
        if not task.done():
            task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    if settings.ENVIRONMENT.lower() != "test":
        await engine.dispose()


app = FastAPI(title="Deep Research Engine", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    raw_errors = jsonable_encoder(exc.errors())
    clean_errors = []
    for err in raw_errors:
        if isinstance(err, dict):
            clean_err = dict(err)
            clean_err.pop("input", None)
            if "msg" in clean_err and clean_err["msg"].startswith("Value error, "):
                clean_err["msg"] = clean_err["msg"].replace("Value error, ", "", 1)
            clean_errors.append(clean_err)
        else:
            clean_errors.append(err)
    return JSONResponse(status_code=422, content={"detail": clean_errors})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "Last-Event-ID", "X-API-Key"],
)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(research_router)
app.include_router(briefing_router)
app.include_router(investigation_router)
app.include_router(audit_router)


@app.get("/health")
async def health():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "healthy", "database": "connected", "version": app.version}
