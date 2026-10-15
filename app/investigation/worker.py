"""PersonaWorker da investigação (T010, RN-04/RN-06/RN-07/RN-08/RN-10/RN-13/RN-14)."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from uuid import UUID

from app.investigation.llm_binding import LLMCallError, call_llm_with_retries
from app.investigation.prompts import build_persona_system_prompt, get_model_for_persona
from app.investigation.schemas import JINA_SEARCH_TOOL, PersonaResultPayload
from app.investigation.tools import JinaSearchError, JinaToolAdapter

_MAX_SEARCHES = 3
_MAX_JSON_CORRECTIONS = 3
_GLOBAL_TIMEOUT_S = 600.0
_MAX_POST_CEILING_TOOL_ATTEMPTS = 1
_MAX_TOOL_CALL_TURNS = 10

_CEILING_MSG = (
    "Teto de 3 buscas atingido. Não execute mais buscas. "
    'Entregue imediatamente a resposta final em JSON: {"result": "...", "used_urls": [...]}.'
)
_CORRECTION_MSG = (
    "Sua resposta final deve ser estritamente um único objeto JSON válido, "
    'sem texto adicional nem markdown, no formato {"result": "...", "used_urls": [...]}. '
    "Corrija e reenvie apenas o JSON."
)


@dataclass
class PersonaExecutionResult:
    success: bool
    result: str
    used_urls: list[str] = field(default_factory=list)
    read_urls: list[str] = field(default_factory=list)
    error: str | None = None


def _sanitize_error(value: BaseException | str) -> str:
    text = str(value) if isinstance(value, BaseException) else str(value)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9\-._~+/=]+", "Bearer ***", text)
    text = re.sub(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s;,]+)", r"\1***", text)
    text = re.sub(r"sk-[A-Za-z0-9\-_]+", "***", text)
    text = re.sub(r"(https?://)[^/\s@]*:[^/\s@]*@", r"\1***@", text)
    text = re.sub(r"(?i)(token\s*[:=]\s*)([^\s;,]+)", r"\1***", text)
    text = text.strip() or "Worker failed"
    return text[:500]


def _extract_json_text(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", t, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _parse_and_validate(text: str) -> PersonaResultPayload:
    raw = _extract_json_text(text)
    data = json.loads(raw)
    try:
        validate = getattr(PersonaResultPayload, "model_validate")
    except AttributeError:
        return PersonaResultPayload(**data)  # pydantic v1
    return validate(data)


def _get_message(resp: object) -> object | None:
    try:
        if isinstance(resp, dict):
            choices = resp.get("choices") or []
        else:
            choices = getattr(resp, "choices", None) or []
        if not choices:
            return None
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            return msg if msg is not None else first
        msg = getattr(first, "message", None)
        return msg if msg is not None else first
    except Exception:
        return None


def _get_tool_calls(message: object) -> list:
    if message is None:
        return []
    if isinstance(message, dict):
        tcs = message.get("tool_calls")
    else:
        tcs = getattr(message, "tool_calls", None)
    if not tcs:
        return []
    try:
        return list(tcs)
    except TypeError:
        return []


def _tool_call_info(tc: object) -> tuple[str, str, object]:
    if isinstance(tc, dict):
        tc_id = str(tc.get("id", "") or "")
        fn = tc.get("function", {}) or {}
        if isinstance(fn, dict):
            name = str(fn.get("name", "") or "")
            args_raw = fn.get("arguments", "")
        else:
            name = str(getattr(fn, "name", "") or "")
            args_raw = getattr(fn, "arguments", "")
        return tc_id, name, args_raw
    tc_id = str(getattr(tc, "id", "") or "")
    fn = getattr(tc, "function", None)
    if isinstance(fn, dict):
        name = str(fn.get("name", "") or "")
        args_raw = fn.get("arguments", "")
    elif fn is not None:
        name = str(getattr(fn, "name", "") or "")
        args_raw = getattr(fn, "arguments", "")
    else:
        name = str(getattr(tc, "name", "") or "")
        args_raw = getattr(tc, "arguments", "")
    return tc_id, name, args_raw


def _extract_query(args_raw: object) -> str:
    if isinstance(args_raw, dict):
        q = args_raw.get("q", "")
        return q.strip() if isinstance(q, str) else ""
    if isinstance(args_raw, str):
        if not args_raw.strip():
            return ""
        try:
            data = json.loads(args_raw)
        except (ValueError, TypeError):
            return ""
        if isinstance(data, dict):
            q = data.get("q", "")
            return q.strip() if isinstance(q, str) else ""
        return ""
    return ""


def _merge_urls(dst: list[str], src: list[str]) -> None:
    for u in src or []:
        if isinstance(u, str) and u and u not in dst:
            dst.append(u)


def _message_content(message: object) -> str:
    if message is None:
        return ""
    if isinstance(message, dict):
        c = message.get("content")
        return c if isinstance(c, str) else ("" if c is None else str(c))
    c = getattr(message, "content", None)
    if c is None:
        return ""
    return c if isinstance(c, str) else str(c)


def _serialize_tool_calls(tcs: list) -> list[dict]:
    out: list[dict] = []
    for tc in tcs:
        tc_id, name, args_raw = _tool_call_info(tc)
        if isinstance(args_raw, dict):
            args_str = json.dumps(args_raw)
        elif isinstance(args_raw, str):
            args_str = args_raw
        else:
            args_str = ""
        out.append(
            {
                "id": tc_id,
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            }
        )
    return out


class PersonaWorker:
    def __init__(
        self,
        jina_adapter: JinaToolAdapter,
        app_settings_models: dict | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        self.jina_adapter = jina_adapter
        self.app_settings_models = app_settings_models
        self.api_base = api_base
        self.api_key = api_key

    async def execute(
        self,
        research_id: UUID,
        step_id: UUID,
        step_title: str,
        persona: str,
        research_theme: str | None = None,
    ) -> PersonaExecutionResult:
        read_urls: list[str] = []
        try:
            async with asyncio.timeout(_GLOBAL_TIMEOUT_S):
                return await self._run(step_title, persona, research_theme, read_urls)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            msg = _sanitize_error(exc if str(exc) else "Worker timeout after 600s")
            return PersonaExecutionResult(
                success=False, result=msg, used_urls=[], read_urls=read_urls, error=msg
            )
        except (LLMCallError, JinaSearchError) as exc:
            msg = _sanitize_error(exc)
            return PersonaExecutionResult(
                success=False, result=msg, used_urls=[], read_urls=read_urls, error=msg
            )
        except Exception as exc:
            msg = _sanitize_error(exc)
            return PersonaExecutionResult(
                success=False, result=msg, used_urls=[], read_urls=read_urls, error=msg
            )

    async def _run(
        self,
        step_title: str,
        persona: str,
        research_theme: str | None,
        read_urls: list[str],
    ) -> PersonaExecutionResult:
        model = get_model_for_persona(persona, self.app_settings_models)
        credentials = (self.app_settings_models or {}).get("_credentials_by_persona", {}).get(persona, {})
        api_base = credentials.get("api_base", self.api_base)
        api_key = credentials.get("api_key", self.api_key)
        system_prompt = build_persona_system_prompt(persona, step_title, research_theme)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Investigue o ponto: {step_title}"},
        ]
        search_count = 0
        corrections = 0
        post_ceiling_tool_attempts = 0
        total_tool_turns = 0
        while True:
            tools = [JINA_SEARCH_TOOL] if search_count < _MAX_SEARCHES else None
            resp = await call_llm_with_retries(
                model=model,
                messages=messages,
                tools=tools,
                api_base=api_base,
                api_key=api_key,
            )
            message = _get_message(resp)
            tool_calls = _get_tool_calls(message)
            if tool_calls:
                total_tool_turns += 1
                if total_tool_turns > _MAX_TOOL_CALL_TURNS:
                    err = "Maximum tool call turns exceeded"
                    return PersonaExecutionResult(
                        success=False,
                        result=err,
                        used_urls=[],
                        read_urls=read_urls,
                        error=err,
                    )
                if search_count >= _MAX_SEARCHES:
                    post_ceiling_tool_attempts += 1
                    if post_ceiling_tool_attempts > _MAX_POST_CEILING_TOOL_ATTEMPTS:
                        err = "Maximum tool call attempts exceeded after search ceiling reached"
                        return PersonaExecutionResult(
                            success=False,
                            result=err,
                            used_urls=[],
                            read_urls=read_urls,
                            error=err,
                        )
                content = _message_content(message)
                messages.append(
                    {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": _serialize_tool_calls(tool_calls),
                    }
                )
                for tc in tool_calls:
                    tc_id, name, args_raw = _tool_call_info(tc)
                    if name == "jina_search":
                        if search_count >= _MAX_SEARCHES:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": "jina_search",
                                    "content": _CEILING_MSG,
                                }
                            )
                            continue
                        query = _extract_query(args_raw)
                        if not query:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": "jina_search",
                                    "content": "Query vazia. Forneça q não-vazia ou entregue o JSON final.",
                                }
                            )
                            continue
                        search_count += 1
                        jina_result = await self.jina_adapter.search(query)
                        _merge_urls(read_urls, jina_result.urls)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": "jina_search",
                                "content": jina_result.content,
                            }
                        )
                    else:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": name,
                                "content": f"Ferramenta '{name}' desconhecida. Utilize apenas jina_search ou entregue o JSON final.",
                            }
                        )
                continue
            content = _message_content(message)
            try:
                parsed = _parse_and_validate(content)
                return PersonaExecutionResult(
                    success=True,
                    result=parsed.result,
                    used_urls=list(parsed.used_urls or []),
                    read_urls=read_urls,
                    error=None,
                )
            except Exception:
                if corrections >= _MAX_JSON_CORRECTIONS:
                    err = "Invalid JSON response after 3 corrections"
                    return PersonaExecutionResult(
                        success=False,
                        result=err,
                        used_urls=[],
                        read_urls=read_urls,
                        error=err,
                    )
                corrections += 1
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": _CORRECTION_MSG})
                continue
