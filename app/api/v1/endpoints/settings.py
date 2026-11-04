"""Configuração do Hermes: provedor OpenAI-compatible e modelos por subagente."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core import hermes_config

router = APIRouter()


class HermesSettingsPayload(BaseModel):
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    modelo_padrao: Optional[str] = None
    modelo_planejador: Optional[str] = None
    modelo_historiador: Optional[str] = None
    modelo_pragmatico: Optional[str] = None
    modelo_cetico: Optional[str] = None
    modelo_visionario: Optional[str] = None
    modelo_auditor: Optional[str] = None
    modelo_redator: Optional[str] = None


def _publico(dados: Dict[str, str]) -> Dict[str, Any]:
    """Nunca devolve a chave: só se ela existe."""
    chave = dados.get("openai_api_key") or ""
    saida = {campo: dados.get(campo, "") for campo in hermes_config.CAMPOS if campo != "openai_api_key"}
    saida["tem_api_key"] = bool(chave)
    saida["modelos_por_papel"] = hermes_config.modelos_por_papel(dados)
    return saida


@router.get("/settings/hermes")
async def get_hermes_settings() -> Dict[str, Any]:
    return _publico(hermes_config.carregar())


@router.put("/settings/hermes")
async def put_hermes_settings(payload: HermesSettingsPayload) -> Dict[str, Any]:
    dados = payload.model_dump(exclude_none=True)
    base = (dados.get("openai_base_url") or "").strip()
    if base:
        partes = urlsplit(base)
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="openai_base_url precisa ser http(s) com host válido.",
            )
    if "openai_api_key" in dados and dados["openai_api_key"] is not None:
        dados["openai_api_key"] = str(dados["openai_api_key"]).strip()
    final = hermes_config.salvar(dados)
    return _publico(final)
