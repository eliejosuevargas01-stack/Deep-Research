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
