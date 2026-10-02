import hmac
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import COOKIE, Principal, digest, new_session_values, require_admin
from app.db.database import get_db
from app.schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    if not hmac.compare_digest(payload.password, settings.ADMIN_PASSWORD):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token, csrf, record = new_session_values()
    db.add(record)
    await db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.production, samesite="lax", max_age=settings.SESSION_TTL_HOURS * 3600, path="/")
    return {
        "authenticated": True,
        "role": "admin",
        "csrf_token": csrf,
        "jwt_token": csrf,
        "api_key": settings.API_AUTH_SECRET or "session-admin",
    }


@router.get("/me")
async def me(_: Principal = Depends(require_admin)):
    return {"authenticated": True, "role": "admin"}


@router.get("/csrf")
async def refresh_csrf(principal: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if principal.session is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cookie session required")
    csrf = secrets.token_urlsafe(32)
    principal.session.csrf_hash = digest(csrf)
    await db.commit()
    return {"csrf_token": csrf}


@router.post("/logout", status_code=204)
async def logout(response: Response, principal: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if principal.session:
        principal.session.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    response.delete_cookie(COOKIE, path="/")
