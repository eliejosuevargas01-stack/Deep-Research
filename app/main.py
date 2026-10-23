"""Aplicação principal FastAPI com lifespan assíncrono, rota /health e tratamento global de exceções.

Atende a T039 e DT-01.
"""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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
            "Jina_BASE_URL": "https://s.jina.ai",
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
        content={"detail": exc.errors()},
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
