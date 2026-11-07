"""Lacunas SDD §2.2.4 / §2.1 / §5.5: telemetria rica, planner, materializar, por_papel."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

import telemetria
from engine import Tarefa


def _banco(tmp_path, workspace, linhas_sessao, linhas_msg=()):
    banco = tmp_path / "state.db"
    con = sqlite3.connect(banco)
    con.execute(
        "CREATE TABLE sessions (id TEXT, parent_session_id TEXT, title TEXT, model TEXT,"
        " cwd TEXT, started_at REAL, ended_at REAL, input_tokens INTEGER, output_tokens INTEGER,"
        " reasoning_tokens INTEGER, tool_call_count INTEGER)"
    )
    con.execute(
        "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, tool_calls TEXT,"
        " tool_name TEXT, reasoning TEXT, reasoning_content TEXT, timestamp REAL)"
    )
    for linha in linhas_sessao:
        sid, pai, titulo, modelo, ini, fim, inp, out, rea, ntools = linha
        con.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (sid, pai, titulo, modelo, str(workspace), ini, fim, inp, out, rea, ntools),
        )
    for linha in linhas_msg:
        con.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)", linha)
    con.commit()
    con.close()
    return banco


def test_coletar_reasoning_toollcalls_latency(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    banco = _banco(
        tmp_path,
        ws,
        [("s1", "root", "[auditor] auditor_p1_r2 x", "m/x", 100.0, 102.5, 900, 120, 30, 4)],
        [
            ("s1", "assistant", "texto", None, None, "raciocinio-a", "extra-b", 1.0),
            (
                "s1",
                "assistant",
                "texto",
                json.dumps([{"name": "web_search", "args": {"q": "x"}}]),
                None,
                None,
                None,
                2.0,
            ),
            ("s1", "assistant", "texto", "invalido{{{", None, None, None, 3.0),
        ],
    )
    monkeypatch.setenv("DR_HERMES_STATE_DB", str(banco))
    sessoes = telemetria.coletar(ws, 0)
    entrada = sessoes["auditor_p1_r2"]
    assert entrada["reasoning_trace"] == "raciocinio-a\nextra-b"
    assert entrada["tool_calls_lista"] == [{"name": "web_search", "args": {"q": "x"}}]
    assert entrada["tool_calls"] == 4
    assert entrada["latency_ms"] == 2500
    assert callable(getattr(telemetria, "coletar"))


def test_coletar_sem_tabela_messages(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    banco = tmp_path / "state.db"
    con = sqlite3.connect(banco)
    con.execute(
        "CREATE TABLE sessions (id TEXT, parent_session_id TEXT, title TEXT, model TEXT,"
        " cwd TEXT, started_at REAL, ended_at REAL, input_tokens INTEGER, output_tokens INTEGER,"
        " reasoning_tokens INTEGER, tool_call_count INTEGER)"
    )
    con.execute(
        "INSERT INTO sessions VALUES ('s1',NULL,'[redator] redator_p1 x','m',?,1.0,3.0,10,5,2,1)",
        (str(ws),),
    )
    con.commit()
    con.close()
    monkeypatch.setenv("DR_HERMES_STATE_DB", str(banco))
    sessoes = telemetria.coletar(ws, 0)
    assert sessoes["redator_p1"]["reasoning_trace"] == ""
    assert sessoes["redator_p1"]["tool_calls_lista"] == []
    assert sessoes["redator_p1"]["latency_ms"] == 2000


def test_planner_usa_sessao_pai_e_propagacao(tmp_path, monkeypatch):
    from hermes_runner import HermesRunner
    from config import Config

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "saidas").mkdir()
    (ws / "saidas" / "planner.json").write_text(
        json.dumps(
            {
                "pontos": [
                    {
                        "ponto_id": 1,
                        "enunciado": "e",
                        "subperguntas": ["a", "b", "c"],
                        "hipoteses": ["h1", "h2", "h3"],
                        "lacunas_iniciais": ["l1", "l2", "l3"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    banco = _banco(
        tmp_path,
        ws,
        [("s0", None, "Você é o agente principal", "mp", 10.0, 13.0, 400, 60, 10, 2)],
        [("s0", "assistant", "t", json.dumps({"name": "web_search"}), None, "porque-sim", None, 1.0)],
    )
    monkeypatch.setenv("DR_HERMES_STATE_DB", str(banco))
    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    cfg = Config()
    cfg.pipeline.hermes_bin = f"{sys.executable} /bin/false"
    runner = HermesRunner(cfg)
    tarefa = Tarefa(id="planner", papel="planner", sistema="s", prompt="p", payload={"profundidade": 1})
    saidas = runner._coletar_saidas(ws, [tarefa], 0.0, "", modo="planner")
    got = saidas["planner"]
    assert got.total_tokens == 470
    assert got.latency_ms == 3000
    assert got.reasoning_trace == "porque-sim"
    assert got.tool_calls == [{"name": "web_search"}]


def test_materializar_perfil(tmp_path, monkeypatch):
    import settings

    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model:\n  default: 'prefixo-${LLM_MODEL_EXTRA}-sufixo'\n"
        "  provider: custom\n  base_url: 'https://x/v1'\n  api_key: 'sk-falso'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_MODEL_EXTRA", "segredo-123")
    assert settings.materializar_perfil() is True
    texto = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "segredo-123" in texto
    assert "sk-falso" not in texto and "base_url" not in texto
    assert settings.materializar_perfil() is False  # nada a expandir agora


def test_entrypoint_fallback_por_papel(tmp_path):
    """Sem env: planner/auditor/redator fortes, buscadores leves (sem eval)."""
    import re

    texto = (Path(__file__).resolve().parent.parent / "engine" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )
    for papel in ("PLANNER", "HISTORIADOR", "CETICO", "VISIONARIO", "FUTURISTA", "AUDITOR", "REDATOR"):
        assert re.search(rf"\b{papel}\)", texto), papel
    assert "\neval " not in texto and "$(eval" not in texto
    assert "MODELO_LEVE_PADRAO" in texto and "MODELO_FORTE_PADRAO" in texto


def test_por_papel_resolve_workspace_da_task(tmp_path, monkeypatch):
    sys.path.insert(0, "/opt/hermes")
    sys.path.insert(0, "hermes_home/plugins/delegation/por_papel")
    import importlib

    mod = importlib.import_module("__init__")
    importlib.reload(mod)
    outro = tmp_path / "outro"
    outro.mkdir()
    (outro / "MODELS.json").write_text(
        json.dumps({"modelos_por_papel": {"auditor": "modelo-certo"}}), encoding="utf-8"
    )
    ws_real = tmp_path / "data" / "workspaces" / "R1"
    ws_real.mkdir(parents=True)
    (ws_real / "MODELS.json").write_text(
        json.dumps({"modelos_por_papel": {"auditor": "modelo-certo"}}), encoding="utf-8"
    )
    monkeypatch.chdir(outro)  # cwd alheio: sem a task cairia no fallback vazio
    task = {"papel": "auditor", "goal": f"[auditor] auditor_p1_r1 — Trabalhe SOMENTE dentro de {ws_real}"}
    prov = mod.PorPapelDelegationProvider()
    rota = prov.route_task(task, {"backends": {"por_papel": {"modelos": {}}}})
    assert rota["model"] == "modelo-certo"
    with pytest.raises(Exception):
        prov.route_task({"papel": "desconhecido"}, {})
