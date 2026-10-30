"""Transparent ASGI payload recorder for the real integrated-app acceptance run.

Run only on localhost. It uses the actual FastAPI app and configured providers;
no dependency overrides, request modifications or mocked transports are added.
Cookies, headers, credentials, reasoning and model envelopes are not recorded.

    .venv/bin/python docs/frontend/remediation/capture_app.py --port 8012
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[3]
MAX_BYTES = 4 * 1024 * 1024
PATHS = {f"/api/v1/{name}" for name in ("plan", "search", "audit", "writer")}
PRIVATE = {
    "reasoning", "reasoning_planejamento", "reasoning_auditoria", "reasoning_dossier",
    "reasoning_coleta", "reasoning_content", "envelopes", "envelope", "prompt", "prompts",
    "prompt_hash", "authorization", "cookie", "set-cookie", "api_secret_key", "openai_api_key",
    "jina_api_key", "webhook_hmac_secret", "credenciais", "credentials_master_key",
    "generation_attempts", "attempts_payloads", "system_message", "messages_sent"
}
SENSITIVE_VALUES: list[str] = []


def is_private_key(k: object) -> bool:
    key_str = str(k).lower().strip()
    if key_str in PRIVATE:
        return True
    if any(s in key_str for s in ("secret", "password", "credential", "auth_token", "api_key", "master_key", "fernet")):
        return True
    if any(key_str.endswith(sfx) for sfx in ("_envelope", "_envelopes", "_reasoning", "_prompt", "_prompts")):
        return True
    if any(key_str.startswith(pfx) for pfx in ("envelope_", "envelopes_", "reasoning_", "prompt_")):
        return True
    return False


def public(value):
    if isinstance(value, dict):
        return {k: ("[OMITTED]" if is_private_key(k) else public(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [public(v) for v in value]
    if isinstance(value, str):
        for secret in SENSITIVE_VALUES:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        if value.startswith(("http://", "https://")):
            p = urlsplit(value)
            host = p.hostname or ""
            if p.port:
                host += f":{p.port}"
            return urlunsplit((p.scheme, host, p.path, "", ""))
        return value
    return value


def payload(body: bytes, truncated: bool):
    if truncated:
        return {"capture_truncated": True, "captured_bytes": len(body)}
    try:
        return public(json.loads(body))
    except (ValueError, UnicodeDecodeError):
        return {"non_json_bytes": len(body)}


class Recorder:
    def __init__(self, app, output: Path, provider_mode="live_configured_no_pytest_transport"):
        self.app = app
        self.output = output
        self.provider_mode = provider_mode

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") not in PATHS:
            return await self.app(scope, receive, send)
        start = time.monotonic()
        request_body, response_body = bytearray(), bytearray()
        request_hash, response_hash = hashlib.sha256(), hashlib.sha256()
        request_size = response_size = 0
        response_status = None

        async def observed_receive():
            nonlocal request_size
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                request_hash.update(body)
                request_size += len(body)
                request_body.extend(body[:max(0, MAX_BYTES - len(request_body))])
            return message

        async def observed_send(message):
            nonlocal response_status, response_size
            if message["type"] == "http.response.start":
                response_status = message["status"]
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_hash.update(body)
                response_size += len(body)
                response_body.extend(body[:max(0, MAX_BYTES - len(response_body))])
            await send(message)

        try:
            await self.app(scope, observed_receive, observed_send)
        finally:
            record = {"method": scope["method"], "path": scope["path"], "status": response_status, "elapsed_s": round(time.monotonic() - start, 3), "request": payload(bytes(request_body), request_size > MAX_BYTES), "response": payload(bytes(response_body), response_size > MAX_BYTES), "request_bytes": request_size, "response_bytes": response_size, "request_sha256": request_hash.hexdigest(), "response_sha256": response_hash.hexdigest(), "provider_mode": self.provider_mode}
            with self.output.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args()
    if "PYTEST_CURRENT_TEST" in os.environ:
        raise SystemExit("Refusing live proof while PYTEST_CURRENT_TEST is present")
    sys.path.insert(0, str(ROOT))
    from scripts.run_local import load_env
    load_env()
    SENSITIVE_VALUES.extend(v for k, v in os.environ.items() if v and k.upper() in {"API_SECRET_KEY", "OPENAI_API_KEY", "JINA_API_KEY", "CREDENTIALS_MASTER_KEY", "WEBHOOK_HMAC_SECRET"})
    if "PYTEST_CURRENT_TEST" in os.environ:
        raise SystemExit("Refusing configured pytest transport in live proof")
    os.chdir(ROOT)
    output_dir = ROOT / "docs/frontend/remediation/evidence"
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{output_dir / 'live-acceptance.db'}"
    from app.main import app
    import uvicorn
    index = ROOT / "frontend/dist/index.html"
    proof = {"pid": os.getpid(), "host": "127.0.0.1", "port": args.port, "pytest_transport_enabled": False, "dependency_overrides": len(app.dependency_overrides), "database": "isolated SQLite; actual configured model and search providers", "app_source_sha256": hashlib.sha256((ROOT / "app/main.py").read_bytes()).hexdigest(), "frontend_index_sha256": hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else None, "model_light": os.environ.get("LLM_MODEL_LIGHT"), "model_strong": os.environ.get("LLM_MODEL_STRONG"), "recorder": "transparent ASGI receive/send observation; headers never captured", "session_auth": "real app mechanism; no injected X-API-Key"}
    (output_dir / "live-runtime-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    uvicorn.run(Recorder(app, output_dir / "live-payloads.jsonl"), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
