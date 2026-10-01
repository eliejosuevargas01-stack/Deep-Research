from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, update

from app.core.config import settings
from app.db.database import AsyncSessionLocal, engine
from app.models import Base, Research
from app.routers.auth import router as auth_router
from app.routers.research import router as research_router, schedule, schedule_scout
from app.routers.settings import router as settings_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        scouting = list((await db.scalars(select(Research.id).where(Research.status == "scouting"))).all())
        active = list((await db.scalars(select(Research.id).where(Research.status.in_(["approved", "in_progress"])))).all())
    for research_id in scouting:
        schedule_scout(research_id)
    for research_id in active:
        schedule(research_id)
    yield
    await engine.dispose()


app = FastAPI(title="Deep Research Engine", version="1.0.0", lifespan=lifespan)
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
