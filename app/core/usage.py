"""Contabilidade de tokens da pesquisa: agente principal + subagentes.

O Hermes escreve `usage.json` no workspace a cada turno — parcial, sobrescrito.
A soma tem que ser monotônica: nenhum turno menor pode apagar o que já foi gasto.
Quando existir `usage_<etapa>.json` (plan/search/audit/write), a soma por etapa é
a verdade; `usage.json` cobre o caso de um único turno acumulado.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

ETAPAS = ("plan", "search", "audit", "write")
CAMPOS = ("input_tokens", "output_tokens", "total_tokens")


def _ler(caminho: Path) -> Optional[Dict[str, Any]]:
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


def _soma(usos) -> Dict[str, int]:
    return {campo: sum(int(u.get(campo) or 0) for u in usos) for campo in CAMPOS}


def resumo_uso(workspace: Path) -> Dict[str, Any]:
    """Totais e quebra por etapa/agente da pesquisa."""
    por_etapa = {}
    for etapa in ETAPAS:
        uso = _ler(workspace / f"usage_{etapa}.json")
        if uso:
            por_etapa[etapa] = {campo: int(uso.get(campo) or 0) for campo in CAMPOS}
    cumulativo = _ler(workspace / "usage.json")
    if por_etapa:
        total = _soma(por_etapa.values())
    elif cumulativo:
        total = {campo: int(cumulativo.get(campo) or 0) for campo in CAMPOS}
    else:
        total = {campo: 0 for campo in CAMPOS}

    por_agente: Dict[str, Dict[str, int]] = {}
    agentes = (cumulativo or {}).get("agents")
    if isinstance(agentes, dict):
        for agente, uso in agentes.items():
            if isinstance(uso, dict):
                por_agente[str(agente)] = {campo: int(uso.get(campo) or 0) for campo in CAMPOS}
    for etapa, uso in por_etapa.items():
        por_agente.setdefault(etapa, uso)
    return {
        "total": total,
        "por_etapa": por_etapa,
        "por_agente": por_agente,
        "modelo": (cumulativo or {}).get("model"),
        "api_calls": int((cumulativo or {}).get("api_calls") or 0),
    }


def gravar_resumo(workspace: Path) -> Dict[str, Any]:
    """Persiste `USAGE_SUMMARY.json` com o detalhamento por agente e o total."""
    resumo = resumo_uso(workspace)
    try:
        (workspace / "USAGE_SUMMARY.json").write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return resumo
