"""Aplicação principal FastAPI com lifespan assíncrono, rota /health e tratamento global de exceções.

Atende a T039 e DT-01.
"""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

import logging as _logging

_logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
# Algum import de terceiro sobe o logger-pai "app" para WARNING e silencia o pipeline:
# reafirma o nivel efetivo no pacote da aplicacao.
_logging.getLogger("app").setLevel(_logging.getLogger().level)
from app.core.security import verify_api_key
from app.ui_session import (
    COOKIE_NAME,
    _canonical_origin,
    _is_local_host,
    get_default_preferences,
    get_request_origin,
    is_local_eligible,
    set_session_cookie,
    verify_session_token,
)

FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _setup_integration_test_env() -> None:
    """Configura ambiente estritamente durante testes de integração sem poluir testes unitários."""
    current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
    if "tests/integration/" in current_test:
        test_defaults = {
            "CREDENTIALS_MASTER_KEY": "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY=",
            "DATABASE_URL": "sqlite+aiosqlite:////tmp/test_deep_research.db",
            "N_PONTOS": "5",
            "PERSONAS_CONFIG": "planejador,historiador,visionario,cetico,futurista,auditor,redator final",
            "WEBHOOK_HMAC_SECRET": "test-webhook-secret-key-1234567890",
            "CALLBACK_WEBHOOK_URL": "https://mock.webhook.test/callback",
            "LLM_BASE_URL": "https://api.openai.com/v1",
            "LLM_MODEL_LIGHT": "gpt-4o-mini",
            "LLM_MODEL_STRONG": "gpt-4o",
        }
        modified = False
        for k, v in test_defaults.items():
            if k not in os.environ:
                os.environ[k] = v
                modified = True
        if modified:
            from app.config import get_settings
            get_settings.cache_clear()


_setup_integration_test_env()

from app.api.v1.router import api_router
from app.db.init_db import init_db


# ponytail: lifespan executa init_db() assíncrono direto; plugar warmup de pool e telemetria OTel no futuro
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida assíncrono para inicialização DDL e verificação de pragmas WAL."""
    _setup_integration_test_env()
    await init_db()
    yield


app = FastAPI(
    title="Deep Research API",
    version="0.1.0",
    description="Pipeline modular assíncrono de pesquisa profunda na internet",
    lifespan=lifespan,
)

# Agregação dos endpoints operacionais e administrativos sob prefixo /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict:
    """Verificação de integridade operacional do serviço."""
    return {"status": "healthy"}


@app.get("/app/session")
async def get_app_session(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """Emite ou renova sessão de navegador local e devolve preferências padrão do servidor."""
    prefs = await get_default_preferences(db)
    eligible = is_local_eligible(request)
    if not eligible:
        # UI remota autenticada por chave de API (ex.: frontend atrás de proxy confiável
        # que injeta X-API-Key no servidor). A chave continua obrigatória nas rotas de negócio.
        has_api_key_header = bool(
            request.headers.get("x-api-key")
            or request.headers.get("authorization")
            or (
                hasattr(request, "query_params")
                and (request.query_params.get("token") or request.query_params.get("api_key"))
            )
        )
        if has_api_key_header:
            try:
                await verify_api_key(
                    request=request,
                    x_api_key=request.headers.get("x-api-key"),
                    authorization=request.headers.get("authorization"),
                    db=db,
                )
            except HTTPException:
                pass
            else:
                res = JSONResponse(
                    content={
                        "authenticated": True,
                        "mode": "api-key",
                        "preferences": prefs,
                    },
                    status_code=status.HTTP_200_OK,
                )
                # Cookie assinado permite EventSource (SSE), que nao envia cabecalhos customizados.
                set_session_cookie(res, request)
                return res

        expected_origin = get_request_origin(request)
        origin = request.headers.get("origin")
        sec_fetch_site = request.headers.get("sec-fetch-site")
        host_header = request.headers.get("host")
        referer = request.headers.get("referer")

        # Se houver tentativa com host inválido, origin divergente ou cross-site, rejeita com 403
        if not _is_local_host(host_header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso rejeitado: cabeçalho Host não é um host local autorizado.",
            )
        if origin and _canonical_origin(origin) != expected_origin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso de sessão cross-site ou com origem divergente rejeitado.",
            )
        if referer and _canonical_origin(referer) != expected_origin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso de sessão com Referer divergente rejeitado.",
            )
        if sec_fetch_site and sec_fetch_site.lower() == "cross-site":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso de sessão cross-site rejeitado.",
            )

        return JSONResponse(
            content={
                "authenticated": False,
                "mode": "remote",
                "preferences": prefs,
            },
            status_code=status.HTTP_200_OK,
        )

    res = JSONResponse(
        content={
            "authenticated": True,
            "mode": "local",
            "preferences": prefs,
        },
        status_code=status.HTTP_200_OK,
    )
    set_session_cookie(res, request)
    return res


@app.get("/assets/{file_path:path}")
async def get_static_asset(file_path: str) -> FileResponse:
    """Serve arquivos estáticos compilados da interface React com 404 estrito em arquivos ausentes."""
    if ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset não localizado.")

    assets_dir = (FRONTEND_DIST_DIR / "assets").resolve()
    requested_file = (assets_dir / file_path).resolve()

    try:
        requested_file.relative_to(assets_dir)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset não localizado.")

    if not requested_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset não localizado.")

    return FileResponse(requested_file)


@app.get("/{full_path:path}")
async def serve_spa_frontend(request: Request, full_path: str = "") -> Response:
    """Serve o index.html da interface SPA e emite sessão local automaticamente para clientes elegíveis."""
    # Preserva explicitamente rotas protegidas e reservadas da API
    clean_path = full_path.strip("/")
    if (
        clean_path.startswith("api/")
        or clean_path == "api"
        or clean_path == "health"
        or clean_path.startswith("docs")
        or clean_path == "openapi.json"
        or clean_path == "app/session"
        or clean_path.startswith("assets")
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota não encontrada.")

    # Se a requisição contiver extensão de arquivo estático (ex: .js, .css, .toml, .py), não deve servir index.html
    if "." in Path(clean_path).name and Path(clean_path).suffix.lower() not in ("", ".html", ".htm"):
        static_file = (FRONTEND_DIST_DIR / clean_path).resolve()
        try:
            static_file.relative_to(FRONTEND_DIST_DIR.resolve())
            if static_file.is_file():
                return FileResponse(static_file)
        except ValueError:
            pass
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo estático não localizado.")

    index_html = FRONTEND_DIST_DIR / "index.html"
    if not index_html.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Frontend bundle não compilado ou ausente. Execute o build do frontend antes de iniciar.",
        )

    res = FileResponse(index_html)
    if is_local_eligible(request):
        existing_cookie = request.cookies.get(COOKIE_NAME)
        if not existing_cookie or not verify_session_token(existing_cookie):
            set_session_cookie(res, request)

    return res


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Tratamento padronizado de exceções HTTP."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Tratamento de erros de validação sintática do payload."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Tratamento de erros de validação e domínio lançados como ValueError."""
    msg = str(exc)
    if "RESEARCH_NOT_FOUND" in msg or "não localizada" in msg or "NO_PENDING_POINTS" in msg:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": msg},
        )
    if (
        "SEARCH_NOT_COMPLETED" in msg
        or "PENDING_AUDIT_POINTS" in msg
        or "coleta" in msg
        or "pendente" in msg
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": msg},
        )
    if "N_PONTOS" in msg or "CONFIG_ERROR" in msg or "Configuração ausente" in msg:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"CONFIG_ERROR: {msg}"},
        )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": msg},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Tratamento de exceções inesperadas do sistema sem expor segredos sensíveis."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro interno do servidor."},
    )
