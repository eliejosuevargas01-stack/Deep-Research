# -*- coding: utf-8 -*-
"""Auxiliares e fixtures dedicadas para os testes do Gate 1 (Reprodução/Regressão).

Isolamento completo: não modifica conftest.py nem os mocks preexistentes.
"""
from typing import Any, Callable, Dict, List, Optional
import json
import httpx


def make_llm_json_response(payload_dict: Any, reasoning: Optional[str] = None, finish_reason: str = "stop") -> httpx.Response:
    """Cria resposta HTTP 200 formatada para /chat/completions retornando JSON serializado."""
    content_str = json.dumps(payload_dict, ensure_ascii=False) if not isinstance(payload_dict, str) else payload_dict
    msg = {
        "role": "assistant",
        "content": content_str,
    }
    if reasoning is not None:
        msg["reasoning_content"] = reasoning

    data = {
        "id": "chatcmpl-gate1-mock",
        "object": "chat.completion",
        "created": 1729720000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": msg,
                "finish_reason": finish_reason,
            }
        ],
    }
    return httpx.Response(200, json=data)


def make_llm_raw_response(
    content: Optional[str] = None,
    reasoning: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    finish_reason: str = "stop",
) -> httpx.Response:
    """Cria resposta HTTP 200 formatada para /chat/completions com campos específicos."""
    msg: Dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls

    data = {
        "id": "chatcmpl-gate1-raw",
        "object": "chat.completion",
        "created": 1729720000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": msg,
                "finish_reason": finish_reason,
            }
        ],
    }
    return httpx.Response(200, json=data)


def make_serp_response(items: List[Dict[str, Any]]) -> httpx.Response:
    """Cria resposta HTTP 200 formatada para o Jina SERP (s.jina.ai)."""
    return httpx.Response(200, json={"code": 200, "data": items})
