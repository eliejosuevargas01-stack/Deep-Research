"""Máquina de estados do pipeline (SDD §1, PRD RF01-RF09).

O backend não chama LLM: cada rodada vira um lote de tarefas hidratadas do banco e executadas pelo
Hermes (`Executor`), que faz o fan-out de até 4 personas × N pontos com `delegate_task`.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

import hydrator
import planner
import settings
from config import RAIZ, Config
from contracts import (
    PERSONAS,
    AuditorSaida,
    BuscadorSaida,
    PlanoLLM,
    PontoPlano,
    RedatorSaida,
    ResearchRequest,
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
        self._research_id_atual = ""

    @property
    def repositorio(self) -> Repositorio:
        return self._repo

    def criar(self, requisicao: ResearchRequest) -> str:
        research_id = secrets.token_hex(8).upper()
        self._repo.criar_run(research_id, requisicao)
        self._preparar_workspace(research_id)
        return research_id

    def caminho_workspace(self, research_id: str) -> Path:
        base = Path(self._config.pipeline.workspaces_dir)
        if not base.is_absolute():
            base = RAIZ / base
        return base / research_id

    def _preparar_workspace(self, research_id: str) -> Path:
        """Diretório exclusivo da pesquisa; o Hermes roda com cwd aqui (SDD §2.2.3)."""
        workspace = self.caminho_workspace(research_id)
        workspace.mkdir(parents=True, exist_ok=True)
        modelos = settings.ler_config()["modelos_por_papel"]
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
        self._modelos = settings.ler_config()["modelos_por_papel"]
        workspace = self.caminho_workspace(research_id)
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
        except Exception:
            self._repo.marcar_status(research_id, "FAILED")
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
            return PlanoLLM.model_validate(dados).validar_para(requisicao.profundidade)

        tarefa = Tarefa(id="planner", papel="planner", sistema=sistema, prompt=prompt, payload=payload)
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
                self._registrar(tarefa, call)
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
                    )
                )

        saidas = self._executar_lote(workspace, tarefas, BuscadorSaida.model_validate)
        for ponto_id, item in estado.items():
            ignoradas = set(item["ignoradas"])
            sucessos = 0
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
            if not sucessos:
                raise PipelineError(
                    f"ponto {ponto_id}: nenhuma persona concluiu a rodada {item['rodada']}"
                )

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
                )
            )

        saidas = self._executar_lote(workspace, tarefas, AuditorSaida.model_validate)
        encerrados: list[tuple[dict[str, Any], dict[str, bool], dict[str, Any], int]] = []
        for ponto_id, item in estado.items():
            tarefa_id = f"auditor_p{ponto_id}_r{item['rodada']}"
            resultado = saidas.get(tarefa_id)
            if resultado is None:
                raise PipelineError(
                    f"ponto {ponto_id}: auditor sem saída na rodada {item['rodada']}"
                )
            saida, call = resultado
            tarefa = next(t for t in tarefas if t.id == tarefa_id)
            self._registrar(tarefa, call)
            respostas = saida.perguntas_respondidas
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
                (item["ponto"], respostas, acumulados[ponto_id], item["rodada"])
            )

        for ponto, _respostas, _acumulado, _rodada in encerrados:
            del estado[ponto["ponto_id"]]
        if encerrados:
            self._redigir(research_id, encerrados, workspace)

    def _redigir(
        self,
        research_id: str,
        encerrados: list[tuple[dict[str, Any], dict[str, bool], dict[str, Any], int]],
        workspace: Path,
    ) -> None:
        tarefas: list[Tarefa] = []
        validadores: dict[str, Callable[[dict[str, Any]], RedatorSaida]] = {}
        for ponto, respostas, acumulado, rodada in encerrados:
            payload = hydrator.payload_redator(
                research_id=research_id,
                ponto=ponto,
                resultado_final_auditor=respostas,
                urls_usadas_acumuladas=acumulado["urls_usadas"],
                acumulado_integral=acumulado["rodadas"],
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
            )
            tarefas.append(tarefa)
            validadores[tarefa.id] = self._validador_redator(acumulado["urls_usadas"])

        # Cada ponto tem seu próprio conjunto de URLs permitidas: o lote é validado por tarefa.
        saidas: dict[str, tuple[RedatorSaida, AgentCall]] = {}
        pendentes = tarefas
        for _tentativa in range(1, self._config.pipeline.tentativas_por_agente + 1):
            calls = self._executor.executar(workspace, pendentes)
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

        for ponto, _respostas, _acumulado, _rodada in encerrados:
            tarefa_id = f"redator_p{ponto['ponto_id']}"
            resultado = saidas.get(tarefa_id)
            if resultado is None:
                raise PipelineError(f"ponto {ponto['ponto_id']}: redator sem saída válida")
            saida, call = resultado
            tarefa = next(t for t in tarefas if t.id == tarefa_id)
            self._registrar(tarefa, call)
            self._repo.salvar_relatorio(
                research_id=research_id,
                ponto_id=ponto["ponto_id"],
                relatorio=saida.relatorio_ponto,
                lacunas=saida.lacunas_identificadas,
            )

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
        )

    def _validador_redator(
        self, urls_permitidas: list[str]
    ) -> Callable[[dict[str, Any]], RedatorSaida]:
        permitidas = set(urls_permitidas)

        def validar(dados: dict[str, Any]) -> RedatorSaida:
            saida = RedatorSaida.model_validate(dados)
            texto = f"{saida.relatorio_ponto}\n{saida.lacunas_identificadas}"
            citadas = normalizar_urls([*saida.urls_citadas, *URL_NO_TEXTO.findall(texto)])
            fora = sorted({url for url in citadas if url not in permitidas})
            if fora:
                raise ValueError(
                    "URLs fora de urls_usadas_acumuladas: " + ", ".join(fora[:5])
                )
            return saida

        return validar

    # -- telemetria --------------------------------------------------------
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


def construir_pipeline(config: Config | None = None) -> Pipeline:
    from hermes_runner import HermesRunner

    config = config or Config.carregar()
    caminho_db = Path(config.pipeline.db_path)
    if not caminho_db.is_absolute():
        caminho_db = RAIZ / caminho_db
    return Pipeline(Repositorio(caminho_db), HermesRunner(config), config)
