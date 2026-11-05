"""E2E do executor real: o backend aciona o CLI Hermes no workspace da pesquisa."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

import settings
import telemetria
from config import Config
from engine import Tarefa
from hermes_runner import HermesRunner

STUB = Path(__file__).with_name("fake_hermes.py")
PROMPT = "```json\n" + json.dumps({"profundidade": 2, "tema": "tema", "ponto_id": 1, "rodada": 1}) + "\n```"


@pytest.fixture
def runner(config: Config, monkeypatch, tmp_path) -> HermesRunner:
    config.pipeline.hermes_bin = f"{sys.executable} {STUB}"
    config.pipeline.hermes_timeout_s = 30
    monkeypatch.delenv("DR_HERMES_PROFILE_DIR", raising=False)
    monkeypatch.delenv("DR_HERMES_STATE_DB", raising=False)
    return HermesRunner(config)


def test_planejar_aciona_hermes_com_cwd_no_workspace(runner, tmp_path):
    workspace = tmp_path / "ws"
    tarefa = Tarefa(
        id="planner",
        papel="planner",
        sistema="sistema",
        prompt=PROMPT,
        payload={"profundidade": 2, "tema": "tema"},
    )

    call = runner.planejar(workspace, tarefa)

    assert call.erro == ""
    assert [ponto["ponto_id"] for ponto in call.dados["pontos"]] == [1, 2]
    assert call.total_tokens == 1250
    assert call.prompt_tokens == 1000
    assert call.model_used == settings.ler_config()["modelos_por_papel"]["planner"]

    chamadas = [
        json.loads(linha) for linha in (workspace / "chamadas.jsonl").read_text().splitlines()
    ]
    assert chamadas[0]["cwd"] == str(workspace)
    assert (workspace / "prompts" / "planner.md").exists()
    assert (workspace / "saidas" / "planner.json").exists()


def test_lote_executa_uma_tarefa_por_papel(runner, tmp_path):
    workspace = tmp_path / "ws"
    tarefas = [
        Tarefa(
            id=f"{papel}_p1_r1",
            papel=papel,
            sistema="sistema",
            prompt=PROMPT,
            payload={"ponto_id": 1, "rodada": 1},
            ponto_id=1,
            rodada=1,
        )
        for papel in ("historiador", "auditor")
    ]

    saidas = runner.executar(workspace, tarefas)

    assert set(saidas) == {"historiador_p1_r1", "auditor_p1_r1"}
    assert saidas["historiador_p1_r1"].dados["urls_usadas"]
    assert saidas["auditor_p1_r1"].dados["perguntas_respondidas"]["12"] is True
    assert json.loads((workspace / "tarefas.json").read_text())[0]["arquivo"] == (
        "prompts/historiador_p1_r1.md"
    )


def test_sem_saida_vira_erro_por_tarefa(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_HERMES_SEM_SAIDA", "1")
    workspace = tmp_path / "ws"
    tarefa = Tarefa(
        id="historiador_p1_r1",
        papel="historiador",
        sistema="sistema",
        prompt=PROMPT,
        payload={"ponto_id": 1, "rodada": 1},
    )

    call = runner.executar(workspace, [tarefa])["historiador_p1_r1"]

    assert call.erro
    assert "sem saidas/historiador_p1_r1.json" in call.erro


def test_telemetria_le_tokens_e_modelo_do_state_db(tmp_path, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    banco = tmp_path / "state.db"
    con = sqlite3.connect(banco)
    con.execute(
        "CREATE TABLE sessions (id TEXT, parent_session_id TEXT, title TEXT, model TEXT,"
        " cwd TEXT, started_at REAL, ended_at REAL, input_tokens INTEGER, output_tokens INTEGER,"
        " reasoning_tokens INTEGER, tool_call_count INTEGER)"
    )
    con.execute(
        "INSERT INTO sessions VALUES ('s1', 'root', '[auditor] auditor_p1_r2 — conferir',"
        " 'openai/gpt-5.1', ?, 100.0, 110.0, 900, 120, 30, 4)",
        (str(workspace),),
    )
    con.commit()
    con.close()
    monkeypatch.setenv("DR_HERMES_STATE_DB", str(banco))

    sessoes = telemetria.coletar(workspace, 0)

    assert sessoes["auditor_p1_r2"]["total_tokens"] == 1050
    assert sessoes["auditor_p1_r2"]["model_used"] == "openai/gpt-5.1"
    assert sessoes["auditor_p1_r2"]["tool_calls"] == 4
