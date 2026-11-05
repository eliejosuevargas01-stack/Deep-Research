"""Máquina de estados do pipeline (SDD §1, PRD RF01-RF08)."""

from __future__ import annotations

import json
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
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
)
from db.repository import Repositorio
from engine import Engine, EngineError
from webhook import enviar_callback

logger = logging.getLogger(__name__)

Notificador = Callable[..., None]


class PipelineError(RuntimeError):
    pass


class Pipeline:
    def __init__(
        self,
        repositorio: Repositorio,
        engine: Engine,
        config: Config,
        *,
        notificador: Notificador = enviar_callback,
    ):
        self._repo = repositorio
        self._engine = engine
        self._config = config
        self._notificador = notificador

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

    def executar(self, research_id: str) -> None:
        run = self._repo.obter_run(research_id)
        if run is None:
            raise KeyError(f"pesquisa {research_id} não existe")
        requisicao = ResearchRequest(
            tema=run["tema"],
            profundidade=run["profundidade"],
            veracidade_alvo=run["veracidade_alvo"],
            max_rodadas_auditoria=run["max_rodadas_auditoria"],
            atualidade=run["atualidade"],
            callback_url=run["callback_url"],
        )
        try:
            self._planejar(research_id, requisicao)
            pontos = self._repo.obter_pontos(research_id)
            erros: list[tuple[int, str]] = []
            with ThreadPoolExecutor(
                max_workers=self._config.pipeline.max_pontos_paralelos,
                thread_name_prefix="ponto",
            ) as pool:
                futuros = {
                    pool.submit(self._processar_ponto, research_id, requisicao, ponto): ponto[
                        "ponto_id"
                    ]
                    for ponto in pontos
                }
                for futuro in as_completed(futuros):
                    try:
                        futuro.result()
                    except Exception as exc:  # isolamento por ponto (RNF03)
                        logger.exception("ponto %s falhou", futuros[futuro])
                        erros.append((futuros[futuro], str(exc)))
            if erros:
                raise PipelineError(f"pontos com falha: {erros}")
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
    def _planejar(self, research_id: str, requisicao: ResearchRequest) -> None:
        payload = requisicao.model_dump(mode="json")

        def validar(dados: dict[str, Any]) -> PlanoLLM:
            return PlanoLLM.model_validate(dados).validar_para(requisicao.profundidade)

        plano = self._chamar(
            papel="planner",
            research_id=research_id,
            ponto_id=None,
            rodada=1,
            payload=payload,
            validador=validar,
        )
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

    def _processar_ponto(
        self, research_id: str, requisicao: ResearchRequest, ponto: dict[str, Any]
    ) -> None:
        pendentes: dict[str, str] = {}
        urls_ignoradas: list[str] = []
        rodada = 1
        while True:
            self._coletar_rodada(
                research_id, requisicao, ponto, rodada, pendentes, urls_ignoradas
            )
            acumulado = self._repo.hidratar(research_id, ponto["ponto_id"])
            respostas = self._auditar(research_id, requisicao, ponto, rodada, acumulado)
            decisao = planner.avaliar(
                perguntas_respondidas=respostas,
                veracidade_alvo=requisicao.veracidade_alvo,
                tentativa_atual=rodada,
                max_rodadas_auditoria=requisicao.max_rodadas_auditoria,
            )
            self._repo.salvar_auditoria(
                research_id=research_id,
                ponto_id=ponto["ponto_id"],
                rodada=rodada,
                perguntas_respondidas=respostas,
                decisao=decisao,
            )
            if decisao["proxima_acao"] == planner.ACAO_NOVA_RODADA:
                pendentes = {
                    chave: pergunta
                    for chave, pergunta in ponto["perguntas_auditoria"].items()
                    if not respostas.get(chave, False)
                }
                urls_ignoradas = acumulado["urls_lidas"]
                rodada += 1
                continue
            self._redigir(research_id, ponto, respostas, acumulado, rodada)
            return

    def _coletar_rodada(
        self,
        research_id: str,
        requisicao: ResearchRequest,
        ponto: dict[str, Any],
        rodada: int,
        pendentes: dict[str, str],
        urls_ignoradas: list[str],
    ) -> None:
        def coletar(persona: str):
            payload = hydrator.payload_buscador(
                research_id=research_id,
                tema=requisicao.tema,
                ponto=ponto,
                persona=persona,
                rodada=rodada,
                perguntas_pendentes=pendentes,
                urls_ignoradas=urls_ignoradas,
                max_queries=self._config.pipeline.max_queries_por_persona,
            )
            return self._chamar(
                papel=persona,
                research_id=research_id,
                ponto_id=ponto["ponto_id"],
                rodada=rodada,
                payload=payload,
                validador=BuscadorSaida.model_validate,
            )

        sucessos = 0
        with ThreadPoolExecutor(max_workers=len(PERSONAS), thread_name_prefix="persona") as pool:
            futuros = {pool.submit(coletar, persona): persona for persona in PERSONAS}
            for futuro in as_completed(futuros):
                try:
                    futuro.result()
                    sucessos += 1
                except Exception as exc:  # uma persona não derruba as outras (RNF03)
                    logger.warning(
                        "ponto %s rodada %s: persona %s falhou: %s",
                        ponto["ponto_id"],
                        rodada,
                        futuros[futuro],
                        exc,
                    )
        if not sucessos:
            raise PipelineError(
                f"ponto {ponto['ponto_id']}: nenhuma persona concluiu a rodada {rodada}"
            )

    def _auditar(
        self,
        research_id: str,
        requisicao: ResearchRequest,
        ponto: dict[str, Any],
        rodada: int,
        acumulado: dict[str, Any],
    ) -> dict[str, bool]:
        payload = hydrator.payload_auditor(
            research_id=research_id,
            ponto=ponto,
            tentativa_atual=rodada,
            max_rodadas_auditoria=requisicao.max_rodadas_auditoria,
            acumulado=acumulado["rodadas"],
        )
        saida = self._chamar(
            papel="auditor",
            research_id=research_id,
            ponto_id=ponto["ponto_id"],
            rodada=rodada,
            payload=payload,
            validador=AuditorSaida.model_validate,
        )
        return saida.perguntas_respondidas

    def _redigir(
        self,
        research_id: str,
        ponto: dict[str, Any],
        respostas: dict[str, bool],
        acumulado: dict[str, Any],
        rodada: int,
    ) -> None:
        payload = hydrator.payload_redator(
            research_id=research_id,
            ponto=ponto,
            resultado_final_auditor=respostas,
            urls_usadas_acumuladas=acumulado["urls_usadas"],
            acumulado_integral=acumulado["rodadas"],
        )
        saida = self._chamar(
            papel="redator",
            research_id=research_id,
            ponto_id=ponto["ponto_id"],
            rodada=rodada,
            payload=payload,
            validador=RedatorSaida.model_validate,
        )
        self._repo.salvar_relatorio(
            research_id=research_id,
            ponto_id=ponto["ponto_id"],
            relatorio=saida.relatorio_ponto,
            lacunas=saida.lacunas_identificadas,
        )

    # -- chamada + telemetria ---------------------------------------------
    def _chamar(
        self,
        *,
        papel: str,
        research_id: str,
        ponto_id: int | None,
        rodada: int,
        payload: dict[str, Any],
        validador: Callable[[dict[str, Any]], Any],
    ) -> Any:
        sistema, prompt_base = hydrator.montar(papel, payload)
        prompt = prompt_base
        ultimo_erro: Exception | None = None
        for _tentativa in range(1, self._config.pipeline.tentativas_por_agente + 1):
            try:
                call = self._engine.executar(papel, sistema, prompt)
            except EngineError as exc:
                ultimo_erro = exc
                prompt = f"{prompt_base}\n\n## Correção obrigatória\n{exc}. Responda apenas com JSON válido."
                continue
            if call.erro:
                ultimo_erro = EngineError(call.erro)
                self._registrar(
                    research_id=research_id,
                    ponto_id=ponto_id,
                    rodada=rodada,
                    papel=papel,
                    payload=payload,
                    call=call,
                )
                prompt = (
                    f"{prompt_base}\n\n## Correção obrigatória\n"
                    f"{call.erro}. Responda apenas com o objeto JSON."
                )
                continue
            try:
                saida = validador(call.dados)
            except (ValidationError, ValueError) as exc:
                ultimo_erro = exc
                self._registrar(
                    research_id=research_id,
                    ponto_id=ponto_id,
                    rodada=rodada,
                    papel=papel,
                    payload=payload,
                    call=call,
                )
                prompt = (
                    f"{prompt_base}\n\n## Correção obrigatória\n"
                    f"A resposta anterior foi rejeitada: {exc}\n"
                    "Responda novamente apenas com o JSON corrigido."
                )
                continue
            self._registrar(
                research_id=research_id,
                ponto_id=ponto_id,
                rodada=rodada,
                papel=papel,
                payload=payload,
                call=call,
                informacao_coletada=getattr(saida, "informacao_coletada", None),
                urls_usadas=getattr(saida, "urls_usadas", ()) or (),
                urls_lidas=getattr(saida, "urls_lidas", ()) or (),
            )
            return saida
        raise PipelineError(
            f"agente {papel} não produziu saída válida após "
            f"{self._config.pipeline.tentativas_por_agente} tentativas: {ultimo_erro}"
        )

    def _registrar(
        self,
        *,
        research_id: str,
        ponto_id: int | None,
        rodada: int,
        papel: str,
        payload: dict[str, Any],
        call,
        informacao_coletada: str | None = None,
        urls_usadas=(),
        urls_lidas=(),
    ) -> None:
        self._repo.registrar_execucao(
            research_id=research_id,
            ponto_id=ponto_id,
            rodada=rodada,
            agent_role=papel,
            input_prompt_payload=payload,
            call=call,
            informacao_coletada=informacao_coletada,
            urls_usadas=urls_usadas,
            urls_lidas=urls_lidas,
        )


def construir_pipeline(config: Config | None = None) -> Pipeline:
    from engine import OpenAICompatEngine

    config = config or Config.carregar()
    caminho_db = Path(config.pipeline.db_path)
    if not caminho_db.is_absolute():
        caminho_db = RAIZ / caminho_db
    return Pipeline(Repositorio(caminho_db), OpenAICompatEngine(config.engine), config)
