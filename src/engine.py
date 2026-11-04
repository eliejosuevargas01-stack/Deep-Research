"""Chamada ao núcleo agêntico (Hermes) via API compatível com OpenAI."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from config import ConfigEngine


class EngineError(RuntimeError):
    pass


@dataclass(slots=True)
class AgentCall:
    dados: dict[str, Any]
    texto: str = ""
    erro: str = ""
    reasoning_trace: str = ""
    tool_calls: list[Any] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0


class Engine(Protocol):
    def executar(self, papel: str, sistema: str, prompt: str) -> AgentCall: ...


class OpenAICompatEngine:
    """Cliente `POST {base_url}/chat/completions` com extração estrita de JSON."""

    def __init__(self, config: ConfigEngine):
        self._config = config

    def executar(self, papel: str, sistema: str, prompt: str) -> AgentCall:
        if not self._config.api_key:
            raise EngineError(f"defina {self._config.api_key_env} para chamar o engine")
        inicio = time.monotonic()
        try:
            resposta = httpx.post(
                f"{self._config.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                json={
                    "model": self._config.model,
                    "temperature": self._config.temperature,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": sistema},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=self._config.timeout_s,
            )
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            raise EngineError(f"falha HTTP no engine: {exc}") from exc

        corpo = resposta.json()
        mensagem = corpo["choices"][0]["message"]
        texto = mensagem.get("content") or ""
        uso = corpo.get("usage") or {}
        detalhes = uso.get("completion_tokens_details") or {}
        call = AgentCall(
            dados={},
            texto=texto,
            reasoning_trace=mensagem.get("reasoning_content") or mensagem.get("reasoning") or "",
            tool_calls=mensagem.get("tool_calls") or [],
            prompt_tokens=int(uso.get("prompt_tokens") or 0),
            completion_tokens=int(uso.get("completion_tokens") or 0),
            reasoning_tokens=int(detalhes.get("reasoning_tokens") or uso.get("reasoning_tokens") or 0),
            total_tokens=int(uso.get("total_tokens") or 0),
            latency_ms=int((time.monotonic() - inicio) * 1000),
        )
        try:
            call.dados = extrair_json(texto)
        except EngineError as exc:
            # O texto bruto ainda é telemetria válida: devolve para o orquestrador persistir.
            call.erro = str(exc)
        return call


def extrair_json(texto: str) -> dict[str, Any]:
    limpo = texto.strip()
    if limpo.startswith("```"):
        linhas = limpo.splitlines()[1:]
        if linhas and linhas[-1].strip().startswith("```"):
            linhas = linhas[:-1]
        limpo = "\n".join(linhas).strip()

    try:
        valor = json.loads(limpo)
    except json.JSONDecodeError:
        decodificador = json.JSONDecoder()
        valor = None
        for indice, caractere in enumerate(limpo):
            if caractere != "{":
                continue
            try:
                valor, _ = decodificador.raw_decode(limpo[indice:])
                break
            except json.JSONDecodeError:
                continue
        if valor is None:
            raise EngineError("resposta do agente não contém JSON válido") from None

    if not isinstance(valor, dict):
        raise EngineError("JSON retornado pelo agente não é um objeto")
    return valor
