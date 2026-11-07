from __future__ import annotations

import json

import pytest
import yaml
from conftest import FakeExecutor
from fastapi.testclient import TestClient

import settings
from api import create_app
from contracts import ResearchRequest
from engine import AgentCall
from orchestrator import Pipeline

PERFIL = """
model:
  default: "modelo-antigo"
delegation:
  backend: default
  max_concurrent_children: 3
"""


def test_ler_e_gravar_config_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_BASE_URL", "http://9router:20128/v1")
    monkeypatch.delenv("DR_ENGINE_URL", raising=False)
    (tmp_path / "config.yaml").write_text(PERFIL, encoding="utf-8")

    lido = settings.ler_config()
    assert lido["default_model"] == "modelo-antigo"
    assert lido["base_url"] == "http://9router:20128/v1"
    assert lido["api_key"] == ""
    assert lido["provider_fonte"] == "env"

    # Provedor não é gravável: PUT com base_url/api_key vira 422.
    for campo in ("base_url", "api_key"):
        with pytest.raises(Exception, match="provedor vem do ambiente"):
            settings.ConfigHermes.model_validate({campo: "x"})

    atualizado = settings.aplicar_config(
        settings.ConfigHermes(
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
    # Segredo nunca persiste no YAML.
    assert "api_key" not in gravado["model"]
    assert "base_url" not in gravado["model"]
    # Campo omitido no PUT continua como estava.
    assert gravado["model"]["default"] == "deepseek/deepseek-v3.2"


def test_endpoints_de_configuracao(config, repositorio, tmp_path, monkeypatch):
    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_BASE_URL", "http://9router:20128/v1")
    monkeypatch.delenv("DR_ENGINE_URL", raising=False)
    (tmp_path / "config.yaml").write_text(PERFIL, encoding="utf-8")
    cliente = TestClient(
        create_app(Pipeline(repositorio, FakeExecutor(lambda *_: {}), config))
    )

    corpo = cliente.get("/config").json()
    assert corpo["default_model"] == "modelo-antigo"
    assert corpo["base_url"] == "http://9router:20128/v1"
    assert corpo["api_key"] == ""
    assert corpo["provider_fonte"] == "env"

    resposta = cliente.put(
        "/config",
        json={"max_spawn_depth": 2, "oneshot_max_children": 0, "max_concurrent_children": 40},
    )
    assert resposta.status_code == 200
    assert cliente.get("/api/v1/settings").json()["max_concurrent_children"] == 40

    # Provedor via PUT é rejeitado com 422 e mensagem canônica.
    for campo in ("base_url", "api_key"):
        negado = cliente.put("/config", json={campo: "https://x/v1"})
        assert negado.status_code == 422
        assert "provedor vem do ambiente" in negado.text

    assert cliente.put("/config", json={"modelos_por_papel": {"inexistente": "x"}}).status_code == 422


def test_aplicar_config_com_engine_mockado(tmp_path, monkeypatch):
    import httpx as _httpx

    monkeypatch.setenv("DR_ENGINE_URL", "http://engine:8090")
    monkeypatch.setenv("DR_ENGINE_TOKEN", "tok-123")
    monkeypatch.setenv("DR_HERMES_PROFILE_DIR", str(tmp_path))
    visto: dict = {}

    def _handler(requisicao: _httpx.Request) -> _httpx.Response:
        visto["url"] = str(requisicao.url)
        visto["token"] = requisicao.headers.get("X-Engine-Token")
        visto["json"] = json.loads(requisicao.content.decode())
        assert "base_url" not in visto["json"] and "api_key" not in visto["json"]
        return _httpx.Response(200, json={"ok": True, "eco": visto["json"]})

    _RealClient = _httpx.Client
    monkeypatch.setattr(
        _httpx,
        "Client",
        lambda *a, **k: _RealClient(
            transport=_httpx.MockTransport(_handler), timeout=k.get("timeout")
        ),
    )
    saida = settings.aplicar_config(
        settings.ConfigHermes(
            default_model="m-novo",
            max_concurrent_children=40,
            modelos_por_papel=settings.ModelosPorPapel(planner="m-novo"),
        )
    )
    assert visto["url"] == "http://engine:8090/config"
    assert visto["token"] == "tok-123"
    assert visto["json"]["default_model"] == "m-novo"
    assert visto["json"]["max_concurrent_children"] == 40
    assert visto["json"]["modelos_por_papel"] == {"planner": "m-novo"}
    assert saida["ok"] is True
    # Nada gravado localmente quando o engine é dono do config.
    assert not (tmp_path / "config.yaml").exists()


def test_workspace_isolado_por_pesquisa(config, repositorio):
    pipeline = Pipeline(repositorio, FakeExecutor(lambda *_: {}), config)
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


def test_modelo_por_papel_defaults(monkeypatch):
    for var in (
        "LLM_MODEL",
        "LLM_MODEL_PLANNER",
        "LLM_MODEL_HISTORIADOR",
        "LLM_MODEL_CETICO",
        "LLM_MODEL_VISIONARIO",
        "LLM_MODEL_FUTURISTA",
        "LLM_MODEL_AUDITOR",
        "LLM_MODEL_REDATOR",
    ):
        monkeypatch.delenv(var, raising=False)
    assert settings.modelo_do_papel("planner") == "ocg/deepseek-v4.1-flash"
    assert settings.modelo_do_papel("auditor") == "ocg/deepseek-v4.1-flash"
    assert settings.modelo_do_papel("redator") == "ocg/deepseek-v4.1-flash"
    for papel in ("historiador", "cetico", "visionario", "futurista"):
        assert settings.modelo_do_papel(papel) == "gemini/gemini-3.5-flash-lite"
    monkeypatch.setenv("LLM_MODEL", "custom/planner-x")
    assert settings.modelo_do_papel("planner") == "custom/planner-x"
    assert settings.modelo_do_papel("historiador") == "gemini/gemini-3.5-flash-lite"
    monkeypatch.setenv("LLM_MODEL_CETICO", "custom/cetico-y")
    assert settings.modelo_do_papel("cetico") == "custom/cetico-y"


def test_teto_delegacao_por_papel_pregado():
    """RF02/SDD §2: o teto de fan-out 40 vive no perfil (autoridade única)."""
    from pathlib import Path

    import yaml

    raiz = Path(settings.__file__).resolve().parent.parent
    perfil = yaml.safe_load((raiz / "hermes_home" / "profiles" / "deep-research" / "config.yaml").read_text(encoding="utf-8"))

    delegacao = perfil.get("delegation") or {}
    assert delegacao.get("backend") == "por_papel", "perfil"
    assert delegacao.get("max_concurrent_children") == 40, "perfil"
    assert delegacao.get("max_spawn_depth") == 2, "perfil"
    assert delegacao.get("oneshot_max_children") == 0, "perfil"
