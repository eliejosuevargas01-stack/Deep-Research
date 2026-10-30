"""Testes unitários para o módulo de segurança e verificação de API Key."""

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock
from app.core.security import verify_api_key


@pytest.mark.asyncio
async def test_verify_api_key_when_no_key_configured_allows_access(monkeypatch: pytest.MonkeyPatch):
    """Verifica que quando nenhuma chave está configurada (modo dev), a requisição é permitida."""
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    request = MagicMock()
    db = AsyncMock()

    # resolve_key retorna None
    with monkeypatch.context() as m:
        m.setattr("app.core.security.resolve_key", AsyncMock(return_value=None))
        result = await verify_api_key(request=request, x_api_key=None, authorization=None, db=db)
        assert result is True


@pytest.mark.asyncio
async def test_verify_api_key_with_valid_x_api_key(monkeypatch: pytest.MonkeyPatch):
    """Verifica sucesso com header X-API-Key correspondente."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-valido")
    request = MagicMock()
    db = AsyncMock()

    result = await verify_api_key(
        request=request,
        x_api_key="segredo-super-valido",
        authorization=None,
        db=db,
    )
    assert result is True


@pytest.mark.asyncio
async def test_verify_api_key_with_valid_bearer_token(monkeypatch: pytest.MonkeyPatch):
    """Verifica sucesso com header Authorization: Bearer <token>."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-valido")
    request = MagicMock()
    db = AsyncMock()

    result = await verify_api_key(
        request=request,
        x_api_key=None,
        authorization="Bearer segredo-super-valido",
        db=db,
    )
    assert result is True


@pytest.mark.asyncio
async def test_verify_api_key_with_invalid_key_raises_401(monkeypatch: pytest.MonkeyPatch):
    """Verifica rejeição HTTP 401 com chave inválida."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-valido")
    request = MagicMock()
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(
            request=request,
            x_api_key="chave-errada",
            authorization=None,
            db=db,
        )
    assert exc_info.value.status_code == 401
    assert "ausente ou inválida" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_missing_header_raises_401(monkeypatch: pytest.MonkeyPatch):
    """Verifica rejeição HTTP 401 quando o header está ausente."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-valido")
    request = MagicMock()
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(
            request=request,
            x_api_key=None,
            authorization=None,
            db=db,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_query_token_allowed_on_get_and_head(monkeypatch: pytest.MonkeyPatch):
    """Verifica que ?token= na query string é aceito para métodos seguros GET e HEAD."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-valido")
    db = AsyncMock()

    # GET com query param token
    req_get = MagicMock()
    req_get.method = "GET"
    req_get.query_params = {"token": "segredo-super-valido"}
    res_get = await verify_api_key(request=req_get, x_api_key=None, authorization=None, db=db)
    assert res_get is True

    # HEAD com query param token
    req_head = MagicMock()
    req_head.method = "HEAD"
    req_head.query_params = {"token": "segredo-super-valido"}
    res_head = await verify_api_key(request=req_head, x_api_key=None, authorization=None, db=db)
    assert res_head is True


@pytest.mark.asyncio
async def test_verify_api_key_query_token_rejected_on_mutating_methods(monkeypatch: pytest.MonkeyPatch):
    """Verifica que ?token= na query string é estritamente rejeitado em métodos mutantes (POST, PUT, DELETE)."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-valido")
    db = AsyncMock()

    for method in ("POST", "PUT", "DELETE", "PATCH"):
        req = MagicMock()
        req.method = method
        req.query_params = {"token": "segredo-super-valido"}
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request=req, x_api_key=None, authorization=None, db=db)
        assert exc_info.value.status_code == 401

