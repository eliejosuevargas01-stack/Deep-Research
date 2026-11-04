"""Configuração do provedor OpenAI-compatible e modelos por subagente."""

from __future__ import annotations

import json

import pytest

from app.api.v1.endpoints.settings import HermesSettingsPayload, get_hermes_settings, put_hermes_settings
from app.core import hermes_config, hermes_planner


class _Proc:
    def __init__(self) -> None:
        self.returncode = 0

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.returncode = -9


@pytest.fixture
def arquivo_settings(tmp_path, monkeypatch):
    destino = tmp_path / "hermes_settings.json"
    monkeypatch.setenv("DR_SETTINGS_FILE", str(destino))
    return destino


@pytest.mark.asyncio
async def test_salvar_configuracoes_propaga_base_url_api_key_e_modelos_para_execucao_hermes(
    arquivo_settings, tmp_path, monkeypatch
):
    await put_hermes_settings(
        HermesSettingsPayload(
            openai_base_url="https://llm.exemplo.com/v1",
            openai_api_key="sk-teste-123",
            modelo_padrao="modelo-base",
            modelo_planejador="modelo-plano",
            modelo_historiador="modelo-hist",
            modelo_auditor="modelo-audit",
            modelo_redator="modelo-red",
        )
    )
    publico = await get_hermes_settings()
    assert publico["openai_base_url"] == "https://llm.exemplo.com/v1"
    assert publico["tem_api_key"] is True
    assert "openai_api_key" not in publico, "a chave não pode voltar para a UI"
    assert publico["modelos_por_papel"]["auditor"] == "modelo-audit"
    assert publico["modelos_por_papel"]["cetico"] == "modelo-base", "fallback para o padrão"

    capturado = {}

    async def fake_exec(*argv, **kwargs):
        capturado["argv"] = argv
        capturado["env"] = kwargs["env"]
        return _Proc()

    monkeypatch.setattr(hermes_planner.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setenv("DR_HERMES_PESQUISAS_DIR", str(tmp_path / "pesquisas"))
    monkeypatch.setenv("DR_HERMES_BIN", "/usr/local/bin/hermes")

    await hermes_planner.executar("Tema de teste", "plan-1791234567890-a9f4c21b")

    env = capturado["env"]
    assert env["OPENAI_API_KEY"] == "sk-teste-123"
    assert env["LLM_BASE_URL"] == "https://llm.exemplo.com/v1"
    assert env["DR_MODEL_HISTORIADOR"] == "modelo-hist"
    assert env["DR_MODEL_AUDITOR"] == "modelo-audit"
    assert env["DR_MODEL_REDATOR"] == "modelo-red"
    argv = list(capturado["argv"])
    assert "-m" in argv and argv[argv.index("-m") + 1] == "modelo-plano"

    workspace = hermes_planner.criar_workspace("plan-1791234567890-a9f4c21b", "Tema de teste")
    modelos = json.loads((workspace / "MODELS.json").read_text(encoding="utf-8"))
    assert modelos["historiador"] == "modelo-hist"
    assert modelos["auditor"] == "modelo-audit"


def test_base_url_invalida_e_recusada(arquivo_settings):
    import asyncio

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(put_hermes_settings(HermesSettingsPayload(openai_base_url="ftp://x")))


def test_sem_configuracao_nao_inventa_modelo(arquivo_settings):
    assert hermes_config.carregar()["modelo_padrao"] == ""
    assert hermes_config.env_hermes({}) == {}
