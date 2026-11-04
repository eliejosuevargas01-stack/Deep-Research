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


def test_papel_desconhecido_cai_no_modelo_padrao(modelos):
    plugin = _carregar_plugin()
    rota = plugin.DelegationPorPapel()
    assert rota.route_task({"goal": "Tarefa sem persona reconhecível"}, {})["model"] == "modelo-plano"


def test_sem_arquivo_nem_config_herda_o_pai(tmp_path, monkeypatch):
    plugin = _carregar_plugin()
    monkeypatch.setenv("DR_MODELOS_FILE", str(tmp_path / "inexistente.json"))
    assert plugin.DelegationPorPapel().route_task({"goal": "Historiador"}, {}) == {}


def test_config_do_perfil_serve_de_fallback(tmp_path, monkeypatch):
    plugin = _carregar_plugin()
    monkeypatch.setenv("DR_MODELOS_FILE", str(tmp_path / "inexistente.json"))
    config = {"backends": {"por_papel": {"modelos": {"auditor": "modelo-yaml"}}}}
    assert plugin.DelegationPorPapel().route_task({"goal": "Auditor"}, config)["model"] == "modelo-yaml"
