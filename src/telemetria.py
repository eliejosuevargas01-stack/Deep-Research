"""Telemetria real das sessões do Hermes (`state.db`, SDD §2.2.4 / RNF01).

Cada subagente delegado abre uma sessão com `cwd` no workspace da pesquisa; a sessão guarda
modelo, tokens de entrada/saída/raciocínio e duração. O backend lê essas linhas em vez de
estimar consumo.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

PAPEL_NO_TITULO = re.compile(r"\[(planner|historiador|cetico|visionario|futurista|auditor|redator)\]")
LIMITE_REASONING = 20_000


def _resumo_mensagens(con: sqlite3.Connection, ids_sessao: list[str]) -> dict[str, dict[str, Any]]:
    """Agrega reasoning/tool_calls da tabela `messages` por sessão.

    Ausência da tabela (state.db antigo) resulta em agregados vazios.
    """
    vazio: dict[str, dict[str, Any]] = {sid: {"reasoning": [], "tool_calls": []} for sid in ids_sessao}
    if not ids_sessao:
        return vazio
    try:
        colunas = {linha[1] for linha in con.execute("PRAGMA table_info(messages)").fetchall()}
    except sqlite3.Error:
        return vazio
    if not colunas or "session_id" not in colunas:
        return vazio
    tem_reasoning = "reasoning" in colunas
    tem_reasoning_content = "reasoning_content" in colunas
    tem_tool_calls = "tool_calls" in colunas
    if not (tem_reasoning or tem_reasoning_content or tem_tool_calls):
        return vazio
    selecionar = ["session_id"]
    if tem_reasoning:
        selecionar.append("reasoning")
    if tem_reasoning_content:
        selecionar.append("reasoning_content")
    if tem_tool_calls:
        selecionar.append("tool_calls")
    ordem = "timestamp ASC" if "timestamp" in colunas else "rowid ASC"
    marcadores = ",".join("?" for _ in ids_sessao)
    try:
        linhas = con.execute(
            f"SELECT {', '.join(selecionar)} FROM messages"
            f" WHERE session_id IN ({marcadores}) ORDER BY {ordem}",
            ids_sessao,
        ).fetchall()
    except sqlite3.Error:
        return vazio
    for linha in linhas:
        agregado = vazio.get(linha["session_id"])
        if agregado is None:
            continue
        if tem_reasoning and linha["reasoning"]:
            agregado["reasoning"].append(str(linha["reasoning"]))
        if tem_reasoning_content and linha["reasoning_content"]:
            agregado["reasoning"].append(str(linha["reasoning_content"]))
        if tem_tool_calls and linha["tool_calls"]:
            bruto = linha["tool_calls"]
            try:
                parsed = json.loads(bruto) if isinstance(bruto, str) else bruto
            except (ValueError, TypeError):
                continue  # inválido: ignora sem quebrar a coleta
            if isinstance(parsed, list):
                agregado["tool_calls"].extend(parsed)
            elif isinstance(parsed, dict):
                agregado["tool_calls"].append(parsed)
    return vazio


def _caminho_state_db() -> Path | None:
    import os

    from settings import diretorio_perfil

    caminho = Path(os.getenv("DR_HERMES_STATE_DB", diretorio_perfil() / "state.db"))
    return caminho if caminho.exists() else None


def coletar(workspace: Path, desde: float) -> dict[str, dict[str, Any]]:
    """Sessões abertas desde `desde` no workspace, indexadas pelo id da tarefa.

    O título da sessão do subagente começa com `[papel] <id_da_tarefa>` (o runner instrui o
    Hermes a montar o goal assim); sem id reconhecível a sessão é agregada em `_pai`.
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
    por_tarefa: dict[str, dict[str, Any]] = {}
    sessoes_por_tarefa: dict[str, list[str]] = {}
    try:
        linhas = con.execute(
            "SELECT id, parent_session_id, title, model, cwd, started_at, ended_at,"
            " input_tokens, output_tokens, reasoning_tokens, tool_call_count"
            " FROM sessions WHERE started_at >= ? AND (cwd = ? OR cwd IS NULL)"
            " ORDER BY started_at ASC",
            (desde, alvo),
        ).fetchall()
        for linha in linhas:
            titulo = linha["title"] or ""
            casamento = PAPEL_NO_TITULO.search(titulo)
            alvo = re.search(r"\[[a-z]+\]\s+([A-Za-z0-9_]+)", titulo)
            tarefa_id = alvo.group(1) if alvo else "_pai"
            papel = casamento.group(0)[1:-1] if casamento else ""
            entrada = por_tarefa.setdefault(
                tarefa_id,
                {
                    "model_used": linha["model"] or "",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls": 0,
                    "latency_ms": 0,
                    "reasoning_trace": "",
                    "tool_calls_lista": [],
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
            entrada["sessoes"].append({"id": linha["id"], "papel": papel})
            sessoes_por_tarefa.setdefault(tarefa_id, []).append(linha["id"])
            try:
                inicio = float(linha["started_at"]) if linha["started_at"] else 0.0
                fim = float(linha["ended_at"]) if linha["ended_at"] else 0.0
            except (TypeError, ValueError):
                inicio = fim = 0.0
            if inicio and fim and fim >= inicio:
                entrada["latency_ms"] += int((fim - inicio) * 1000)
        todos_ids = [sid for ids in sessoes_por_tarefa.values() for sid in ids]
        resumos = _resumo_mensagens(con, todos_ids)
        for tarefa_id, ids in sessoes_por_tarefa.items():
            partes_trace: list[str] = []
            chamadas: list[Any] = []
            for sid in ids:
                resumo = resumos.get(sid, {})
                partes_trace.extend(resumo.get("reasoning", []))
                chamadas.extend(resumo.get("tool_calls", []))
            por_tarefa[tarefa_id]["reasoning_trace"] = "\n".join(partes_trace)[:LIMITE_REASONING]
            por_tarefa[tarefa_id]["tool_calls_lista"] = chamadas
        return por_tarefa
    except sqlite3.Error:
        return {}
    finally:
        con.close()
