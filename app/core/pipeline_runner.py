"""Orquestrador do ciclo contínuo assíncrono do pipeline Deep Research.

Executa de forma autônoma e ininterrupta:
1. Busca agêntica com personas ReAct e deduplicação (Searcher).
2. Auditoria cumulativa frente às 12 perguntas de qualidade (Auditor).
3. Ciclo de re-tentativas automáticas até aprovação ou teto de 4 tentativas.
4. Redação final completa do dossiê em Markdown com 100% de fontes canônicas (Writer).
5. Despacho assinado HMAC-SHA256 para o webhook de callback configurado.
"""

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auditor import Auditor
from app.core.personas import resolve_required_search_personas
from app.core.stream_context import publish_stage_event
from app.core.reading_coordinator import ReadingCoordinator
from app.core.searcher import Searcher
from app.core.writer import Writer
from app.db.research_repository import ResearchRepository
from app.db.session import get_sessionmaker
from app.services.credential_resolver import (
    resolve_callback_webhook_url,
    resolve_jina_base_url,
    resolve_key,
    resolve_personas,
    resolve_webhook_hmac_secret,
)
from app.services.webhook_client import WebhookClient
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _clean_key(val: Optional[str]) -> Optional[str]:
    """Garante chave em ASCII puro para compatibilidade estrita com headers HTTP."""
    if val is None:
        return None
    cleaned = val.encode("ascii", "ignore").decode("ascii").strip()
    return cleaned if cleaned else None


def _format_iso_utc() -> str:
    """Retorna timestamp corrente formatado em ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


class PipelineEventHub:
    """Hub thread-safe e assíncrono para publicação e assinatura de eventos do pipeline em tempo real."""

    def __init__(self, max_history_per_research: int = 100, max_researches: int = 50) -> None:
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._history: OrderedDict[str, List[Tuple[str, Dict[str, Any]]]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_history = max_history_per_research
        self._max_researches = max_researches

    def subscribe(self, id_pesquisa: str) -> asyncio.Queue:
        """Registra um assinante e retorna uma fila assíncrona isolada para a pesquisa."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            if id_pesquisa not in self._subscribers:
                self._subscribers[id_pesquisa] = set()
            self._subscribers[id_pesquisa].add(q)
        return q

    def unsubscribe(self, id_pesquisa: str, queue: asyncio.Queue) -> None:
        """Remove o assinante da pesquisa de forma segura."""
        with self._lock:
            if id_pesquisa in self._subscribers:
                self._subscribers[id_pesquisa].discard(queue)
                if not self._subscribers[id_pesquisa]:
                    self._subscribers.pop(id_pesquisa, None)

    def publish(self, id_pesquisa: str, event: str, data: Dict[str, Any]) -> None:
        """Publica um evento para todos os assinantes ativos e armazena no buffer recente."""
        with self._lock:
            if id_pesquisa not in self._history:
                while len(self._history) >= self._max_researches:
                    evicted_id, _ = self._history.popitem(last=False)
                    self._subscribers.pop(evicted_id, None)
                self._history[id_pesquisa] = []
            else:
                self._history.move_to_end(id_pesquisa)
            hist = self._history[id_pesquisa]
            hist.append((event, data))
            if len(hist) > self._max_history:
                hist.pop(0)
            subscribers = list(self._subscribers.get(id_pesquisa, set()))

        for q in subscribers:
            try:
                q.put_nowait((event, data))
            except Exception:
                try:
                    loop = getattr(q, "_loop", None)
                    if loop and loop.is_running():
                        loop.call_soon_threadsafe(q.put_nowait, (event, data))
                except Exception as exc_put:
                    logger.warning(
                        f"[PipelineEventHub] Falha ao despachar evento '{event}' para {id_pesquisa}: {exc_put}"
                    )

    def get_history(self, id_pesquisa: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Retorna snapshot imutável do histórico de eventos recentes para a pesquisa."""
        with self._lock:
            if id_pesquisa in self._history:
                self._history.move_to_end(id_pesquisa)
                return list(self._history[id_pesquisa])
            return []

    def clear(self, id_pesquisa: Optional[str] = None) -> None:
        """Limpa filas e histórico da pesquisa ou globalmente."""
        with self._lock:
            if id_pesquisa:
                self._subscribers.pop(id_pesquisa, None)
                self._history.pop(id_pesquisa, None)
            else:
                self._subscribers.clear()
                self._history.clear()


_global_pipeline_event_hub = PipelineEventHub()


def get_pipeline_event_hub() -> PipelineEventHub:
    """Retorna a instância canônica compartilhada do barramento de eventos."""
    return _global_pipeline_event_hub


class PipelineRunner:
    """Executor autônomo do pipeline ponta a ponta em segundo plano."""

    def __init__(self, transport: Optional[Any] = None) -> None:
        self.transport = transport

    async def run(
        self,
        id_pesquisa: str,
        callback_url: Optional[str] = None,
        execution_mode: str = "parallel",
    ) -> Dict[str, Any]:
        """Executa o ciclo completo em segundo plano com tratamento de erros e atualização de status.

        ``execution_mode`` (PRD v2, I-3) governa o processamento dos pontos de pesquisa:
        ``parallel`` (default) ou ``sequential`` (um ponto por vez, ordem crescente de ponto_n).
        """
        if execution_mode not in ("parallel", "sequential"):
            return {
                "status": "erro",
                "detalhe": (
                    f"EXECUTION_MODE_INVALID: '{execution_mode}' não é um modo válido. "
                    "Valores aceitos: parallel, sequential."
                ),
            }
        session_factory = get_sessionmaker()
        jina_client: Optional[JinaClient] = None
        llm_client: Optional[LLMClient] = None
        async with session_factory() as db:
            repo = ResearchRepository(session=db)
            pesquisa = await repo.get_research(id_pesquisa)
            if not pesquisa:
                logger.error(f"[PipelineRunner] Pesquisa não encontrada: {id_pesquisa}")
                return {"status": "erro", "detalhe": f"Pesquisa não encontrada: {id_pesquisa}"}

            try:
                hub = get_pipeline_event_hub()
                hub.publish(id_pesquisa, "pipeline.status", {
                    "id_pesquisa": id_pesquisa,
                    "status_pipeline": "buscando",
                    "timestamp": _format_iso_utc(),
                })

                # 1. Resolução dinâmica de credenciais e clientes
                jina_key = _clean_key(await resolve_key(db, "JINA_API_KEY", self.transport)) or "jina-mock-key"
                jina_base_url = _clean_key(await resolve_jina_base_url(db, self.transport))
                llm_key = _clean_key(await resolve_key(db, "OPENAI_API_KEY", self.transport)) or "openai-mock-key"
                llm_base_url = _clean_key(await resolve_key(db, "LLM_BASE_URL", self.transport))
                model_light = _clean_key(await resolve_key(db, "LLM_MODEL_LIGHT", self.transport))
                model_strong = _clean_key(await resolve_key(db, "LLM_MODEL_STRONG", self.transport))
                global_personas = None if self.transport else await resolve_personas(db)
                allowed_personas = resolve_required_search_personas(pesquisa)

                jina_client = JinaClient(
                    api_key=jina_key,
                    base_url=jina_base_url,
                    transport=self.transport,
                )
                llm_client = LLMClient(
                    api_key=llm_key,
                    base_url=llm_base_url,
                    model_light=model_light,
                    model_strong=model_strong,
                    transport=self.transport,
                )

                webhook_secret = _clean_key(await resolve_webhook_hmac_secret(db)) or (
                    "test-secret" if self.transport else None
                )
                webhook_client = (
                    WebhookClient(secret=webhook_secret, transport=self.transport, research_repo=repo)
                    if webhook_secret
                    else None
                )

                resolved_callback = (
                    callback_url
                    or await resolve_callback_webhook_url(db)
                )

                searcher = Searcher(
                    research_repo=repo,
                    jina_client=jina_client,
                    llm_client=llm_client,
                    personas=allowed_personas,
                )
                auditor = Auditor(
                    research_repo=repo,
                    llm_client=llm_client,
                    personas=global_personas,
                )
                writer = Writer(
                    research_repo=repo,
                    llm_client=llm_client,
                    webhook_client=webhook_client,
                    callback_url=resolved_callback,
                    personas=global_personas,
                )

                # 2. Ciclo de Busca e Auditoria com Retentativas Automáticas
                max_ciclos = 4
                audit_res: Dict[str, Any] = {}
                targeted_personas: Optional[List[str]] = None

                for ciclo in range(1, max_ciclos + 1):
                    logger.info(f"[PipelineRunner] Iniciando ciclo de busca {ciclo} para {id_pesquisa}...")
                    pontos = await repo.list_points(id_pesquisa)

                    # Executa busca apenas para pontos não aprovados e abaixo do teto
                    pontos_para_busca = [
                        p for p in pontos
                        if p.status != "aprovado" and (p.tentativas or 0) < 4
                    ]
                    if not pontos_para_busca and all(p.status == "aprovado" for p in pontos):
                        logger.info(f"[PipelineRunner] Todos os pontos já estão aprovados antes da busca.")
                    else:
                        await repo.update_pipeline_status(id_pesquisa, "buscando")
                        hub.publish(id_pesquisa, "pipeline.status", {
                            "id_pesquisa": id_pesquisa,
                            "status_pipeline": "buscando",
                            "timestamp": _format_iso_utc(),
                        })
                        pontos_alvo_info = [(p.ponto_id, p.ponto_n) for p in pontos_para_busca]
                        reading_coordinator = ReadingCoordinator()

                        async def _exec_point_search(p_id: str, p_n: int) -> None:
                            hub.publish(id_pesquisa, "point.status", {
                                "id_pesquisa": id_pesquisa,
                                "ponto_id": p_id,
                                "ponto_n": p_n,
                                "status": "em_andamento",
                                "tentativas": ciclo,
                            })
                            p_alvos: List[str] = []
                            if audit_res:
                                a_item = next(
                                    (a for a in audit_res.get("auditorias", []) if a.get("ponto_id") == p_id),
                                    None,
                                )
                                if a_item:
                                    for t in a_item.get("tarefas") or []:
                                        for p_nome in t.get("personas_alvo") or []:
                                            if p_nome in allowed_personas and p_nome not in p_alvos:
                                                p_alvos.append(p_nome)
                            async with session_factory() as pt_db:
                                pt_repo = ResearchRepository(session=pt_db)
                                pt_searcher = Searcher(
                                    research_repo=pt_repo,
                                    jina_client=jina_client,
                                    llm_client=llm_client,
                                    personas=allowed_personas,
                                    session_factory=session_factory,
                                    reading_coordinator=reading_coordinator,
                                )
                                search_res = await pt_searcher.execute_search(
                                    id_pesquisa=id_pesquisa,
                                    ponto_id=p_id,
                                    personas=p_alvos if p_alvos else None,
                                    execution_mode=execution_mode,
                                )
                                if search_res:
                                    hub.publish(id_pesquisa, "point.status", {
                                        "id_pesquisa": id_pesquisa,
                                        "ponto_id": p_id,
                                        "ponto_n": search_res.get("ponto_n", p_n),
                                        "status": search_res.get("status", "coletado"),
                                        "tentativas": search_res.get("tentativas", ciclo),
                                    })
                                    for p_item in search_res.get("personas", []):
                                        hub.publish(id_pesquisa, "search.progress", {
                                            "id_pesquisa": id_pesquisa,
                                            "ponto_id": p_id,
                                            "persona": p_item.get("persona"),
                                            "queries_executadas": p_item.get("queries_executadas", 0),
                                            "urls_lidas": len(p_item.get("urls_fonte", [])) or search_res.get("total_urls_lidas", 0),
                                            "falha_coleta": bool(p_item.get("falha_coleta", False)),
                                            "reasoning_coleta": p_item.get("reasoning"),
                                        })

                        try:
                            if execution_mode == "sequential":
                                # Sequencial (I-3): um ponto em voo por vez, ordem crescente de ponto_n.
                                for p_info in sorted(pontos_alvo_info, key=lambda x: x[1]):
                                    await _exec_point_search(p_info[0], p_info[1])
                            else:
                                search_tasks = [
                                    asyncio.create_task(_exec_point_search(p_info[0], p_info[1]))
                                    for p_info in pontos_alvo_info
                                ]
                                try:
                                    await asyncio.gather(*search_tasks)
                                except BaseException:
                                    for t in search_tasks:
                                        if not t.done():
                                            t.cancel()
                                    await asyncio.gather(*search_tasks, return_exceptions=True)
                                    raise
                        finally:
                            await reading_coordinator.close()

                        try:
                            await repo.session.rollback()
                        except Exception:
                            pass

                    logger.info(f"[PipelineRunner] Iniciando auditoria para {id_pesquisa}...")
                    await repo.update_pipeline_status(id_pesquisa, "auditando")
                    hub.publish(id_pesquisa, "pipeline.status", {
                        "id_pesquisa": id_pesquisa,
                        "status_pipeline": "auditando",
                        "timestamp": _format_iso_utc(),
                    })
                    publish_stage_event(id_pesquisa, "stage.start", "audit", agent="auditor")
                    try:
                        audit_res = await auditor.execute_audit(id_pesquisa=id_pesquisa)
                    finally:
                        publish_stage_event(id_pesquisa, "stage.end", "audit", agent="auditor")
                    pontos_auditados = await repo.list_points(id_pesquisa)
                    ponto_audit_map = {p.ponto_id: p for p in pontos_auditados}
                    for a_item in audit_res.get("auditorias", []):
                        p_id = a_item.get("ponto_id")
                        p_obj = ponto_audit_map.get(p_id)
                        reasoning_audit_val = (
                            a_item.get("reasoning_auditoria")
                            or (p_obj.reasoning_auditoria if p_obj else None)
                            or a_item.get("resumo_auditoria")
                        )
                        hub.publish(id_pesquisa, "audit.result", {
                            "id_pesquisa": id_pesquisa,
                            "ponto_id": p_id,
                            "ponto_n": a_item.get("ponto_n", 1),
                            "status": a_item.get("status", "reprovado"),
                            "pontuacao_percentual": a_item.get("pontuacao_percentual", 0.0),
                            "criterios_aprovados": a_item.get("criterios_aprovados", 0),
                            "reasoning_auditoria": reasoning_audit_val,
                            "pontos_fracos": a_item.get("pontos_fracos"),
                        })
                        hub.publish(id_pesquisa, "point.status", {
                            "id_pesquisa": id_pesquisa,
                            "ponto_id": a_item.get("ponto_id"),
                            "ponto_n": a_item.get("ponto_n", 1),
                            "status": a_item.get("status", "reprovado"),
                            "tentativas": ciclo,
                        })

                    if audit_res.get("pronto_para_writer") is True:
                        logger.info(f"[PipelineRunner] Todos os pontos foram aprovados na auditoria!")
                        break

                    # Verifica se todos os pontos pendentes atingiram o teto de auditoria ou busca
                    pontos_frescos = await repo.list_points(id_pesquisa)
                    pontos_pendentes = [p for p in pontos_frescos if p.status != "aprovado"]
                    todos_pendentes_no_teto = all(
                        (p.tentativas or 0) >= 4 or (p.tentativas_auditoria or 0) >= 3
                        for p in pontos_pendentes
                    ) if pontos_pendentes else False

                    if todos_pendentes_no_teto or ciclo == max_ciclos:
                        logger.warning(
                            f"[PipelineRunner] Pesquisa {id_pesquisa} não alcançou aprovação na auditoria "
                            "ou atingiu o teto de tentativas. Redação bloqueada."
                        )
                        final_status = "reprovado" if any(p.status == "reprovado" for p in pontos_frescos) else "parcial"
                        await repo.update_pipeline_status(id_pesquisa, final_status)
                        hub.publish(id_pesquisa, "pipeline.status", {
                            "id_pesquisa": id_pesquisa,
                            "status_pipeline": final_status,
                            "timestamp": _format_iso_utc(),
                        })
                        return {
                            "status": final_status,
                            "detalhe": "Teto de tentativas ou reprovação na auditoria; redação bloqueada.",
                            "audit_res": audit_res,
                        }

                # 3. Redação Final e Despacho ao Webhook (APENAS se aprovado na auditoria)
                if not audit_res.get("pronto_para_writer"):
                    logger.warning(f"[PipelineRunner] Redação bloqueada: pesquisa {id_pesquisa} não pronta para Writer.")
                    hub.publish(id_pesquisa, "pipeline.status", {
                        "id_pesquisa": id_pesquisa,
                        "status_pipeline": "bloqueado",
                        "timestamp": _format_iso_utc(),
                    })
                    return {"status": "bloqueado", "detalhe": "Auditoria não aprovou todos os pontos."}

                logger.info(f"[PipelineRunner] Iniciando redação final para {id_pesquisa}...")
                await repo.update_pipeline_status(id_pesquisa, "redigindo")
                hub.publish(id_pesquisa, "pipeline.status", {
                    "id_pesquisa": id_pesquisa,
                    "status_pipeline": "redigindo",
                    "timestamp": _format_iso_utc(),
                })
                hub.publish(id_pesquisa, "writer.progress", {
                    "id_pesquisa": id_pesquisa,
                    "status": "redigindo",
                    "reasoning_dossier": None,
                    "total_caracteres": 0,
                })
                publish_stage_event(id_pesquisa, "stage.start", "writer", agent="redator final")
                try:
                    writer_res = await writer.execute_writer(id_pesquisa=id_pesquisa)
                finally:
                    publish_stage_event(id_pesquisa, "stage.end", "writer", agent="redator final")

                final_status = (writer_res or {}).get("status") or "falha"
                dossier_final = (writer_res or {}).get("dossier_final") or ""
                reasoning_dossier = (writer_res or {}).get("reasoning_dossier")
                concluido_em = (writer_res or {}).get("concluido_em") or _format_iso_utc()

                hub.publish(id_pesquisa, "writer.progress", {
                    "id_pesquisa": id_pesquisa,
                    "status": final_status,
                    "reasoning_dossier": reasoning_dossier,
                    "total_caracteres": len(dossier_final),
                })
                if final_status == "concluido" and dossier_final:
                    hub.publish(id_pesquisa, "report.final", {
                        "id_pesquisa": id_pesquisa,
                        "status": "concluido",
                        "dossier_final": dossier_final,
                        "total_caracteres": len(dossier_final),
                        "concluido_em": concluido_em,
                    })
                    hub.publish(id_pesquisa, "pipeline.status", {
                        "id_pesquisa": id_pesquisa,
                        "status_pipeline": "concluido",
                        "timestamp": concluido_em,
                    })
                else:
                    hub.publish(id_pesquisa, "pipeline.status", {
                        "id_pesquisa": id_pesquisa,
                        "status_pipeline": final_status,
                        "timestamp": _format_iso_utc(),
                    })
                logger.info(f"[PipelineRunner] Pesquisa {id_pesquisa} finalizada com status '{final_status}'.")
                return writer_res or {}

            except Exception as exc:
                from app.tools.errors import JinaError

                erro_msg = str(exc)
                if isinstance(exc, JinaError):
                    erro_msg = (
                        f"{type(exc).__name__} [HTTP {exc.http_status}/{exc.categoria}]: {exc} "
                        f"| Ação: {exc.acao_corretiva}"
                    )
                logger.error(f"[PipelineRunner] Falha na execução da pesquisa {id_pesquisa}: {erro_msg}", exc_info=True)
                hub = get_pipeline_event_hub()
                hub.publish(id_pesquisa, "pipeline.error", {
                    "id_pesquisa": id_pesquisa,
                    "erro": erro_msg,
                })
                hub.publish(id_pesquisa, "pipeline.status", {
                    "id_pesquisa": id_pesquisa,
                    "status_pipeline": "falha",
                    "timestamp": _format_iso_utc(),
                })
                return {"status": "falha", "erro": erro_msg}
            finally:
                if jina_client is not None:
                    await jina_client.aclose()
                if llm_client is not None:
                    await llm_client.aclose()


async def execute_sync_pipeline(
    id_pesquisa: str,
    callback_url: Optional[str] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    """Helper síncrono para execução do pipeline autônomo completo em ambientes fechados/testes."""
    runner = PipelineRunner(transport=transport)
    return await runner.run(id_pesquisa=id_pesquisa, callback_url=callback_url)
