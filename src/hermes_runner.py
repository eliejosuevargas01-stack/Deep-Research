"""Executor real: um processo Hermes por etapa, com cwd no workspace da pesquisa.

O backend não chama LLM. Ele hidrata os prompts no workspace (`prompts/<id>.md`), grava a lista de
tarefas (`tarefas.json`) e aciona `hermes -p <perfil> -z ...`:

- `planejar`: o agente principal faz a varredura exploratória (`web_search`/`web_extract`) e grava
  o plano em `saidas/<id>.json`.
- `executar`: o agente principal apenas delega — um `delegate_task` por tarefa, com `papel` roteado
  pelo plugin `por_papel`; cada subagente grava seu JSON em `saidas/<id>.json`.

Tokens/modelo vêm do `state.db` do Hermes (sessões abertas no workspace); o `--usage-file` é o
fallback agregado.
"""

from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

import telemetria
from config import Config
from engine import AgentCall, EngineError, Tarefa, extrair_json

INSTRUCAO_PLANNER = """\
Você é o agente principal (planner) de uma pesquisa profunda. Trabalhe SOMENTE dentro de {workspace}.

1. Leia `prompts/{tarefa_id}.md`.
2. Faça a varredura exploratória obrigatória: use `web_search` e abra as páginas relevantes com
   `web_extract` para levantar o estado atual do tema antes de planejar. Máximo de 5 buscas.
3. Gere exatamente {profundidade} pontos, conforme as regras do prompt.
4. Grave o objeto JSON final em `saidas/{tarefa_id}.json` (write_file) e responda apenas com o JSON.

Não delegue esta etapa: o planner é você."""

INSTRUCAO_LOTE = """\
Você é o agente principal de uma pesquisa profunda. Trabalhe SOMENTE dentro de {workspace}.
NÃO responda às tarefas: apenas delegue.

1. Leia `tarefas.json` (lista de tarefas com `id`, `papel` e `arquivo`).
2. Para CADA tarefa, chame `delegate_task` com `papel` = campo `papel` da tarefa e `goal` no formato
   `[{primeiro_papel}] {primeiro_id} — execute o prompt de prompts/{primeiro_id}.md e grave o JSON em saidas/{primeiro_id}.json`.
   O subagente deve ler o arquivo de prompt, fazer as buscas que o prompt pede e gravar o JSON final
   em `saidas/<id>.json`.
3. Dispare todas as tarefas em paralelo; não faça o trabalho de nenhuma delas você mesmo.
4. Ao final, escreva `CONCLUIDO` em `saidas/_ok`."""


class HermesRunner:
    def __init__(self, config: Config):
        self._cfg = config.pipeline
        self._modelos: dict[str, str] = {}

    # -- executor ----------------------------------------------------------
    def planejar(self, workspace: Path, tarefa: Tarefa) -> AgentCall:
        self._modelos = self._modelos_por_papel()
        return self._rodar(workspace, [tarefa], modo="planner")[tarefa.id]

    def executar(
        self, workspace: Path, tarefas: Sequence[Tarefa]
    ) -> dict[str, AgentCall]:
        self._modelos = self._modelos_por_papel()
        return self._rodar(workspace, list(tarefas), modo="lote")

    # -- interno -----------------------------------------------------------
    def _modelos_por_papel(self) -> dict[str, str]:
        try:
            from settings import ler_config

            return dict(ler_config()["modelos_por_papel"])
        except Exception:  # arquivo ausente: cai no default_model
            return {}

    def _rodar(
        self, workspace: Path, tarefas: list[Tarefa], *, modo: str
    ) -> dict[str, AgentCall]:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "prompts").mkdir(exist_ok=True)
        (workspace / "saidas").mkdir(exist_ok=True)
        for tarefa in tarefas:
            (workspace / "prompts" / f"{tarefa.id}.md").write_text(
                f"{tarefa.sistema}\n\n{tarefa.prompt}", encoding="utf-8"
            )
            alvo = workspace / "saidas" / f"{tarefa.id}.json"
            alvo.unlink(missing_ok=True)
        (workspace / "tarefas.json").write_text(
            json.dumps(
                [
                    {
                        "id": tarefa.id,
                        "papel": tarefa.papel,
                        "arquivo": f"prompts/{tarefa.id}.md",
                        "ponto_id": tarefa.ponto_id,
                        "rodada": tarefa.rodada,
                    }
                    for tarefa in tarefas
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        primeira = tarefas[0]
        if modo == "planner":
            instrucao = INSTRUCAO_PLANNER.format(
                workspace=workspace,
                tarefa_id=primeira.id,
                profundidade=primeira.payload.get("profundidade", ""),
            )
        else:
            instrucao = INSTRUCAO_LOTE.format(
                workspace=workspace, primeiro_papel=primeira.papel, primeiro_id=primeira.id
            )

        inicio = time.time()
        erro = self._acionar(workspace, instrucao)
        return self._coletar_saidas(workspace, tarefas, inicio, erro)

    def _acionar(self, workspace: Path, instrucao: str) -> str:
        comando = [
            *shlex.split(self._cfg.hermes_bin),
            "-p",
            self._cfg.hermes_profile,
            "-z",
            instrucao,
            "--usage-file",
            str(workspace / "usage.json"),
        ]
        env = os.environ.copy()
        if self._cfg.hermes_home:
            env["HERMES_HOME"] = self._cfg.hermes_home
        env["DR_WORKSPACE"] = str(workspace)
        try:
            processo = subprocess.run(
                comando,
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=self._cfg.hermes_timeout_s,
            )
        except subprocess.TimeoutExpired:
            return f"Hermes excedeu {self._cfg.hermes_timeout_s}s"
        except OSError as exc:
            return f"Hermes não executou: {exc}"
        if processo.returncode != 0:
            return (processo.stderr or processo.stdout or "falha sem saída").strip()[-800:]
        return ""

    def _coletar_saidas(
        self, workspace: Path, tarefas: list[Tarefa], inicio: float, erro: str
    ) -> dict[str, AgentCall]:
        uso = _ler_usage(workspace / "usage.json")
        sessoes = telemetria.coletar(workspace, inicio - 1)
        saidas: dict[str, AgentCall] = {}
        for tarefa in tarefas:
            arquivo = workspace / "saidas" / f"{tarefa.id}.json"
            sessao = sessoes.get(tarefa.id, {})
            modelo = sessao.get("model_used") or self._modelos.get(tarefa.papel, "")
            if not arquivo.exists():
                motivo = erro or f"sem saidas/{tarefa.id}.json"
                saidas[tarefa.id] = AgentCall(
                    dados={}, erro=motivo, model_used=modelo, **_tokens(sessao)
                )
                continue
            texto = arquivo.read_text(encoding="utf-8")
            call = AgentCall(
                dados={},
                texto=texto,
                model_used=modelo,
                reasoning_trace=sessao.get("reasoning_trace", ""),
                tool_calls=[],
                **_tokens(sessao),
            )
            try:
                call.dados = extrair_json(texto)
            except EngineError as exc:
                call.erro = str(exc)
            saidas[tarefa.id] = call

        if len(tarefas) == 1 and not any(c.total_tokens for c in saidas.values()) and uso:
            call = saidas[tarefas[0].id]
            call.prompt_tokens = uso.get("prompt_tokens", 0)
            call.completion_tokens = uso.get("completion_tokens", 0)
            call.reasoning_tokens = uso.get("reasoning_tokens", 0)
            call.total_tokens = uso.get("total_tokens", 0) or (
                call.prompt_tokens + call.completion_tokens + call.reasoning_tokens
            )
        return saidas


def _tokens(sessao: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt_tokens": int(sessao.get("prompt_tokens", 0)),
        "completion_tokens": int(sessao.get("completion_tokens", 0)),
        "reasoning_tokens": int(sessao.get("reasoning_tokens", 0)),
        "total_tokens": int(sessao.get("total_tokens", 0)),
        "latency_ms": int(sessao.get("latency_ms", 0)),
    }


def _ler_usage(caminho: Path) -> dict[str, int]:
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}

    def _int(*chaves: str) -> int:
        for chave in chaves:
            valor = dados.get(chave)
            if isinstance(valor, (int, float)):
                return int(valor)
            if isinstance(valor, dict):
                soma = sum(v for v in valor.values() if isinstance(v, (int, float)))
                if soma:
                    return int(soma)
        return 0

    return {
        "prompt_tokens": _int("prompt_tokens", "input_tokens"),
        "completion_tokens": _int("completion_tokens", "output_tokens"),
        "reasoning_tokens": _int("reasoning_tokens"),
        "total_tokens": _int("total_tokens", "tokens"),
    }


def limpar_workspace(workspace: Path) -> None:
    """Remove artefatos de execução mantendo o workspace da pesquisa."""
    for nome in ("prompts", "saidas", "tarefas.json", "usage.json"):
        alvo = workspace / nome
        if alvo.is_dir():
            shutil.rmtree(alvo)
        elif alvo.exists():
            alvo.unlink()
