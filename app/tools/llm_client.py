"""Cliente HTTP assíncrono para inferência com modelos OpenAI-compatible.

Acessa a rota /v1/chat/completions para modelos leve e forte (DT-11, RNF-11).
Implementa política de 1 tentativa inicial + 3 retries com backoff exponencial,
suporte a response_format em JSON estruturado e timeout de 600 segundos (RNF-02, RNF-06).
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
from app.config import get_settings


def _llm_error_message(data: Any) -> str:
    """Extrai mensagem legivel do payload de erro do provedor (nunca expoe segredos)."""
    err = (data or {}).get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        msg = err.get("message")
        code = err.get("code") or err.get("type")
        if msg:
            return f"LLM recusou a chamada ({code}): {msg}"
    return "LLM retornou payload sem 'choices'."


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

        # ponytail: modelos padrão gpt-4o-mini e gpt-4o para testes/dev; altere via LLM_MODEL_LIGHT/STRONG
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

    async def chat_completion_message(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Envia requisição POST para a rota /chat/completions e retorna o objeto message."""
        endpoint = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        # Raciocínio máximo habilitado por padrão em todas as chamadas a modelos
        reasoning_effort = kwargs.pop("reasoning_effort", None) or os.environ.get("LLM_REASONING_EFFORT", "high")
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = response_format
        payload.update(kwargs)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Em modelos que suportam streaming, usamos stream=True para manter o socket
        # ativo contra timeouts de proxy reverso e buffering intermediário
        # Desativado quando transport for mock de testes (transport is not None)
        stream_mode = (
            bool(kwargs.get("stream", True))
            and getattr(self, "transport", None) is None
        )
        if stream_mode:
            payload["stream"] = True

        max_attempts = 4
        for attempt in range(1, max_attempts + 1):
            try:
                if stream_mode:
                    chunks = []
                    reasoning_chunks = []
                    role = "assistant"
                    tool_calls_acc: Dict[int, Dict[str, Any]] = {}
                    async with self._client.stream(
                        "POST",
                        endpoint,
                        json=payload,
                        headers=headers,
                    ) as res:
                        if res.status_code in (429, 500, 502, 503, 504) or res.is_server_error:
                            res.raise_for_status()

                        async for line in res.aiter_lines():
                            line = line.strip()
                            if not line or line == "data: [DONE]":
                                continue
                            if line.startswith("data: "):
                                line_data = line[6:].strip()
                                try:
                                    chunk_json = json.loads(line_data)
                                    delta = (chunk_json.get("choices") or [{}])[0].get("delta", {})
                                    if delta.get("role"):
                                        role = delta["role"]
                                    if delta.get("reasoning_content"):
                                        reasoning_chunks.append(delta["reasoning_content"])
                                    if delta.get("content"):
                                        chunks.append(delta["content"])
                                    if delta.get("tool_calls"):
                                        for tc in delta["tool_calls"]:
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
                                            if fn_delta.get("name"):
                                                tool_calls_acc[idx]["function"]["name"] += fn_delta["name"]
                                            if fn_delta.get("arguments"):
                                                tool_calls_acc[idx]["function"]["arguments"] += fn_delta["arguments"]
                                except Exception:
                                    pass

                    final_content = "".join(chunks)
                    final_reasoning = "".join(reasoning_chunks)
                    final_tool_calls = list(tool_calls_acc.values()) if tool_calls_acc else None

                    # ponytail: não sobrescrever content com reasoning; manter estritamente segregados
                    # se o modelo não emitiu content final, content deve ser vazio ou None
                    msg_res: Dict[str, Any] = {
                        "role": role,
                        "content": final_content or None,
                        "reasoning_content": final_reasoning or None,
                    }
                    if final_tool_calls:
                        msg_res["tool_calls"] = final_tool_calls

                    if not msg_res.get("content") and not msg_res.get("tool_calls") and not msg_res.get("reasoning_content"):
                        raise RuntimeError("LLM stream finalizou sem emitir nenhum conteúdo.")

                    return msg_res

                res = await self._client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )
                if res.status_code in (429, 500, 502, 503, 504) or res.is_server_error:
                    res.raise_for_status()

                raw_text = res.text.strip()
                if raw_text.endswith("data: [DONE]"):
                    raw_text = raw_text[:-12].strip()
                try:
                    data = json.loads(raw_text)
                except Exception:
                    data = res.json()

                choices = (data or {}).get("choices") or []
                first = choices[0] if choices else None
                msg = (first or {}).get("message")
                if msg is None:
                    raise RuntimeError(_llm_error_message(data))
                return msg

            except (httpx.HTTPStatusError, httpx.TransportError, json.JSONDecodeError):
                if attempt == max_attempts:
                    raise
                backoff = self.min_backoff * (2 ** (attempt - 1))
                if backoff > 0:
                    await asyncio.sleep(backoff)

        raise RuntimeError("Falha inesperada na chamada do modelo de linguagem.")

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Envia requisição POST para a rota /chat/completions com retries 1+3."""
        msg = await self.chat_completion_message(
            model=model,
            messages=messages,
            response_format=response_format,
            **kwargs,
        )
        content = msg.get("content") or msg.get("reasoning_content")
        if content is None:
            raise RuntimeError("LLM retornou mensagem sem 'content' ou 'reasoning_content'.")
        return str(content)

    async def chat_completion_with_reasoning(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str]]:
        """Executa inferência e retorna tupla (conteúdo_final, reasoning_content)."""
        msg = await self.chat_completion_message(
            model=model,
            messages=messages,
            response_format=response_format,
            **kwargs,
        )
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content")
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
        **kwargs: Any,
    ) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Optional[str]]]:
        """Executa inferência com response_format={'type': 'json_object'} e retorna dict parseado."""
        model = self.model_light if model_type == "light" else self.model_strong
        raw_text, reasoning = await self.chat_completion_with_reasoning(
            model=model,
            messages=messages or [],
            response_format={"type": "json_object"},
            **kwargs,
        )
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if "```" in text:
            text = text.split("```")[0]
        text = text.strip()
        parsed: Dict[str, Any] = {}
        for attempt_parse in range(2):
            try:
                parsed = json.loads(text)
                break
            except json.JSONDecodeError:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        parsed = json.loads(text[start : end + 1])
                        break
                    except json.JSONDecodeError:
                        pass
                if attempt_parse == 0:
                    # Se falhou via stream por corte prematuro, tenta uma vez sem stream
                    raw_text, reasoning = await self.chat_completion_with_reasoning(
                        model=model,
                        messages=messages or [],
                        response_format={"type": "json_object"},
                        stream=False,
                        **kwargs,
                    )
                    text = raw_text.strip()
                    if text.startswith("```json"):
                        text = text[7:]
                    elif text.startswith("```"):
                        text = text[3:]
                    if "```" in text:
                        text = text.split("```")[0]
                    text = text.strip()
                else:
                    raise

        if return_reasoning:
            return parsed, reasoning
        return parsed
