from __future__ import annotations

import json

import yaml
from conftest import FakeEngine
from fastapi.testclient import TestClient

import settings
from api import create_app
from contracts import ResearchRequest
from engine import AgentCall
from orchestrator import Pipeline

PERFIL = """
model:
  default: "modelo-antigo"
  base_url: "http://antigo/v1"
  api_key: "chave-antiga"
delegation:
  backend: default
  max_concurrent_children: 3
"""


def test_ler_e_gravar_config_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(PERFIL, encoding="utf-8")

    assert settings.ler_config()["default_model"] == "modelo-antigo"

    atualizado = settings.aplicar_config(
        settings.ConfigHermes(
            base_url="http://9router:20128/v1",
            default_model="deepseek/deepseek-v3.2",
            max_concurrent_children=40,
            modelos_por_papel=settings.ModelosPorPapel(
                planner="deepseek/deepseek-v3.2", auditor="ocg/deepseek-v4.1-flash"
            ),
        )
    )
    assert atualizado["max_concurrent_children"] == 40
    assert atualizado["modelos_por_papel"]["auditor"] == "ocg/deepseek-v4.1-flash"
    assert atualizado["modelos_por_papel"]["historiador"] == ""

    gravado = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert gravado["delegation"]["backend"] == "por_papel"
    assert gravado["delegation"]["max_concurrent_children"] == 40
    assert gravado["delegation"]["backends"]["por_papel"]["modelos"]["planner"] == (
        "deepseek/deepseek-v3.2"
    )
    # Campo omitido no PUT continua como estava.
    assert gravado["model"]["api_key"] == "chave-antiga"


def test_endpoints_de_configuracao(config, repositorio, tmp_path, monkeypatch):
    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(PERFIL, encoding="utf-8")
    cliente = TestClient(
        create_app(Pipeline(repositorio, FakeEngine(lambda *_: {}), config))
    )

    assert cliente.get("/config").json()["default_model"] == "modelo-antigo"

    resposta = cliente.put(
        "/config",
        json={"max_spawn_depth": 2, "oneshot_max_children": 0, "max_concurrent_children": 40},
    )
    assert resposta.status_code == 200
    assert cliente.get("/api/v1/settings").json()["max_concurrent_children"] == 40

    assert cliente.put("/config", json={"modelos_por_papel": {"inexistente": "x"}}).status_code == 422


def test_workspace_isolado_por_pesquisa(config, repositorio):
    pipeline = Pipeline(repositorio, FakeEngine(lambda *_: {}), config)
    requisicao = ResearchRequest(
        tema="matriz energética",
        profundidade=1,
        veracidade_alvo=90,
        max_rodadas_auditoria=2,
        atualidade="24H",
        callback_url="https://webhook.example/cb",
    )
    primeiro = pipeline.criar(requisicao)
    segundo = pipeline.criar(requisicao)

    workspace = pipeline.caminho_workspace(primeiro)
    assert workspace.is_dir()
    assert workspace != pipeline.caminho_workspace(segundo)
    modelos = json.loads((workspace / "MODELS.json").read_text(encoding="utf-8"))
    assert set(modelos["modelos_por_papel"]) == set(settings.PAPEIS)


def test_model_used_persistido(repositorio):
    requisicao = ResearchRequest(
        tema="tema de teste",
        profundidade=1,
        veracidade_alvo=90,
        max_rodadas_auditoria=2,
        atualidade="24H",
        callback_url="https://webhook.example/cb",
    )
    repositorio.criar_run("R1", requisicao)
    repositorio.registrar_execucao(
        research_id="R1",
        ponto_id=1,
        rodada=1,
        agent_role="historiador",
        model_used="deepseek/deepseek-v3.2",
        input_prompt_payload={},
        call=AgentCall(dados={}),
    )
    assert repositorio.obter_execucoes("R1")[0]["model_used"] == "deepseek/deepseek-v3.2"
