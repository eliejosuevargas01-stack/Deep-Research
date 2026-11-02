"""Cliente HTTP assíncrono para inferência com modelos OpenAI-compatible.

Acessa a rota /v1/chat/completions para modelos leve e forte (DT-11, RNF-11).
Implementa política de 1 tentativa inicial + 3 retries com backoff exponencial,
suporte a response_format em JSON estruturado e timeout configurável (RNF-02, RNF-06).

Atende rigorosamente a DR-001, DR-005, DR-013 e DR-014:
- API de envelope imutável e isolada por chamada (sem last_response global).
- finish_reason autêntico sem fallbacks artificiais (nunca finish_reason or 'stop').
- Leitura de usage inclusive em chunks de stream sem choices.
- Erros de SSE/JSON malformado registrados sem transformar fluxo corrompido em sucesso.
- Falha imediata e coerente em HTTP 400/401/403 sem retries desnecessários.
- Preservação estrita de cancelamento (asyncio.CancelledError).
- Segregação absoluta entre content_final e reasoning_content.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
from app.config import get_settings
from app.tools import llm_capture
from app.tools.errors import LLMCallError
from app.tools.llm_types import (
    LLMEnvelope,
    PricingRegistry,
    compute_prompt_hash,
    estimate_cost,
    estimate_cost_detailed,
    redact_sensitive_string,
    sanitize_messages_for_audit,
    sanitize_recursively,
)

RETRIABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

_stream_publish_delta: Any = None


def publish_delta(kind: str, text: str) -> None:
    """Publica delta de streaming no hub SSE (reasoning/content).

    Import tardio: `app.core.__init__` importa planner -> llm_client, então
    importar `app.core.stream_context` no topo criaria ciclo de importação.
    """
    global _stream_publish_delta
    if _stream_publish_delta is None:
        try:
            from app.core.stream_context import publish_delta as _pd
        except Exception:
            _stream_publish_delta = False
            return
        _stream_publish_delta = _pd
    if _stream_publish_delta is False:
        return
    try:
        _stream_publish_delta(kind, text)
    except Exception:
        return


def _llm_error_message(data: Any, client_api_key: Optional[str] = None) -> str:
    """Extrai mensagem legivel do payload de erro do provedor (nunca expoe segredos)."""
    err = (data or {}).get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        msg = err.get("message")
        code = err.get("code") or err.get("type")
        if msg:
            clean = redact_sensitive_string(str(msg), client_api_key=client_api_key)
            return f"LLM recusou a chamada ({code}): {clean}"
    return "LLM retornou payload sem 'choices'."


def _sanitize_json_text(raw: str) -> str:
    """Remove marcadores markdown comuns e vírgulas extras que quebram JSON de LLMs."""
    # 1. Remove marcadores de lista (- , * , + ) antes de chaves, arrays, strings ou literais
    t = re.sub(r'(?m)^(\s*)[-*+]\s+(?=[\"\'{}[\]]|true\b|false\b|null\b)', r'\1', raw)
    # 2. Remove vírgulas sobressalentes antes de fechamento de objeto ou array
    t = re.sub(r',(\s*[}\]])', r'\1', t)
    return t


class LLMClient:
    """Cliente assíncrono para inferência com LLMs compatíveis com OpenAI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_light: Optional[str] = None,
        model_strong: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 1800.0,
        min_backoff: float = 0.01,
        pricing_registry: Optional[PricingRegistry] = None,
    ) -> None:
        settings = get_settings()
        resolved_key = (
            api_key
            or settings.openai_api_key
            or os.environ.get("OPENAI_API_KEY")
        )
        if not resolved_key or not str(resolved_key).strip():
            raise ValueError("Configuração ausente: OPENAI_API_KEY não informada no ambiente.")
        self.api_key = str(resolved_key).strip()
        self.pricing_registry = pricing_registry

        # Modelos padrão gpt-4o-mini e gpt-4o para testes/dev; altere via LLM_MODEL_LIGHT/STRONG
        self.base_url = (
            base_url
            or settings.llm_base_url
            or os.environ.get("LLM_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")

        self.model_light = (
            model_light
            or settings.llm_model_light
            or os.environ.get("LLM_MODEL_LIGHT")
            or "gpt-4o-mini"
        )

        self.model_strong = (
            model_strong
            or settings.llm_model_strong
            or os.environ.get("LLM_MODEL_STRONG")
            or "gpt-4o"
        )

        env_timeout = os.environ.get("LLM_TIMEOUT")
        self.timeout = float(env_timeout) if env_timeout else timeout
        if "PYTEST_CURRENT_TEST" in os.environ:
            self.min_backoff = min_backoff
        else:
            self.min_backoff = 2.0 if min_backoff <= 0.05 else min_backoff
        self.transport = transport
        self._client = client or httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(self.timeout),
        )

    def __repr__(self) -> str:
        return (
            f"LLMClient(api_key='[REDACTED]', base_url='{self.base_url}', "
            f"model_light='{self.model_light}', model_strong='{self.model_strong}')"
        )

    async def aclose(self) -> None:
        """Encerra a sessão HTTP subjacente."""
        await self._client.aclose()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def call_envelope(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMEnvelope:
        """Captura entrada/saída JSON de cada chamada e delega à implementação."""
        request = {
            "model": model,
            "base_url": self.base_url,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "response_format": response_format,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "params": kwargs,
        }
        try:
            envelope = await self._call_envelope_impl(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                **kwargs,
            )
        except BaseException as exc:
            llm_capture.record(
                "error",
                request=request,
                envelope=getattr(exc, "envelope", None),
                error=str(exc),
            )
            raise
        llm_capture.record("ok", request=request, envelope=envelope)
        return envelope

    async def _call_envelope_impl(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMEnvelope:
        """Executa chamada ao LLM e retorna envelope imutável e completo (DR-005, DR-013).
        
        Garante ausência de estado global compartilhado e registra todas as métricas observáveis.
        """
        endpoint = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )

        # Metadados de auditoria do prompt emitido pela aplicação
        system_msg: Optional[str] = None
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "system":
                system_msg = str(m.get("content") or "")
                break
        system_msg_sanitized = redact_sensitive_string(system_msg, client_api_key=self.api_key) if system_msg else None

        stream_mode = (
            bool(kwargs.get("stream", True))
            and getattr(self, "transport", None) is None
        )

        reasoning_effort = kwargs.pop("reasoning_effort", None) or os.environ.get("LLM_REASONING_EFFORT", "high")

        # Constrói o payload final real efetivamente enviado pela rede (R2-F09)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream_mode,
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        payload.update(kwargs)

        if stream_mode:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
        else:
            payload["stream"] = False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Constrói request_params a partir do payload final enviado (menos messages e segredos) (R2-F09)
        request_params = {k: v for k, v in payload.items() if k != "messages"}
        sanitized_request_params = sanitize_recursively(request_params, client_api_key=self.api_key)
        prompt_hash = compute_prompt_hash(messages, request_params=sanitized_request_params)
        messages_sent = sanitize_messages_for_audit(messages, client_api_key=self.api_key)

        errors_log: List[Dict[str, Any]] = []
        max_attempts = 4
        start_time = time.perf_counter()

        for attempt in range(1, max_attempts + 1):
            try:
                if stream_mode:
                    finish_reason: Optional[str] = None
                    chunks: List[str] = []
                    reasoning_chunks: List[str] = []
                    role: str = "assistant"
                    tool_calls_acc: Dict[int, Dict[str, Any]] = {}
                    usage_data: Optional[Dict[str, Any]] = None
                    model_used: Optional[str] = None
                    has_malformed_chunk = False
                    has_error_chunk = False

                    async with self._client.stream(
                        "POST",
                        endpoint,
                        json=payload,
                        headers=headers,
                    ) as res:
                        if res.status_code >= 400:
                            body_bytes = await res.aread()
                            err_body = redact_sensitive_string(
                                body_bytes.decode("utf-8", errors="replace"),
                                client_api_key=self.api_key,
                            )
                            clean_msg = err_body.strip() or f"HTTPStatusError {res.status_code}"
                            errors_log.append({
                                "attempt": attempt,
                                "error_type": "HTTPStatusError",
                                "status_code": res.status_code,
                                "message": clean_msg,
                            })
                            if res.status_code not in RETRIABLE_STATUS_CODES or attempt == max_attempts:
                                cost, curr, src = estimate_cost_detailed(
                                    model,
                                    None,
                                    pricing_registry=self.pricing_registry,
                                )
                                failed_envelope = LLMEnvelope(
                                    content_final=None,
                                    reasoning_content=None,
                                    finish_reason="error",
                                    is_regular_finish=False,
                                    model_requested=model,
                                    model_used=None,
                                    usage=None,
                                    cost_estimated=cost,
                                    cost_currency=curr,
                                    cost_source=src,
                                    latency_seconds=round(time.perf_counter() - start_time, 4),
                                    attempts=attempt,
                                    request_params=sanitized_request_params,
                                    errors=errors_log,
                                    prompt_id=prompt_id,
                                    prompt_version=prompt_version,
                                    prompt_hash=prompt_hash,
                                    system_message_sent=system_msg_sanitized,
                                    messages_sent=messages_sent,
                                )
                                raise LLMCallError(clean_msg, envelope=failed_envelope, status_code=res.status_code)
                            backoff = self.min_backoff * (2 ** (attempt - 1))
                            if backoff > 0:
                                await asyncio.sleep(backoff)
                            continue

                        async for line in res.aiter_lines():
                            line = line.strip()
                            if not line or line in ("data: [DONE]", "data:[DONE]"):
                                continue
                            if line.startswith(":") or line.startswith("event:") or line.startswith("id:") or line.startswith("retry:"):
                                continue
                            if line.startswith("data:"):
                                line_data = line[5:].strip()
                                try:
                                    chunk_json = json.loads(line_data)
                                except json.JSONDecodeError as jde:
                                    has_malformed_chunk = True
                                    clean_err = redact_sensitive_string(
                                        f"SSE chunk inválido: {str(jde)}",
                                        client_api_key=self.api_key,
                                    )
                                    errors_log.append({
                                        "attempt": attempt,
                                        "error_type": "MalformedSSEChunk",
                                        "message": clean_err,
                                    })
                                    continue

                                if not isinstance(chunk_json, dict):
                                    has_malformed_chunk = True
                                    errors_log.append({
                                        "attempt": attempt,
                                        "error_type": "MalformedSSEChunk",
                                        "message": f"SSE chunk não é dict: {type(chunk_json).__name__}",
                                    })
                                    continue

                                if chunk_json.get("error"):
                                    has_error_chunk = True
                                    err_payload = chunk_json.get("error")
                                    clean_err = redact_sensitive_string(
                                        str(err_payload),
                                        client_api_key=self.api_key,
                                    )
                                    errors_log.append({
                                        "attempt": attempt,
                                        "error_type": "StreamErrorChunk",
                                        "message": clean_err,
                                    })

                                if chunk_json.get("model") and not model_used:
                                    model_used = str(chunk_json["model"])
                                if "usage" in chunk_json:
                                    raw_u = chunk_json.get("usage")
                                    if isinstance(raw_u, dict):
                                        usage_data = raw_u
                                    elif raw_u is not None:
                                        has_malformed_chunk = True
                                        errors_log.append({
                                            "attempt": attempt,
                                            "error_type": "MalformedSSEUsage",
                                            "message": f"Usage em chunk SSE não é um objeto dict ({type(raw_u).__name__})",
                                        })

                                choices = chunk_json.get("choices") or []
                                if choices and isinstance(choices, list) and len(choices) > 0:
                                    choice0 = choices[0]
                                    if isinstance(choice0, dict):
                                        if choice0.get("finish_reason"):
                                            finish_reason = choice0.get("finish_reason")
                                        delta = choice0.get("delta")
                                        if isinstance(delta, dict):
                                            if delta.get("finish_reason"):
                                                finish_reason = delta.get("finish_reason")
                                            if delta.get("role"):
                                                role = delta["role"]
                                            if delta.get("reasoning_content"):
                                                _delta_reasoning = str(delta["reasoning_content"])
                                                reasoning_chunks.append(_delta_reasoning)
                                                publish_delta("reasoning", _delta_reasoning)
                                            if delta.get("content"):
                                                _delta_content = str(delta["content"])
                                                chunks.append(_delta_content)
                                                publish_delta("content", _delta_content)
                                            if delta.get("tool_calls"):
                                                for tc in delta["tool_calls"]:
                                                    if not isinstance(tc, dict):
                                                        continue
                                                    idx = tc.get("index", 0)
                                                    if idx not in tool_calls_acc:
                                                        tool_calls_acc[idx] = {
                                                            "id": tc.get("id", f"call_{idx}"),
                                                            "type": tc.get("type", "function"),
                                                            "function": {"name": "", "arguments": ""},
                                                        }
                                                    if tc.get("id"):
                                                        tool_calls_acc[idx]["id"] = tc["id"]
                                                    fn_delta = tc.get("function") or {}
                                                    if isinstance(fn_delta, dict):
                                                        if fn_delta.get("name"):
                                                            tool_calls_acc[idx]["function"]["name"] += str(fn_delta["name"])
                                                        if fn_delta.get("arguments"):
                                                            tool_calls_acc[idx]["function"]["arguments"] += str(fn_delta["arguments"])
                            else:
                                # Linha SSE não reconhecida
                                has_malformed_chunk = True
                                errors_log.append({
                                    "attempt": attempt,
                                    "error_type": "UnrecognizedSSELine",
                                    "message": redact_sensitive_string(f"Linha SSE não reconhecida: {line[:100]}", client_api_key=self.api_key),
                                })

                    final_content = "".join(chunks) if chunks else None
                    final_reasoning = "".join(reasoning_chunks) if reasoning_chunks else None
                    final_tool_calls = list(tool_calls_acc.values()) if tool_calls_acc else None

                    # DR-005: Término regular exige finish_reason confiável e ausência de corrupção ou erro SSE
                    is_regular = bool(
                        finish_reason in ("stop", "tool_calls")
                        and not has_malformed_chunk
                        and not has_error_chunk
                    )

                    latency = time.perf_counter() - start_time
                    cost, curr, src = estimate_cost_detailed(
                        model_used or model,
                        usage_data,
                        pricing_registry=self.pricing_registry,
                    )

                    final_content_sanitized = redact_sensitive_string(final_content, client_api_key=self.api_key) if final_content else None
                    final_reasoning_sanitized = redact_sensitive_string(final_reasoning, client_api_key=self.api_key) if final_reasoning else None
                    final_tools_sanitized = sanitize_recursively(final_tool_calls, client_api_key=self.api_key) if final_tool_calls else None

                    envelope = LLMEnvelope(
                        content_final=final_content_sanitized,
                        reasoning_content=final_reasoning_sanitized,
                        finish_reason=finish_reason,  # Autêntico: nunca fabricado
                        is_regular_finish=is_regular,
                        model_requested=model,
                        model_used=model_used,
                        usage=usage_data,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(latency, 4),
                        attempts=attempt,
                        request_params=sanitized_request_params,
                        errors=errors_log,
                        tool_calls=final_tools_sanitized,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    return envelope

                # Modo sem streaming
                res = await self._client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )
                if res.status_code >= 400:
                    err_body = redact_sensitive_string(res.text, client_api_key=self.api_key)
                    clean_msg = err_body.strip() or f"HTTPStatusError {res.status_code}"
                    errors_log.append({
                        "attempt": attempt,
                        "error_type": "HTTPStatusError",
                        "status_code": res.status_code,
                        "message": clean_msg,
                    })
                    if res.status_code not in RETRIABLE_STATUS_CODES or attempt == max_attempts:
                        cost, curr, src = estimate_cost_detailed(
                            model,
                            None,
                            pricing_registry=self.pricing_registry,
                        )
                        failed_envelope = LLMEnvelope(
                            content_final=None,
                            reasoning_content=None,
                            finish_reason="error",
                            is_regular_finish=False,
                            model_requested=model,
                            model_used=None,
                            usage=None,
                            cost_estimated=cost,
                            cost_currency=curr,
                            cost_source=src,
                            latency_seconds=round(time.perf_counter() - start_time, 4),
                            attempts=attempt,
                            errors=errors_log,
                            request_params=sanitized_request_params,
                            prompt_id=prompt_id,
                            prompt_version=prompt_version,
                            prompt_hash=prompt_hash,
                            system_message_sent=system_msg_sanitized,
                            messages_sent=messages_sent,
                        )
                        raise LLMCallError(clean_msg, envelope=failed_envelope, status_code=res.status_code)
                    backoff = self.min_backoff * (2 ** (attempt - 1))
                    if backoff > 0:
                        await asyncio.sleep(backoff)
                    continue

                raw_text = res.text.strip()
                if raw_text.endswith("data: [DONE]"):
                    raw_text = raw_text[:-12].strip()
                elif raw_text.endswith("data:[DONE]"):
                    raw_text = raw_text[:-11].strip()
                try:
                    data = json.loads(raw_text) if raw_text else {}
                except Exception:
                    try:
                        data = res.json()
                    except Exception:
                        data = None

                if not isinstance(data, dict):
                    err_msg = redact_sensitive_string(
                        f"Resposta JSON do modelo inválida: {type(data).__name__}",
                        client_api_key=self.api_key,
                    )
                    errors_log.append({
                        "attempt": attempt,
                        "error_type": "InvalidPayload",
                        "message": err_msg,
                    })
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=None,
                        usage=None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        errors=errors_log,
                        request_params=sanitized_request_params,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    raise LLMCallError(err_msg, envelope=failed_envelope)

                choices = data.get("choices")
                if not isinstance(choices, list) or len(choices) == 0:
                    err_msg = _llm_error_message(data, client_api_key=self.api_key)
                    clean_err = redact_sensitive_string(err_msg, client_api_key=self.api_key)
                    errors_log.append({
                        "attempt": attempt,
                        "error_type": "InvalidPayload",
                        "message": clean_err,
                    })
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        data.get("usage") if isinstance(data.get("usage"), dict) else None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=str(data.get("model")) if (data and data.get("model")) else None,
                        usage=data.get("usage") if (data and isinstance(data.get("usage"), dict)) else None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        errors=errors_log,
                        request_params=sanitized_request_params,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    raise LLMCallError(clean_err, envelope=failed_envelope)

                if not isinstance(choices, list) or len(choices) == 0:
                    clean_err = "Resposta da API não contém lista 'choices' válida."
                    errors_log.append({
                        "attempt": attempt,
                        "error_type": "InvalidPayload",
                        "message": clean_err,
                    })
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        data.get("usage") if isinstance(data.get("usage"), dict) else None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=str(data.get("model")) if (data and data.get("model")) else None,
                        usage=data.get("usage") if (data and isinstance(data.get("usage"), dict)) else None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        errors=errors_log,
                        request_params=sanitized_request_params,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    raise LLMCallError(clean_err, envelope=failed_envelope)

                first = choices[0]
                if not isinstance(first, dict):
                    clean_err = f"Primeiro item de choices não é um dict ({type(first).__name__})."
                    errors_log.append({
                        "attempt": attempt,
                        "error_type": "InvalidPayload",
                        "message": clean_err,
                    })
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        data.get("usage") if isinstance(data.get("usage"), dict) else None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=str(data.get("model")) if (data and data.get("model")) else None,
                        usage=data.get("usage") if (data and isinstance(data.get("usage"), dict)) else None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        errors=errors_log,
                        request_params=sanitized_request_params,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    raise LLMCallError(clean_err, envelope=failed_envelope)

                msg = first.get("message")
                if not isinstance(msg, dict):
                    clean_err = f"Campo 'message' de choices[0] não é um dict ({type(msg).__name__ if msg is not None else 'None'})."
                    errors_log.append({
                        "attempt": attempt,
                        "error_type": "InvalidPayload",
                        "message": clean_err,
                    })
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        data.get("usage") if isinstance(data.get("usage"), dict) else None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=str(data.get("model")) if (data and data.get("model")) else None,
                        usage=data.get("usage") if (data and isinstance(data.get("usage"), dict)) else None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        errors=errors_log,
                        request_params=sanitized_request_params,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    raise LLMCallError(clean_err, envelope=failed_envelope)

                finish_reason = first.get("finish_reason")
                usage_raw = data.get("usage") if isinstance(data, dict) else None
                usage_data = usage_raw if isinstance(usage_raw, dict) else None
                model_used = data.get("model") if isinstance(data, dict) else None

                content = msg.get("content")
                reasoning = msg.get("reasoning_content")
                tool_calls = msg.get("tool_calls")

                is_regular = bool(finish_reason in ("stop", "tool_calls"))
                latency = time.perf_counter() - start_time
                cost, curr, src = estimate_cost_detailed(
                    model_used or model,
                    usage_data,
                    pricing_registry=self.pricing_registry,
                )

                content_sanitized = redact_sensitive_string(str(content), client_api_key=self.api_key) if content is not None else None
                reasoning_sanitized = redact_sensitive_string(str(reasoning), client_api_key=self.api_key) if reasoning is not None else None
                tool_calls_sanitized = sanitize_recursively(tool_calls, client_api_key=self.api_key) if isinstance(tool_calls, list) else None

                envelope = LLMEnvelope(
                    content_final=content_sanitized,
                    reasoning_content=reasoning_sanitized,
                    finish_reason=finish_reason,  # Autêntico: nunca fabricado
                    is_regular_finish=is_regular,
                    model_requested=model,
                    model_used=str(model_used) if model_used else None,
                    usage=usage_data if isinstance(usage_data, dict) else None,
                    cost_estimated=cost,
                    cost_currency=curr,
                    cost_source=src,
                    latency_seconds=round(latency, 4),
                    attempts=attempt,
                    request_params=sanitized_request_params,
                    errors=errors_log,
                    tool_calls=tool_calls_sanitized,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    prompt_hash=prompt_hash,
                    system_message_sent=system_msg_sanitized,
                    messages_sent=messages_sent,
                )
                return envelope

            except asyncio.CancelledError:
                # DR-005: Preservar cancelamento estrito de tarefas assíncronas
                raise

            except httpx.HTTPStatusError as hse:
                status_code = hse.response.status_code
                clean_msg = redact_sensitive_string(str(hse), client_api_key=self.api_key)
                errors_log.append({
                    "attempt": attempt,
                    "error_type": "HTTPStatusError",
                    "status_code": status_code,
                    "message": clean_msg,
                })
                if status_code not in RETRIABLE_STATUS_CODES or attempt == max_attempts:
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        usage_data if "usage_data" in locals() and usage_data else None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=model_used if "model_used" in locals() and model_used else None,
                        usage=usage_data if "usage_data" in locals() and usage_data else None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        request_params=sanitized_request_params,
                        errors=errors_log,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    setattr(hse, "envelope", failed_envelope)
                    raise LLMCallError(clean_msg, envelope=failed_envelope, status_code=status_code) from hse
                backoff = self.min_backoff * (2 ** (attempt - 1))
                if backoff > 0:
                    await asyncio.sleep(backoff)

            except (httpx.TransportError, json.JSONDecodeError) as exc:
                clean_msg = redact_sensitive_string(str(exc), client_api_key=self.api_key)
                errors_log.append({
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "message": clean_msg,
                })
                if attempt == max_attempts:
                    cost, curr, src = estimate_cost_detailed(
                        model,
                        usage_data if "usage_data" in locals() and usage_data else None,
                        pricing_registry=self.pricing_registry,
                    )
                    failed_envelope = LLMEnvelope(
                        content_final=None,
                        reasoning_content=None,
                        finish_reason="error",
                        is_regular_finish=False,
                        model_requested=model,
                        model_used=model_used if "model_used" in locals() and model_used else None,
                        usage=usage_data if "usage_data" in locals() and usage_data else None,
                        cost_estimated=cost,
                        cost_currency=curr,
                        cost_source=src,
                        latency_seconds=round(time.perf_counter() - start_time, 4),
                        attempts=attempt,
                        request_params=sanitized_request_params,
                        errors=errors_log,
                        prompt_id=prompt_id,
                        prompt_version=prompt_version,
                        prompt_hash=prompt_hash,
                        system_message_sent=system_msg_sanitized,
                        messages_sent=messages_sent,
                    )
                    setattr(exc, "envelope", failed_envelope)
                    raise LLMCallError(clean_msg, envelope=failed_envelope) from exc
                backoff = self.min_backoff * (2 ** (attempt - 1))
                if backoff > 0:
                    await asyncio.sleep(backoff)

        raise RuntimeError("Falha inesperada na chamada do modelo de linguagem.")

    async def chat_completion_message(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Projeção de compatibilidade retornando o dicionário message (DR-001, DR-005)."""
        envelope = await self.call_envelope(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            **kwargs,
        )

        msg_res: Dict[str, Any] = {
            "role": "assistant",
            "content": envelope.content_final,
            "reasoning_content": envelope.reasoning_content,
            "finish_reason": envelope.finish_reason,  # Autêntico, sem fabricar "stop"
        }
        if envelope.tool_calls:
            msg_res["tool_calls"] = envelope.tool_calls
        if envelope.usage:
            msg_res["usage"] = envelope.usage
        if envelope.model_used:
            msg_res["model_used"] = envelope.model_used
        msg_res["_envelope"] = envelope

        return msg_res

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Envia requisição POST para a rota /chat/completions.

        DR-001: Nunca utiliza reasoning_content como fallback para content.
        """
        envelope = await self.call_envelope(
            model=model,
            messages=messages,
            response_format=response_format,
            **kwargs,
        )
        if envelope.content_final is None:
            return ""
        return str(envelope.content_final)

    async def chat_completion_with_reasoning(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str]]:
        """Executa inferência e retorna tupla (conteúdo_final, reasoning_content)."""
        envelope = await self.call_envelope(
            model=model,
            messages=messages,
            response_format=response_format,
            **kwargs,
        )
        content = envelope.content_final or ""
        reasoning = envelope.reasoning_content
        return str(content), str(reasoning) if reasoning else None

    async def generate_light(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Executa inferência com o modelo leve configurado."""
        return await self.chat_completion(
            model=self.model_light,
            messages=messages,
            response_format=response_format,
            **kwargs,
        )

    async def generate_strong(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Executa inferência com o modelo forte configurado."""
        return await self.chat_completion(
            model=self.model_strong,
            messages=messages,
            response_format=response_format,
            **kwargs,
        )

    async def generate_json(
        self,
        model_type: str = "light",
        messages: Optional[List[Dict[str, Any]]] = None,
        return_reasoning: bool = False,
        return_envelope: bool = False,
        **kwargs: Any,
    ) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Optional[str]], Tuple[Dict[str, Any], LLMEnvelope]]:
        """Executa inferência com response_format={'type': 'json_object'} e retorna dict parseado.
        
        DR-001/DR-005:
        - Valida a saída estritamente a partir de content_final, nunca de reasoning_content.
        - Registra tentativas de reparo estrutural se markdown fences precisarem de extração.
        """
        model = self.model_light if model_type == "light" else self.model_strong
        envelope = await self.call_envelope(
            model=model,
            messages=messages or [],
            response_format={"type": "json_object"},
            **kwargs,
        )

        content = envelope.content_final
        if content is None or not str(content).strip():
            # Diagnóstico acionável: finish_reason e tokens explicam se o
            # provedor filtrou/bloqueou ou se a resposta veio vazia.
            motivo = getattr(envelope, "finish_reason", None) or "desconhecido"
            uso = getattr(envelope, "usage", None) or {}
            pt = uso.get("prompt_tokens") if isinstance(uso, dict) else None
            ct = uso.get("completion_tokens") if isinstance(uso, dict) else None
            detalhe = f"finish_reason={motivo}"
            if pt is not None or ct is not None:
                detalhe += f", prompt_tokens={pt}, completion_tokens={ct}"
            if motivo == "content_filter":
                detalhe += " — o provedor bloqueou a resposta antes de gerar conteúdo"
            raise LLMCallError(
                f"Modelo não emitiu conteúdo final ('content') para validação de JSON ({detalhe}).",
                envelope=envelope,
            )

        text = str(content).strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if "```" in text:
            text = text.split("```")[0]
        text = text.strip()

        parsed: Dict[str, Any] = {}
        last_json_err: Optional[Exception] = None
        for attempt_parse in range(2):
            try:
                parsed = json.loads(text)
                break
            except json.JSONDecodeError as jde:
                last_json_err = jde
                start = text.find("{")
                end = text.rfind("}")
                candidate = text[start : end + 1] if (start != -1 and end != -1 and end > start) else text
                if candidate != text:
                    try:
                        parsed = json.loads(candidate)
                        break
                    except json.JSONDecodeError:
                        pass
                sanitized = _sanitize_json_text(candidate)
                try:
                    parsed = json.loads(sanitized)
                    break
                except json.JSONDecodeError:
                    pass
                if attempt_parse == 0:
                    first_envelope = envelope
                    # Se falhou via stream por corte prematuro, tenta uma vez sem stream
                    try:
                        envelope = await self.call_envelope(
                            model=model,
                            messages=messages or [],
                            response_format={"type": "json_object"},
                            stream=False,
                            **kwargs,
                        )
                    except (Exception, asyncio.CancelledError) as second_call_exc:
                        if hasattr(second_call_exc, "envelope") and second_call_exc.envelope:
                            from dataclasses import replace
                            prior = list(getattr(second_call_exc.envelope, "prior_envelopes", None) or [])
                            if first_envelope not in prior:
                                second_call_exc.envelope = replace(
                                    second_call_exc.envelope,
                                    prior_envelopes=[first_envelope] + prior,
                                )
                        elif hasattr(second_call_exc, "envelopes"):
                            existing = list(second_call_exc.envelopes or [])
                            if first_envelope not in existing:
                                second_call_exc.envelopes = [first_envelope] + existing
                        else:
                            setattr(second_call_exc, "envelopes", [first_envelope])
                        raise
                    from dataclasses import replace
                    envelope = replace(envelope, prior_envelopes=[first_envelope])
                    content = envelope.content_final
                    if content is None or not str(content).strip():
                        raise LLMCallError(
                            "Modelo não emitiu conteúdo final na retentativa de JSON.",
                            envelope=envelope,
                        )
                    text = str(content).strip()
                    if text.startswith("```json"):
                        text = text[7:]
                    elif text.startswith("```"):
                        text = text[3:]
                    if "```" in text:
                        text = text.split("```")[0]
                    text = text.strip()
                else:
                    raise LLMCallError(
                        f"Falha ao decodificar JSON retornado pelo modelo: {last_json_err}",
                        envelope=envelope,
                    )

        if return_envelope:
            return parsed, envelope
        if return_reasoning:
            return parsed, envelope.reasoning_content
        return parsed

    async def generate_json_envelope(
        self,
        model_type: str = "light",
        messages: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Tuple[Dict[str, Any], LLMEnvelope]:
        """Atalho conveniente que retorna o dicionário parseado e o envelope da chamada."""
        res = await self.generate_json(
            model_type=model_type,
            messages=messages,
            return_envelope=True,
            **kwargs,
        )
        return res  # type: ignore[return-value]
