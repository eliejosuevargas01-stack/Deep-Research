"""O perfil Hermes precisa manter delegation.backend: por_papel.

Sem isso o gateway delega pelo backend default e todo subagente herda o modelo
do pai — a seleção de modelo por papel vira decoração.
"""
from app.core import hermes_config


def test_sincronizar_perfil_forca_backend_por_papel(tmp_path, monkeypatch):
    perfil = tmp_path / "profiles" / "deep-research"
    perfil.mkdir(parents=True)
    (perfil / "config.yaml").write_text(
        'model:\n  default: "${LLM_MODEL_STRONG}"\n  base_url: "http://x/v1"\n'
        "delegation:\n  backend: default\n  max_depth: 2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hermes_config, "perfil_hermes", lambda _p=None: perfil)

    assert hermes_config.sincronizar_perfil(
        {"modelo_padrao": "m1", "openai_base_url": "http://9router:20128/v1", "openai_api_key": "k"}
    )
    texto = (perfil / "config.yaml").read_text(encoding="utf-8")
    assert "backend: por_papel" in texto
    assert "backend: default" not in texto
    assert 'default: "m1"' in texto


def test_sincronizar_perfil_preserva_backend_quando_ja_correto(tmp_path, monkeypatch):
    perfil = tmp_path / "profiles" / "deep-research"
    perfil.mkdir(parents=True)
    original = (
        'model:\n  default: "velho"\n  base_url: "http://x/v1"\n'
        "delegation:\n  backend: por_papel\n  max_depth: 2\n"
    )
    (perfil / "config.yaml").write_text(original, encoding="utf-8")
    monkeypatch.setattr(hermes_config, "perfil_hermes", lambda _p=None: perfil)

    hermes_config.sincronizar_perfil({"modelo_padrao": "m2", "openai_api_key": "k"})
    texto = (perfil / "config.yaml").read_text(encoding="utf-8")
    assert texto.count("backend: por_papel") == 1
