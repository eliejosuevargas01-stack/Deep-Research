"""Contrato de chamada de agente e extração de JSON.

A partir da spec v1.2 o backend não fala com provedor de LLM: quem executa é o Hermes
(`src/hermes_runner.py`). Este módulo guarda só o contrato de dados trocado com o executor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence


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
    model_used: str = ""


@dataclass(slots=True)
class Tarefa:
    """Um papel a executar no Hermes: prompt já hidratado pelo backend."""

    id: str
    papel: str
    sistema: str
    prompt: str
    payload: dict[str, Any]
    ponto_id: int | None = None
    rodada: int = 1
    toolsets: tuple[str, ...] | None = None


class Executor(Protocol):
    def planejar(self, workspace: Path, tarefa: Tarefa) -> AgentCall: ...

    def executar(
        self, workspace: Path, tarefas: Sequence[Tarefa]
    ) -> dict[str, AgentCall]: ...


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
