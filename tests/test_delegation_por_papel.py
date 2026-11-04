"""Delegação por papel: cada subagente no modelo configurado para o seu papel."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "hermes_home" / "plugins" / "delegation_por_papel" / "__init__.py"


def _carregar_plugin():
    """Importa o plugin do Hermes sem o runtime dele (stub do ABC)."""
    if "agent.delegation_provider" not in sys.modules:
        modulo_agent = types.ModuleType("agent")
        modulo_provider = types.ModuleType("agent.delegation_provider")

        class _Provider:
            pass

        modulo_provider.DelegationProvider = _Provider
        sys.modules["agent"] = modulo_agent
        sys.modules["agent.delegation_provider"] = modulo_provider
    spec = importlib.util.spec_from_file_location("delegation_por_papel_teste", PLUGIN)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def modelos(tmp_path, monkeypatch):
    arquivo = tmp_path / "MODELS.json"
    arquivo.write_text(
        json.dumps(
            {
                "planejador": "modelo-plano",
                "historiador": "modelo-hist",
                "pragmatico": "modelo-prag",
                "cetico": "modelo-cet",
                "visionario": "modelo-vis",
                "auditor": "modelo-audit",
                "redator": "modelo-red",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DR_MODELOS_FILE", str(arquivo))
    return arquivo


def test_salvar_configuracoes_propaga_modelos_distintos_por_subagente(modelos):
    plugin = _carregar_plugin()
    rota = plugin.DelegationPorPapel()

    assert rota.route_task({"goal": "Você é o Historiador. Colete evidências."}, {})["model"] == "modelo-hist"
    assert rota.route_task({"goal": "Auditor: avalie os 12 critérios."}, {})["model"] == "modelo-audit"
    assert rota.route_task({"goal": "Redator final: escreva o dossiê."}, {})["model"] == "modelo-red"
    assert rota.route_task({"goal": "Assuma o papel de Cético."}, {})["model"] == "modelo-cet"
    assert rota.route_task({"goal": "Pragmático: o que funciona hoje?"}, {})["model"] == "modelo-prag"
    assert rota.route_task({"goal": "Visionário: cenários de 2030."}, {})["model"] == "modelo-vis"


def test_contexto_com_todas_as_personas_nao_sequestra_o_papel(modelos):
    """O contexto da pesquisa lista as 4 personas; quem manda é o goal."""
    plugin = _carregar_plugin()
    rota = plugin.DelegationPorPapel()
    tarefa = {
        "goal": "Pesquise no papel de cético e grave CETICO_SEARCH.json",
        "context": "Personas: historiador, visionário, cético, futurista.",
    }
    assert rota.route_task(tarefa, {})["model"] == "modelo-cet"


def test_auditor_e_redator_por_verbo_da_tarefa(modelos):
    plugin = _carregar_plugin()
    rota = plugin.DelegationPorPapel()
    assert rota.route_task({"goal": "Audite a rodada 1 da pesquisa"}, {})["model"] == "modelo-audit"
    assert rota.route_task({"goal": "Redija o dossiê final"}, {})["model"] == "modelo-red"


def test_papel_desconhecido_cai_no_modelo_padrao(modelos):
    plugin = _carregar_plugin()
    rota = plugin.DelegationPorPapel()
    assert rota.route_task({"goal": "Tarefa sem persona reconhecível"}, {})["model"] == "modelo-plano"


def test_modelos_vem_do_workspace_da_tarefa(tmp_path, monkeypatch):
    """Gateway é daemon: o arquivo por pesquisa viaja no contexto da tarefa."""
    plugin = _carregar_plugin()
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    (workspace / "MODELS.json").write_text(
        json.dumps({"planejador": "m-pai", "cetico": "m-cetico-novo"}), encoding="utf-8"
    )
    monkeypatch.setenv("DR_MODELOS_FILE", str(tmp_path / "outra-pesquisa.json"))
    tarefa = {
        "goal": "Pesquise no papel de cético",
        "context": f"CONTRATO:cetico TEMA: X WORKSPACE: {workspace} RODADA: 1",
    }
    assert plugin.DelegationPorPapel().route_task(tarefa, {})["model"] == "m-cetico-novo"


def test_sem_arquivo_nem_config_herda_o_pai(tmp_path, monkeypatch):
    plugin = _carregar_plugin()
    monkeypatch.setenv("DR_MODELOS_FILE", str(tmp_path / "inexistente.json"))
    assert plugin.DelegationPorPapel().route_task({"goal": "Historiador"}, {}) == {}


def test_config_do_perfil_serve_de_fallback(tmp_path, monkeypatch):
    plugin = _carregar_plugin()
    monkeypatch.setenv("DR_MODELOS_FILE", str(tmp_path / "inexistente.json"))
    config = {"backends": {"por_papel": {"modelos": {"auditor": "modelo-yaml"}}}}
    assert plugin.DelegationPorPapel().route_task({"goal": "Auditor"}, config)["model"] == "modelo-yaml"
