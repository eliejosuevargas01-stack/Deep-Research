"""Run the real FastAPI app with isolated storage and existing provider fixtures.

This is acceptance-test infrastructure, never a production entry point.
    .venv/bin/python docs/frontend/serve_contract_api.py
The fixed access key below is a public fixture, not a project credential.
"""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import tempfile
    from cryptography.fernet import Fernet
    import uvicorn

    isolated_dir = tempfile.TemporaryDirectory(prefix="deep-research-ui-contract-")
    fixtures = {
        "PYTEST_CURRENT_TEST": "tests/integration/frontend_browser_contract (call)",
        "DATABASE_URL": f"sqlite+aiosqlite:///{isolated_dir.name}/acceptance.db",
        "CREDENTIALS_MASTER_KEY": Fernet.generate_key().decode(),
        "API_SECRET_KEY": "frontend-contract-key",
        "OPENAI_API_KEY": "fixture-openai-key",
        "JINA_API_KEY": "fixture-jina-key",
        "Jina_API_KEY": "fixture-jina-key",
        "N_PONTOS": "5",
        "PERSONAS_CONFIG": "planejador,historiador,visionario,cetico,futurista,auditor,redator final",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL_LIGHT": "gpt-4o-mini",
        "LLM_MODEL_STRONG": "gpt-4o",
        "JINA_BASE_URL": "https://s.jina.ai",
        "Jina_BASE_URL": "https://s.jina.ai",
        "WEBHOOK_HMAC_SECRET": "public-fixture-webhook-secret",
        "CALLBACK_WEBHOOK_URL": "https://mock.webhook.test/callback",
    }
    os.environ.update(fixtures)
    os.chdir(ROOT)
    print("Acceptance API: isolated SQLite; mocked external providers; port 8011")
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8011, log_level="warning")
    finally:
        isolated_dir.cleanup()
