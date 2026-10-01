import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models import AdminSession

COOKIE = "dr_session"
MUTATIONS = {"POST", "PUT", "PATCH", "DELETE"}


def digest(value: str) -> str:
    return hmac.new(settings.SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


@dataclass
class Principal:
    session: AdminSession | None
    via_bearer: bool = False


async def require_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    if request.headers.get("x-tenant-id"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client tenant identity is not accepted")
    bearer = request.headers.get("authorization", "")
    if bearer.startswith("Bearer ") and settings.API_AUTH_SECRET:
        if hmac.compare_digest(bearer[7:], settings.API_AUTH_SECRET):
            return Principal(None, True)
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    row = await db.scalar(select(AdminSession).where(AdminSession.token_hash == digest(raw)))
    now = datetime.now(timezone.utc)
    if not row or row.revoked_at or row.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")
    if request.method in MUTATIONS:
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not hmac.compare_digest(row.csrf_hash, digest(supplied)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    return Principal(row)


def new_session_values() -> tuple[str, str, AdminSession]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    record = AdminSession(
        token_hash=digest(token), csrf_hash=digest(csrf),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_TTL_HOURS),
    )
    return token, csrf, record
