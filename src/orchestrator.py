"""Máquina de estados do pipeline (SDD §1, PRD RF01-RF09).

O backend não chama LLM: cada rodada vira um lote de tarefas hidratadas do banco e executadas pelo
Hermes (`Executor`), que faz o fan-out de até 4 personas × N pontos com `delegate_task`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

import hydrator
import planner
import settings
from config import RAIZ, Config
from contracts import (
    PERSONAS,
    PERGUNTAS,
    PERGUNTAS_AUDITORIA_ESTATICAS,
    AuditorSaida,
    BuscadorSaida,
    PlanoLLM,
    PontoPlano,
    RedatorSaida,
    ResearchRequest,
    chave_url,
    normalizar_urls,
)
from db.repository import Repositorio
from engine import AgentCall, EngineError, Executor, Tarefa
from webhook import enviar_callback

logger = logging.getLogger(__name__)

Notificador = Callable[..., None]
URL_NO_TEXTO = re.compile(r"https?://[^\s<>\"'\]\),;]+")


class PipelineError(RuntimeError):
    pass


class Pipeline:
    def __init__(
        self,
        repositorio: Repositorio,
        executor: Executor,
        config: Config,
        *,
        notificador: Notificador = enviar_callback,
    ):
        self._repo = repositorio
        self._executor = executor
        self._config = config
        self._notificador = notificador
        self._modelos: dict[str, str] = {}
        self._tokens_por_papel: dict[str, int] = {}
        self._research_id_atual = ""

    @property
    def repositorio(self) -> Repositorio:
        return self._repo

    def criar(self, requisicao: ResearchRequest) -> str:
        research_id = secrets.token_hex(8).upper()
        self._repo.criar_run(research_id, requisicao)
        self._evento(research_id, "run.criado", {"research_id": research_id})
        self._preparar_workspace(research_id)
        return research_id

    def _evento(self, research_id: str, tipo: str, payload: dict[str, Any]) -> int:
        """Grava o evento antes de publicar: o SSE só lê do banco."""
        return self._repo.emitir_evento(research_id, tipo, payload)

    def _tokens_totais(self, research_id: str) -> dict[str, int]:
        run = self._repo.obter_run(research_id) or {}
        return {
            "prompt_tokens": int(run.get("total_prompt_tokens") or 0),
            "completion_tokens": int(run.get("total_completion_tokens") or 0),
            "reasoning_tokens": int(run.get("total_reasoning_tokens") or 0),
            "total_tokens": int(run.get("total_tokens") or 0),
        }

    def caminho_workspace(self, research_id: str) -> Path:
        base = Path(self._config.pipeline.workspaces_dir)
        if not base.is_absolute():
            base = RAIZ / base
        return base / research_id

    def _preparar_workspace(self, research_id: str) -> Path:
        """Diretório exclusivo da pesquisa; o Hermes roda com cwd aqui (SDD §2.2.3)."""
        workspace = self.caminho_workspace(research_id)
        workspace.mkdir(parents=True, exist_ok=True)
        # O engine roda como outro usuário (hermes) no container isolado; o backend
        # (root) cria o workspace, então libera escrita para o motor.
        for alvo in (workspace, workspace / "prompts", workspace / "saidas"):
            alvo.mkdir(parents=True, exist_ok=True)
            try:
                alvo.chmod(0o777)
            except OSError:
                pass
        modelos = (settings._ler_config_remota() or settings.ler_config())["modelos_por_papel"]
        (workspace / "MODELS.json").write_text(
            json.dumps({"modelos_por_papel": modelos}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return workspace

    # -- execução ----------------------------------------------------------
    def executar(self, research_id: str) -> None:
        run = self._repo.obter_run(research_id)
        if run is None:
            raise KeyError(f"pesquisa {research_id} não existe")
        self._research_id_atual = research_id
        requisicao = ResearchRequest(
            tema=run["tema"],
            profundidade=run["profundidade"],
            veracidade_alvo=run["veracidade_alvo"],
            max_rodadas_auditoria=run["max_rodadas_auditoria"],
            atualidade=run["atualidade"],
            callback_url=run["callback_url"],
        )
        try:
            if not (os.getenv("DR_ENGINE_URL") or "").strip():
                settings.materializar_perfil()
        except Exception:
            pass
        self._modelos = settings.ler_config()["modelos_por_papel"]
        workspace = self.caminho_workspace(research_id)
        self._evento(research_id, "run.status", {"status": "PROCESSING"})
        try:
            self._planejar(research_id, requisicao, workspace)
            estado = {
                ponto["ponto_id"]: {
                    "ponto": ponto,
                    "pendentes": {},
                    "ignoradas": [],
                    "rodada": 1,
                }
                for ponto in self._repo.obter_pontos(research_id)
            }
            while estado:
                self._coletar(research_id, requisicao, estado, workspace)
                self._auditar(research_id, requisicao, estado, workspace)
            payload = self._repo.consolidar(research_id)
            self._evento(
                research_id,
                "run.concluido",
                {
                    "status": "COMPLETED",
                    "pontos_falhos": payload.get("pontos_falhos", []),
                    "metricas_tokens": payload.get("metricas_tokens", {}),
                    "avaliacao_pontos": (payload.get("avaliacao_pontos") or {}).get("avaliacao_pontos", []),
                },
            )
        except Exception as exc:
            self._repo.marcar_status(research_id, "FAILED")
            self._evento(research_id, "run.falhou", {"status": "FAILED", "erro": str(exc)})
            logger.exception("pesquisa %s falhou", research_id)
            raise

        try:
            self._notificador(
                str(requisicao.callback_url),
                payload,
                timeout_s=self._config.pipeline.webhook_timeout_s,
            )
        except Exception:
            logger.exception("webhook da pesquisa %s falhou", research_id)

    # -- etapas ------------------------------------------------------------
    def _planejar(self, research_id: str, requisicao: ResearchRequest, workspace: Path) -> None:
        payload = requisicao.model_dump(mode="json")
        sistema, prompt = hydrator.montar("planner", payload)

        def validar(dados: dict[str, Any]) -> PlanoLLM:
            plano = PlanoLLM.model_validate(dados).validar_para(requisicao.profundidade)
            # Perguntas estáticas: backend sobrescreve qualquer valor do planner.
            for ponto in plano.pontos:
                ponto.perguntas_auditoria = dict(PERGUNTAS_AUDITORIA_ESTATICAS)
            return plano

        tarefa = Tarefa(
            id="planner",
            papel="planner",
            sistema=sistema,
            prompt=prompt,
            payload=payload,
            # planner precisa buscar E gravar saidas/planner.json (sem delegar).
            toolsets=("web", "file"),
        )
        plano: PlanoLLM | None = None
        ultimo_erro: Exception | None = None
        for _tentativa in range(1, self._config.pipeline.tentativas_por_agente + 1):
            call = self._executor.planejar(workspace, tarefa)
            if not call.erro:
                try:
                    plano = validar(call.dados)
                except (ValidationError, ValueError) as exc:
                    ultimo_erro = exc
                    call.erro = str(exc)
            if plano is not None:
                self._registrar(
                    tarefa,
                    call,
                    urls_usadas=plano.urls_usadas,
                    urls_lidas=plano.urls_lidas,
                )
                break
            ultimo_erro = ultimo_erro or EngineError(call.erro or "planner sem saída")
            self._registrar(tarefa, call)
            tarefa = self._corrigir(tarefa, str(ultimo_erro))
        if plano is None:
            raise PipelineError(f"planner não produziu plano válido: {ultimo_erro}")

        plano_publico = {
            "research_id": research_id,
            "tema": requisicao.tema,
            "profundidade": requisicao.profundidade,
            "veracidade_alvo": requisicao.veracidade_alvo,
            "max_rodadas_auditoria": requisicao.max_rodadas_auditoria,
            "atualidade": requisicao.atualidade,
            "callback_url": str(requisicao.callback_url),
            "pontos": [ponto.model_dump() for ponto in plano.pontos],
        }
        self._repo.salvar_plano(research_id, plano_publico, plano.pontos)
        self._evento(
            research_id,
            "plano.pronto",
            {"pontos": [ponto.ponto_id for ponto in plano.pontos], "total_pontos": len(plano.pontos)},
        )

    def _coletar(
        self,
        research_id: str,
        requisicao: ResearchRequest,
        estado: dict[int, dict[str, Any]],
        workspace: Path,
    ) -> None:
        tarefas: list[Tarefa] = []
        for ponto_id, item in estado.items():
            for persona in PERSONAS:
                payload = hydrator.payload_buscador(
                    research_id=research_id,
                    tema=requisicao.tema,
                    atualidade=requisicao.atualidade,
                    ponto=item["ponto"],
                    persona=persona,
                    rodada=item["rodada"],
                    perguntas_pendentes=item["pendentes"],
                    urls_ignoradas=item["ignoradas"],
                    max_queries=self._config.pipeline.max_queries_por_persona,
                )
                sistema, prompt = hydrator.montar(persona, payload)
                tarefas.append(
                    Tarefa(
                        id=f"{persona}_p{ponto_id}_r{item['rodada']}",
                        papel=persona,
                        sistema=sistema,
                        prompt=prompt,
                        payload=payload,
                        ponto_id=ponto_id,
                        rodada=item["rodada"],
                        # lote de coleta: o pai delega; os filhos herdam web+file (sem terminal).
                        toolsets=("web", "file", "delegation"),
                    )
                )

        emitidas_vivo: set[str] = set()
        parar = threading.Event()
        observador = threading.Thread(
            target=self._observar_coleta,
            args=(research_id, workspace, tarefas, emitidas_vivo, parar),
            daemon=True,
        )
        observador.start()
        try:
            saidas = self._executar_lote(workspace, tarefas, BuscadorSaida.model_validate)
        finally:
            parar.set()
            observador.join()
        falhos: list[int] = []
        for ponto_id, item in estado.items():
            self._evento(research_id, "ponto.iniciado", {"ponto_id": ponto_id, "rodada": item["rodada"]})
            ignoradas = set(item["ignoradas"])
            sucessos = 0
            personas_ok: list[str] = []
            for persona in PERSONAS:
                tarefa_id = f"{persona}_p{ponto_id}_r{item['rodada']}"
                resultado = saidas.get(tarefa_id)
                if resultado is None:
                    logger.warning(
                        "ponto %s rodada %s: persona %s sem saída",
                        ponto_id,
                        item["rodada"],
                        persona,
                    )
                    continue
                saida, call = resultado
                # Bloqueio programático da re-busca: URL já lida em rodada anterior não entra.
                urls_lidas = [url for url in saida.urls_lidas if url not in ignoradas]
                urls_usadas = [url for url in saida.urls_usadas if url not in ignoradas]
                tarefa = next(t for t in tarefas if t.id == tarefa_id)
                self._registrar(
                    tarefa,
                    call,
                    informacao_coletada=saida.informacao_coletada,
                    urls_usadas=urls_usadas,
                    urls_lidas=urls_lidas,
                )
                sucessos += 1
                personas_ok.append(persona)
                if tarefa.id in emitidas_vivo:
                    continue
                emitidas_vivo.add(tarefa.id)
                self._evento(
                    research_id,
                    "fonte.lida",
                    {
                        "ponto_id": ponto_id,
                        "rodada": item["rodada"],
                        "persona": persona,
                        "urls_lidas": urls_lidas,
                        "urls_usadas": urls_usadas,
                    },
                )
            acumulado = self._repo.hidratar(research_id, ponto_id)
            self._evento(
                research_id,
                "ponto.coletado",
                {
                    "ponto_id": ponto_id,
                    "rodada": item["rodada"],
                    "urls_usadas": acumulado["urls_usadas"],
                    "urls_lidas": acumulado["urls_lidas"],
                    "personas": personas_ok,
                },
            )
            if not sucessos:
                erro = f"ponto {ponto_id}: nenhuma persona concluiu a rodada {item['rodada']}"
                logger.warning("%s", erro)
                self._evento(
                    research_id, "ponto.erro", {"ponto_id": ponto_id, "erro": erro}
                )
                falhos.append(ponto_id)
        for ponto_id in falhos:
            estado.pop(ponto_id, None)

    def _auditar(
        self,
        research_id: str,
        requisicao: ResearchRequest,
        estado: dict[int, dict[str, Any]],
        workspace: Path,
    ) -> None:
        tarefas: list[Tarefa] = []
        acumulados: dict[int, dict[str, Any]] = {}
        for ponto_id, item in estado.items():
            acumulado = self._repo.hidratar(research_id, ponto_id)
            acumulados[ponto_id] = acumulado
            payload = hydrator.payload_auditor(
                research_id=research_id,
                atualidade=requisicao.atualidade,
                ponto=item["ponto"],
                tentativa_atual=item["rodada"],
                max_rodadas_auditoria=requisicao.max_rodadas_auditoria,
                acumulado=acumulado["rodadas"],
            )
            sistema, prompt = hydrator.montar("auditor", payload)
            tarefas.append(
                Tarefa(
                    id=f"auditor_p{ponto_id}_r{item['rodada']}",
                    papel="auditor",
                    sistema=sistema,
                    prompt=prompt,
                    payload=payload,
                    ponto_id=ponto_id,
                    rodada=item["rodada"],
                    # auditor: filhos só precisam de file para escrever saidas/<id>.json.
                    toolsets=("file", "delegation"),
                )
            )

        saidas = self._executar_lote(workspace, tarefas, AuditorSaida.model_validate)
        encerrados: list[
            tuple[dict[str, Any], dict[str, bool], dict[str, Any], int, str | None]
        ] = []
        for ponto_id, item in estado.items():
            tarefa_id = f"auditor_p{ponto_id}_r{item['rodada']}"
            resultado = saidas.get(tarefa_id)
            anteriores = self._repo.carregar_auditoria(research_id=research_id, ponto_id=ponto_id)
            if resultado is None:
                erro = (
                    f"ponto {ponto_id}: auditor sem saída na rodada {item['rodada']};"
                    " segue ao redator com as perguntas não concluídas da base acumulada"
                )
                logger.warning("%s", erro)
                item["erro_coleta"] = (
                    f"{item.get('erro_coleta')}; {erro}" if item.get("erro_coleta") else erro
                )
                # Auditor ausente não rebaixa: reaproveita o merge acumulado.
                mescladas = {
                    chave: bool(anteriores.get(chave, False)) for chave in PERGUNTAS
                }
                self._evento(
                    research_id,
                    "auditoria.executada",
                    {
                        "ponto_id": ponto_id,
                        "rodada": item["rodada"],
                        "perguntas_true": sum(1 for v in mescladas.values() if v),
                        "total_perguntas": 12,
                        "porcentagem_aprovacao": planner.taxa_aprovacao(mescladas),
                        "aprovado": False,
                        "auditor_ausente": True,
                        "perguntas_respondidas": mescladas,
                        "perguntas_respondidas_rodada": {
                            str(i): False for i in range(1, 13)
                        },
                        "model_used": "",
                        "total_tokens": 0,
                    },
                )
                self._evento(
                    research_id, "ponto.reprovado", {"ponto_id": ponto_id, "rodada": item["rodada"]}
                )
                encerrados.append(
                    (
                        item["ponto"],
                        mescladas,
                        acumulados[ponto_id],
                        item["rodada"],
                        item.get("erro_coleta"),
                    )
                )
                continue
            saida, call = resultado
            tarefa = next(t for t in tarefas if t.id == tarefa_id)
            self._registrar(tarefa, call)
            brutas = saida.perguntas_respondidas
            # Merge monotônico: base de coleta é acumulativa, true nunca volta a false.
            respostas = {
                chave: bool(anteriores.get(chave, False) or brutas.get(chave, False))
                for chave in PERGUNTAS
            }
            decisao = planner.avaliar(
                perguntas_respondidas=respostas,
                veracidade_alvo=requisicao.veracidade_alvo,
                tentativa_atual=item["rodada"],
                max_rodadas_auditoria=requisicao.max_rodadas_auditoria,
            )
            self._repo.salvar_auditoria(
                research_id=research_id,
                ponto_id=ponto_id,
                rodada=item["rodada"],
                perguntas_respondidas=respostas,
                decisao=decisao,
            )
            self._evento(
                research_id,
                "auditoria.executada",
                {
                    "ponto_id": ponto_id,
                    "rodada": item["rodada"],
                    "perguntas_true": decisao["perguntas_true"],
                    "total_perguntas": decisao["total_perguntas"],
                    "porcentagem_aprovacao": decisao["porcentagem_aprovacao"],
                    "aprovado": decisao["aprovado"],
                    "perguntas_respondidas": respostas,
                    "perguntas_respondidas_rodada": brutas,
                    "model_used": call.model_used or self._modelos.get("auditor") or "",
                    "total_tokens": call.total_tokens
                    or (call.prompt_tokens + call.completion_tokens + call.reasoning_tokens),
                },
            )
            if decisao["aprovado"]:
                self._evento(
                    research_id, "ponto.aprovado", {"ponto_id": ponto_id, "rodada": item["rodada"]}
                )
            elif decisao["proxima_acao"] != planner.ACAO_NOVA_RODADA:
                self._evento(
                    research_id, "ponto.reprovado", {"ponto_id": ponto_id, "rodada": item["rodada"]}
                )
            if decisao["proxima_acao"] == planner.ACAO_NOVA_RODADA:
                item["pendentes"] = {
                    chave: pergunta
                    for chave, pergunta in item["ponto"]["perguntas_auditoria"].items()
                    if not respostas.get(chave, False)
                }
                item["ignoradas"] = acumulados[ponto_id]["urls_lidas"]
                item["rodada"] += 1
                continue
            encerrados.append(
                (item["ponto"], respostas, acumulados[ponto_id], item["rodada"], item.get("erro_coleta"))
            )

        for ponto, _respostas, _acumulado, _rodada, _erro in encerrados:
            del estado[ponto["ponto_id"]]
        if encerrados:
            self._redigir(research_id, encerrados, workspace)

    def _redigir(
        self,
        research_id: str,
        encerrados: list[tuple[dict[str, Any], dict[str, bool], dict[str, Any], int, str | None]],
        workspace: Path,
    ) -> None:
        tarefas: list[Tarefa] = []
        validadores: dict[str, Callable[[dict[str, Any]], RedatorSaida]] = {}
        for ponto, respostas, acumulado, rodada, erro_coleta in encerrados:
            nao_concluidas = {
                chave: texto
                for chave, texto in ponto["perguntas_auditoria"].items()
                if not respostas.get(chave, False)
            }
            self._evento(research_id, "redator.iniciado", {"ponto_id": ponto["ponto_id"]})
            payload = hydrator.payload_redator(
                research_id=research_id,
                ponto=ponto,
                resultado_final_auditor=respostas,
                urls_usadas_acumuladas=acumulado["urls_usadas"],
                acumulado_integral=acumulado["rodadas"],
                perguntas_nao_concluidas=nao_concluidas,
                erro_coleta=erro_coleta,
            )
            sistema, prompt = hydrator.montar("redator", payload)
            tarefa = Tarefa(
                id=f"redator_p{ponto['ponto_id']}",
                papel="redator",
                sistema=sistema,
                prompt=prompt,
                payload=payload,
                ponto_id=ponto["ponto_id"],
                rodada=rodada,
                toolsets=("file", "delegation"),
            )
            tarefas.append(tarefa)
            validadores[tarefa.id] = self._validador_redator(acumulado["urls_usadas"])

        # Cada ponto tem seu próprio conjunto de URLs permitidas: o lote é validado por tarefa.
        saidas: dict[str, tuple[RedatorSaida, AgentCall]] = {}
        pendentes = tarefas
        for _tentativa in range(1, self._config.pipeline.tentativas_por_agente + 1):
            calls = self._executor.executar(workspace, pendentes)
            self._registrar_orquestrador(calls, pendentes)
            novas: list[Tarefa] = []
            for tarefa in pendentes:
                call = calls.get(tarefa.id) or AgentCall(dados={}, erro="tarefa sem saída")
                motivo = call.erro
                saida: RedatorSaida | None = None
                if not motivo:
                    try:
                        saida = validadores[tarefa.id](call.dados)
                    except (ValidationError, ValueError) as exc:
                        motivo = str(exc)
                if saida is None:
                    self._registrar(tarefa, call)
                    novas.append(self._corrigir(tarefa, motivo or "saída inválida"))
                    continue
                saidas[tarefa.id] = (saida, call)
            if not novas:
                break
            pendentes = novas

        for ponto, _respostas, _acumulado, _rodada, _erro in encerrados:
            tarefa_id = f"redator_p{ponto['ponto_id']}"
            resultado = saidas.get(tarefa_id)
            if resultado is None:
                erro = f"ponto {ponto['ponto_id']}: redator sem saída válida"
                logger.warning("%s", erro)
                self._evento(
                    research_id, "ponto.erro", {"ponto_id": ponto["ponto_id"], "erro": erro}
                )
                continue
            saida, call = resultado
            tarefa = next(t for t in tarefas if t.id == tarefa_id)
            self._registrar(tarefa, call)
            self._repo.salvar_relatorio(
                research_id=research_id,
                ponto_id=ponto["ponto_id"],
                relatorio=saida.relatorio_ponto,
                lacunas=saida.lacunas_identificadas,
            )
            self._evento(
                research_id, "ponto.finalizado", {"ponto_id": ponto["ponto_id"]}
            )

    def _observar_coleta(
        self,
        research_id: str,
        workspace: Path,
        tarefas: list[Tarefa],
        emitidas: set[str],
        parar: threading.Event,
    ) -> None:
        """Emite fonte.lida as JSONs aparecem em saidas/<id>.json (poll 2s).

        Só emite quando o arquivo parseia e contém urls_lidas/urls_usadas.
        Sem arquivo (FakeExecutor), nada emite — comportamento antigo segue.
        """
        por_id = {tarefa.id: tarefa for tarefa in tarefas}
        while not parar.is_set():
            for tarefa_id, tarefa in por_id.items():
                if tarefa_id in emitidas:
                    continue
                arquivo = workspace / "saidas" / f"{tarefa_id}.json"
                try:
                    texto = arquivo.read_text(encoding="utf-8")
                except OSError:
                    continue
                try:
                    dados = json.loads(texto)
                except ValueError:
                    continue
                if not isinstance(dados, dict):
                    continue
                if "urls_lidas" not in dados or "urls_usadas" not in dados:
                    continue
                emitidas.add(tarefa_id)
                lidas, usadas = self._urls_do_arquivo(dados)
                self._evento(
                    research_id,
                    "fonte.lida",
                    {
                        "ponto_id": tarefa.ponto_id,
                        "rodada": tarefa.rodada,
                        "persona": tarefa.papel,
                        "urls_lidas": lidas,
                        "urls_usadas": usadas,
                    },
                )
            parar.wait(2.0)

    @staticmethod
    def _urls_do_arquivo(dados: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Mesma normalização do caminho final; arquivo em escrita/URL suja não derruba a thread."""
        try:
            usadas = normalizar_urls(dados.get("urls_usadas") or [])
            lidas = normalizar_urls([*(dados.get("urls_lidas") or []), *usadas])
        except ValueError:
            return [], []
        return lidas, usadas

    # -- lote + retentativa ------------------------------------------------
    def _executar_lote(
        self,
        workspace: Path,
        tarefas: list[Tarefa],
        validador: Callable[[dict[str, Any]], Any],
    ) -> dict[str, tuple[Any, AgentCall]]:
        if not tarefas:
            return {}
        pendentes = list(tarefas)
        aceitos: dict[str, tuple[Any, AgentCall]] = {}
        for _tentativa in range(1, self._config.pipeline.tentativas_por_agente + 1):
            calls = self._executor.executar(workspace, pendentes)
            self._registrar_orquestrador(calls, pendentes)
            novas: list[Tarefa] = []
            for tarefa in pendentes:
                call = calls.get(tarefa.id) or AgentCall(dados={}, erro="tarefa sem saída")
                motivo = call.erro
                valor: Any = None
                if not motivo:
                    try:
                        valor = validador(call.dados)
                    except (ValidationError, ValueError) as exc:
                        motivo = str(exc)
                if valor is None:
                    self._registrar(tarefa, call)
                    novas.append(self._corrigir(tarefa, motivo or "saída inválida"))
                    continue
                aceitos[tarefa.id] = (valor, call)
            if not novas:
                break
            pendentes = novas
        return aceitos

    def _corrigir(self, tarefa: Tarefa, motivo: str) -> Tarefa:
        return Tarefa(
            id=tarefa.id,
            papel=tarefa.papel,
            sistema=tarefa.sistema,
            prompt=(
                f"{tarefa.prompt}\n\n## Correção obrigatória\n{motivo}\n"
                "Responda novamente apenas com o JSON corrigido."
            ),
            payload=tarefa.payload,
            ponto_id=tarefa.ponto_id,
            rodada=tarefa.rodada,
            toolsets=tarefa.toolsets,
        )

    def _validador_redator(
        self, urls_permitidas: list[str]
    ) -> Callable[[dict[str, Any]], RedatorSaida]:
        chaves_permitidas = {chave_url(u) for u in urls_permitidas if chave_url(u)}

        def validar(dados: dict[str, Any]) -> RedatorSaida:
            saida = RedatorSaida.model_validate(dados)
            texto = f"{saida.relatorio_ponto}\n{saida.lacunas_identificadas}"
            citadas = normalizar_urls([*saida.urls_citadas, *URL_NO_TEXTO.findall(texto)])
            fora = sorted({url for url in citadas if chave_url(url) not in chaves_permitidas})
            if fora:
                raise ValueError(
                    "URLs fora de urls_usadas_acumuladas: " + ", ".join(fora[:5])
                )
            return saida

        return validar

    # -- telemetria --------------------------------------------------------
    def _registrar_orquestrador(
        self, calls: dict[str, AgentCall], tarefas: list[Tarefa]
    ) -> None:
        """Tokens do agente principal do lote (o delegador), reportados pelo Hermes."""
        pai = calls.pop("__orquestrador__", None)
        if pai is None or not tarefas:
            return
        self._registrar(
            Tarefa(
                id="orquestrador",
                papel="orquestrador",
                sistema="",
                prompt="",
                payload={"lote": [tarefa.id for tarefa in tarefas]},
                rodada=tarefas[0].rodada,
            ),
            pai,
        )

    def _registrar(
        self,
        tarefa: Tarefa,
        call: AgentCall,
        *,
        informacao_coletada: str | None = None,
        urls_usadas: Any = (),
        urls_lidas: Any = (),
    ) -> None:
        self._repo.registrar_execucao(
            research_id=self._research_id_atual,
            ponto_id=tarefa.ponto_id,
            rodada=tarefa.rodada,
            agent_role=tarefa.papel,
            model_used=call.model_used or self._modelos.get(tarefa.papel) or "",
            input_prompt_payload=tarefa.payload,
            call=call,
            informacao_coletada=informacao_coletada,
            urls_usadas=urls_usadas,
            urls_lidas=urls_lidas,
        )
        total = call.total_tokens or (
            call.prompt_tokens + call.completion_tokens + call.reasoning_tokens
        )
        self._tokens_por_papel[tarefa.papel] = (
            self._tokens_por_papel.get(tarefa.papel, 0) + total
        )
        self._evento(
            self._research_id_atual,
            "tokens.atualizados",
            {
                "papel": tarefa.papel,
                "ponto_id": tarefa.ponto_id,
                "tokens_execucao": total,
                "tokens_por_papel": dict(self._tokens_por_papel),
                **self._tokens_totais(self._research_id_atual),
            },
        )


def construir_pipeline(config: Config | None = None) -> Pipeline:
    from hermes_runner import HermesRunner

    config = config or Config.carregar()
    caminho_db = Path(config.pipeline.db_path)
    if not caminho_db.is_absolute():
        caminho_db = RAIZ / caminho_db
    return Pipeline(Repositorio(caminho_db), HermesRunner(config), config)
