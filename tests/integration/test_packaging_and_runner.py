"""Testes de integração e validação estática para empacotamento, Docker e scripts de execução.

Valida:
1. Dockerfile: multi-stage build, ausência de cópia de .env para a imagem, bind 127.0.0.1 seguro por padrão.
2. docker-compose.yml: comando explícito vinculando a 127.0.0.1:8085, network_mode host no Linux,
   volume de dados relativo ao projeto (./data:/app/data), passagem de variáveis sensíveis via env_file.
3. scripts/run_app.py: tratamento de falha de build, limpeza antes de build forçado, resolução de npm ausente.
"""

import re
from pathlib import Path
import pytest

from scripts.run_app import build_frontend, load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_dockerfile_multi_stage_and_secure_bind():
    """Valida que o Dockerfile possui multi-stage build, não inclui .env e faz bind em 127.0.0.1."""
    dockerfile_path = ROOT_DIR / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile deve existir na raiz do projeto."

    content = dockerfile_path.read_text(encoding="utf-8")

    # 1. Multi-stage build
    assert "FROM node:20-slim AS frontend-builder" in content
    assert "FROM python:3.14-slim" in content
    assert "COPY --from=frontend-builder /frontend/dist" in content

    # 2. Segurança: .env NUNCA deve ser copiado para a imagem
    for line in content.splitlines():
        clean = line.strip()
        if clean.startswith("COPY") or clean.startswith("ADD"):
            assert ".env" not in clean, f"O Dockerfile não pode copiar o arquivo .env para a imagem: {clean}"

    # 3. Bind seguro: 127.0.0.1 por padrão, com variáveis HOST e PORT configuráveis
    assert "ENV HOST=127.0.0.1" in content
    assert "ENV PORT=8000" in content
    assert "--host ${HOST:-127.0.0.1}" in content
    assert "0.0.0.0" not in content, "Dockerfile de entrega local não deve fazer bind padrão em 0.0.0.0."


def test_docker_compose_config_structure_sanitized():
    """Valida a estrutura do docker-compose.yml de forma sanitizada (sem expor segredos)."""
    compose_path = ROOT_DIR / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml deve existir na raiz do projeto."

    content = compose_path.read_text(encoding="utf-8")

    # 1. Comando explícito vinculando a 127.0.0.1 e porta 8085
    assert "--host" in content
    assert "127.0.0.1" in content
    assert "--port" in content
    assert "8085" in content
    assert 'command: ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8085"]' in content

    # 2. Rede host para Linux
    assert re.search(r"network_mode:\s*host", content) is not None

    # 3. Variáveis de ambiente sensíveis fornecidas via env_file
    assert re.search(r"env_file:\s*\n\s*-\s*\.env", content) is not None

    # 4. Volume de dados relativo ao projeto, sem caminhos hardcoded como /root/projects
    assert "./data:/app/data" in content
    assert "/root/projects" not in content, "Não deve usar caminho absoluto hardcoded /root/projects."

    # 5. Preserva overrides essenciais
    assert "DATABASE_URL=sqlite+aiosqlite:////app/data/deep_research.db" in content
    assert "CREDENTIALS_MASTER_KEY=${CREDENTIALS_MASTER_KEY}" in content


def test_run_app_build_clean_handles_missing_npm_gracefully(monkeypatch: pytest.MonkeyPatch):
    """Valida que scripts/run_app.py falha claramente se npm não estiver no PATH sem mascarar com dist antigo."""
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    # Executa build_frontend com npm simuladamente ausente
    res = build_frontend(ROOT_DIR, force_clean=True)
    assert res is False, "build_frontend deve retornar False quando npm não estiver no PATH."


def test_run_app_load_dotenv_does_not_override_existing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Valida que load_dotenv carrega variáveis sem sobrescrever as já exportadas no ambiente."""
    fake_env = tmp_path / "test.env"
    fake_env.write_text("CHAVE_TESTE_EXISTENTE=valor_do_arquivo\nNOVA_CHAVE=valor_novo\n", encoding="utf-8")

    monkeypatch.setenv("CHAVE_TESTE_EXISTENTE", "valor_do_ambiente_preservado")

    load_dotenv(fake_env)

    import os
    assert os.environ.get("CHAVE_TESTE_EXISTENTE") == "valor_do_ambiente_preservado"
    assert os.environ.get("NOVA_CHAVE") == "valor_novo"
