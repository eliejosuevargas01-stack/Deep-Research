"""Telemetria real das sessões do Hermes (`state.db`, SDD §2.2.4 / RNF01).

Cada subagente delegado abre uma sessão com `cwd` no workspace da pesquisa; a sessão guarda
modelo, tokens de entrada/saída/raciocínio e duração. O backend lê essas linhas em vez de
estimar consumo.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

PAPEL_NO_TITULO = re.compile(r"\[(planner|historiador|cetico|visionario|futurista|auditor|redator)\]")


def _caminho_state_db() -> Path | None:
    import os

    from settings import diretorio_perfil

    caminho = Path(os.getenv("DR_HERMES_STATE_DB", diretorio_perfil() / "state.db"))
    return caminho if caminho.exists() else None


def coletar(workspace: Path, desde: float) -> dict[str, dict[str, Any]]:
    """Sessões abertas desde `desde` no workspace, indexadas pelo id da tarefa.

    O título da sessão do subagente começa com `[papel] <id_da_tarefa>` (o runner instrui o
    Hermes a montar o goal assim); sem id reconhecível a sessão é agregada em `planner`.
    """
    caminho = _caminho_state_db()
    if caminho is None:
        return {}
    alvo = str(workspace)
    try:
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
    except sqlite3.Error:
        return {}
    try:
        linhas = con.execute(
            "SELECT id, parent_session_id, title, model, cwd, started_at, ended_at,"
            " input_tokens, output_tokens, reasoning_tokens, tool_call_count"
            " FROM sessions WHERE started_at >= ? AND (cwd = ? OR cwd IS NULL)"
            " ORDER BY started_at ASC",
            (desde, alvo),
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        con.close()

    por_tarefa: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        titulo = linha["title"] or ""
        papel = PAPEL_NO_TITULO.search(titulo)
        partes = titulo.split()
        tarefa_id = partes[1] if titulo.startswith("[") and len(partes) > 1 else "planner"
        entrada = por_tarefa.setdefault(
            tarefa_id,
            {
                "model_used": linha["model"] or "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0,
                "tool_calls": 0,
                "sessoes": [],
            },
        )
        entrada["prompt_tokens"] += int(linha["input_tokens"] or 0)
        entrada["completion_tokens"] += int(linha["output_tokens"] or 0)
        entrada["reasoning_tokens"] += int(linha["reasoning_tokens"] or 0)
        entrada["tool_calls"] += int(linha["tool_call_count"] or 0)
        entrada["total_tokens"] = (
            entrada["prompt_tokens"]
            + entrada["completion_tokens"]
            + entrada["reasoning_tokens"]
        )
        if papel and not entrada["model_used"]:
            entrada["model_used"] = linha["model"] or ""
        entrada["sessoes"].append({"id": linha["id"], "papel": papel.group(1) if papel else ""})
    return por_tarefa
