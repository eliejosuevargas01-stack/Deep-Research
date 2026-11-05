"""Configuração: config/hermes_config.yaml com override por variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ / "config" / "hermes_config.yaml"


@dataclass(slots=True)
class ConfigEngine:
    base_url: str = "http://9router:20128/v1"
    api_key_env: str = "LLM_API_KEY"
    model: str = ""
    temperature: float = 0.2
    timeout_s: int = 600

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "")


@dataclass(slots=True)
class ConfigPipeline:
    max_pontos_paralelos: int = 3
    max_queries_por_persona: int = 3
    tentativas_por_agente: int = 2
    webhook_timeout_s: int = 15
    db_path: str = "data/deep_research.db"
    workspaces_dir: str = "data/workspaces"


@dataclass(slots=True)
class Config:
    engine: ConfigEngine = field(default_factory=ConfigEngine)
    pipeline: ConfigPipeline = field(default_factory=ConfigPipeline)

    @classmethod
    def carregar(cls, caminho: str | Path | None = None) -> "Config":
        caminho = Path(caminho or os.getenv("DR_CONFIG", CAMINHO_PADRAO))
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        dados = dados or {}
        config = cls(
            engine=_preencher(ConfigEngine, dados.get("engine")),
            pipeline=_preencher(ConfigPipeline, dados.get("pipeline")),
        )
        # Env vence o arquivo: o container sobrescreve sem rebuild.
        for env, atributo in (
            ("LLM_BASE_URL", "base_url"),
            ("DR_ENGINE_MODEL", "model"),
            ("LLM_MODEL", "model"),
        ):
            if valor := os.getenv(env):
                setattr(config.engine, atributo, valor)
        if valor := os.getenv("DR_DB_PATH"):
            config.pipeline.db_path = valor
        return config


def _preencher(tipo, dados: dict | None):
    dados = dados or {}
    conhecidos = {campo.name for campo in fields(tipo)}
    return tipo(**{chave: valor for chave, valor in dados.items() if chave in conhecidos})
