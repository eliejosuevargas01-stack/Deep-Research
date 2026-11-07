"""Estratégia de delegação ``por_papel`` (``delegation.backend: por_papel``).

Cada ``delegate_task`` declara ``papel``; o modelo vem de ``delegation.backends.por_papel.modelos``
no config.yaml do perfil ou, quando o workspace da pesquisa gravou ``MODELS.json`` (cwd do processo
Hermes), do papel correspondente nesse arquivo. Papel desconhecido é recusado — nunca herda o
modelo do pai silenciosamente.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from agent.delegation_provider import DelegationProvider, DelegationRouteError

PAPEIS = (
    "planner",
    "historiador",
    "cetico",
    "visionario",
    "futurista",
    "auditor",
    "redator",
)


_CAMINHO_WORKSPACE = re.compile(r"/[^\s\"']*data/workspaces/[^\s\"']*")
_CHAVE_WORKSPACE = re.compile(
    r"(?:WORKSPACE|workspace)\s*[:=]\s*([^\s\"']+)|Trabalhe\s+SOMENTE\s+dentro\s+de\s+([^\s\"']+)",
    re.IGNORECASE,
)


def _workspace_da_task(task: Mapping[str, Any]) -> Path | None:
    """Resolve o workspace a partir do texto da task (gateway roda com cwd alheio)."""
    texto = " ".join(str(task.get(chave, "") or "") for chave in ("goal", "context", "prompt"))
    if not texto.strip():
        return None
    candidatos = _CAMINHO_WORKSPACE.findall(texto)
    for chave in _CHAVE_WORKSPACE.findall(texto):
        candidatos.extend(parte for parte in chave if parte)
    for candidato in reversed(candidatos):
        base = Path(candidato.rstrip("/").rstrip("\\"))
        for palpite in (base, *base.parents):
            if (palpite / "MODELS.json").exists():
                return palpite
            if palpite.name == "workspaces":
                break
    return None


def _ler_modelos(caminho: Path) -> dict[str, str]:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    modelos = dados.get("modelos_por_papel", dados)
    if not isinstance(modelos, Mapping):
        return {}
    return {
        papel: valor
        for papel, valor in modelos.items()
        if papel in PAPEIS and isinstance(valor, str) and valor
    }


def _modelos_do_workspace(task: Mapping[str, Any] | None = None) -> dict[str, str]:
    """MODELS.json do workspace da pesquisa; fallback: cwd (comportamento antigo)."""
    if task:
        workspace = _workspace_da_task(task)
        if workspace is not None:
            modelos = _ler_modelos(workspace / "MODELS.json")
            if modelos:
                return modelos
    try:
        return _ler_modelos(Path(os.getcwd(), "MODELS.json"))
    except OSError:
        return {}


class PorPapelDelegationProvider(DelegationProvider):
    @property
    def name(self) -> str:
        return "por_papel"

    @property
    def display_name(self) -> str:
        return "Por papel"

    @property
    def summary(self) -> str:
        return "Cada subagente usa o modelo do seu papel (planner, historiador, auditor, ...)."

    def task_parameters(self, config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            "papel": {
                "type": "string",
                "enum": list(PAPEIS),
                "description": "Papel do subagente; define o modelo usado na execução.",
            }
        }

    def description(self, config: Mapping[str, Any]) -> str:
        return "Informe `papel` em cada task: o modelo do subagente é o configurado para esse papel."

    def route_task(self, task: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        papel = task.get("papel")
        if papel not in PAPEIS:
            raise DelegationRouteError(
                "Informe `papel` em cada task: " + ", ".join(PAPEIS) + "."
            )
        modelos = self.settings(config).get("modelos")
        modelos = dict(modelos) if isinstance(modelos, Mapping) else {}
        modelos.update(_modelos_do_workspace(task))
        modelo = modelos.get(papel)
        if not modelo:
            raise DelegationRouteError(
                f"Nenhum modelo configurado para o papel '{papel}' em "
                "delegation.backends.por_papel.modelos."
            )
        rota: dict[str, Any] = {"model": modelo, "label": papel}
        for chave in ("provider", "base_url", "api_key", "api_mode"):
            if isinstance(config.get(chave), str) and config[chave]:
                rota[chave] = config[chave]
        return rota


def register(ctx) -> None:
    ctx.register_delegation_provider(PorPapelDelegationProvider())
