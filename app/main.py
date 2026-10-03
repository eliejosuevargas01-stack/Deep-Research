from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update

from app.core.config import settings
from app.db.database import AsyncSessionLocal, engine
from app.models import Base, Research
from app.routers.auth import router as auth_router
from app.routers.research import router as research_router, schedule, schedule_revision, schedule_scout
from app.routers.settings import router as settings_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        scouting = list((await db.scalars(select(Research.id).where(Research.status == "scouting"))).all())
        revising = list((await db.scalars(select(Research.id).where(Research.status == "revising"))).all())
        active = list((await db.scalars(select(Research.id).where(Research.status.in_(["approved", "in_progress"])))).all())
    for research_id in scouting:
        schedule_scout(research_id)
    for research_id in revising:
        schedule_revision(research_id)
    for research_id in active:
        schedule(research_id)
    yield
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
            clean_errors.append(clean_err)
        else:
            clean_errors.append(err)
    return JSONResponse(status_code=422, content={"detail": clean_errors})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "Last-Event-ID"],
)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(research_router)


@app.get("/health")
async def health():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "healthy", "database": "connected", "version": app.version}
