"""Tokens vêm da sessão do Hermes, que enxerga o agente principal e os delegados."""
import sqlite3

from app.core import usage


def _db(tmp_path, workspace, linhas):
    perfil = tmp_path / "profiles" / "deep-research"
    perfil.mkdir(parents=True)
    db = perfil / "state.db"
    conexao = sqlite3.connect(db)
    conexao.execute(
        "create table sessions (id text, model text, title text, display_name text,"
        " cwd text, input_tokens integer, output_tokens integer)"
    )
    conexao.executemany("insert into sessions values (?,?,?,?,?,?,?)", linhas)
    conexao.commit()
    conexao.close()
    return db


def test_resumo_soma_agente_principal_e_subagentes(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    _db(
        tmp_path,
        workspace,
        [
            ("s1", "m-pai", "Plano", None, str(workspace), 3000, 2000),
            ("s2", "m-hist", "Subagent: Pesquise o tema", None, str(workspace), 20000, 4000),
            ("s3", "m-aud", "Subagent: Audite a rodada 1", None, str(workspace), 5000, 1000),
            ("s4", "m-outro", "Outra pesquisa", None, str(tmp_path / "pesquisas" / "x"), 9, 9),
        ],
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_PROFILE", "deep-research")

    resumo = usage.resumo_uso(workspace)
    assert resumo["total"] == {"input_tokens": 28000, "output_tokens": 7000, "total_tokens": 35000}
    assert len(resumo["por_agente"]) == 3
    assert "m-outro" not in str(resumo["por_agente"])


def test_uso_do_arquivo_nao_encolhe_total_do_banco(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    _db(tmp_path, workspace, [("s1", "m", "Plano", None, str(workspace), 1000, 500)])
    (workspace / "usage.json").write_text(
        '{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}', encoding="utf-8"
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_PROFILE", "deep-research")

    assert usage.resumo_uso(workspace)["total"]["total_tokens"] == 1500


def test_sem_state_db_usa_arquivo(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-x"
    workspace.mkdir(parents=True)
    (workspace / "usage_plan.json").write_text(
        '{"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}', encoding="utf-8"
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "vazio"))

    assert usage.resumo_uso(workspace)["total"]["total_tokens"] == 120
