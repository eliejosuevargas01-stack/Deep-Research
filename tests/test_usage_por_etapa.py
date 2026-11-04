"""Uso por etapa: um arquivo por invocação do Hermes, soma monotônica e por persona."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.core import hermes_planner, usage


def _uso(workspace: Path, nome: str, entrada: int, saida: int) -> None:
    (workspace / nome).write_text(
        json.dumps(
            {"input_tokens": entrada, "output_tokens": saida, "total_tokens": entrada + saida}
        ),
        encoding="utf-8",
    )


def _sem_state_db(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "vazio"))
    monkeypatch.setenv("HERMES_PROFILE", "sem-perfil")


def test_quatro_etapas_somam_total_exato(tmp_path, monkeypatch):
    _sem_state_db(monkeypatch, tmp_path)
    _uso(tmp_path, "usage_plan.json", 4000, 1000)
    _uso(tmp_path, "usage_search_ponto_1.json", 20000, 4000)
    _uso(tmp_path, "usage_audit_ponto_1_rodada_1.json", 5000, 1000)
    _uso(tmp_path, "usage_write.json", 12000, 2400)

    resumo = usage.resumo_uso(tmp_path)
    assert resumo["total"] == {"input_tokens": 41000, "output_tokens": 8400, "total_tokens": 49400}
    assert set(resumo["por_etapa"]) == {
        "plan",
        "search_ponto_1",
        "audit_ponto_1_rodada_1",
        "write",
    }


def test_total_nunca_regride_com_arquivo_menor(tmp_path, monkeypatch):
    _sem_state_db(monkeypatch, tmp_path)
    _uso(tmp_path, "usage_plan.json", 4000, 1000)
    _uso(tmp_path, "usage_write.json", 12000, 2400)
    primeiro = usage.gravar_resumo(tmp_path)["total"]["total_tokens"]
    assert primeiro == 19400

    # Turno parcial sobrescreve a etapa com número menor: total não pode cair.
    _uso(tmp_path, "usage_write.json", 100, 10)
    segundo = usage.gravar_resumo(tmp_path)["total"]["total_tokens"]
    # Arquivo novo e menor apenas acrescenta.
    _uso(tmp_path, "usage_search_ponto_1.json", 30, 5)
    terceiro = usage.gravar_resumo(tmp_path)["total"]["total_tokens"]

    assert segundo == primeiro
    assert terceiro == primeiro + 35


def test_por_agente_lista_personas_do_state_db(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    perfil = tmp_path / "profiles" / "deep-research"
    perfil.mkdir(parents=True)
    conexao = sqlite3.connect(perfil / "state.db")
    conexao.execute(
        "create table sessions (id text, model text, title text, display_name text,"
        " cwd text, input_tokens integer, output_tokens integer)"
    )
    conexao.executemany(
        "insert into sessions values (?,?,?,?,?,?,?)",
        [
            ("s1", "m-pai", "Plano da pesquisa", None, str(workspace), 3000, 2000),
            ("s2", "m-hist", "Subagent: historiador no eixo 1", None, str(workspace), 20000, 4000),
            ("s3", "m-prag", "Subagent: pragmatico no eixo 2", None, str(workspace), 8000, 1000),
            ("s4", "m-cet", "Subagent: cético no eixo 3", None, str(workspace), 7000, 900),
            ("s5", "m-vis", "Subagent: visionario no eixo 4", None, str(workspace), 6000, 800),
            ("s6", "m-aud", "Subagent: auditor da rodada 1", None, str(workspace), 5000, 700),
            ("s7", "m-red", "Subagent: redator do dossiê", None, str(workspace), 9000, 1500),
        ],
    )
    conexao.commit()
    conexao.close()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_PROFILE", "deep-research")

    por_agente = usage.resumo_uso(workspace)["por_agente"]
    for persona in ("historiador", "pragmatico", "cetico", "visionario", "auditor", "redator"):
        assert persona in por_agente, f"persona {persona} ausente no detalhamento"
    assert por_agente["historiador"]["total_tokens"] == 24000
    assert por_agente["cetico"]["total_tokens"] == 7900
    assert usage.resumo_uso(workspace)["total"]["total_tokens"] == 68900


class _Proc:
    def __init__(self, code: int = 0) -> None:
        self.returncode = code

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("etapa", "ponto", "rodada", "esperado"),
    [
        ("plan", 1, 1, "usage_plan.json"),
        ("search", 2, 1, "usage_search_ponto_2.json"),
        ("audit", 1, 3, "usage_audit_ponto_1_rodada_3.json"),
        ("write", 1, 1, "usage_write.json"),
    ],
)
async def test_planner_escolhe_arquivo_de_uso_por_etapa(
    tmp_path, monkeypatch, etapa, ponto, rodada, esperado
):
    capturado = {}

    async def fake_exec(*argv, **kwargs):
        capturado["argv"] = argv
        return _Proc()

    monkeypatch.setattr(hermes_planner.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setenv("DR_HERMES_PESQUISAS_DIR", str(tmp_path))
    monkeypatch.setenv("DR_HERMES_BIN", "/usr/local/bin/hermes")
    monkeypatch.delenv("DR_HERMES_ETAPA", raising=False)

    execucao = await hermes_planner.iniciar(
        "Tema curto", "abcd1234efgh", etapa=etapa, ponto=ponto, rodada=rodada
    )
    await execucao.aguardar()

    argv = list(capturado["argv"])
    assert argv[5] == "--usage-file"
    assert argv[6] == str(execucao.workspace / esperado)
