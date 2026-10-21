"""Orquestrador fan-out da investigação (T012, RN-02/RN-03/RN-09/RN-10)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.investigation.prompts import PERSONA_NAMES
from app.investigation.storage import (
    STATUS_AUDIT_PENDING,
    check_merge_barrier,
    get_pending_workers_for_research,
    save_investigation_merge,
    save_step_result,
)
from app.audit.service import AuditService
from app.audit.domain import MAX_AUDIT_ATTEMPTS, SCRAPER_RETRY, STATE_INCONCLUSIVE
from app.models.domain_models import (
    AppSettings,
    Report,
    Research,
    ResearchPoint,
    ResearchStatus,
    ResearchStepResult,
)
from app.services.crypto import decrypt_secret
from app.core.config import settings as app_config
from app.services.settings import PROVIDER_BASE_URLS, runtime_jina_proxy, runtime_settings
from app.investigation.tools import JinaToolAdapter


def _provider_for_model(model: str) -> str:
    return model.split("/", 1)[0].lower() if "/" in model else "openai"


#: Estados de ponto PRESERVADOS antes de chamar ``audit_point`` (RN-301/D-301):
#: já auditáveis (``AUDIT_INCONCLUSIVE``/``SCRAPER_RETRY``) ou terminais
#: (``SCRAPER_FAILED`` e estados conclusivos) — nenhum deles é reescrito para
#: ``AUDIT_PENDING``. Estados de coleta em andamento (ex. retomada ainda em
#: ``SCRAPER_IN_PROGRESS``) são canonicalizados para ``AUDIT_PENDING``.
_POINT_STATES_PRESERVED_BEFORE_AUDIT: frozenset[str] = frozenset(
    {
        "AUDIT_PENDING",
        "AUDIT_INCONCLUSIVE",
        "SCRAPER_RETRY",
        "SCRAPER_FAILED",
        "AUDIT_APPROVED",
        "AUDIT_CAVEAT",
    }
)


async def _resolve_credentials(db: AsyncSession) -> tuple[str, str | None, str | None, dict]:
    """Resolve stable legacy tuple; model provider secrets available in models metadata."""
    keys, models = await runtime_settings(db)
    proxy_url, proxy_auth, _timeout = await runtime_jina_proxy(db)
    record = await db.get(AppSettings, 1)
    model = models.get("scout", "")
    provider = _provider_for_model(model)
    provider_key = keys.get(provider)
    base_url = None
    if record is not None:
        encrypted = record.encrypted_credentials or {}
        provider_key = decrypt_secret(encrypted[provider]) if encrypted.get(provider) else provider_key
        base_field = PROVIDER_BASE_URLS.get(provider, (None, ""))[1]
        base_url = getattr(record, base_field, None) if base_field else None
        if provider == "openai":
            base_url = base_url or record.openai_base_url
    base_url = base_url or getattr(app_config, f"{provider.upper()}_BASE_URL", None)
    models = dict(models)
    models["_provider_key"] = provider_key or ""
    models["_provider_base_url"] = base_url or ""
    return (keys.get("jina") or "", proxy_url, proxy_auth, models)


async def _resolve_persona_credentials(db: AsyncSession, models: dict) -> dict:
    keys, _ = await runtime_settings(db)
    record = await db.get(AppSettings, 1)
    encrypted = record.encrypted_credentials or {} if record else {}
    resolved = {}
    for persona in PERSONA_NAMES:
        model = models.get(persona) or models.get("scout", "")
        provider = _provider_for_model(model)
        key = keys.get(provider)
        if encrypted.get(provider):
            try:
                key = decrypt_secret(encrypted[provider])
            except Exception:
                key = None
        base_url = None
        if record:
            base_field = PROVIDER_BASE_URLS.get(provider, (None, ""))[1]
            base_url = getattr(record, base_field, None) if base_field else None
            if provider == "openai":
                base_url = base_url or record.openai_base_url
        base_url = base_url or getattr(app_config, f"{provider.upper()}_BASE_URL", None)
        resolved[persona] = {"api_key": key or None, "api_base": base_url or None}
    return resolved

from app.investigation.worker import PersonaWorker
from app.models.domain_models import Research, ResearchPoint, ResearchStatus


# provider metadata remains alongside model settings to preserve four-value contract.



class InvestigationService:
    def __init__(
        self,
        session_factory,
        jina_adapter: JinaToolAdapter | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        self.session_factory = session_factory
        self.jina_adapter = jina_adapter
        self.api_base = api_base
        self.api_key = api_key

    # ------------------------------------------------ flags de auditoria --

    async def _ensure_point_ready_for_audit(self, step_id: UUID) -> None:
        """Sinaliza o ponto como ``AUDIT_PENDING`` após as personas fecharem.

        RN-301: cada worker grava seu resultado via ``save_step_result`` (que
        já consolida ``AUDIT_PENDING``/``SCRAPER_FAILED``) e, ANTES de
        ``audit_point``, este helper garante a flag de auditoria em sessão
        curta e isolada — sem chamada de rede dentro dela e SEM aninhar com a
        sessão de gravação do veredito (SQLite permite uma transação por vez
        na conexão). Estados em
        ``_POINT_STATES_PRESERVED_BEFORE_AUDIT`` (auditáveis e terminais)
        nunca são regredidos.
        """
        async with self.session_factory() as session:
            point = await session.get(ResearchPoint, step_id)
            if point is None:
                return
            if str(point.status or "") in _POINT_STATES_PRESERVED_BEFORE_AUDIT:
                return
            point.status = STATUS_AUDIT_PENDING
            await session.commit()

    async def _reset_inconclusive_point_to_pending(self, step_id: UUID) -> None:
        """RN-304/D-305: auditoria inconclusiva deixa o ponto AGUARDANDO.

        ``AUDIT_INCONCLUSIVE`` ou auditor não configurado: o ponto permanece
        em ``AUDIT_PENDING`` e a pesquisa segue/retorna para ``AUDIT`` na
        consolidação final. Sessão curta: converte para ``AUDIT_PENDING``
        SOMENTE o ponto que o ``AuditService`` deixou como
        ``AUDIT_INCONCLUSIVE``; ``SCRAPER_FAILED``, coleta em andamento e
        estados conclusivos não são regredidos.
        """
        async with self.session_factory() as session:
            point = await session.get(ResearchPoint, step_id)
            if point is None:
                return
            if str(point.status or "") != STATE_INCONCLUSIVE:
                return
            point.status = STATUS_AUDIT_PENDING
            await session.commit()

    async def run_investigation(self, research_id: UUID) -> None:
        """Orquestrador fan-out + ciclo reativo de auditoria por ponto (T046–T049).

        Fluxo (RN-301, RN-303, RN-305, RN-306; D-301, D-302, D-305):
        1. Carrega pesquisa, pontos e credenciais; agrupa as personas
           pendentes por ``step_id``.
        2. Executa as 4 personas de cada ponto em paralelo (pontos
           também paralelos entre si).
        3. Assim que as personas de um ponto finalizam, dispara
           imediatamente ``AuditService.audit_point`` daquele ponto —
           sem esperar os demais. Antes de auditar, o ponto é sinalizado
           como ``AUDIT_PENDING`` (``save_step_result`` por persona +
           ``_ensure_point_ready_for_audit``); as sessões de banco são
           curtas e fechadas antes da chamada LLM (sem transações
           aninhadas disputando a mesma conexão SQLite).
        4. Veredito ``SCRAPER_RETRY`` com ``attempt_count < 4``:
           incrementa ``attempt_count``, agrega todas as ``read_urls``
           já coletadas como filtro anti-duplicação, re-executa as 4
           personas com ``missing_research`` do Auditor e re-audita.
        5. Veredito ``AUDIT_APPROVED``/``AUDIT_CAVEAT`` finaliza o ponto;
           ``AUDIT_INCONCLUSIVE``/auditor não configurado mantém o ponto em
           ``AUDIT_PENDING`` aguardando a etapa de auditoria e a pesquisa
           segue/retorna para ``AUDIT`` (RN-304/D-305).
        6. 100% dos pontos conclusivos -> transição ``AUDIT`` -> `WRITE`.
        """

        async with self.session_factory() as session:
            research = await session.get(Research, research_id)
            if research is None:
                return
            if research.status == ResearchStatus.DONE.value:
                return
            has_report = False
            writer_points: list[ResearchPoint] = []
            if research.status == ResearchStatus.WRITE.value:
                has_report = bool(await session.scalar(
                    select(Report.id).where(Report.research_id == research_id)
                ))
                if not has_report:
                    rows = await session.execute(
                        select(ResearchPoint)
                        .where(ResearchPoint.research_id == research_id)
                        .order_by(ResearchPoint.position.asc())
                    )
                    writer_points = list(rows.scalars().all())
                else:
                    return

        if research.status == ResearchStatus.WRITE.value and not has_report:
            from app.services.pipeline.writer import _write_report
            await _write_report(research, writer_points)
            if research.callback_url:
                from app.services.webhook import dispatch_callback
                await dispatch_callback(research_id)
            return

        async with self.session_factory() as session:
            research = await session.get(Research, research_id)
            if research is None:
                return
            theme = research.theme
            rows = await session.execute(
                select(ResearchPoint)
                .where(ResearchPoint.research_id == research_id)
                .order_by(ResearchPoint.position.asc())
            )
            points = list(rows.scalars().all())
            if not points:
                return
            jina_key, proxy_url, proxy_key, models = await _resolve_credentials(session)
            resolved_base = models.get("_provider_base_url") or None
            resolved_key = models.get("_provider_key") or None
            models = {key: value for key, value in models.items() if not key.startswith("_")}
            persona_credentials = await _resolve_persona_credentials(session, models)
            pending_workers = await get_pending_workers_for_research(session, research_id)
            audit_service = AuditService(self.session_factory)
            # Agrupamento por ponto: personâs pendentes + pontos retomados
            # que já têm material completo mas não foram auditados (RN-301).
            work_by_point: dict[UUID, dict] = {}
            for item in pending_workers:
                work_by_point.setdefault(
                    item["step_id"],
                    {"step_title": item["step_title"], "personas": []},
                )["personas"].append(item["persona"])
            for point in points:
                if point.status == "AUDIT_PENDING" and point.id not in work_by_point:
                    work_by_point[point.id] = {
                        "step_title": point.title,
                        "personas": [],
                    }
            if not work_by_point:
                return

        adapter: Any = self.jina_adapter
        if adapter is None:
            try:
                adapter = JinaToolAdapter(api_key=jina_key, proxy_url=proxy_url, proxy_key=proxy_key)
            except Exception:
                adapter = None
        models["_credentials_by_persona"] = persona_credentials
        worker = PersonaWorker(
            adapter,
            app_settings_models=models,
            api_base=resolved_base if self.api_base is None else self.api_base,
            api_key=resolved_key if self.api_key is None else self.api_key,
        )

        async def _run_single(
            step_id: UUID,
            step_title: str,
            persona: str,
            missing_research: list[str] | None = None,
            excluded_urls: set[str] | list[str] | None = None,
            round: int = 1,
        ) -> None:
            try:
                res = await worker.execute(
                    research_id,
                    step_id,
                    step_title,
                    persona,
                    theme,
                    missing_research=missing_research,
                    excluded_urls=excluded_urls,
                )
            except TypeError:
                res = await worker.execute(
                    research_id,
                    step_id,
                    step_title,
                    persona,
                    theme,
                )
            async with self.session_factory() as session:
                await save_step_result(
                    session,
                    research_id,
                    step_id,
                    step_title,
                    persona,
                    res.result,
                    res.used_urls,
                    res.read_urls,
                    res.success,
                    round=round,
                )

        async def _is_auditor_configured() -> bool:
            async with self.session_factory() as session:
                keys, r_models = await runtime_settings(session)
                aud_model = r_models.get("auditor")
                if not aud_model:
                    return False
                provider = _provider_for_model(aud_model)
                return bool(keys.get(provider))

        async def _run_reactive_cycle(step_id: UUID, step_title: str, personas: list[str]) -> None:
            """Coleta -> auditoria reativa -> retry por ponto (T046–T048)."""

            current_round = 1
            async with self.session_factory() as session:
                point = await session.get(ResearchPoint, step_id)
                if point is not None and point.investigation_round:
                    current_round = point.investigation_round

            missing_research: list[str] | None = None
            excluded_urls: set[str] | list[str] | None = None
            personas_to_run = personas
            while True:
                tasks = [
                    _run_single(
                        step_id,
                        step_title,
                        persona,
                        missing_research,
                        excluded_urls,
                        round=current_round,
                    )
                    for persona in personas_to_run
                ]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                is_failed = False
                async with self.session_factory() as session:
                    point = await session.get(ResearchPoint, step_id)
                    if point is not None:
                        if point.status == "SCRAPER_FAILED":
                            is_failed = True
                        else:
                            point.status = STATUS_AUDIT_PENDING
                            await session.commit()

                if is_failed:
                    return

                # Grava snapshot committed de merge se a barreira de 4 personas foi superada
                async with self.session_factory() as session:
                    if await check_merge_barrier(session, research_id, step_id, round=current_round):
                        step_rows = await session.scalars(
                            select(ResearchStepResult).where(
                                ResearchStepResult.step_id == step_id,
                                ResearchStepResult.round == current_round,
                                ResearchStepResult.status == STATUS_AUDIT_PENDING,
                            )
                        )
                        personas_data = {}
                        for r in step_rows:
                            try:
                                parsed = json.loads(r.result) if isinstance(r.result, str) else r.result
                            except Exception:
                                parsed = {"analysis": r.result, "citations": []}
                            personas_data[r.worker] = parsed
                        await save_investigation_merge(
                            session,
                            research_id=research_id,
                            step_id=step_id,
                            round=current_round,
                            content={"personas": personas_data},
                        )

                if not await _is_auditor_configured():
                    return

                verdict = await audit_service.audit_point(
                    research_id, step_id, round=current_round
                )
                if verdict.status in (STATUS_AUDIT_PENDING, STATE_INCONCLUSIVE):
                    return
                if verdict.status != SCRAPER_RETRY:
                    return
                # RN-303/RN-305/T017: reprovado com SCRAPER_RETRY antes do teto -> re-executar personas.
                evidence: list[dict] = []
                async with self.session_factory() as session:
                    point = await session.get(ResearchPoint, step_id)
                    if point is None:
                        return
                    point.attempt_count += 1
                    await session.commit()
                    # D-302: filtro anti-duplicação com todas as read_urls
                    # coletadas nas tentativas anteriores deste ponto.
                    evidence = await audit_service.get_point_evidence(
                        session, step_id, round=current_round
                    )
                excluded_urls = {
                    url
                    for row in evidence
                    for url in row.get("read_urls", [])
                    if isinstance(url, str) and url.strip()
                }
                missing_research = list(verdict.missing_research)
                current_round += 1
                # Retry re-executa as 4 personas do ponto (evidência append-only).
                personas_to_run = list(PERSONA_NAMES)

        from app.services.research import ready_point_batches
        batches = ready_point_batches(points)
        for batch in batches:
            batch_tasks = []
            for idx in batch:
                p = points[idx]
                if p.id in work_by_point:
                    batch_tasks.append(
                        _run_reactive_cycle(
                            p.id,
                            work_by_point[p.id]["step_title"],
                            list(work_by_point[p.id]["personas"]),
                        )
                    )
            if batch_tasks:
                await asyncio.gather(*batch_tasks, return_exceptions=True)

        async with self.session_factory() as session:
            research = await session.get(Research, research_id)
            if research is None:
                return
            rows = await session.execute(
                select(ResearchPoint).where(ResearchPoint.research_id == research_id)
            )
            final_points = list(rows.scalars().all())
            write_transitioned = await audit_service.check_all_points_completed(
                session, research_id
            )
            if not write_transitioned:
                if final_points and all(
                    p.status == "SCRAPER_FAILED" for p in final_points
                ):
                    research.status = ResearchStatus.FAILED.value
                elif not final_points:
                    research.status = ResearchStatus.FAILED.value
                else:
                    # Pesquisa permanece em AUDIT até conclusão de 100% dos
                    # pontos (RN-306). Transição WRITE é atômica via
                    # check_all_points_completed.
                    research.status = ResearchStatus.AUDIT.value
                await session.commit()

        # T021: CAS WRITE, sessão fechada antes Writer.
        if write_transitioned:
            async with self.session_factory() as session:
                research = await session.get(Research, research_id)
                rows = await session.execute(
                    select(ResearchPoint)
                    .where(ResearchPoint.research_id == research_id)
                    .order_by(ResearchPoint.position.asc())
                )
                writer_points = list(rows.scalars().all())
                has_report = bool(await session.scalar(
                    select(Report.id).where(Report.research_id == research_id)
                ))
            if research and not has_report:
                from app.services.pipeline.writer import _write_report
                await _write_report(research, writer_points)
                if research.callback_url:
                    from app.services.webhook import dispatch_callback
                    await dispatch_callback(research_id)
