"""Sincronização de credenciais/modelos no config.yaml do perfil Hermes."""

from __future__ import annotations

import os
import stat

from app.core import hermes_config

CONFIG = """model:
  default: "${LLM_MODEL_STRONG}"
  provider: custom
  base_url: "${LLM_BASE_URL}"
  api_key: "${OPENAI_API_KEY}"

delegation:
  backend: por_papel
  max_spawn_depth: 2
"""


def _perfil(tmp_path):
    perfil = tmp_path / "profiles" / "deep-research"
    perfil.mkdir(parents=True)
    (perfil / "config.yaml").write_text(CONFIG, encoding="utf-8")
    (perfil / "SOUL.md").write_text("soul", encoding="utf-8")
    return perfil


def test_sincronizar_perfil_grava_valores_concretos(tmp_path, monkeypatch):
    perfil = _perfil(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_PROFILE", "deep-research")

    ok = hermes_config.sincronizar_perfil(
        {
            "openai_base_url": "http://9router:20128/v1",
            "openai_api_key": "sk-real-123",
            "modelo_padrao": "modelo-padrao",
            "modelo_auditor": "modelo-aud",
        }
    )

    assert ok is True
    texto = (perfil / "config.yaml").read_text(encoding="utf-8")
    assert "modelo-padrao" in texto
    assert "http://9router:20128/v1" in texto
    assert "sk-real-123" in texto
    assert "${LLM_MODEL_STRONG}" not in texto
    # O resto do perfil continua intacto.
    assert "backend: por_papel" in texto
    assert stat.S_IMODE(os.stat(perfil / "config.yaml").st_mode) == 0o600


def test_sem_configuracao_nao_reescreve(tmp_path, monkeypatch):
    perfil = _perfil(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    antes = (perfil / "config.yaml").read_text(encoding="utf-8")
    assert hermes_config.sincronizar_perfil({}) is False
    assert (perfil / "config.yaml").read_text(encoding="utf-8") == antes


def test_perfil_ausente_devolve_none(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "vazio"))
    assert hermes_config.perfil_hermes("deep-research") is None
