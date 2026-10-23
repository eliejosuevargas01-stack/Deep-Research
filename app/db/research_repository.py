"""Repositório de persistência e consulta do pipeline de pesquisa profunda.

Implementa operações assíncronas para criação de pesquisa, listagem/atualização de pontos,
armazenamento de conteúdo coletado sem truncamento e deduplicação de URLs.
Atende a RF-02, RF-04, RF-05, RF-06 e RF-08.
"""

from datetime import datetime, timezone
import json
from typing import Any, List, Optional, Set
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ConteudoColetado, Pesquisa, Ponto


class ResearchRepository:
    """Repositório de acesso a dados para pesquisas, pontos e coletas."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_research(
        self,
        tema: str,
        pontos_textos: List[str],
        id_pesquisa: Optional[str] = None,
        reasoning_planejamento: Optional[str] = None,
    ) -> Pesquisa:
        """Cria uma nova pesquisa raiz e persiste os N pontos formulados com status 'pendente'."""
        if not tema or not tema.strip():
            raise ValueError("O tema da pesquisa não pode ser vazio.")
        if not pontos_textos:
            raise ValueError("A lista de pontos não pode ser vazia.")

        pesquisa_id = id_pesquisa or str(uuid.uuid4())
        agora = datetime.now(timezone.utc).isoformat()

        pesquisa = Pesquisa(
            id_pesquisa=pesquisa_id,
            tema=tema.strip(),
            criado_em=agora,
        )
        self.session.add(pesquisa)

        for i, texto_ponto in enumerate(pontos_textos, start=1):
            ponto = Ponto(
                ponto_id=str(uuid.uuid4()),
                id_pesquisa=pesquisa_id,
                tema=tema.strip(),
                ponto_n=i,
                ponto=texto_ponto.strip(),
                status="pendente",
                reasoning_planejamento=reasoning_planejamento,
                criado_em=agora,
                atualizado_em=agora,
            )
            self.session.add(ponto)

        await self.session.commit()
        await self.session.refresh(pesquisa)
        return pesquisa

    async def get_research(self, id_pesquisa: str) -> Optional[Pesquisa]:
        """Obtém os dados da pesquisa pelo identificador canônico."""
        stmt = select(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_research_dossier(
        self,
        id_pesquisa: str,
        dossier_final: str,
        reasoning_dossier: Optional[str] = None,
        webhook_status: Optional[str] = None,
        webhook_resposta: Optional[str] = None,
    ) -> Optional[Pesquisa]:
        """Grava o dossiê Markdown final e registra os metadados de envio ao webhook."""
        stmt = select(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa)
        result = await self.session.execute(stmt)
        pesquisa = result.scalar_one_or_none()
        if not pesquisa:
            return None

        pesquisa.dossier_final = dossier_final
        if reasoning_dossier is not None:
            pesquisa.reasoning_dossier = reasoning_dossier
        pesquisa.concluido_em = datetime.now(timezone.utc).isoformat()
        pesquisa.status_pipeline = "concluido"
        if webhook_status is not None:
            pesquisa.webhook_status = webhook_status
        if webhook_resposta is not None:
            pesquisa.webhook_resposta = webhook_resposta

        await self.session.commit()
        await self.session.refresh(pesquisa)
        return pesquisa

    async def update_pipeline_status(
        self,
        id_pesquisa: str,
        status_pipeline: str,
        erro_pipeline: Optional[str] = None,
    ) -> Optional[Pesquisa]:
        """Atualiza o estágio atual de execução do pipeline assíncrono."""
        stmt = select(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa)
        result = await self.session.execute(stmt)
        pesquisa = result.scalar_one_or_none()
        if not pesquisa:
            return None
        pesquisa.status_pipeline = status_pipeline
        if erro_pipeline is not None:
            pesquisa.erro_pipeline = erro_pipeline
        await self.session.commit()
        await self.session.refresh(pesquisa)
        return pesquisa

    async def list_points(self, id_pesquisa: str) -> List[Ponto]:
        """Lista os pontos de investigação de uma pesquisa ordenados por ponto_n."""
        stmt = select(Ponto).where(Ponto.id_pesquisa == id_pesquisa).order_by(Ponto.ponto_n.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_point(self, ponto_id: str) -> Optional[Ponto]:
        """Obtém um ponto específico pelo seu identificador."""
        stmt = select(Ponto).where(Ponto.ponto_id == ponto_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_point_status(
        self,
        ponto_id: str,
        status: str,
        pontos_fracos: Optional[Any] = None,
        incrementar_tentativa: bool = False,
        reasoning_auditoria: Optional[str] = None,
    ) -> Optional[Ponto]:
        """Atualiza o status operacional do ponto e anota pontos fracos apontados pela auditoria."""
        stmt = select(Ponto).where(Ponto.ponto_id == ponto_id)
        result = await self.session.execute(stmt)
        ponto = result.scalar_one_or_none()
        if not ponto:
            return None

        ponto.status = status
        if pontos_fracos is not None:
            if isinstance(pontos_fracos, list):
                ponto.pontos_fracos = "\n".join(f"- {item}" for item in pontos_fracos)
            elif isinstance(pontos_fracos, dict):
                ponto.pontos_fracos = json.dumps(pontos_fracos, ensure_ascii=False)
            else:
                ponto.pontos_fracos = str(pontos_fracos)

        if reasoning_auditoria is not None:
            ponto.reasoning_auditoria = reasoning_auditoria

        if incrementar_tentativa:
            ponto.tentativas_auditoria = (ponto.tentativas_auditoria or 0) + 1

        ponto.atualizado_em = datetime.now(timezone.utc).isoformat()

        await self.session.commit()
        await self.session.refresh(ponto)
        return ponto

    async def save_collected_content(
        self,
        id_pesquisa: str,
        ponto_id: str,
        tema: str,
        ponto: str,
        conteudo_coletado: str,
        urls_lidas: List[str],
        urls_fonte: List[str],
        reasoning_coleta: Optional[str] = None,
        status_ponto: Optional[str] = None,
        diagnostico_falha: Optional[str] = None,
    ) -> ConteudoColetado:
        """Salva a coleta da rodada atual sem sobrescrever coletas anteriores, mantendo histórico.

        `status_ponto`/`diagnostico_falha` (RF-04/RF-06) registram a coleta falha
        sem apagar coletas anteriores: a rodada fica como evidência do problema e a
        coleta válida de rodadas anteriores continua consultável.
        """
        agora = datetime.now(timezone.utc).isoformat()
        urls_lidas_json = json.dumps(urls_lidas, ensure_ascii=False)
        urls_fonte_json = json.dumps(urls_fonte, ensure_ascii=False)

        # Determina a rodada atual a partir do histórico já salvo
        stmt_count = select(func.count(ConteudoColetado.id)).where(
            ConteudoColetado.id_pesquisa == id_pesquisa,
            ConteudoColetado.ponto_id == ponto_id,
        )
        count_res = await self.session.execute(stmt_count)
        rodada_atual = (count_res.scalar() or 0) + 1

        record = ConteudoColetado(
            id=str(uuid.uuid4()),
            id_pesquisa=id_pesquisa,
            ponto_id=ponto_id,
            rodada=rodada_atual,
            tema=tema,
            ponto=ponto,
            conteudo_coletado=conteudo_coletado,
            reasoning_coleta=reasoning_coleta,
            urls_lidas=urls_lidas_json,
            urls_fonte=urls_fonte_json,
            criado_em=agora,
        )
        self.session.add(record)

        # Atualiza status do ponto e incrementa tentativas de busca.
        # RF-06/CA-06.1: status e diagnóstico informados prevalecem sobre o padrão;
        # RF-06/CA-06.3: o histórico de coletas anteriores nunca é apagado.
        ponto_stmt = select(Ponto).where(Ponto.ponto_id == ponto_id)
        ponto_res = await self.session.execute(ponto_stmt)
        ponto_obj = ponto_res.scalar_one_or_none()
        if ponto_obj:
            ponto_obj.tentativas = (ponto_obj.tentativas or 0) + 1
            if status_ponto is not None:
                ponto_obj.status = status_ponto
            elif ponto_obj.status in ("pendente", "em_andamento", "reprovado", "falha_coleta"):
                ponto_obj.status = "coletado"
            if diagnostico_falha is not None:
                ponto_obj.pontos_fracos = diagnostico_falha
            ponto_obj.atualizado_em = agora

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_collected_content_for_point(
        self,
        id_pesquisa: str,
        ponto_id: str,
    ) -> List[ConteudoColetado]:
        """Retorna todas as coletas (histórico de rodadas) para um ponto específico ordenadas por rodada."""
        stmt = (
            select(ConteudoColetado)
            .where(
                ConteudoColetado.id_pesquisa == id_pesquisa,
                ConteudoColetado.ponto_id == ponto_id,
            )
            .order_by(ConteudoColetado.rodada.asc(), ConteudoColetado.criado_em.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_last_coleta_evidence(
        self,
        id_pesquisa: str,
        ponto_id: str,
    ) -> Optional[ConteudoColetado]:
        """Devolve a última coleta do ponto com evidência web real (RF-07).

        A auditoria delibera sobre fontes efetivamente lidas, não sobre o volume textual
        da rodada mais recente: uma rodada `falha_coleta` fica visível no histórico mas
        nunca reabilita um ponto sem URLs lidas.
        """
        rodadas = await self.get_collected_content_for_point(id_pesquisa, ponto_id)
        for record in reversed(rodadas):
            try:
                urls_lidas = json.loads(record.urls_lidas) if record.urls_lidas else []
            except Exception:
                urls_lidas = []
            if isinstance(urls_lidas, list) and len(urls_lidas) > 0:
                return record
        return None

    async def get_collected_content(self, id_pesquisa: str) -> List[ConteudoColetado]:
        """Retorna todos os conteúdos coletados para uma pesquisa."""
        stmt = select(ConteudoColetado).where(ConteudoColetado.id_pesquisa == id_pesquisa)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ponytail: desserialização in-memory de JSON; migrar para tabela de junção se volume > 10.000 URLs/pesquisa
    async def get_read_urls(self, id_pesquisa: str) -> Set[str]:
        """Retorna o conjunto de URLs já consultadas na pesquisa para deduplicação (RN-04)."""
        stmt = select(ConteudoColetado.urls_lidas).where(ConteudoColetado.id_pesquisa == id_pesquisa)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        read_urls: Set[str] = set()
        for urls_json in rows:
            if urls_json:
                try:
                    urls_list = json.loads(urls_json)
                    if isinstance(urls_list, list):
                        read_urls.update(urls_list)
                except Exception:
                    pass
        return read_urls
