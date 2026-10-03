import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
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
    via_api_key: bool = False


async def require_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    # Client tenant identity headers are strictly prohibited (A-04 & frontend criteria)
    if "x-tenant-id" in request.headers:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client tenant headers are prohibited")

    raw_cookie = request.cookies.get(COOKIE)
    auth_header = request.headers.get("authorization", "")
    api_key_hdr = request.headers.get("x-api-key", "")

    # Reject simultaneous or ambiguous credentials
    active_creds = sum([
        bool(raw_cookie),
        bool(auth_header),
        bool(api_key_hdr),
    ])
    if active_creds > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ambiguous authentication: multiple credential types supplied")

    if auth_header:
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication scheme")
        token = auth_header[7:].strip()
        if settings.API_AUTH_SECRET and hmac.compare_digest(token, settings.API_AUTH_SECRET):
            return Principal(None, via_bearer=True, via_api_key=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing Bearer token")

    if api_key_hdr:
        token = api_key_hdr.strip()
        if settings.API_AUTH_SECRET and hmac.compare_digest(token, settings.API_AUTH_SECRET):
            return Principal(None, via_bearer=False, via_api_key=True)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    if not raw_cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    # Validate JWT session token
    jti_digest: str
    try:
        payload = jwt.decode(raw_cookie, settings.SESSION_SECRET, algorithms=["HS256"])
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token")
        jti_digest = digest(jti)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    except (jwt.InvalidTokenError, jwt.DecodeError):
        # Fallback for legacy opaque sessions during safe migration
        jti_digest = digest(raw_cookie)

    row = await db.scalar(select(AdminSession).where(AdminSession.token_hash == jti_digest))
    now = datetime.now(timezone.utc)
    if not row or row.revoked_at or row.expires_at.replace(tzinfo=timezone.utc) <= now:
        await db.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")

    if request.method in MUTATIONS:
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not hmac.compare_digest(row.csrf_hash, digest(supplied)):
            await db.rollback()
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")

    return Principal(row)


def new_session_values() -> tuple[str, str, AdminSession]:
    jti = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.SESSION_TTL_HOURS)

    payload = {
        "sub": "admin",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    jwt_token = jwt.encode(payload, settings.SESSION_SECRET, algorithm="HS256")
    record = AdminSession(
        token_hash=digest(jti),
        csrf_hash=digest(csrf),
        expires_at=expires_at,
    )
    return jwt_token, csrf, record

