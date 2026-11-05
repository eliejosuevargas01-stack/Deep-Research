"""Configuração: config/hermes_config.yaml com override por variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ / "config" / "hermes_config.yaml"


@dataclass(slots=True)
class ConfigPipeline:
    max_queries_por_persona: int = 3
    tentativas_por_agente: int = 2
    webhook_timeout_s: int = 15
    db_path: str = "data/deep_research.db"
    workspaces_dir: str = "data/workspaces"
    hermes_bin: str = "hermes"
    hermes_profile: str = "deep-research"
    hermes_home: str = ""
    hermes_timeout_s: int = 3600


@dataclass(slots=True)
class Config:
    pipeline: ConfigPipeline = field(default_factory=ConfigPipeline)

    @classmethod
    def carregar(cls, caminho: str | Path | None = None) -> "Config":
        caminho = Path(caminho or os.getenv("DR_CONFIG", CAMINHO_PADRAO))
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        dados = dados or {}
        config = cls(pipeline=_preencher(ConfigPipeline, dados.get("pipeline")))
        # Env vence o arquivo: o container sobrescreve sem rebuild.
        if valor := os.getenv("DR_DB_PATH"):
            config.pipeline.db_path = valor
        for env, atributo in (
            ("DR_HERMES_BIN", "hermes_bin"),
            ("DR_HERMES_PROFILE", "hermes_profile"),
            ("DR_HERMES_HOME", "hermes_home"),
            ("DR_WORKSPACES_DIR", "workspaces_dir"),
        ):
            if valor := os.getenv(env):
                setattr(config.pipeline, atributo, valor)
        if valor := os.getenv("DR_HERMES_TIMEOUT_S"):
            config.pipeline.hermes_timeout_s = int(valor)
        return config


def _preencher(tipo, dados: dict | None):
    dados = dados or {}
    conhecidos = {campo.name for campo in fields(tipo)}
    return tipo(**{chave: valor for chave, valor in dados.items() if chave in conhecidos})
