"""Módulo de gerenciamento de sessão local e segurança para navegador (UI Session).

Atende aos requisitos de autenticação automática para acesso local legítimo,
emissão de cookie HttpOnly SameSite=Strict assinado e verificação estrita de mesma origem (CSRF).
"""

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)

COOKIE_NAME = "dr_local_session"
DEFAULT_SESSION_TTL_SECONDS = 86400  # 24 horas

ALLOWED_SEARCH_PERSONAS = ["historiador", "visionario", "cetico", "futurista"]
ALLOWED_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}

# Chave privada gerada por processo caso nenhum segredo esteja configurado
_EPHEMERAL_SECRET: bytes = secrets.token_bytes(32)


def _get_signing_key() -> bytes:
    """Obtém chave de assinatura privada sem jamais expô-la ou logá-la."""
    settings = get_settings()
    secret_str = (
        os.environ.get("API_SECRET_KEY")
        or getattr(settings, "api_secret_key", None)
        or os.environ.get("WEBHOOK_HMAC_SECRET")
        or getattr(settings, "webhook_hmac_secret", None)
        or os.environ.get("CREDENTIALS_MASTER_KEY")
        or getattr(settings, "credentials_master_key", None)
    )
    if secret_str and str(secret_str).strip():
        return hashlib.sha256(str(secret_str).strip().encode("utf-8")).digest()
    return _EPHEMERAL_SECRET


def _is_loopback_ip(ip_str: Optional[str]) -> bool:
    """Verifica com parsing estrito se o endereço IP é loopback local (127.0.0.0/8 ou ::1)."""
    if not ip_str or not isinstance(ip_str, str):
        return False
    clean_ip = ip_str.strip()
    try:
        return ipaddress.ip_address(clean_ip).is_loopback
    except ValueError:
        return False


def _is_local_host(host_str: Optional[str]) -> bool:
    """Verifica se o cabeçalho Host corresponde estritamente a um host local permitido."""
    if not host_str or not isinstance(host_str, str):
        return False
    h = host_str.strip()
    # Tratamento de IPv6 com colchetes: ex: [::1] ou [::1]:8000
    if h.startswith("["):
        idx = h.find("]")
        if idx != -1:
            raw_host = h[1:idx]
        else:
            return False
    else:
        # Separa porta caso informada
        raw_host = h.split(":")[0].strip()

    raw_host_lower = raw_host.lower()
    if raw_host_lower in ALLOWED_LOCAL_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(raw_host_lower).is_loopback
    except ValueError:
        return False


def get_request_origin(request: Request) -> str:
    """Extrai a origem canônica da requisição (scheme://host[:port])."""
    scheme = "http"
    if hasattr(request, "scope") and isinstance(request.scope, dict):
        scheme = request.scope.get("scheme") or "http"
    elif hasattr(request, "url"):
        try:
            scheme = getattr(request.url, "scheme", "http") or "http"
        except Exception:
            scheme = "http"
    scheme = str(scheme).lower()

    host_header = request.headers.get("host") if hasattr(request, "headers") else None
    if host_header and host_header.strip():
        host = host_header.strip().lower()
    else:
        server = (
            request.scope.get("server")
            if (hasattr(request, "scope") and isinstance(request.scope, dict))
            else None
        )
        if server and isinstance(server, (list, tuple)) and len(server) >= 2:
            h, port = server[0], server[1]
            host = f"{h}:{port}" if port not in (80, 443, None) else str(h)
        else:
            try:
                host = request.url.netloc.strip().lower()
            except Exception:
                host = "localhost"
    return f"{scheme}://{host}".rstrip("/")


def _canonical_origin(url_str: Optional[str]) -> Optional[str]:
    """Extrai a origem canônica (scheme://netloc) de uma URL formatada."""
    if not url_str or not isinstance(url_str, str):
        return None
    try:
        parsed = urlparse(url_str.strip())
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}".rstrip("/")
    except Exception:
        return None


def is_local_eligible(request: Request) -> bool:
    """Determina se a requisição é elegível para emissão de sessão local automática.

    A elegibilidade exige que o IP real do cliente seja estritamente loopback,
    o cabeçalho Host seja estritamente local e, havendo cabeçalhos de origem (Origin/Referer),
    estes coincidam com a mesma origem exata (esquema, hostname e porta).
    """
    client_ip = request.client.host if request.client else None
    if not _is_loopback_ip(client_ip):
        return False

    host_header = request.headers.get("host")
    if not _is_local_host(host_header):
        return False

    expected_origin = get_request_origin(request)

    # Rejeita requisições com Origin malicioso ou divergente no bootstrap
    origin = request.headers.get("origin")
    if origin:
        canon_origin = _canonical_origin(origin)
        if not canon_origin or canon_origin != expected_origin:
            return False

    sec_fetch_site = request.headers.get("sec-fetch-site")
    if sec_fetch_site and sec_fetch_site.lower() in ("cross-site", "same-site"):
        # Se for cross-site ou same-site com origem divergente, recusa
        if not origin or _canonical_origin(origin) != expected_origin:
            return False

    referer = request.headers.get("referer")
    if referer:
        canon_ref = _canonical_origin(referer)
        if not canon_ref or canon_ref != expected_origin:
            return False

    return True


def create_session_token(ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> str:
    """Gera token de sessão assinado com HMAC-SHA256, timestamp e prazo de expiração."""
    now = int(time.time())
    payload = {
        "sub": "local_user",
        "iat": now,
        "exp": now + ttl_seconds,
        "nonce": secrets.token_hex(8),
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")
    key = _get_signing_key()
    sig = hmac.new(key, b64_payload.encode("ascii"), hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{b64_payload}.{b64_sig}"


def verify_session_token(token: Optional[str]) -> bool:
    """Valida token de sessão verificando integridade HMAC-SHA256 e expiração de forma à prova de falhas."""
    if not token or not isinstance(token, str):
        return False

    try:
        token_clean = token.strip()
        parts = token_clean.split(".")
        if len(parts) != 2:
            return False

        b64_payload, b64_sig = parts[0], parts[1]
        if not b64_payload or not b64_sig:
            return False

        # Validação estrita de ASCII para evitar UnicodeEncodeError
        try:
            payload_ascii = b64_payload.encode("ascii")
            sig_ascii = b64_sig.encode("ascii")
        except UnicodeEncodeError:
            return False

        key = _get_signing_key()
        expected_sig = hmac.new(key, payload_ascii, hashlib.sha256).digest()
        expected_b64_sig = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")

        # Comparação timing-safe da assinatura
        if not hmac.compare_digest(b64_sig, expected_b64_sig):
            return False

        # Decodificação do payload
        pad = len(b64_payload) % 4
        padded_b64 = b64_payload + ("=" * (4 - pad) if pad else "")
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if not isinstance(payload, dict):
            return False

        exp = payload.get("exp")
        if not isinstance(exp, (int, float)) or exp <= time.time():
            return False

        return True
    except Exception:
        return False


def set_session_cookie(response: Response, request: Request, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> str:
    """Configura cookie assinado HttpOnly SameSite=Strict na resposta."""
    token = create_session_token(ttl_seconds)
    is_https = request.url.scheme == "https"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=ttl_seconds,
        httponly=True,
        samesite="strict",
        secure=is_https,
        path="/",
    )
    return token


def clear_session_cookie(response: Response) -> None:
    """Remove o cookie de sessão local."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


def verify_same_origin_csrf(request: Request) -> bool:
    """Verifica proteção estrita de mesma origem contra CSRF em requisições autenticadas via cookie."""
    expected_origin = get_request_origin(request)
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    sec_fetch_site = request.headers.get("sec-fetch-site")

    if sec_fetch_site and sec_fetch_site.lower() == "cross-site":
        return False

    is_mutating = request.method in ("POST", "PUT", "DELETE", "PATCH")

    if is_mutating:
        # Requisições mutantes exigem prova estrita de origem (Origin ou Referer)
        if not origin and not referer:
            return False

        if origin:
            canon_origin = _canonical_origin(origin)
            if not canon_origin or canon_origin != expected_origin:
                return False

        if referer:
            canon_ref = _canonical_origin(referer)
            if not canon_ref or canon_ref != expected_origin:
                return False

        return True

    # Requisições de leitura (GET/HEAD): se houver Origin ou Referer, devem ser mesma origem exata
    if origin:
        canon_origin = _canonical_origin(origin)
        if not canon_origin or canon_origin != expected_origin:
            return False

    if referer:
        canon_ref = _canonical_origin(referer)
        if not canon_ref or canon_ref != expected_origin:
            return False

    return True


async def get_default_preferences(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Retorna preferências padrão do servidor resolvidas de forma isolada via ENV -> Banco Cifrado."""
    resolved_n = None
    if db is not None:
        try:
            from app.services.credential_resolver import resolve_n_pontos
            resolved_n = await resolve_n_pontos(db)
        except Exception:
            resolved_n = None

    if resolved_n is None:
        settings = get_settings()
        raw_n = getattr(settings, "n_pontos", None) or os.environ.get("N_PONTOS")
        try:
            resolved_n = int(raw_n) if raw_n is not None else 1
        except (ValueError, TypeError):
            resolved_n = 1

    if resolved_n <= 0:
        resolved_n = 1

    resolved_personas: List[str] = []
    if db is not None:
        try:
            from app.services.credential_resolver import resolve_personas
            personas_db = await resolve_personas(db)
            resolved_personas = [p for p in personas_db if p in ALLOWED_SEARCH_PERSONAS]
        except Exception:
            resolved_personas = []

    if not resolved_personas:
        settings = get_settings()
        raw_personas = getattr(settings, "personas_config", None) or os.environ.get("PERSONAS_CONFIG")
        if raw_personas:
            candidates = [p.strip() for p in str(raw_personas).split(",") if p.strip()]
            resolved_personas = [p for p in candidates if p in ALLOWED_SEARCH_PERSONAS]

    if not resolved_personas:
        resolved_personas = list(ALLOWED_SEARCH_PERSONAS)

    return {
        "n_pontos": resolved_n,
        "personas": resolved_personas,
    }
