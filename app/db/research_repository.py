"""Repositório de persistência e consulta do pipeline de pesquisa profunda.

Implementa operações assíncronas para criação de pesquisa, listagem/atualização de pontos,
armazenamento de conteúdo coletado sem truncamento, deduplicação de URLs e persistência
atômica de telemetria e plano estruturado.

Atende a RF-02, RF-04, RF-05, RF-06, RF-08, DR-005, DR-006, DR-013 e DR-015.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Coroutine, Dict, List, Optional, Set, Union
import uuid
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
from app.db.models import (
    ConteudoColetado,
    GenerationAttempt,
    Pesquisa,
    Ponto,
)


def _format_iso_utc(dt: Optional[datetime] = None) -> str:
    """Retorna timestamp ISO 8601 UTC estritamente de 27 caracteres (%Y-%m-%dT%H:%M:%S.%fZ),
    compatível com VARCHAR(30) e com ordenação lexicográfica precisa."""
    d = dt or datetime.now(timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    else:
        d = d.astimezone(timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def normalize_iso_utc(ts: Union[str, datetime]) -> str:
    """Normaliza qualquer timestamp ISO/legado para ISO 8601 UTC estrito com 27 caracteres (%Y-%m-%dT%H:%M:%S.%fZ).

    Converte fusos horários legados com offset (ex: -03:00) para o instante correspondente em UTC,
    garantindo compatibilidade lexicográfica (< lease_cutoff) e conformidade com VARCHAR(30).
    """
    if isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, str):
        s = ts.strip()
        if not s:
            raise ValueError("Timestamp vazio")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.fromisoformat(s.replace(" ", "T"))
    else:
        raise TypeError(f"Tipo inválido para timestamp: {type(ts)}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _shield_and_wait(coro: Coroutine[Any, Any, Any]) -> Any:
    """Executa e aguarda uma corrotina blindada contra cancelamento, garantindo que
    o commit ou operação em andamento seja concluído antes de propagar cancelamento externo.
    Evita commits em background após fechamento de sessão."""
    task = asyncio.create_task(coro)
    was_cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            was_cancelled = True
    exc = task.exception()
    if exc is not None:
        raise exc
    if was_cancelled:
        raise asyncio.CancelledError()
    return task.result()


def _map_downstream_router_mutations(val: Any) -> Optional[bool]:
    """Preserva None para valores desconhecidos ou unobserved e bool estrito quando observado."""
    if isinstance(val, bool):
        return val
    return None


class ResearchRepository:
    """Repositório de acesso a dados para pesquisas, pontos e coletas."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _accumulate_tokens(
        self,
        id_pesquisa: Optional[str],
        usage: Any,
    ) -> None:
        if not id_pesquisa or not usage:
            return
        if isinstance(usage, str):
            try:
                usage = json.loads(usage)
            except Exception:
                return
        if not isinstance(usage, dict):
            return
        p = usage.get("prompt_tokens") or usage.get("input_tokens") or usage.get("promptTokens")
        c = usage.get("completion_tokens") or usage.get("output_tokens") or usage.get("completionTokens")
        t = usage.get("total_tokens") or usage.get("totalTokens")
        try:
            p_int = int(p) if p is not None else 0
            c_int = int(c) if c is not None else 0
            t_int = int(t) if t is not None else (p_int + c_int)
        except Exception:
            return
        if p_int == 0 and c_int == 0 and t_int == 0:
            return
        from sqlalchemy import update
        await self.session.execute(
            update(Pesquisa)
            .where(Pesquisa.id_pesquisa == id_pesquisa)
            .values(
                tokens_prompt=func.coalesce(Pesquisa.tokens_prompt, 0) + p_int,
                tokens_completion=func.coalesce(Pesquisa.tokens_completion, 0) + c_int,
                tokens_total=func.coalesce(Pesquisa.tokens_total, 0) + t_int,
            )
        )

    async def create_research(
        self,
        tema: str,
        pontos_textos: List[str],
        id_pesquisa: Optional[str] = None,
        reasoning_planejamento: Optional[str] = None,
        plano_estruturado: Optional[Dict[str, Any]] = None,
        metadados_planejamento: Optional[Dict[str, Any]] = None,
        eixos_estruturados: Optional[List[Dict[str, Any]]] = None,
        generation_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> Pesquisa:
        """Cria uma nova pesquisa raiz e persiste pontos e telemetria em transação única e atômica."""
        if not tema or not tema.strip():
            raise ValueError("O tema da pesquisa não pode ser vazio.")
        if not pontos_textos:
            raise ValueError("A lista de pontos não pode ser vazia.")

        pesquisa_id = id_pesquisa or str(uuid.uuid4())
        agora = _format_iso_utc()

        try:
            plano_json = json.dumps(plano_estruturado, ensure_ascii=False) if plano_estruturado else None
            meta_json = json.dumps(metadados_planejamento, ensure_ascii=False) if metadados_planejamento else None

            pesquisa = Pesquisa(
                id_pesquisa=pesquisa_id,
                tema=tema.strip(),
                criado_em=agora,
                plano_estruturado=plano_json,
                metadados_planejamento=meta_json,
            )
            self.session.add(pesquisa)

            for i, texto_ponto in enumerate(pontos_textos, start=1):
                eixo_json = None
                if eixos_estruturados and len(eixos_estruturados) >= i:
                    eixo_json = json.dumps(eixos_estruturados[i - 1], ensure_ascii=False)

                ponto = Ponto(
                    ponto_id=str(uuid.uuid4()),
                    id_pesquisa=pesquisa_id,
                    tema=tema.strip(),
                    ponto_n=i,
                    ponto=texto_ponto.strip(),
                    status="pendente",
                    reasoning_planejamento=reasoning_planejamento,
                    eixo_estruturado=eixo_json,
                    criado_em=agora,
                    atualizado_em=agora,
                )
                self.session.add(ponto)

            if generation_attempts:
                for att_data in generation_attempts:
                    msgs = att_data.get("messages", [])
                    msgs_str = json.dumps(msgs, ensure_ascii=False) if isinstance(msgs, (list, dict)) else str(msgs or "[]")

                    req_params = att_data.get("request_params")
                    req_params_str = json.dumps(req_params, ensure_ascii=False) if req_params is not None else None

                    att_record = GenerationAttempt(
                        id=att_data.get("id") or str(uuid.uuid4()),
                        id_pesquisa=pesquisa_id,
                        ponto_id=att_data.get("ponto_id"),
                        etapa=att_data.get("etapa", "plan"),
                        persona=att_data.get("persona"),
                        model_requested=att_data.get("model_requested", ""),
                        model_used=att_data.get("model_used"),
                        prompt_hash=att_data.get("prompt_hash", ""),
                        prompt_version=att_data.get("prompt_version"),
                        system_message=att_data.get("system_message"),
                        messages_json=msgs_str,
                        content_final=att_data.get("content_final"),
                        reasoning_content=att_data.get("reasoning_content"),
                        finish_reason=att_data.get("finish_reason"),
                        is_regular_finish=bool(att_data.get("is_regular_finish", False)),
                        usage_json=json.dumps(att_data.get("usage"), ensure_ascii=False) if att_data.get("usage") else None,
                        cost_estimated=att_data.get("cost_estimated"),
                        cost_currency=att_data.get("cost_currency"),
                        cost_source=att_data.get("cost_source"),
                        request_params_json=req_params_str,
                        downstream_router_mutations=_map_downstream_router_mutations(att_data.get("downstream_router_mutations")),
                        latency_seconds=float(att_data.get("latency_seconds", 0.0)),
                        attempts=int(att_data.get("attempts", 1)),
                        errors_json=json.dumps(att_data.get("errors"), ensure_ascii=False) if att_data.get("errors") else None,
                        tool_calls_json=json.dumps(att_data.get("tool_calls"), ensure_ascii=False) if att_data.get("tool_calls") else None,
                        criado_em=att_data.get("criado_em") or agora,
                    )
                    self.session.add(att_record)
                    try:
                        usage_u = att_data.get("usage")
                        if isinstance(usage_u, str):
                            try:
                                usage_u = json.loads(usage_u)
                            except Exception:
                                usage_u = None
                        if isinstance(usage_u, dict):
                            pu = usage_u.get("prompt_tokens") or usage_u.get("input_tokens") or usage_u.get("promptTokens") or 0
                            cu = usage_u.get("completion_tokens") or usage_u.get("output_tokens") or usage_u.get("completionTokens") or 0
                            tu = usage_u.get("total_tokens") or usage_u.get("totalTokens") or (int(pu or 0) + int(cu or 0))
                            try:
                                pesquisa.tokens_prompt = int(getattr(pesquisa, "tokens_prompt", 0) or 0) + int(pu or 0)
                                pesquisa.tokens_completion = int(getattr(pesquisa, "tokens_completion", 0) or 0) + int(cu or 0)
                                pesquisa.tokens_total = int(getattr(pesquisa, "tokens_total", 0) or 0) + int(tu or 0)
                            except Exception:
                                pass
                    except Exception:
                        pass

            await self.session.commit()
            await self.session.refresh(pesquisa)
            return pesquisa
        except Exception:
            await self.session.rollback()
            raise

    async def get_research(self, id_pesquisa: str) -> Optional[Pesquisa]:
        """Obtém os dados da pesquisa pelo identificador canônico."""
        stmt = (
            select(Pesquisa)
            .where(Pesquisa.id_pesquisa == id_pesquisa)
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_research_dossier(
        self,
        id_pesquisa: str,
        dossier_final: str,
        reasoning_dossier: Optional[str] = None,
        webhook_status: Optional[str] = None,
        webhook_resposta: Optional[str] = None,
        status_pipeline: Optional[str] = None,
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
        pesquisa.concluido_em = _format_iso_utc()
        if status_pipeline is not None:
            pesquisa.status_pipeline = status_pipeline
        elif not pesquisa.status_pipeline or pesquisa.status_pipeline in ("planejado", "buscando", "auditando", "redigindo"):
            pesquisa.status_pipeline = "concluido"
        if webhook_status is not None:
            pesquisa.webhook_status = webhook_status
        if webhook_resposta is not None:
            pesquisa.webhook_resposta = webhook_resposta

        await self.session.commit()
        await self.session.refresh(pesquisa)
        return pesquisa

    async def set_research_tokens(
        self,
        id_pesquisa: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> Optional[Pesquisa]:
        """Grava o consumo do ciclo (usage.json do processo Hermes) na pesquisa."""
        stmt = select(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa)
        pesquisa = (await self.session.execute(stmt)).scalar_one_or_none()
        if not pesquisa:
            return None
        pesquisa.tokens_prompt = int(prompt_tokens or 0)
        pesquisa.tokens_completion = int(completion_tokens or 0)
        pesquisa.tokens_total = int(total_tokens or 0)
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
        stmt = (
            select(Ponto)
            .where(Ponto.id_pesquisa == id_pesquisa)
            .order_by(Ponto.ponto_n.asc())
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_point(self, ponto_id: str) -> Optional[Ponto]:
        """Obtém um ponto específico pelo seu identificador."""
        stmt = (
            select(Ponto)
            .where(Ponto.ponto_id == ponto_id)
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _sync_pipeline_status_in_tx(
        self,
        id_pesquisa: str,
        force_status: Optional[str] = None,
    ) -> str:
        """Sincroniza o status_pipeline da pesquisa derivando atomicamente de escalares frescos na mesma transação.

        Nota sobre PostgreSQL e Concorrência:
        - Bloqueia a linha da pesquisa (`SELECT ... FOR UPDATE`) serializando a sincronização agregada
          da pesquisa corrente sem criar deadlocks circulares (bloqueio atômico de recurso único em ordem fixa).
        - Escopo de validação atual: comprovado contratualmente via compilação SQL (dialeto PostgreSQL) e
          comportamentalmente via concorrência multissessão em SQLite com WAL. Não há instância ativa de PostgreSQL
          neste ambiente de testes unitários; comportamentos de MVCC sob Read Committed/Repeatable Read
          devem ser verificados em suite com PostgreSQL real, sem prometer mais do que o escopo testado comprova.
        """
        stmt_lock = (
            select(Pesquisa.id_pesquisa)
            .where(Pesquisa.id_pesquisa == id_pesquisa)
            .with_for_update()
        )
        await self.session.execute(stmt_lock)

        if force_status:
            novo_status = force_status
        else:
            stmt = select(Ponto.status).where(Ponto.id_pesquisa == id_pesquisa)
            res = await self.session.execute(stmt)
            statuses = list(res.scalars().all())
            if not statuses:
                novo_status = "planejado"
            elif any(s == "em_andamento" for s in statuses):
                novo_status = "buscando"
            elif any(s == "auditando" for s in statuses):
                novo_status = "auditando"
            elif all(s == "aprovado" for s in statuses):
                novo_status = "auditado"
            elif all(s in ("coletado", "aprovado") for s in statuses):
                novo_status = "coletado"
            elif all(s in ("falha_coleta", "falha") for s in statuses):
                novo_status = "falha"
            elif any(s == "reprovado" for s in statuses):
                novo_status = "reprovado"
            else:
                novo_status = "parcial"

        stmt_up = (
            update(Pesquisa)
            .where(Pesquisa.id_pesquisa == id_pesquisa)
            .values(status_pipeline=novo_status)
        )
        await self.session.execute(stmt_up)
        return novo_status

    async def get_points_status_summary(self, id_pesquisa: str) -> Dict[str, Any]:
        """Obtém resumo escalar fresco dos status dos pontos e status da pesquisa sem mutação."""
        stmt = select(Ponto.status).where(Ponto.id_pesquisa == id_pesquisa)
        statuses = list((await self.session.execute(stmt)).scalars().all())
        stmt_pesq = select(Pesquisa.status_pipeline).where(Pesquisa.id_pesquisa == id_pesquisa)
        status_pesq = (await self.session.execute(stmt_pesq)).scalar_one_or_none() or "planejado"
        total_falhas = sum(1 for s in statuses if s in ("falha_coleta", "falha"))
        return {
            "statuses": statuses,
            "status_pipeline": status_pesq,
            "total_falhas_coleta": total_falhas,
        }

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
        if status == "aprovado":
            ponto.pontos_fracos = None
        elif pontos_fracos is not None:
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

        ponto.atualizado_em = _format_iso_utc()

        await self.session.commit()
        await self.session.refresh(ponto)
        return ponto

    async def reserve_point(
        self,
        ponto_id: str,
        lease_seconds: int = 600,
        lease_token: Optional[str] = None,
    ) -> Ponto:
        """Reserva atômica de ponto antes de qualquer I/O com lease temporário (DR-004, DR-012).

        Impede concorrência de requisições sobre o mesmo ponto e impõe teto de 4 tentativas.
        """
        now_dt = datetime.now(timezone.utc)
        agora = _format_iso_utc(now_dt)
        lease_cutoff = _format_iso_utc(now_dt - timedelta(seconds=lease_seconds))
        token = lease_token or uuid.uuid4().hex

        stmt_check = select(Ponto).where(Ponto.ponto_id == ponto_id)
        res_check = await self.session.execute(stmt_check)
        ponto = res_check.scalar_one_or_none()
        if not ponto:
            raise ValueError(f"Ponto {ponto_id} não localizado.")

        if (ponto.tentativas or 0) >= 4:
            if ponto.status == "em_andamento" and ponto.atualizado_em < lease_cutoff:
                # Abandono da quarta tentativa deve terminar como falha
                stmt_expire_4 = (
                    update(Ponto)
                    .where(
                        Ponto.ponto_id == ponto_id,
                        Ponto.tentativas >= 4,
                        Ponto.status == "em_andamento",
                        Ponto.atualizado_em < lease_cutoff,
                    )
                    .values(
                        status="falha",
                        pontos_fracos="Limite máximo de 4 tentativas esgotado e reserva expirada.",
                        atualizado_em=agora,
                        lease_token=None,
                    )
                )
                await self.session.execute(stmt_expire_4)
                await self._sync_pipeline_status_in_tx(ponto.id_pesquisa)
                await _shield_and_wait(self.session.commit())
            raise ValueError(
                f"MAX_ATTEMPTS_EXCEEDED: O ponto {ponto_id} já esgotou o limite máximo de 4 tentativas "
                "de busca (1 inicial + 3 retentativas pós-reprovação)."
            )

        stmt = (
            update(Ponto)
            .where(
                Ponto.ponto_id == ponto_id,
                Ponto.tentativas < 4,
                or_(
                    ~Ponto.status.in_(["em_andamento", "auditando"]),
                    Ponto.atualizado_em < lease_cutoff,
                ),
            )
            .values(
                status="em_andamento",
                tentativas=Ponto.tentativas + 1,
                atualizado_em=agora,
                lease_token=token,
            )
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            await _shield_and_wait(self.session.commit())
            ponto_atual = await self.get_point(ponto_id)
            if ponto_atual and (ponto_atual.tentativas or 0) >= 4:
                raise ValueError(
                    f"MAX_ATTEMPTS_EXCEEDED: O ponto {ponto_id} já esgotou o limite máximo de 4 tentativas "
                    "de busca (1 inicial + 3 retentativas pós-reprovação)."
                )
            raise ValueError(
                f"CONCURRENT_EXECUTION: Ponto {ponto_id} já está em andamento por outra requisição."
            )

        # Na reserva com posse comprovada, reflete 'buscando' e invalida dossiê no mesmo commit
        stmt_pesq = (
            update(Pesquisa)
            .where(Pesquisa.id_pesquisa == ponto.id_pesquisa)
            .values(dossier_final=None, concluido_em=None, metadados_redacao=None, status_pipeline="buscando")
        )
        await self.session.execute(stmt_pesq)
        await _shield_and_wait(self.session.commit())

        await _shield_and_wait(self.session.refresh(ponto))
        return ponto

    async def release_point_reservation(
        self,
        ponto_id: str,
        status: str = "falha_coleta",
        diagnostic: Optional[str] = None,
        expected_tentativa: Optional[int] = None,
        expected_token: Optional[str] = None,
    ) -> bool:
        """Libera a reserva atômica do ponto após cancelamento, timeout ou erro fatal protegida por tentativa e token."""
        # Recuperação preventiva de sessão abortada por erro prévio
        if self.session.is_active:
            sync_tx = getattr(getattr(self.session, "sync_session", None), "_transaction", None)
            if sync_tx is not None and not getattr(sync_tx, "is_active", True):
                try:
                    await self.session.rollback()
                except Exception:
                    pass

        agora = _format_iso_utc()
        conditions = [Ponto.ponto_id == ponto_id, Ponto.status == "em_andamento"]
        if expected_tentativa is not None:
            conditions.append(Ponto.tentativas == expected_tentativa)
        if expected_token is not None:
            conditions.append(
                or_(
                    Ponto.lease_token == expected_token,
                    and_(Ponto.lease_token.is_(None), Ponto.atualizado_em == expected_token),
                )
            )

        stmt = (
            update(Ponto)
            .where(*conditions)
            .values(
                status=status,
                pontos_fracos=diagnostic,
                atualizado_em=agora,
                lease_token=None,
            )
        )
        res = await self.session.execute(stmt)
        if res.rowcount > 0:
            p_stmt = select(Ponto.id_pesquisa).where(Ponto.ponto_id == ponto_id)
            p_id_pesq = (await self.session.execute(p_stmt)).scalar_one_or_none()
            if p_id_pesq:
                await self._sync_pipeline_status_in_tx(p_id_pesq)
        await _shield_and_wait(self.session.commit())
        return res.rowcount > 0

    async def terminate_expired_audit_lease(
        self,
        ponto_id: str,
        lease_cutoff: str,
        diagnostico: str,
        criterios_minimos: int = 11,
    ) -> bool:
        """Consolida o encerramento atômico de lease expirada na 3ª tentativa de auditoria (DR-004, DR-012)."""
        agora = _format_iso_utc()
        stmt_term = (
            update(Ponto)
            .where(
                Ponto.ponto_id == ponto_id,
                Ponto.status == "auditando",
                Ponto.tentativas_auditoria >= 3,
                Ponto.atualizado_em < lease_cutoff,
            )
            .values(
                status="reprovado",
                pontos_fracos=diagnostico,
                atualizado_em=agora,
                lease_token=None,
            )
        )
        res_term = await self.session.execute(stmt_term)
        fence_ok = (res_term.rowcount > 0)
        if not fence_ok:
            return False

        # Invalida o dossiê da pesquisa
        p_stmt = select(Ponto.id_pesquisa).where(Ponto.ponto_id == ponto_id)
        p_id_pesq = (await self.session.execute(p_stmt)).scalar_one_or_none()
        if p_id_pesq:
            stmt_inv = (
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == p_id_pesq)
                .values(dossier_final=None, concluido_em=None, metadados_redacao=None)
            )
            await self.session.execute(stmt_inv)

        # Busca a coleta mais recente no instante do fence (não confia em ORM stale)
        stmt_last_coleta = (
            select(ConteudoColetado.id, ConteudoColetado.rodada)
            .where(ConteudoColetado.ponto_id == ponto_id)
            .order_by(ConteudoColetado.rodada.desc(), ConteudoColetado.criado_em.desc())
            .limit(1)
        )
        coleta_row = (await self.session.execute(stmt_last_coleta)).first()
        if coleta_row:
            coleta_id, rodada = coleta_row[0], coleta_row[1]
            stmt_meta_fresco = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta_id)
            raw_meta = (await self.session.execute(stmt_meta_fresco)).scalar_one_or_none()
            meta = {}
            if raw_meta:
                try:
                    meta = json.loads(raw_meta)
                except Exception:
                    meta = {}
            if "auditorias" not in meta or not isinstance(meta["auditorias"], list):
                meta["auditorias"] = []

            # Evita duplicar diagnóstico estruturado em repetições
            ja_registrado = any(
                isinstance(a, dict)
                and a.get("status") == "reprovado"
                and a.get("valido") is False
                and a.get("diagnostico") == diagnostico
                for a in meta["auditorias"]
            )
            if not ja_registrado:
                meta["auditorias"].append({
                    "id_auditoria": str(uuid.uuid4()),
                    "coleta_id": coleta_id,
                    "rodada": rodada,
                    "valido": False,
                    "aplicado": True,
                    "status": "reprovado",
                    "diagnostico": diagnostico,
                    "pontos_fracos": diagnostico,
                    "criterios": None,
                    "criterios_aprovados": 0,
                    "criterios_minimos": criterios_minimos,
                    "pontuacao_percentual": 0.0,
                    "resumo_auditoria": None,
                    "tarefas": None,
                    "antes_depois": None,
                    "criado_em": agora,
                })
                novo_meta_str = json.dumps(meta, ensure_ascii=False)
                stmt_upd_coleta = (
                    update(ConteudoColetado)
                    .where(ConteudoColetado.id == coleta_id)
                    .values(metadados_coleta=novo_meta_str)
                )
                await self.session.execute(stmt_upd_coleta)

                target_coleta = (
                    await self.session.execute(
                        select(ConteudoColetado)
                        .where(ConteudoColetado.id == coleta_id)
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                if target_coleta:
                    target_coleta.metadados_coleta = novo_meta_str

        if p_id_pesq:
            await self.session.flush()
            await self._sync_pipeline_status_in_tx(p_id_pesq)

        await self.session.commit()
        return True

    async def reserve_point_for_audit(
        self,
        ponto_id: str,
        lease_seconds: int = 600,
        lease_token: Optional[str] = None,
    ) -> str:
        """Reserva atômica de ponto para auditoria com lease temporário (DR-004, DR-012).

        Impede concorrência de requisições sobre o mesmo ponto e impõe teto de 3 tentativas de auditoria.
        """
        now_dt = datetime.now(timezone.utc)
        agora = _format_iso_utc(now_dt)
        lease_cutoff = _format_iso_utc(now_dt - timedelta(seconds=lease_seconds))
        audit_token = lease_token or uuid.uuid4().hex

        stmt_check = select(Ponto).where(Ponto.ponto_id == ponto_id)
        res_check = await self.session.execute(stmt_check)
        ponto = res_check.scalar_one_or_none()
        if not ponto:
            raise ValueError(f"Ponto {ponto_id} não localizado.")

        if (ponto.tentativas_auditoria or 0) >= 3:
            if ponto.status == "auditando" and (ponto.atualizado_em or "") < lease_cutoff:
                diag_exp = "Limite máximo de 3 tentativas de auditoria esgotado com lease expirada."
                await self.terminate_expired_audit_lease(ponto_id, lease_cutoff, diag_exp)
            raise ValueError(
                f"MAX_ATTEMPTS_EXCEEDED: O ponto {ponto_id} já esgotou o limite máximo de 3 tentativas de auditoria."
            )

        stmt = (
            update(Ponto)
            .where(
                Ponto.ponto_id == ponto_id,
                Ponto.tentativas_auditoria < 3,
                or_(
                    ~Ponto.status.in_(["em_andamento", "auditando"]),
                    Ponto.atualizado_em < lease_cutoff,
                ),
            )
            .values(
                status="auditando",
                tentativas_auditoria=Ponto.tentativas_auditoria + 1,
                atualizado_em=agora,
                lease_token=audit_token,
            )
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            await _shield_and_wait(self.session.commit())
            ponto_atual = await self.get_point(ponto_id)
            if ponto_atual and (ponto_atual.tentativas_auditoria or 0) >= 3:
                raise ValueError(
                    f"MAX_ATTEMPTS_EXCEEDED: O ponto {ponto_id} já esgotou o limite máximo de 3 tentativas de auditoria."
                )
            raise ValueError(
                f"CONCURRENT_EXECUTION: Ponto {ponto_id} já está em andamento/auditoria por outra requisição."
            )

        await self._sync_pipeline_status_in_tx(ponto.id_pesquisa)
        await _shield_and_wait(self.session.commit())
        await _shield_and_wait(self.session.refresh(ponto))
        return audit_token

    def _persist_generation_attempts_in_tx(
        self,
        id_pesquisa: str,
        ponto_id: Optional[str],
        generation_attempts: List[Any],
        agora: str,
        default_etapa: str = "audit",
        default_persona: Optional[str] = "auditor",
    ) -> tuple:
        """Persiste envelopes observados em GenerationAttempt de forma idempotente e estrita.
        Retorna (persisted_ids, usage_sum_dict)
        """
        persisted_ids: List[str] = []
        usage_sum = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for item in generation_attempts:
            if isinstance(item, GenerationAttempt):
                self.session.add(item)
                if item.id:
                    persisted_ids.append(item.id)
                continue

            if isinstance(item, dict) and "envelope" in item:
                env = item["envelope"]
                env_dict = env.to_dict() if hasattr(env, "to_dict") else (env if isinstance(env, dict) else {})
                att_item = dict(env_dict)
                att_item.update({k: v for k, v in item.items() if k != "envelope"})
            elif hasattr(item, "to_dict"):
                att_item = item.to_dict()
            elif isinstance(item, dict):
                att_item = item
            else:
                continue

            msgs = att_item.get("messages") or att_item.get("messages_sent", [])
            msgs_str = json.dumps(msgs, ensure_ascii=False) if isinstance(msgs, (list, dict)) else str(msgs or "[]")
            req_params = att_item.get("request_params")
            req_params_str = json.dumps(req_params, ensure_ascii=False) if req_params is not None else None
            sys_msg = att_item.get("system_message") or att_item.get("system_message_sent")

            rec_id = att_item.get("id") or str(uuid.uuid4())
            persisted_ids.append(rec_id)
            etapa = att_item.get("etapa") or default_etapa
            persona = att_item.get("persona")
            if not persona:
                content_check = (str(sys_msg or "") + " " + msgs_str).lower()
                if "auditor_redacao" in content_check or "avaliador_redacao" in content_check:
                    persona = "auditor_redacao"
                elif "redator final" in content_check:
                    persona = "redator final"
                else:
                    persona = default_persona
            att_record = GenerationAttempt(
                id=rec_id,
                id_pesquisa=id_pesquisa,
                ponto_id=ponto_id or att_item.get("ponto_id"),
                etapa=etapa,
                persona=persona,
                model_requested=att_item.get("model_requested", ""),
                model_used=att_item.get("model_used"),
                prompt_hash=att_item.get("prompt_hash", ""),
                prompt_version=att_item.get("prompt_version"),
                system_message=sys_msg,
                messages_json=msgs_str,
                content_final=att_item.get("content_final"),
                reasoning_content=att_item.get("reasoning_content"),
                finish_reason=att_item.get("finish_reason"),
                is_regular_finish=bool(att_item.get("is_regular_finish", False)),
                usage_json=json.dumps(att_item.get("usage"), ensure_ascii=False) if att_item.get("usage") else None,
                cost_estimated=att_item.get("cost_estimated"),
                cost_currency=att_item.get("cost_currency"),
                cost_source=att_item.get("cost_source"),
                request_params_json=req_params_str,
                downstream_router_mutations=_map_downstream_router_mutations(att_item.get("downstream_router_mutations")),
                latency_seconds=float(att_item.get("latency_seconds", 0.0)),
                attempts=int(att_item.get("attempts", 1)),
                errors_json=json.dumps(att_item.get("errors"), ensure_ascii=False) if att_item.get("errors") else None,
                tool_calls_json=json.dumps(att_item.get("tool_calls"), ensure_ascii=False) if att_item.get("tool_calls") else None,
                criado_em=att_item.get("criado_em") or att_item.get("created_at") or agora,
            )
            self.session.add(att_record)
            try:
                usage_u = att_item.get("usage")
                if isinstance(usage_u, str):
                    try:
                        usage_u = json.loads(usage_u)
                    except Exception:
                        usage_u = None
                if isinstance(usage_u, dict):
                    pu = usage_u.get("prompt_tokens") or usage_u.get("input_tokens") or usage_u.get("promptTokens") or 0
                    cu = usage_u.get("completion_tokens") or usage_u.get("output_tokens") or usage_u.get("completionTokens") or 0
                    tu = usage_u.get("total_tokens") or usage_u.get("totalTokens") or (int(pu or 0) + int(cu or 0))
                    try:
                        usage_sum["prompt_tokens"] += int(pu or 0)
                        usage_sum["completion_tokens"] += int(cu or 0)
                        usage_sum["total_tokens"] += int(tu or 0)
                    except Exception:
                        pass
                if id_pesquisa and isinstance(usage_u, dict):
                    try:
                        from sqlalchemy import inspect
                        insp = inspect(self.session)
                        for obj in insp.identity_map.values():
                            if isinstance(obj, Pesquisa) and getattr(obj, 'id_pesquisa', None) == id_pesquisa:
                                pu2 = usage_u.get("prompt_tokens") or usage_u.get("input_tokens") or usage_u.get("promptTokens") or 0
                                cu2 = usage_u.get("completion_tokens") or usage_u.get("output_tokens") or usage_u.get("completionTokens") or 0
                                tu2 = usage_u.get("total_tokens") or usage_u.get("totalTokens") or (int(pu2 or 0) + int(cu2 or 0))
                                try:
                                    obj.tokens_prompt = int(getattr(obj, 'tokens_prompt', 0) or 0) + int(pu2 or 0)
                                    obj.tokens_completion = int(getattr(obj, 'tokens_completion', 0) or 0) + int(cu2 or 0)
                                    obj.tokens_total = int(getattr(obj, 'tokens_total', 0) or 0) + int(tu2 or 0)
                                except Exception:
                                    pass
                                break
                    except Exception:
                        pass
            except Exception:
                pass
        return persisted_ids, usage_sum

    async def release_point_audit_reservation(
        self,
        ponto_id: str,
        expected_token: Optional[str] = None,
        expected_tentativa: Optional[int] = None,
        status: str = "coletado",
        diagnostico: Optional[str] = None,
        generation_attempts: Optional[List[Any]] = None,
        coleta_id: Optional[str] = None,
        rodada: Optional[int] = None,
    ) -> bool:
        """Libera a reserva atômica de auditoria do ponto após cancelamento, timeout ou erro."""
        # Recuperação preventiva de sessão abortada por erro prévio
        if self.session.is_active:
            sync_tx = getattr(getattr(self.session, "sync_session", None), "_transaction", None)
            if sync_tx is not None and not getattr(sync_tx, "is_active", True):
                try:
                    await self.session.rollback()
                except Exception:
                    pass

        agora = _format_iso_utc()
        conditions = [Ponto.ponto_id == ponto_id, Ponto.status == "auditando"]
        if expected_token is not None:
            conditions.append(
                or_(
                    Ponto.lease_token == expected_token,
                    and_(Ponto.lease_token.is_(None), Ponto.atualizado_em == expected_token),
                )
            )
        if expected_tentativa is not None:
            conditions.append(Ponto.tentativas_auditoria == expected_tentativa)

        update_values: Dict[str, Any] = {
            "status": status,
            "atualizado_em": agora,
            "lease_token": None,
        }
        if diagnostico is not None:
            update_values["pontos_fracos"] = diagnostico

        stmt = update(Ponto).where(*conditions).values(**update_values)
        res = await self.session.execute(stmt)

        p_stmt = select(Ponto.id_pesquisa).where(Ponto.ponto_id == ponto_id)
        p_id_pesq = (await self.session.execute(p_stmt)).scalar_one_or_none()

        persisted_ids: List[str] = []
        if generation_attempts and p_id_pesq:
            res_tx = self._persist_generation_attempts_in_tx(
                id_pesquisa=p_id_pesq,
                ponto_id=ponto_id,
                generation_attempts=generation_attempts,
                agora=agora,
            )
            if isinstance(res_tx, tuple):
                persisted_ids, usage_sum = res_tx[0], res_tx[1]
                if usage_sum and any((usage_sum.get(k) or 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                    try:
                        await self._accumulate_tokens(p_id_pesq, usage_sum)
                    except Exception:
                        pass
            else:
                persisted_ids = res_tx
        if coleta_id:
            stmt_meta_fresco = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta_id)
            raw_meta = (await self.session.execute(stmt_meta_fresco)).scalar_one_or_none()
            stmt_exists = select(ConteudoColetado.id, ConteudoColetado.rodada).where(ConteudoColetado.id == coleta_id)
            coleta_row = (await self.session.execute(stmt_exists)).first()
            if coleta_row:
                meta = {}
                if raw_meta:
                    try:
                        meta = json.loads(raw_meta)
                    except Exception:
                        meta = {}
                if "auditorias" not in meta or not isinstance(meta["auditorias"], list):
                    meta["auditorias"] = []
                meta["auditorias"].append({
                    "id_auditoria": str(uuid.uuid4()),
                    "coleta_id": coleta_id,
                    "rodada": rodada or coleta_row.rodada,
                    "valido": False,
                    "aplicado": (res.rowcount > 0),
                    "status": "reprovado",
                    "diagnostico": diagnostico or "Falha de chamada LLM",
                    "criterios": None,
                    "criterios_aprovados": 0,
                    "criterios_minimos": 11,
                    "pontuacao_percentual": 0.0,
                    "generation_attempt_ids": persisted_ids,
                    "criado_em": agora,
                })
                novo_meta_str = json.dumps(meta, ensure_ascii=False)
                stmt_upd_coleta = (
                    update(ConteudoColetado)
                    .where(ConteudoColetado.id == coleta_id)
                    .values(metadados_coleta=novo_meta_str)
                )
                await self.session.execute(stmt_upd_coleta)

                target_coleta = (
                    await self.session.execute(
                        select(ConteudoColetado)
                        .where(ConteudoColetado.id == coleta_id)
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                if target_coleta:
                    target_coleta.metadados_coleta = novo_meta_str

        if res.rowcount > 0 and p_id_pesq:
            await self._sync_pipeline_status_in_tx(p_id_pesq)

        await _shield_and_wait(self.session.commit())
        return res.rowcount > 0

    async def finalize_audit_point(
        self,
        ponto_id: str,
        coleta_id: str,
        expected_token: Optional[str] = None,
        expected_tentativa_audit: Optional[int] = None,
        expected_tentativa_search: Optional[int] = None,
        status: str = "aprovado",
        pontos_fracos: Optional[str] = None,
        criterios: Optional[List[Dict[str, Any]]] = None,
        auditoria_record: Optional[Dict[str, Any]] = None,
        generation_attempts: Optional[List[Any]] = None,
        reasoning_auditoria: Optional[str] = None,
    ) -> bool:
        """Finalização atômica da auditoria com verificação de fence real no banco via SQL CAS."""
        agora = _format_iso_utc()

        # 1. Verifica se a coleta avaliada ainda é a mais recente do ponto
        stmt_last_coleta = (
            select(ConteudoColetado.id)
            .where(ConteudoColetado.ponto_id == ponto_id)
            .order_by(ConteudoColetado.rodada.desc(), ConteudoColetado.criado_em.desc())
            .limit(1)
        )
        latest_coleta_id = (await self.session.execute(stmt_last_coleta)).scalar_one_or_none()
        is_coleta_current = (latest_coleta_id == coleta_id)

        # 2. Executa atualização condicionada no banco via SQL CAS
        cas_conditions = [
            Ponto.ponto_id == ponto_id,
            Ponto.status == "auditando",
        ]
        if expected_token is not None:
            cas_conditions.append(
                or_(
                    Ponto.lease_token == expected_token,
                    and_(Ponto.lease_token.is_(None), Ponto.atualizado_em == expected_token),
                )
            )
        if expected_tentativa_audit is not None:
            cas_conditions.append(Ponto.tentativas_auditoria == expected_tentativa_audit)
        if expected_tentativa_search is not None:
            cas_conditions.append(Ponto.tentativas == expected_tentativa_search)

        fence_passed = False
        p_stmt = select(Ponto.id_pesquisa).where(Ponto.ponto_id == ponto_id)
        p_id_pesq = (await self.session.execute(p_stmt)).scalar_one_or_none()

        if is_coleta_current:
            update_vals: Dict[str, Any] = {
                "status": status,
                "pontos_fracos": pontos_fracos if status == "reprovado" else None,
                "atualizado_em": agora,
                "lease_token": None,
            }
            if reasoning_auditoria is not None:
                update_vals["reasoning_auditoria"] = reasoning_auditoria
            stmt_update_ponto = (
                update(Ponto)
                .where(*cas_conditions)
                .values(**update_vals)
            )
            res = await self.session.execute(stmt_update_ponto)
            fence_passed = (res.rowcount > 0)

        # 3. Salva os envelopes de geração observados sempre
        persisted_ids: List[str] = []
        if generation_attempts and p_id_pesq:
            res_tx = self._persist_generation_attempts_in_tx(
                id_pesquisa=p_id_pesq,
                ponto_id=ponto_id,
                generation_attempts=generation_attempts,
                agora=agora,
            )
            if isinstance(res_tx, tuple):
                persisted_ids, usage_sum = res_tx[0], res_tx[1]
                if usage_sum and any((usage_sum.get(k) or 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                    try:
                        await self._accumulate_tokens(p_id_pesq, usage_sum)
                    except Exception:
                        pass
            else:
                persisted_ids = res_tx

        # 4. Registra histórico na coleta avaliada (metadados_coleta.auditorias) de forma fresca (evita IdentityMap stale)
        if auditoria_record:
            stmt_meta_fresco = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta_id)
            raw_meta = (await self.session.execute(stmt_meta_fresco)).scalar_one_or_none()
            stmt_exists = select(ConteudoColetado.id).where(ConteudoColetado.id == coleta_id)
            has_target = (await self.session.execute(stmt_exists)).scalar_one_or_none()
            if raw_meta is not None or has_target:
                meta = {}
                if raw_meta:
                    try:
                        meta = json.loads(raw_meta)
                    except Exception:
                        meta = {}
                if "auditorias" not in meta or not isinstance(meta["auditorias"], list):
                    meta["auditorias"] = []

                auditoria_entry = dict(auditoria_record)
                auditoria_entry["aplicado"] = fence_passed
                if not fence_passed:
                    auditoria_entry["status_aplicacao"] = "obsoleto_superado"
                if persisted_ids:
                    auditoria_entry["generation_attempt_ids"] = persisted_ids

                existing_ids = {a.get("id_auditoria") for a in meta["auditorias"] if isinstance(a, dict)}
                if auditoria_entry.get("id_auditoria") not in existing_ids:
                    meta["auditorias"].append(auditoria_entry)

                novo_meta_str = json.dumps(meta, ensure_ascii=False)
                stmt_upd_coleta = (
                    update(ConteudoColetado)
                    .where(ConteudoColetado.id == coleta_id)
                    .values(metadados_coleta=novo_meta_str)
                )
                await self.session.execute(stmt_upd_coleta)

                target_coleta = (
                    await self.session.execute(
                        select(ConteudoColetado)
                        .where(ConteudoColetado.id == coleta_id)
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                if target_coleta:
                    target_coleta.metadados_coleta = novo_meta_str

        # 5. Se o fence passou, aplica invalidação de dossiê/metadados do Writer e sincroniza status do pipeline
        if fence_passed and p_id_pesq:
            update_pesq_vals: Dict[str, Any] = {"metadados_redacao": None}
            if status != "aprovado":
                update_pesq_vals["dossier_final"] = None
                update_pesq_vals["concluido_em"] = None
            stmt_invalida_dossier = (
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == p_id_pesq)
                .values(**update_pesq_vals)
            )
            await self.session.execute(stmt_invalida_dossier)

            await self.session.flush()
            await self._sync_pipeline_status_in_tx(p_id_pesq)

        await self.session.commit()
        return fence_passed

    async def recalculate_audit_threshold(
        self,
        ponto_id: str,
        coleta_id: str,
        novo_threshold: int,
        novo_status: str,
        pontos_fracos: Optional[str],
        recalc_record: Dict[str, Any],
        expected_token: Optional[str] = None,
        expected_tentativa_audit: Optional[int] = None,
        expected_tentativa_search: Optional[int] = None,
    ) -> bool:
        """Recalcula o limiar da auditoria em cache sem inferência LLM de forma atômica via SQL CAS."""
        agora = _format_iso_utc()

        # 1. Verifica se a coleta avaliada ainda é a mais recente do ponto (SELECT de leitura)
        stmt_last_coleta = (
            select(ConteudoColetado.id)
            .where(ConteudoColetado.ponto_id == ponto_id)
            .order_by(ConteudoColetado.rodada.desc(), ConteudoColetado.criado_em.desc())
            .limit(1)
        )
        latest_coleta_id = (await self.session.execute(stmt_last_coleta)).scalar_one_or_none()
        if latest_coleta_id != coleta_id:
            return False

        # 2. Executa atualização CAS condicional: ponto não pode estar sob busca ou auditoria ativa
        # e a coleta avaliada precisa continuar sendo a mais recente no instante do UPDATE
        subq_latest_coleta = (
            select(ConteudoColetado.id)
            .where(ConteudoColetado.ponto_id == ponto_id)
            .order_by(ConteudoColetado.rodada.desc(), ConteudoColetado.criado_em.desc())
            .limit(1)
            .scalar_subquery()
        )
        cas_conditions = [
            Ponto.ponto_id == ponto_id,
            ~Ponto.status.in_(["em_andamento", "auditando"]),
            subq_latest_coleta == coleta_id,
        ]
        if expected_token is not None:
            cas_conditions.append(Ponto.atualizado_em == expected_token)
        if expected_tentativa_audit is not None:
            cas_conditions.append(Ponto.tentativas_auditoria == expected_tentativa_audit)
        if expected_tentativa_search is not None:
            cas_conditions.append(Ponto.tentativas == expected_tentativa_search)

        stmt_update_ponto = (
            update(Ponto)
            .where(*cas_conditions)
            .values(
                status=novo_status,
                pontos_fracos=pontos_fracos if novo_status == "reprovado" else None,
                atualizado_em=agora,
            )
        )
        res = await self.session.execute(stmt_update_ponto)
        fence_passed = (res.rowcount > 0)

        p_stmt = select(Ponto.id_pesquisa).where(Ponto.ponto_id == ponto_id)
        p_id_pesq = (await self.session.execute(p_stmt)).scalar_one_or_none()

        if fence_passed and novo_status != "aprovado" and p_id_pesq:
            stmt_invalida_dossier = (
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == p_id_pesq)
                .values(dossier_final=None, concluido_em=None, metadados_redacao=None)
            )
            await self.session.execute(stmt_invalida_dossier)

        # 3. Atualiza histórico na coleta com leitura fresca (evita IdentityMap stale)
        stmt_meta_fresco = select(ConteudoColetado.metadados_coleta).where(ConteudoColetado.id == coleta_id)
        raw_meta = (await self.session.execute(stmt_meta_fresco)).scalar_one_or_none()
        stmt_exists = select(ConteudoColetado.id).where(ConteudoColetado.id == coleta_id)
        has_target = (await self.session.execute(stmt_exists)).scalar_one_or_none()
        if raw_meta is not None or has_target:
            meta = {}
            if raw_meta:
                try:
                    meta = json.loads(raw_meta)
                except Exception:
                    meta = {}
            if "auditorias" not in meta or not isinstance(meta["auditorias"], list):
                meta["auditorias"] = []
            rec = dict(recalc_record)
            rec["aplicado"] = fence_passed
            if not fence_passed:
                rec["status_aplicacao"] = "obsoleto_superado"
            existing_ids = {a.get("id_auditoria") for a in meta["auditorias"] if isinstance(a, dict)}
            if rec.get("id_auditoria") not in existing_ids:
                meta["auditorias"].append(rec)
            novo_meta_str = json.dumps(meta, ensure_ascii=False)
            stmt_upd_coleta = (
                update(ConteudoColetado)
                .where(ConteudoColetado.id == coleta_id)
                .values(metadados_coleta=novo_meta_str)
            )
            await self.session.execute(stmt_upd_coleta)

            target_coleta = (
                await self.session.execute(
                    select(ConteudoColetado)
                    .where(ConteudoColetado.id == coleta_id)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if target_coleta:
                target_coleta.metadados_coleta = novo_meta_str

        if fence_passed and p_id_pesq:
            await self.session.flush()
            await self._sync_pipeline_status_in_tx(p_id_pesq)

        await self.session.commit()
        return fence_passed

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
        metadados_coleta: Optional[Dict[str, Any]] = None,
        generation_attempts: Optional[List[Any]] = None,
        incrementar_tentativa: bool = False,
        invalidar_dossier: bool = True,
        rodada: Optional[int] = None,
        expected_tentativa: Optional[int] = None,
        expected_token: Optional[str] = None,
    ) -> ConteudoColetado:
        """Salva a coleta da rodada atual sem sobrescrever coletas anteriores, comprovando posse atômica."""
        agora = _format_iso_utc()

        # 1. Comprova posse atômica via UPDATE condicional REAL no banco por ponto+tentativa+status (+token)
        if expected_tentativa is not None or expected_token is not None:
            ponto_conditions = [
                Ponto.ponto_id == ponto_id,
                Ponto.status == "em_andamento",
            ]
            if expected_tentativa is not None:
                ponto_conditions.append(Ponto.tentativas == expected_tentativa)

            if expected_token is not None:
                ponto_conditions.append(
                    or_(
                        Ponto.lease_token == expected_token,
                        and_(Ponto.lease_token.is_(None), Ponto.atualizado_em == expected_token),
                    )
                )
            else:
                # Chamada sem token: permite APENAS se o registro não possuir lease_token ativo pertencente a outro worker
                ponto_conditions.append(Ponto.lease_token.is_(None))

            novo_status = status_ponto or "coletado"
            update_values: Dict[str, Any] = {
                "status": novo_status,
                "atualizado_em": agora,
                "lease_token": None,
            }
            if diagnostico_falha is not None:
                update_values["pontos_fracos"] = diagnostico_falha
            if incrementar_tentativa:
                update_values["tentativas"] = Ponto.tentativas + 1

            stmt_posse = (
                update(Ponto)
                .where(*ponto_conditions)
                .values(**update_values)
            )
            res_posse = await self.session.execute(stmt_posse)
            if res_posse.rowcount == 0:
                raise RuntimeError(
                    f"POSSESSION_LOST: Ponto {ponto_id} não pode ser finalizado pois a posse da tentativa "
                    f"{expected_tentativa} com token {expected_token} expirou ou foi assumida por outra execução."
                )
        else:
            ponto_stmt = select(Ponto).where(Ponto.ponto_id == ponto_id)
            ponto_res = await self.session.execute(ponto_stmt)
            ponto_obj = ponto_res.scalar_one_or_none()
            if ponto_obj:
                if status_ponto is not None:
                    ponto_obj.status = status_ponto
                elif ponto_obj.status in ("pendente", "em_andamento", "reprovado", "falha_coleta"):
                    ponto_obj.status = "coletado"
                if diagnostico_falha is not None:
                    ponto_obj.pontos_fracos = diagnostico_falha
                if incrementar_tentativa:
                    ponto_obj.tentativas = (ponto_obj.tentativas or 0) + 1
                ponto_obj.atualizado_em = agora

        # 2. Rodada de produção é a tentativa reservada, sem remapear para count+1
        stmt_count = select(func.count(ConteudoColetado.id)).where(
            ConteudoColetado.id_pesquisa == id_pesquisa,
            ConteudoColetado.ponto_id == ponto_id,
        )
        count_res = await self.session.execute(stmt_count)
        proxima_rodada = (count_res.scalar() or 0) + 1

        if rodada is not None:
            rodada_atual = max(rodada, proxima_rodada)
        else:
            rodada_atual = proxima_rodada

        urls_lidas_json = json.dumps(urls_lidas, ensure_ascii=False)
        urls_fonte_json = json.dumps(urls_fonte, ensure_ascii=False)
        meta_json = json.dumps(metadados_coleta, ensure_ascii=False) if metadados_coleta else None

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
            metadados_coleta=meta_json,
            criado_em=agora,
        )
        self.session.add(record)

        # 3. Persistência de envelopes LLM da rodada
        if generation_attempts:
            for att_item in generation_attempts:
                if isinstance(att_item, GenerationAttempt):
                    self.session.add(att_item)
                elif isinstance(att_item, dict):
                    msgs = att_item.get("messages", [])
                    msgs_str = json.dumps(msgs, ensure_ascii=False) if isinstance(msgs, (list, dict)) else str(msgs or "[]")
                    req_params = att_item.get("request_params")
                    req_params_str = json.dumps(req_params, ensure_ascii=False) if req_params is not None else None

                    att_record = GenerationAttempt(
                        id=att_item.get("id") or str(uuid.uuid4()),
                        id_pesquisa=id_pesquisa,
                        ponto_id=ponto_id,
                        etapa="search",
                        persona=att_item.get("persona"),
                        model_requested=att_item.get("model_requested", ""),
                        model_used=att_item.get("model_used"),
                        prompt_hash=att_item.get("prompt_hash", ""),
                        prompt_version=att_item.get("prompt_version"),
                        system_message=att_item.get("system_message"),
                        messages_json=msgs_str,
                        content_final=att_item.get("content_final"),
                        reasoning_content=att_item.get("reasoning_content"),
                        finish_reason=att_item.get("finish_reason"),
                        is_regular_finish=bool(att_item.get("is_regular_finish", False)),
                        usage_json=json.dumps(att_item.get("usage"), ensure_ascii=False) if att_item.get("usage") else None,
                        cost_estimated=att_item.get("cost_estimated"),
                        cost_currency=att_item.get("cost_currency"),
                        cost_source=att_item.get("cost_source"),
                        request_params_json=req_params_str,
                        downstream_router_mutations=_map_downstream_router_mutations(att_item.get("downstream_router_mutations")),
                        latency_seconds=float(att_item.get("latency_seconds", 0.0)),
                        attempts=int(att_item.get("attempts", 1)),
                        errors_json=json.dumps(att_item.get("errors"), ensure_ascii=False) if att_item.get("errors") else None,
                        tool_calls_json=json.dumps(att_item.get("tool_calls"), ensure_ascii=False) if att_item.get("tool_calls") else None,
                        criado_em=att_item.get("criado_em") or agora,
                    )
                    self.session.add(att_record)
                    try:
                        await self._accumulate_tokens(id_pesquisa, att_item.get("usage"))
                    except Exception:
                        pass

        # 4. Invalidação de dossiê prévio da pesquisa e sincronização atômica do status_pipeline
        if invalidar_dossier:
            stmt_pesq = (
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .values(dossier_final=None, concluido_em=None, metadados_redacao=None)
            )
            await self.session.execute(stmt_pesq)

        await self._sync_pipeline_status_in_tx(id_pesquisa)

        await self.session.commit()
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
        """Devolve a última coleta do ponto com evidência web real."""
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

    # --------------------------------------------------------------------------
    # Fundações de Observabilidade e Persistência Estruturada (DR-005, DR-009, DR-013, DR-015)
    # --------------------------------------------------------------------------

    async def persist_generation_attempts(
        self,
        id_pesquisa: str,
        ponto_id: Optional[str] = None,
        generation_attempts: Optional[List[Any]] = None,
        agora: Optional[str] = None,
        default_etapa: str = "search",
        default_persona: Optional[str] = None,
    ) -> List[str]:
        agora = agora or _format_iso_utc()
        if not generation_attempts:
            return []
        res_tx = self._persist_generation_attempts_in_tx(
            id_pesquisa=id_pesquisa,
            ponto_id=ponto_id,
            generation_attempts=generation_attempts,
            agora=agora,
            default_etapa=default_etapa,
            default_persona=default_persona,
        )
        if isinstance(res_tx, tuple):
            persisted_ids, usage_sum = res_tx[0], res_tx[1]
            if usage_sum and any((usage_sum.get(k) or 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                try:
                    await self._accumulate_tokens(id_pesquisa, usage_sum)
                except Exception:
                    pass
        else:
            persisted_ids = res_tx
        return persisted_ids
    async def get_generation_attempts(
        self,
        id_pesquisa: str,
        etapa: Optional[str] = None,
    ) -> List[GenerationAttempt]:
        stmt = select(GenerationAttempt).where(GenerationAttempt.id_pesquisa == id_pesquisa)
        if etapa:
            stmt = stmt.where(GenerationAttempt.etapa == etapa)
        stmt = stmt.order_by(GenerationAttempt.criado_em.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # --------------------------------------------------------------------------
    # Reserva Atômica, Lease e Publicação da Redação (W08, W10, v6)
    # --------------------------------------------------------------------------

    async def count_generation_attempts_by_ids(
        self,
        id_pesquisa: str,
        attempt_ids: List[str],
    ) -> int:
        """Conta envelopes efetivamente persistidos por IDs (comprovação real do cache, W09)."""
        if not attempt_ids:
            return 0
        result = await self.session.execute(
            select(GenerationAttempt.id).where(
                GenerationAttempt.id_pesquisa == id_pesquisa,
                GenerationAttempt.id.in_(attempt_ids),
            )
        )
        return len([r[0] for r in result.all()])

    async def reserve_research_for_writer(
        self,
        id_pesquisa: str,
        lease_seconds: int = 600,
        input_hash: Optional[str] = None,
    ) -> tuple[str, Pesquisa]:
        """Reserva atômica da pesquisa para a etapa de redação (Writer) com lease temporário,
        identidade da entrada (input_hash) e SQL condicional com rowcount (W08, v6)."""
        now_dt = datetime.now(timezone.utc)
        agora = _format_iso_utc(now_dt)
        lease_exp = _format_iso_utc(now_dt + timedelta(seconds=lease_seconds))
        token = str(uuid.uuid4())

        # 1. Confere se a pesquisa existe
        stmt_check = select(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).execution_options(populate_existing=True)
        pesquisa = (await self.session.execute(stmt_check)).scalar_one_or_none()
        if not pesquisa:
            raise ValueError(f"RESEARCH_NOT_FOUND: Pesquisa não localizada: {id_pesquisa}")

        # 2. Confere se há lease ativa e não expirada de outro worker
        if pesquisa.metadados_redacao:
            try:
                meta = json.loads(pesquisa.metadados_redacao)
                if isinstance(meta, dict):
                    cur_token = meta.get("lease_token")
                    cur_exp = meta.get("lease_expira_em")
                    status_ativo = meta.get("status") == "redigindo" or pesquisa.status_pipeline == "redigindo"
                    if cur_token and status_ativo and cur_exp and cur_exp > agora:
                        raise ValueError(
                            f"CONCURRENCY_CONFLICT: Writer já em execução ativa para {id_pesquisa} (lease expira em {cur_exp})."
                        )
            except json.JSONDecodeError:
                pass

        novo_meta: Dict[str, Any] = {
            "lease_token": token,
            "lease_adquirido_em": agora,
            "lease_expira_em": lease_exp,
            "status": "redigindo",
        }
        if input_hash:
            novo_meta["input_hash"] = input_hash
        if pesquisa.metadados_redacao:
            try:
                prev_meta = json.loads(pesquisa.metadados_redacao)
                if isinstance(prev_meta, dict):
                    for k in ("input_hash", "qualidade_artigo", "generation_attempt_ids"):
                        if k in prev_meta:
                            novo_meta[f"prev_{k}"] = prev_meta[k]
            except Exception:
                pass

        novo_meta_json = json.dumps(novo_meta, ensure_ascii=False)

        # 3. UPDATE condicional atômico no banco com verificação de rowcount
        stmt_reserve = (
            update(Pesquisa)
            .where(
                Pesquisa.id_pesquisa == id_pesquisa,
                or_(
                    Pesquisa.metadados_redacao.is_(None),
                    func.json_extract(Pesquisa.metadados_redacao, "$.lease_token").is_(None),
                    func.json_extract(Pesquisa.metadados_redacao, "$.lease_expira_em") <= agora,
                    Pesquisa.metadados_redacao == pesquisa.metadados_redacao,
                ),
            )
            .values(
                metadados_redacao=novo_meta_json,
                status_pipeline="redigindo",
            )
        )
        try:
            res = await self.session.execute(stmt_reserve)
            # Refresh DENTRO da mesma transação (vê o próprio UPDATE) e ANTES do commit:
            # modelo retornado correto e nenhuma leitura reaberta após o commit — sem
            # transação aberta sobre o I/O externo subsequente (LLM/webhook, W08/v6).
            await self.session.refresh(pesquisa)
            await self.session.commit()
        except asyncio.CancelledError:
            # Cancelamento durante o ciclo de gravação (W08, v6): a posse DESTA aquisição
            # pode ter sido persistida sem que o chamador recebesse o token. Libera
            # EXCLUSIVAMENTE o token local já gerado (CAS por lease_token), sem inferir
            # dono por horário: se a lease vigente for de outro dono (token diferente),
            # o CAS não casa e a posse alheia permanece intacta.
            try:
                await self.session.rollback()
                await self.release_writer_reservation(
                    id_pesquisa=id_pesquisa,
                    lease_token=token,
                    status_pipeline="incompleto",
                )
            except Exception as exc_cleanup:
                logger.warning(
                    f"[Reservation] {id_pesquisa}: falha no best-effort de liberação do token "
                    "local após cancelamento; a lease vigente será assumível por novo dono "
                    "após a expiração.",
                    exc_info=exc_cleanup,
                )
            raise

        if res.rowcount == 0:
            raise ValueError(
                f"CONCURRENCY_CONFLICT: Falha de aquisição atômica da posse de redação para {id_pesquisa}. "
                "Outro processo adquiriu a lease concorrentemente."
            )

        return token, pesquisa

    async def release_writer_reservation(
        self,
        id_pesquisa: str,
        lease_token: str,
        generation_attempts: Optional[List[Any]] = None,
        status_pipeline: Optional[str] = None,
    ) -> bool:
        """Libera a reserva do Writer via UPDATE condicional atômico verificando rowcount (W08, v6)."""
        agora = _format_iso_utc()

        persisted_ids: List[str] = []
        if generation_attempts:
            res_tx = self._persist_generation_attempts_in_tx(
                id_pesquisa=id_pesquisa,
                ponto_id=None,
                generation_attempts=generation_attempts,
                agora=agora,
                default_etapa="write",
                default_persona="redator final",
            )
            if isinstance(res_tx, tuple):
                persisted_ids, usage_sum = res_tx[0], res_tx[1]
                if usage_sum and any((usage_sum.get(k) or 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                    try:
                        await self._accumulate_tokens(id_pesquisa, usage_sum)
                    except Exception:
                        pass
            else:
                persisted_ids = res_tx

        novo_meta = {
            "lease_token": None,
            "status": status_pipeline or "incompleto",
            "liberado_em": agora,
            "generation_attempt_ids": persisted_ids,
        }
        stmt_release = (
            update(Pesquisa)
            .where(
                Pesquisa.id_pesquisa == id_pesquisa,
                func.json_extract(Pesquisa.metadados_redacao, "$.lease_token") == lease_token,
            )
            .values(
                metadados_redacao=json.dumps(novo_meta, ensure_ascii=False),
                status_pipeline=status_pipeline or "incompleto",
            )
        )
        res = await self.session.execute(stmt_release)
        await self.session.commit()
        return res.rowcount > 0

    async def finalize_writer_publication(
        self,
        id_pesquisa: str,
        lease_token: str,
        dossier_final: Optional[str],
        status_pipeline: str,
        metadados_redacao_dict: Dict[str, Any],
        generation_attempts: Optional[List[Any]] = None,
        expected_input_hash: Optional[str] = None,
        reasoning_dossier: Optional[str] = None,
    ) -> bool:
        """Finalização atômica do Writer via UPDATE condicional verificando posse real, vigência
        da lease, identidade da entrada e rowcount (W08, W10, v6, resume3 item 3).

        A fence exige: token do dono, lease NÃO expirada e input_hash igual ao registrado na
        reserva, de modo que mutação in-place da base (plano/eixo, coleta, claims/trechos,
        auditoria aprovado→aprovado, estado) ou expiração sem novo dono impeçam a publicação.
        """
        agora = _format_iso_utc()

        persisted_ids: List[str] = []
        if generation_attempts:
            res_tx = self._persist_generation_attempts_in_tx(
                id_pesquisa=id_pesquisa,
                ponto_id=None,
                generation_attempts=generation_attempts,
                agora=agora,
                default_etapa="write",
                default_persona="redator final",
            )
            if isinstance(res_tx, tuple):
                persisted_ids, usage_sum = res_tx[0], res_tx[1]
                if usage_sum and any((usage_sum.get(k) or 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
                    try:
                        await self._accumulate_tokens(id_pesquisa, usage_sum)
                    except Exception:
                        pass
            else:
                persisted_ids = res_tx
            if not persisted_ids:
                return False

        meta_final = dict(metadados_redacao_dict)
        meta_final["lease_token"] = None
        meta_final["generation_attempt_ids"] = persisted_ids
        meta_final["finalizado_em"] = agora

        # Dossiê entregue é persistido mesmo com status 'incompleto' (relatório com
        # ressalvas, PRD v3 RF-006-D); o chamador decide quando enviar texto.
        publicado_dossier = dossier_final if dossier_final else None
        concluido_timestamp = agora if status_pipeline == "concluido" else None
        if concluido_timestamp:
            meta_final["concluido_em"] = concluido_timestamp

        fence_conditions = [
            Pesquisa.id_pesquisa == id_pesquisa,
            func.json_extract(Pesquisa.metadados_redacao, "$.lease_token") == lease_token,
            # Vigência real da lease: expiração sem novo dono também não publica
            func.json_extract(Pesquisa.metadados_redacao, "$.lease_expira_em") > agora,
        ]
        if expected_input_hash:
            fence_conditions.append(
                func.json_extract(Pesquisa.metadados_redacao, "$.input_hash") == expected_input_hash
            )

        finalize_vals: Dict[str, Any] = {
            "dossier_final": publicado_dossier,
            "status_pipeline": status_pipeline,
            "concluido_em": concluido_timestamp,
            "metadados_redacao": json.dumps(meta_final, ensure_ascii=False),
        }
        if reasoning_dossier is not None:
            finalize_vals["reasoning_dossier"] = reasoning_dossier

        stmt_finalize = (
            update(Pesquisa)
            .where(*fence_conditions)
            .values(**finalize_vals)
        )
        res = await self.session.execute(stmt_finalize)
        await self.session.commit()

        if res.rowcount == 0:
            logger.warning(
                f"[Writer] Finalização atômica rejeitada (rowcount=0): "
                f"token {lease_token} expirou, foi sobrescrito ou a identidade da entrada divergiu."
            )
            return False

        return True

    async def update_webhook_delivery(
        self,
        id_pesquisa: str,
        artifact_hash: str,
        webhook_status: str,
        webhook_resposta: Optional[str] = None,
        tentativas: Optional[int] = 1,
        detalhes_falha: Optional[str] = None,
    ) -> bool:
        """Atualização condicional exclusiva dos campos de webhook após despacho, sem reescrever texto (v6).

        tentativas=None registra entrega NÃO observada (W07: deadline total estourando no
        callback) — quantidade desconhecida persiste explícita, nunca inventada."""
        stmt_check = select(Pesquisa.metadados_redacao).where(Pesquisa.id_pesquisa == id_pesquisa)
        current_meta_str = (await self.session.execute(stmt_check)).scalar_one_or_none()
        if not current_meta_str:
            return False

        try:
            meta = json.loads(current_meta_str)
            if not isinstance(meta, dict) or meta.get("artifact_hash") != artifact_hash:
                return False
            meta["tentativas_webhook"] = tentativas
            if detalhes_falha:
                meta["detalhes_falha_webhook"] = detalhes_falha
            novo_meta_str = json.dumps(meta, ensure_ascii=False)
        except Exception:
            return False

        stmt_upd = (
            update(Pesquisa)
            .where(
                Pesquisa.id_pesquisa == id_pesquisa,
                func.json_extract(Pesquisa.metadados_redacao, "$.artifact_hash") == artifact_hash,
            )
            .values(
                webhook_status=webhook_status,
                webhook_resposta=webhook_resposta,
                metadados_redacao=novo_meta_str,
            )
        )
        res = await self.session.execute(stmt_upd)
        await self.session.commit()
        return res.rowcount > 0
