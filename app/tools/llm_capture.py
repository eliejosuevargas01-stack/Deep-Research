"""Captura de entrada/saída JSON de todas as chamadas a modelos.

Ativado por ambiente (nada é gravado se `DR_LLM_CAPTURE_DIR` estiver vazio):

    DR_LLM_CAPTURE_DIR=/app/data/llm-capture

Cada chamada gera um arquivo `{epoch_ms}_{seq}_{modelo}.json` com:

    {
      "captured_at": "2026-11-02T12:00:00.123-03:00",
      "status": "ok" | "error",
      "request": {"model": ..., "messages": [...], "tools": ..., "params": {...}},
      "response": {"content_final": ..., "reasoning_content": ..., "usage": ...,
                    "finish_reason": ..., "attempts": ..., "errors": [...]},
      "error": "..."            # apenas em status=error
    }

O envelope é o objeto `LLMEnvelope` já sanitizado pelo cliente (segredos
redigidos), então a captura não expõe API keys.
"""

from __future__ import annotations

import itertools
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_LOCK = threading.Lock()
_SEQ = itertools.count(1)


def capture_dir() -> Optional[str]:
    """Diretório de captura ou None quando desativado."""
    raw = (os.environ.get("DR_LLM_CAPTURE_DIR") or "").strip()
    return raw or None


def _serializable(value: Any) -> Any:
    """Converte objetos do domínio (envelopes) em JSON puro."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _serializable(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return _serializable(
            {k: v for k, v in vars(value).items() if not k.startswith("_")}
        )
    return str(value)


def record(
    status: str,
    *,
    request: Dict[str, Any],
    envelope: Any = None,
    error: Any = None,
) -> None:
    """Grava uma chamada de modelo; nunca levanta (captura não pode quebrar a pesquisa)."""
    directory = capture_dir()
    if directory is None:
        return
    try:
        os.makedirs(directory, exist_ok=True)
        model = str(request.get("model") or "model").replace("/", "_").replace(":", "_")
        with _LOCK:
            seq = next(_SEQ)
        stamp = int(time.time() * 1000)
        payload = {
            "captured_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "status": status,
            "request": _serializable(request),
            "response": _serializable(envelope),
        }
        if error is not None:
            payload["error"] = _serializable(error)
        name = f"{stamp}_{seq:05d}_{model}.json"
        final_path = os.path.join(directory, name)
        tmp_path = os.path.join(directory, f".{name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, final_path)
    except Exception:
        # Diagnóstico nunca deve interromper a execução da pesquisa.
        return


def report(directory: str, *, limit: int = 20) -> Dict[str, Any]:
    """Resumo das capturas: total, por status, por modelo e tokens somados."""
    files = sorted(
        f for f in os.listdir(directory) if f.endswith(".json") and not f.startswith(".")
    )
    by_status: Dict[str, int] = {}
    by_model: Dict[str, int] = {}
    tokens = {"prompt": 0, "completion": 0}
    for name in files:
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        status = str(data.get("status") or "?")
        by_status[status] = by_status.get(status, 0) + 1
        model = str((data.get("request") or {}).get("model") or "?")
        by_model[model] = by_model.get(model, 0) + 1
        usage = ((data.get("response") or {}).get("usage")) or {}
        if isinstance(usage, dict):
            tokens["prompt"] += int(usage.get("prompt_tokens") or 0)
            tokens["completion"] += int(usage.get("completion_tokens") or 0)
    return {
        "directory": directory,
        "total": len(files),
        "by_status": by_status,
        "by_model": by_model,
        "tokens": tokens,
        "files": files[-limit:],
    }
