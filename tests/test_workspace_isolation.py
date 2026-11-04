"""Isolamento de workspace por pesquisa (problema 1 do lote de correções).

Cada pesquisa tem diretório próprio, derivado do id completo — nunca dos 8
primeiros caracteres, que em `plan-<timestamp>-<aleatório>` são `plan-179` e se
repetem por ~11 dias.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import hermes_adapter, hermes_planner
from app.core import hermes_stream

TEMA = "Matriz energética Brasil"


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("DR_HERMES_PESQUISAS_DIR", str(tmp_path))
    return tmp_path


def test_duas_pesquisas_mesmo_tema_geram_workspaces_distintos(raiz):
    primeiro = hermes_planner.criar_workspace("plan-1791234567890-aaaaaaaa", TEMA)
    segundo = hermes_planner.criar_workspace("plan-1791234567890-bbbbbbbb", TEMA)

    assert primeiro != segundo
    assert primeiro.is_dir() and segundo.is_dir()
    assert "plan-179" not in primeiro.name
    assert not primeiro.name.endswith("plan-179")

    (primeiro / "PLAN.json").write_text(json.dumps({"tema": TEMA}), encoding="utf-8")
    assert (primeiro / "PLAN.json").exists()
    assert not (segundo / "PLAN.json").exists(), "a segunda pesquisa herdou artefato da primeira"

    # Resolução posterior pelo adaptador acha exatamente o dono, não o vizinho.
    assert hermes_adapter._workspace_exato("plan-1791234567890-bbbbbbbb", TEMA) == segundo
    assert primeiro not in hermes_adapter._raiz_para("plan-1791234567890-bbbbbbbb")


def test_mesmo_id_reabre_o_mesmo_workspace(raiz):
    """Retomar a mesma pesquisa continua idempotente."""
    a = hermes_planner.criar_workspace("plan-1791234567890-cccccccc", TEMA)
    b = hermes_planner.criar_workspace("plan-1791234567890-cccccccc", TEMA)
    assert a == b


def test_hermes_bloqueia_acesso_fora_do_workspace_atual(raiz, monkeypatch, tmp_path):
    """A delegação lida é só a da pesquisa atual; pasta global vizinha é ignorada."""
    alheio = tmp_path / "outra-pesquisa" / ".hermes" / "cache" / "delegation" / "live"
    (alheio / "sessao-alheia").mkdir(parents=True)
    (alheio / "sessao-alheia" / "task-0.log").write_text("https://exemplo.com/x", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "outra-pesquisa" / ".hermes"))
    monkeypatch.delenv("DR_HERMES_DELEGATION_DIR", raising=False)

    ws = hermes_planner.criar_workspace("plan-1791234567890-dddddddd", TEMA)
    watcher = hermes_stream.WatchHermes("plan-1791234567890-dddddddd", ws)
    assert watcher.delegacao._raiz() is None, "leu a delegação de outra pesquisa"

    propria = ws / ".hermes" / "cache" / "delegation" / "live" / "sessao-propria"
    propria.mkdir(parents=True)
    (propria / "task-0.log").write_text("https://exemplo.com/y", encoding="utf-8")
    assert watcher.delegacao._raiz() == propria


def test_delegacao_auditor_nao_reativa_status_ao_vivo_das_personas(raiz):
    """Nova sub-delegação durante auditoria/redação não reabre as personas."""
    ws = hermes_planner.criar_workspace("plan-1791234567890-eeeeeeee", TEMA)
    watcher = hermes_stream.WatchHermes("plan-1791234567890-eeeeeeee", ws)
    propria = ws / ".hermes" / "cache" / "delegation" / "live" / "rodada-auditor"
    propria.mkdir(parents=True)
    (propria / "task-0.log").write_text("https://exemplo.com/auditoria", encoding="utf-8")

    eventos: list[tuple[str, dict]] = []
    watcher._pub = lambda evento, **dados: eventos.append((evento, dados))  # type: ignore[assignment]

    for status in ("auditando", "redigindo"):
        watcher.status = status
        eventos.clear()
        watcher.delegacao.bombear()
        assert not [e for e in eventos if e[0] == "stage.start" and e[1].get("stage") == "search"]
        assert not [e for e in eventos if e[0] == "pipeline.status" and e[1].get("status_pipeline") == "buscando"]

    # Durante a busca real, o sinal de vida continua.
    watcher.status = "buscando"
    eventos.clear()
    watcher.delegacao.bombear()
    assert [e for e in eventos if e[0] == "stage.start" and e[1].get("stage") == "search"]
