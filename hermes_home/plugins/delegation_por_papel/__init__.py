"""Delegação por papel: um modelo por subagente, escolhido pela persona da tarefa.

Os modelos vêm de ``DR_MODELOS_FILE`` (o ``MODELS.json`` do workspace da pesquisa,
escrito pelo backend a partir das Configurações). Sem arquivo, cai em
``delegation.backends.por_papel.modelos`` do config.yaml. Sem papel reconhecido,
o filho herda a rota do pai.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from agent.delegation_provider import DelegationProvider

logger = logging.getLogger(__name__)

# persona -> trechos que aparecem no goal/context da tarefa delegada
PAPEIS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("historiador", ("historiador", "história", "historia")),
    ("pragmatico", ("pragmátic", "pragmatic")),
    ("cetico", ("cétic", "cetic")),
    ("visionario", ("visionári", "visionari", "futurista")),
    ("auditor", ("auditor",)),
    ("redator", ("redator", "dossiê", "dossie")),
)


def _do_arquivo() -> dict[str, str]:
    caminho = os.environ.get("DR_MODELOS_FILE")
    if not caminho:
        return {}
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in dados.items() if isinstance(v, str) and v.strip()}


def _do_config(config: Mapping[str, Any]) -> dict[str, str]:
    backends = config.get("backends")
    if not isinstance(backends, Mapping):
        return {}
    proprio = backends.get("por_papel")
    if not isinstance(proprio, Mapping):
        return {}
    modelos = proprio.get("modelos")
    if not isinstance(modelos, Mapping):
        return {}
    return {str(k).lower(): str(v) for k, v in modelos.items() if isinstance(v, str) and v.strip()}


class DelegationPorPapel(DelegationProvider):
    @property
    def name(self) -> str:
        return "por_papel"

    @property
    def display_name(self) -> str:
        return "Modelos por papel"

    @property
    def summary(self) -> str:
        return "Cada subagente usa o modelo do seu papel; sem papel reconhecido, herda o pai."

    def route_task(self, task: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        modelos = _do_arquivo() or _do_config(config)
        if not modelos:
            return {}
        texto = " ".join(
            str(task.get(chave) or "") for chave in ("goal", "context", "role", "index")
        ).lower()
        for papel, chaves in PAPEIS:
            modelo = modelos.get(papel)
            if modelo and any(chave in texto for chave in chaves):
                return {"model": modelo, "label": f"{papel} · {modelo}"}
        padrao = modelos.get("planejador") or modelos.get("padrao")
        return {"model": padrao, "label": f"padrão · {padrao}"} if padrao else {}


def register(ctx) -> None:
    ctx.register_delegation_provider(DelegationPorPapel())
