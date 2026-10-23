"""Orquestrador do ciclo contínuo assíncrono do pipeline Deep Research.

Executa de forma autônoma e ininterrupta:
1. Busca agêntica com personas ReAct e deduplicação (Searcher).
2. Auditoria cumulativa frente às 12 perguntas de qualidade (Auditor).
3. Ciclo de re-tentativas automáticas até aprovação ou teto de 4 tentativas.
4. Redação final completa do dossiê em Markdown com 100% de fontes canônicas (Writer).
5. Despacho assinado HMAC-SHA256 para o webhook de callback configurado.
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auditor import Auditor
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


class PipelineRunner:
    """Executor autônomo do pipeline ponta a ponta em segundo plano."""

    def __init__(self, transport: Optional[Any] = None) -> None:
        self.transport = transport

    async def run(
        self,
        id_pesquisa: str,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executa o ciclo completo em segundo plano com tratamento de erros e atualização de status."""
        session_factory = get_sessionmaker()
        async with session_factory() as db:
            repo = ResearchRepository(session=db)
            pesquisa = await repo.get_research(id_pesquisa)
            if not pesquisa:
                logger.error(f"[PipelineRunner] Pesquisa não encontrada: {id_pesquisa}")
                return {"status": "erro", "detalhe": f"Pesquisa não encontrada: {id_pesquisa}"}

            try:
                # 1. Resolução dinâmica de credenciais e clientes
                jina_key = _clean_key(await resolve_key(db, "JINA_API_KEY", self.transport)) or "jina-mock-key"
                jina_base_url = _clean_key(await resolve_jina_base_url(db, self.transport))
                llm_key = _clean_key(await resolve_key(db, "OPENAI_API_KEY", self.transport)) or "openai-mock-key"
                llm_base_url = _clean_key(await resolve_key(db, "LLM_BASE_URL", self.transport))
                model_light = _clean_key(await resolve_key(db, "LLM_MODEL_LIGHT", self.transport))
                model_strong = _clean_key(await resolve_key(db, "LLM_MODEL_STRONG", self.transport))
                personas = None if self.transport else await resolve_personas(db)

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
                    personas=personas,
                )
                auditor = Auditor(
                    research_repo=repo,
                    llm_client=llm_client,
                    personas=personas,
                )
                writer = Writer(
                    research_repo=repo,
                    llm_client=llm_client,
                    webhook_client=webhook_client,
                    callback_url=resolved_callback,
                    personas=personas,
                )

                # 2. Ciclo de Busca e Auditoria com Retentativas Automáticas
                max_ciclos = 4
                for ciclo in range(1, max_ciclos + 1):
                    logger.info(f"[PipelineRunner] Iniciando ciclo de busca {ciclo} para {id_pesquisa}...")
                    await repo.update_pipeline_status(id_pesquisa, "buscando")
                    await searcher.execute_search(id_pesquisa=id_pesquisa)

                    logger.info(f"[PipelineRunner] Iniciando auditoria para {id_pesquisa}...")
                    await repo.update_pipeline_status(id_pesquisa, "auditando")
                    audit_res = await auditor.execute_audit(id_pesquisa=id_pesquisa)

                    reprovados = audit_res.get("reprovados", 0)
                    if reprovados == 0:
                        logger.info(f"[PipelineRunner] Todos os pontos foram aprovados na auditoria!")
                        break

                    # Verifica se algum ponto atingiu o teto
                    pontos = await repo.list_points(id_pesquisa)
                    atingiu_teto = any((p.tentativas or 0) >= 4 or (p.tentativas_auditoria or 0) >= 3 for p in pontos)
                    if atingiu_teto or ciclo == max_ciclos:
                        logger.info(f"[PipelineRunner] Teto de tentativas atingido. Prosseguindo para redação com o melhor acervo.")
                        break

                # 3. Redação Final e Despacho ao Webhook
                logger.info(f"[PipelineRunner] Iniciando redação final para {id_pesquisa}...")
                await repo.update_pipeline_status(id_pesquisa, "redigindo")
                writer_res = None
                for w_attempt in range(1, 4):
                    try:
                        writer_res = await writer.execute_writer(id_pesquisa=id_pesquisa)
                        break
                    except Exception as w_exc:
                        # NO_EVIDENCE_COLLECTED é determinístico: retry não cria evidência web (RF-08)
                        if "NO_EVIDENCE_COLLECTED" in str(w_exc) or w_attempt == 3:
                            raise
                        logger.warning(
                            f"[PipelineRunner] Tentativa {w_attempt} do Redator falhou: {w_exc}. Retentando em 5s..."
                        )
                        await asyncio.sleep(5)

                await repo.update_pipeline_status(id_pesquisa, "concluido")
                logger.info(f"[PipelineRunner] Pesquisa {id_pesquisa} concluída com sucesso!")
                return writer_res or {}

            except Exception as exc:
                from app.tools.errors import JinaError

                erro_msg = str(exc)
                # RF-09/CA-09.1: falha de provedor recebe categoria e ação corretiva no pipeline
                if isinstance(exc, JinaError):
                    erro_msg = (
                        f"{type(exc).__name__} [HTTP {exc.http_status}/{exc.categoria}]: {exc} "
                        f"| Ação: {exc.acao_corretiva}"
                    )
                logger.error(f"[PipelineRunner] Falha na execução da pesquisa {id_pesquisa}: {erro_msg}", exc_info=True)
                await repo.update_pipeline_status(id_pesquisa, "falha", erro_pipeline=erro_msg)
                return {"status": "falha", "erro": erro_msg}
