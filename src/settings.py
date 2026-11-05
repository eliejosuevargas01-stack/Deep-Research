"""Configuração do perfil Hermes (`hermes_home/profiles/deep-research/config.yaml`).

SDD §2 e PRD RF09: o backend lê e grava o `config.yaml` do perfil — endpoint do provedor,
limites de delegação e o modelo de cada papel/subagente. `DR_HERMES_PROFILE_DIR` aponta para
outro perfil (produção monta o diretório do Hermes).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

RAIZ = Path(__file__).resolve().parent.parent
PAPEIS = (
    "planner",
    "historiador",
    "cetico",
    "visionario",
    "futurista",
    "auditor",
    "redator",
)


def diretorio_perfil() -> Path:
    return Path(
        os.getenv("DR_HERMES_PROFILE_DIR", RAIZ / "hermes_home" / "profiles" / "deep-research")
    )


def caminho_config() -> Path:
    return diretorio_perfil() / "config.yaml"


class ModelosPorPapel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner: str | None = None
    historiador: str | None = None
    cetico: str | None = None
    visionario: str | None = None
    futurista: str | None = None
    auditor: str | None = None
    redator: str | None = None


class ConfigHermes(BaseModel):
    """Payload de `PUT /config` (SDD §5.2). Campos omitidos ficam como estão."""

    model_config = ConfigDict(extra="forbid")

    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    max_concurrent_children: int | None = Field(default=None, ge=1)
    max_spawn_depth: int | None = Field(default=None, ge=1)
    oneshot_max_children: int | None = Field(default=None, ge=0)
    modelos_por_papel: ModelosPorPapel | None = None


def _secao(dados: dict[str, Any], chave: str) -> dict[str, Any]:
    valor = dados.get(chave)
    return valor if isinstance(valor, dict) else {}


def ler_config(caminho: Path | None = None) -> dict[str, Any]:
    caminho = caminho or caminho_config()
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    dados = dados if isinstance(dados, dict) else {}
    modelo = _secao(dados, "model")
    delegacao = _secao(dados, "delegation")
    backends = _secao(delegacao, "backends")
    por_papel = _secao(backends, "por_papel")
    modelos = _secao(por_papel, "modelos")
    return {
        "base_url": modelo.get("base_url", ""),
        "api_key": modelo.get("api_key", ""),
        "default_model": modelo.get("default", ""),
        "max_concurrent_children": delegacao.get("max_concurrent_children", 40),
        "max_spawn_depth": delegacao.get("max_spawn_depth", 2),
        "oneshot_max_children": delegacao.get("oneshot_max_children", 0),
        "modelos_por_papel": {papel: modelos.get(papel, "") for papel in PAPEIS},
    }


def aplicar_config(payload: ConfigHermes, caminho: Path | None = None) -> dict[str, Any]:
    caminho = caminho or caminho_config()
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    dados = dados if isinstance(dados, dict) else {}

    modelo = dados.setdefault("model", {})
    delegacao = dados.setdefault("delegation", {})
    backends = delegacao.setdefault("backends", {})
    por_papel = backends.setdefault("por_papel", {})
    modelos = por_papel.setdefault("modelos", {})

    if payload.base_url is not None:
        modelo["base_url"] = payload.base_url
    if payload.api_key is not None:
        modelo["api_key"] = payload.api_key
    if payload.default_model is not None:
        modelo["default"] = payload.default_model
    if payload.max_concurrent_children is not None:
        delegacao["max_concurrent_children"] = payload.max_concurrent_children
    if payload.max_spawn_depth is not None:
        delegacao["max_spawn_depth"] = payload.max_spawn_depth
    if payload.oneshot_max_children is not None:
        delegacao["oneshot_max_children"] = payload.oneshot_max_children
    # O backend por papel é o contrato da spec; não deixamos o arquivo em outro backend.
    delegacao["backend"] = "por_papel"
    if payload.modelos_por_papel is not None:
        for papel, valor in payload.modelos_por_papel.model_dump(exclude_none=True).items():
            modelos[papel] = valor

    # ponytail: reescreve o YAML inteiro e perde comentários; usar round-trip ruamel se o
    # arquivo passar a ser editado à mão em produção.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=caminho.parent, delete=False, suffix=".tmp"
    ) as tmp:
        yaml.safe_dump(dados, tmp, sort_keys=False, allow_unicode=True)
        temporario = Path(tmp.name)
    os.replace(temporario, caminho)
    return ler_config(caminho)
