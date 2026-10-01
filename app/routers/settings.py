from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import Principal, require_admin
from app.db.database import get_db
from app.schemas import SettingsUpdate
from app.services.settings import public_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(_: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await public_settings(db)


@router.put("")
async def put_settings(payload: SettingsUpdate, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await update_settings(db, payload.provider_keys, payload.models)
