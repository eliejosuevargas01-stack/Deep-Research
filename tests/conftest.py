from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any, Callable

import pytest

from config import Config
from db.repository import Repositorio
from engine import AgentCall, Tarefa


def extrair_payload(prompt: str) -> dict[str, Any]:
    bloco = re.search(r"```json\n(.*?)\n```", prompt, re.DOTALL)
    assert bloco, "prompt sem bloco JSON"
    return json.loads(bloco.group(1))


class FakeExecutor:
    """Executor determinístico: responde por papel e guarda o payload de cada tarefa."""

    def __init__(self, responder: Callable[[str, dict[str, Any]], dict[str, Any]]):
        self._responder = responder
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self.workspaces: list[Any] = []

    def planejar(self, workspace, tarefa: Tarefa) -> AgentCall:
        return self._chamar(workspace, tarefa)

    def executar(self, workspace, tarefas) -> dict[str, AgentCall]:
        return {tarefa.id: self._chamar(workspace, tarefa) for tarefa in tarefas}

    def _chamar(self, workspace, tarefa: Tarefa) -> AgentCall:
        self.chamadas.append((tarefa.papel, tarefa.payload))
        self.workspaces.append(workspace)
        try:
            dados = self._responder(tarefa.papel, tarefa.payload)
        except Exception as exc:  # contrato do executor: falha vira AgentCall.erro
            return AgentCall(dados={}, erro=str(exc), model_used=f"fake/{tarefa.papel}")
        return AgentCall(
            dados=dados,
            texto=json.dumps(dados, ensure_ascii=False),
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=10,
            total_tokens=160,
            latency_ms=1,
            model_used=f"fake/{tarefa.papel}",
        )

    def payloads(self, papel: str) -> list[dict[str, Any]]:
        return [payload for nome, payload in self.chamadas if nome == papel]


@pytest.fixture
def config(tmp_path) -> Config:
    cfg = Config()
    cfg.pipeline.db_path = str(tmp_path / "deep_research.db")
    cfg.pipeline.workspaces_dir = str(tmp_path / "workspaces")
    cfg.pipeline.tentativas_por_agente = 2
    return cfg


@pytest.fixture
def repositorio(config) -> Iterator[Repositorio]:
    repo = Repositorio(config.pipeline.db_path)
    yield repo
    repo.fechar()
