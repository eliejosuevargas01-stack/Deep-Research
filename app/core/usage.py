"""Contabilidade de tokens da pesquisa: agente principal + subagentes.

O Hermes escreve `usage.json` no workspace a cada turno — parcial, sobrescrito.
A soma tem que ser monotônica: nenhum turno menor pode apagar o que já foi gasto.
Quando existir `usage_<etapa>.json` (plan/search/audit/write), a soma por etapa é
a verdade; `usage.json` cobre o caso de um único turno acumulado.
"""

from __future__ import annotations

import json
import os
import sqlite3
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


def _state_db() -> Optional[Path]:
    """state.db do perfil Hermes: fonte real de tokens, inclusive de subagentes."""
    home = os.environ.get("HERMES_HOME") or ""
    perfil = os.environ.get("HERMES_PROFILE") or os.environ.get("DR_HERMES_PROFILE") or "deep-research"
    candidatos = []
    if home:
        candidatos.append(Path(home) / "profiles" / perfil / "state.db")
    candidatos.append(Path.home() / ".hermes" / "profiles" / perfil / "state.db")
    for caminho in candidatos:
        if caminho.exists():
            return caminho
    # Perfil do processo pode divergir (HERMES_PROFILE do shell/gateway): usa o
    # state.db mais recente entre os perfis em vez de fingir que não há consumo.
    base = Path(home) / "profiles" if home else None
    if base and base.is_dir():
        achados = sorted(base.glob("*/state.db"), key=lambda c: c.stat().st_mtime, reverse=True)
        if achados:
            return achados[0]
    return None


def _do_state_db(workspace: Path) -> Optional[Dict[str, Any]]:
    """Soma tokens das sessões (principal + subagentes) daquele workspace.

    O `--usage-file` do CLI cobre um turno e não vê delegados; a sessão do Hermes
    vê. As duas fontes são monotônicas entre si: vale a maior.
    """
    caminho = _state_db()
    if caminho is None:
        return None
    raiz = str(workspace)
    try:
        conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None
    try:
        linhas = conexao.execute(
            "select coalesce(model,''), coalesce(title, display_name, ''),"
            " sum(coalesce(input_tokens,0)), sum(coalesce(output_tokens,0))"
            " from sessions where cwd = ? or cwd like ? group by 1,2",
            (raiz, raiz + "/%"),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conexao.close()
    if not linhas:
        return None
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    por_agente: Dict[str, Dict[str, int]] = {}
    for modelo, titulo, entrada, saida in linhas:
        entrada, saida = int(entrada or 0), int(saida or 0)
        total["input_tokens"] += entrada
        total["output_tokens"] += saida
        total["total_tokens"] += entrada + saida
        rotulo = (titulo or modelo or "agente").strip()
        alvo = por_agente.setdefault(
            rotulo[:60], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        )
        alvo["input_tokens"] += entrada
        alvo["output_tokens"] += saida
        alvo["total_tokens"] += entrada + saida
    return {"total": total, "por_agente": por_agente, "modelo": linhas[0][0] or None}


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

    estado = _do_state_db(workspace)
    if estado:
        total = {
            campo: max(int(total.get(campo) or 0), int(estado["total"].get(campo) or 0))
            for campo in CAMPOS
        }

    por_agente: Dict[str, Dict[str, int]] = {}
    if estado:
        por_agente.update(estado["por_agente"])
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
        "modelo": (cumulativo or {}).get("model") or (estado or {}).get("modelo"),
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
