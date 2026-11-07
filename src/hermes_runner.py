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
3. Gere exatamente {profundidade} pontos (ponto_id, enunciado, subperguntas, hipoteses, lacunas_iniciais), conforme as regras do prompt.
   NÃO gere `perguntas_auditoria`: o backend injeta as 12 estáticas em cada ponto.
4. Inclua no JSON as listas `urls_lidas` (todas as páginas abertas com `web_extract`)
   e `urls_usadas` (subconjunto das lidas que informou o plano).
5. Grave o objeto JSON final em `saidas/{tarefa_id}.json` (write_file) e responda apenas com o JSON.

Não delegue esta etapa: o planner é você."""

INSTRUCAO_LOTE = """\
Você é o agente principal de uma pesquisa profunda. Trabalhe SOMENTE dentro de {workspace}.
NÃO responda às tarefas: apenas delegue.

1. Leia `tarefas.json` (lista com `id`, `papel` e `arquivo`).
2. Esta rodada tem {quantidade} tarefas. Dispare as {quantidade} em paralelo, uma por item da lista,
   sem pular nenhuma e sem escolher só a primeira.
3. Cada `delegate_task` recebe `papel` = campo `papel` da tarefa e `goal` = `[{exemplo_papel}] {exemplo_id} — leia prompts/{exemplo_id}.md, execute o que ele pede e grave o objeto JSON em saidas/{exemplo_id}.json`
   (trocando `{exemplo_id}` pelo `id` da tarefa correspondente).
4. Não faça o trabalho de nenhuma delas você mesmo e não redija síntese.
5. Ao final, escreva `CONCLUIDO` em `saidas/_ok`."""


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
        import os as _os

        try:
            if not (_os.getenv("DR_ENGINE_URL") or "").strip():
                from settings import materializar_perfil

                materializar_perfil()
        except Exception:
            pass
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
        for alvo in (workspace, workspace / "prompts", workspace / "saidas"):
            try:
                alvo.chmod(0o777)
            except OSError:
                pass
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
                workspace=workspace,
                quantidade=len(tarefas),
                exemplo_papel=primeira.papel,
                exemplo_id=primeira.id,
            )

        inicio = time.time()
        erro = self._acionar(workspace, instrucao)
        return self._coletar_saidas(workspace, tarefas, inicio, erro, modo=modo)

    def _acionar_via_engine(self, base: str, workspace: Path, instrucao: str) -> str:
        import httpx  # import local: subprocess segue sem a dependência

        headers = {"X-Engine-Token": self._cfg.engine_token} if self._cfg.engine_token else {}
        try:
            with httpx.Client(timeout=self._cfg.hermes_timeout_s + 30) as client:
                resposta = client.post(
                    f"{base}/run",
                    json={
                        "workspace": str(workspace),
                        "instrucao": instrucao,
                        "timeout_s": self._cfg.hermes_timeout_s,
                    },
                    headers=headers,
                )
        except Exception as exc:
            return f"Engine não executou: {exc}"
        if resposta.status_code != 200:
            return f"Engine falhou ({resposta.status_code}): {resposta.text.strip()[:800]}"
        return ""

    def _acionar(self, workspace: Path, instrucao: str) -> str:
        base = (self._cfg.engine_url or "").rstrip("/")
        if base:
            return self._acionar_via_engine(base, workspace, instrucao)
        return self._acionar_local(workspace, instrucao)

    def _acionar_local(self, workspace: Path, instrucao: str) -> str:
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
        self, workspace: Path, tarefas: list[Tarefa], inicio: float, erro: str, *, modo: str
    ) -> dict[str, AgentCall]:
        uso = _ler_usage(workspace / "usage.json")
        sessoes = telemetria.coletar(workspace, inicio - 1)
        saidas: dict[str, AgentCall] = {}
        for tarefa in tarefas:
            arquivo = workspace / "saidas" / f"{tarefa.id}.json"
            if modo == "planner" and tarefa.id == "planner" and tarefa.id not in sessoes:
                chave_planner = next(
                    (
                        chave
                        for chave, entrada in sessoes.items()
                        if any(s.get("papel") == "planner" for s in entrada.get("sessoes", []))
                    ),
                    None,
                )
                sessao = sessoes.get("_pai") or (sessoes.get(chave_planner) if chave_planner else None) or {}
            else:
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
                **_tokens(sessao),
            )
            try:
                call.dados = extrair_json(texto)
            except EngineError as exc:
                call.erro = str(exc)
            saidas[tarefa.id] = call

        if modo == "planner":
            if len(tarefas) == 1 and not saidas[tarefas[0].id].total_tokens and uso:
                _aplicar_usage(saidas[tarefas[0].id], uso)
            return saidas

        # O agente principal delegou: os tokens dele ficam na sessão pai (ou no usage agregado).
        pai = sessoes.get("_pai")
        if pai:
            saidas["__orquestrador__"] = AgentCall(
                dados={}, model_used=pai.get("model_used", ""), **_tokens(pai)
            )
        elif uso:
            saidas["__orquestrador__"] = AgentCall(
                dados={}, model_used=self._modelos.get("planner", ""), **_usage_tokens(uso)
            )
        return saidas


def _tokens(sessao: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt_tokens": int(sessao.get("prompt_tokens", 0)),
        "completion_tokens": int(sessao.get("completion_tokens", 0)),
        "reasoning_tokens": int(sessao.get("reasoning_tokens", 0)),
        "total_tokens": int(sessao.get("total_tokens", 0)),
        "latency_ms": int(sessao.get("latency_ms", 0)),
        "reasoning_trace": str(sessao.get("reasoning_trace", "") or ""),
        "tool_calls": list(sessao.get("tool_calls_lista", []) or []),
    }


def _usage_tokens(uso: dict[str, int]) -> dict[str, Any]:
    total = uso.get("total_tokens") or (
        uso.get("prompt_tokens", 0)
        + uso.get("completion_tokens", 0)
        + uso.get("reasoning_tokens", 0)
    )
    return {
        "prompt_tokens": uso.get("prompt_tokens", 0),
        "completion_tokens": uso.get("completion_tokens", 0),
        "reasoning_tokens": uso.get("reasoning_tokens", 0),
        "total_tokens": total,
        "latency_ms": 0,
    }


def _aplicar_usage(call: AgentCall, uso: dict[str, int]) -> None:
    tokens = _usage_tokens(uso)
    call.prompt_tokens = tokens["prompt_tokens"]
    call.completion_tokens = tokens["completion_tokens"]
    call.reasoning_tokens = tokens["reasoning_tokens"]
    call.total_tokens = tokens["total_tokens"]


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
