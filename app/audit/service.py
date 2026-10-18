"""AuditService: agregação das 4 personas, auditoria LLM e persistência (T043/T044).

Fluxo por ponto (``audit_point``):
1. Carrega ``ResearchPoint`` (attempt_count padrão vem do próprio ponto).
2. Agrega os resultados das 4 personas de ``research_step_results``.
3. Resolve API key / base URL / modelo da role "auditor" via
   ``runtime_settings`` (default ``gemini/gemini-3.8-flash``).
4. Chama a LLM com até 4 tentativas de infraestrutura (1 inicial + 3
   retries com backoff exponencial de 1s, 2s, 4s contra falhas de rede,
   timeouts ou HTTP 500/502/503). Nenhuma falha de infraestrutura queima
   ``point.attempt_count``.
5. Parse tolerante a blocos ```json``; ``evaluate_audit_verdict`` aplica a
   máquina de estados RN-302/RN-303/RN-305; sanitização estrita de segredos
   via ``sanitize_audit_dict``; persistência atômica em ``audit_trails`` +
   atualização de ``research_points`` + evento ``verdict_rendered``.

   O fluxo roda em 3 blocos — leitura (sessão fechada), rede/LLM (sem
   transação de banco aberta) e gravação (sessão limpa) — evitando sessões
   aninhadas no SQLite e deadlocks por disputa de conexão; role 'auditor'
   não configurada degrada o ponto para ``AUDIT_PENDING``
   (``AuditorNotConfiguredError``); falhas de infraestrutura persistem
   ``AUDIT_INCONCLUSIVE`` (RN-304).

``check_all_points_completed`` implementa a transição para
``ResearchStatus.WRITE`` quando 100% dos pontos atingem estado conclusivo
(``AUDIT_APPROVED``/``AUDIT_CAVEAT``) — insumo direto de T049.

``audit_research`` (T045/RN-301) audita todos os pontos elegíveis de uma
pesquisa e, em reprovação (``SCRAPER_RETRY``), incrementa o
``attempt_count`` do ponto (RN-303); o re-disparo das personas fica no
``InvestigationService`` (T047).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.domain import (
    CONCLUSIVE_STATES,
    MAX_AUDIT_ATTEMPTS,
    SCRAPER_RETRY,
    AuditVerdict,
    evaluate_audit_verdict,
    normalize_checklist,
    sanitize_audit_dict,
)
from app.db.database import AsyncSessionLocal
from app.models import AuditTrail, Research, ResearchPoint, ResearchStatus, ResearchStepResult

logger = logging.getLogger(__name__)

#: Backoff de infraestrutura: 1s, 2s, 4s entre as tentativas (T043).
_INFRA_BACKOFF_SECONDS = (1.0, 2.0, 4.0)

#: Modelo padrão da role "auditor" quando não configurado (T043).
DEFAULT_AUDITOR_MODEL = "gemini/gemini-3.8-flash"

AUDITOR_STAGE = "point_audit"
INCONCLUSIVE_STATUS = "AUDIT_INCONCLUSIVE"

#: Status "aguardando auditoria": aplicado ao ponto quando a role 'auditor'
#: não está configurada nas credenciais — o ponto deve permanecer elegível
#: para a etapa de auditoria (RN-301) em vez de ficar inconclusivo (RN-304).
AUDIT_PENDING_STATUS = "AUDIT_PENDING"

#: Estados de ponto que PODEM receber a transição de status na persistência
#: inconclusiva. Espelha os estados auditáveis de ``app.audit.router``:
#: pontos ``SCRAPER_FAILED`` (falha total das personas), em coleta ou já
#: conclusivos têm seu status preservado (nunca regredido).
AUDITABLE_POINT_STATES: frozenset[str] = frozenset(
    {"AUDIT_PENDING", "SCRAPER_RETRY", INCONCLUSIVE_STATUS}
)


class AuditorNotConfiguredError(RuntimeError):
    """A role 'auditor' (modelo e/ou API key) não está configurada.

    Degradação graciosa (RN-304): o chamador deve persistir o ``AuditTrail``
    e manter o ponto em ``AUDIT_PENDING`` para aguardar a etapa de
    auditoria — sem queimar ``attempt_count`` e sem chamada LLM ambígua.
    """


class AuditService:
    """Serviço de auditoria factual por ponto de pesquisa.

    ``session_factory`` é injetável para isolamento em testes; o padrão é
    ``AsyncSessionLocal`` de ``app.db.database``.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or AsyncSessionLocal

    # ------------------------------------------------------------- leitura --

    async def get_point_evidence(self, session: AsyncSession, point_id: UUID) -> list[dict]:
        """Agrega os resultados das 4 personas de ``research_step_results``.

        Retorna dicts com ``persona``, ``result``, ``used_urls``,
        ``read_urls`` e ``status`` (ordem estável por criação).
        """
        rows = (
            await session.scalars(
                select(ResearchStepResult)
                .where(ResearchStepResult.step_id == point_id)
                .order_by(ResearchStepResult.created_at, ResearchStepResult.id)
            )
        ).all()
        return [
            {
                "persona": row.worker,
                "result": row.result,
                "used_urls": list(row.used_urls or []),
                "read_urls": list(row.read_urls or []),
                "status": row.status,
            }
            for row in rows
        ]

    # ------------------------------------------------------ auditoria LLM --

    @staticmethod
    def _build_auditor_prompt(
        title: str,
        description: str,
        evidence: list[dict],
        criteria: dict[str, str],
    ) -> str:
        """Prompt do auditor: título + descrição + 4 relatórios das personas.

        Instrui resposta estritamente JSON com os 12 critérios canônicos
        (``q1``..``q12``) e as listas estruturadas.
        """
        criteria_lines = "\n".join(f"  - {key}: {text}" for key, text in criteria.items())
        payload = {
            "point_title": title,
            "point_description": description,
            "persona_reports": evidence[:8_000_000],
        }
        return (
            "<evidence_to_audit>\n"
            f"{json.dumps(payload, ensure_ascii=False)[:60000]}\n"
            "</evidence_to_audit>\n\n"
            "Responda ESTRITAMENTE um objeto JSON (sem texto fora do JSON) com:\n"
            '{"checklist": {"q1": true, "q2": true, "q3": true, "q4": true, '
            '"q5": true, "q6": true, "q7": true, "q8": true, "q9": true, '
            '"q10": true, "q11": true, "q12": true}, "findings": [], '
            '"contradictions": [], "uncertainties": [], "missing_research": [], '
            '"outline": []}\n\n'
            "Cada chave do checklist (q1..q12) é booleana e corresponde a:\n"
            f"{criteria_lines}\n\n"
            "- findings/contradictions/uncertainties/outline: arrays de strings.\n"
            "- missing_research: arrays de strings com instruções CONCRETAS de "
            "re-pesquisa (citação verbatim + URL exigidas); [] se aprovado.\n"
            "Nunca revele raciocínio privado ou cadeia de pensamento."
        )

    @staticmethod
    def _llm_call_kwargs(
        model: str,
        api_key: str,
        base_url: str | None,
        system: str,
        user: str,
    ) -> dict[str, Any]:
        """Binding atômico de modelo/chave/base URL para o provedor resolvado."""

        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "timeout": 180,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if base_url:
            kwargs["api_base"] = base_url
        return kwargs

    @staticmethod
    def _is_retryable_infra_error(exc: Exception) -> bool:
        """Retries contra falhas de rede, timeouts ou HTTP 500/502/503/504."""
        from app.services.llm import _classify_error

        status_code, _err_type, is_retryable, is_auth_error = _classify_error(exc)
        if is_auth_error or status_code in {401, 403}:
            return False
        return is_retryable

    async def _resolve_auditor_credentials(
        self, session: AsyncSession
    ) -> dict[str, Any]:
        """Resolve credenciais/settings da role "auditor" (apenas leitura).

        Somente I/O de banco (``runtime_settings``/``get_record``): é chamado
        no bloco de leitura de ``audit_point``, ANTES da sessão ser fechada.
        Retorna ``model``/``api_key``/``base_url``/``sensitive_keys``; campos
        vazios quando a role não está configurada — a chamada de rede do
        bloco 2 levantará ``AuditorNotConfiguredError`` (degradação graciosa).
        """
        from app.services.llm import _provider
        from app.services.settings import get_record, runtime_settings

        keys, models = await runtime_settings(session)
        model = models.get("auditor")
        api_key: str | None = None
        base_url: str | None = None
        if model:
            provider = _provider(model)
            api_key = keys.get(provider)
            if provider == "openai":
                record = await get_record(session)
                if record is not None and record.openai_base_url:
                    from app.services.settings import validate_base_url

                    base_url = validate_base_url(record.openai_base_url)
        return {
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "sensitive_keys": [str(k) for k in keys.values() if k],
        }

    async def _call_auditor_llm(
        self,
        system: str,
        user: str,
        credentials: dict[str, Any],
    ) -> str:
        """Bloco 2 (rede/LLM): 1 inicial + 3 retries com backoff 1s/2s/4s.

        NÃO recebe sessão e NÃO acessa o banco: nenhuma transação SQLite fica
        aberta durante a chamada de rede (evita sessões aninhadas e
        deadlocks). As credenciais já foram resolvidas pelo caller no bloco
        de leitura (``_resolve_auditor_credentials``).

        Falhas de infraestrutura não queimam ``attempt_count``; se todas as
        4 tentativas falharem, o caller persiste ``AUDIT_INCONCLUSIVE`` sem
        registrar tentativa (RN-304). Erros de autenticação (401/403) falham
        imediatamente (política de segurança, sem retry).
        """
        from app.services.llm import _provider, acompletion, apply_output_guardrail

        model = credentials.get("model")
        if not model:
            # Sem configuração explícita da role 'auditor', não há provedor/modelo
            # definido: degradação graciosa (AUDIT_INCONCLUSIVE) evita chamada LLM
            # ambígua. Padrão produtivo: gemini/gemini-3.8-flash (DEFAULT_AUDITOR_MODEL)
            # registrado em settings/AppSettings.models["auditor"].
            raise AuditorNotConfiguredError(
                "Auditor role not configured: set the 'auditor' model in settings "
                f"(recommended default: {DEFAULT_AUDITOR_MODEL})"
            )
        api_key = credentials.get("api_key")
        if not api_key:
            raise AuditorNotConfiguredError(
                f"No API key configured for auditor model provider '{_provider(model)}'"
            )
        base_url = credentials.get("base_url")

        kwargs = self._llm_call_kwargs(model, api_key, base_url, system, user)
        sensitive_keys = [str(k) for k in (credentials.get("sensitive_keys") or [])]

        last_error: str = ""
        for infra_attempt in range(1, MAX_AUDIT_ATTEMPTS + 1):
            try:
                response = await acompletion(**kwargs)
                msg = response.choices[0].message
                text = msg.content or ""
                if not text:
                    raise RuntimeError("LLM returned empty content")
                return apply_output_guardrail(text, extra_sensitive_values=sensitive_keys)
            except Exception as exc:
                if not self._is_retryable_infra_error(exc):
                    # Autenticação/erros não transitórios: sem retry
                    # imediato contra o mesmo provedor (política ML-01).
                    logger.warning(
                        "auditor LLM non-retryable failure: type=%s", type(exc).__name__
                    )
                    raise
                last_error = type(exc).__name__
                logger.warning(
                    "auditor LLM infra failure (infra attempt %s/%s): type=%s",
                    infra_attempt,
                    MAX_AUDIT_ATTEMPTS,
                    type(exc).__name__,
                )
            if infra_attempt < MAX_AUDIT_ATTEMPTS:
                await asyncio.sleep(_INFRA_BACKOFF_SECONDS[infra_attempt - 1])
        raise RuntimeError(
            f"Auditor LLM failed after {MAX_AUDIT_ATTEMPTS} infrastructure attempts ({last_error})"
        )

    @staticmethod
    def _parse_auditor_json(text: str) -> dict[str, Any]:
        """Parse do JSON do auditor, tolerante a blocos ```json ... ```."""
        from app.services.llm import parse_json

        parsed = parse_json(text)
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            parsed = parsed[0]
        if not isinstance(parsed, dict):
            raise ValueError("Auditor returned non-dict structured output")
        return parsed

    def _verdict_from_payload(self, payload: dict[str, Any], attempt_count: int) -> AuditVerdict:
        if not isinstance(payload.get("missing_research"), list):
            payload["missing_research"] = []
        return evaluate_audit_verdict(
            payload.get("checklist"),
            payload.get("findings"),
            payload.get("contradictions"),
            payload.get("uncertainties"),
            payload.get("missing_research"),
            payload.get("outline"),
            attempt_count,
        )

    def _inconclusive_verdict(self, reason: str) -> AuditVerdict:
        return AuditVerdict(
            approved=False,
            score=0,
            checklist=normalize_checklist(None),
            findings=[f"Auditoria inconclusiva: {reason}"],
            contradictions=[],
            uncertainties=["Evidência não auditada por falha de infraestrutura"],
            missing_research=[],
            outline=[],
            status=INCONCLUSIVE_STATUS,
            is_caveat=False,
        )

    async def _record_inconclusive(
        self,
        research_id: UUID,
        point_id: UUID,
        reason: str,
        *,
        mark_pending: bool = False,
    ) -> AuditVerdict:
        """Persiste falha de auditoria sem queimar ``point.attempt_count``.

        Abre a PRÓPRIA sessão de gravação — callers NÃO podem estar com outra
        sessão aberta (o particionamento em 3 blocos de ``audit_point`` e de
        ``run_investigation`` garante isso; sessões aninhadas bloqueiam o
        SQLite). Grava o ``AuditTrail`` do estágio ``point_audit`` e
        transiciona o ponto:

        - ``mark_pending=False`` (padrão; falha de infra/rede ou payload
          inválido da LLM) -> ``AUDIT_INCONCLUSIVE``;
        - ``mark_pending=True`` (role 'auditor' não configurada nas
          credenciais) -> ``AUDIT_PENDING``, aguardando a etapa de auditoria.

        Pontos fora de ``AUDITABLE_POINT_STATES`` (ex.: ``SCRAPER_FAILED``,
        coleta em andamento ou estados já conclusivos) têm o status
        preservado — nunca regredido.
        """
        from app.services.settings import runtime_settings

        verdict = self._inconclusive_verdict(reason)
        target_status = AUDIT_PENDING_STATUS if mark_pending else INCONCLUSIVE_STATUS
        async with self._session_factory() as session:
            keys, _models = await runtime_settings(session)
            sensitive_keys = [str(k) for k in keys.values() if k]
            sanitized = sanitize_audit_dict(
                {
                    "checklist": verdict.checklist,
                    "score": verdict.score,
                    "approved": verdict.approved,
                    "status": verdict.status,
                    "is_caveat": verdict.is_caveat,
                    "findings": verdict.findings,
                    "contradictions": verdict.contradictions,
                    "uncertainties": verdict.uncertainties,
                    "missing_research": verdict.missing_research,
                    "outline": verdict.outline,
                },
                sensitive_keys,
            )
            session.add(
                AuditTrail(
                    research_id=research_id,
                    point_id=point_id,
                    stage=AUDITOR_STAGE,
                    attempt=None,
                    details=sanitized,
                )
            )
            point = await session.get(ResearchPoint, point_id)
            if point is not None and point.status in AUDITABLE_POINT_STATES:
                # Transição do ponto: AUDIT_INCONCLUSIVE (falha de
                # infraestrutura/payload da LLM) ou AUDIT_PENDING (role
                # 'auditor' não configurada — aguarda a etapa de auditoria).
                point.status = target_status
            await session.commit()
        return verdict

    # ------------------------------------------------------- audit_point --

    async def audit_point(
        self,
        research_id: UUID,
        point_id: UUID,
        attempt_count: int | None = None,
    ) -> AuditVerdict:
        """Audita um ponto com veredito estruturado e persistência atômica.

        Execução em 3 blocos estritamente sequenciais, SEM sessões aninhadas
        (o SQLite bloqueia/congela quando uma segunda sessão disputa a
        conexão enquanto a primeira está aberta):
        1. Leitura: ``point``/attempt, ``evidence``, título/descrição e
           credenciais da role 'auditor' — a sessão é FECHADA ao fim do
           bloco, antes de qualquer rede;
        2. Rede: ``_call_auditor_llm`` roda sem transação de banco aberta;
        3. Gravação: falha da LLM -> ``_record_inconclusive`` (abre a própria
           sessão); sucesso -> parse + ``evaluate_audit_verdict`` + sessão
           limpa persistindo ``AuditTrail`` + ``point.status``/``point.audit``.
        """
        from app.audit.domain import AUDIT_CRITERIA
        from app.audit.prompt_loader import load_auditor_prompt

        attempt: int | None = None
        # ------- Bloco 1 (leitura): sessão fechada antes de qualquer rede ----
        async with self._session_factory() as session:
            point = await session.get(ResearchPoint, point_id)
            if point is None:
                raise ValueError(f"Research point not found: {point_id}")
            if attempt_count is not None:
                attempt = max(1, int(attempt_count))
            else:
                # Ciclo 1-based deste ciclo de auditoria: stored + 1, teto rn-305.
                attempt = int(point.attempt_count or 0) + 1
            attempt = min(attempt, MAX_AUDIT_ATTEMPTS)
            evidence = await self.get_point_evidence(session, point_id)
            point_title = point.title
            point_description = point.description
            credentials = await self._resolve_auditor_credentials(session)

            if not credentials.get("model") or not credentials.get("api_key"):
                if point.status in AUDITABLE_POINT_STATES:
                    point.status = AUDIT_PENDING_STATUS
                    await session.commit()
                return AuditVerdict(
                    approved=False,
                    score=0,
                    checklist=normalize_checklist(None),
                    findings=["Auditor role not configured"],
                    contradictions=[],
                    uncertainties=[],
                    missing_research=[],
                    outline=[],
                    status=AUDIT_PENDING_STATUS,
                    is_caveat=False,
                )

        system_prompt = load_auditor_prompt()
        user_prompt = self._build_auditor_prompt(
            point_title, point_description, evidence, AUDIT_CRITERIA
        )

        # ------- Bloco 2 (rede/LLM): NENHUMA transação de banco aberta -------
        try:
            llm_text = await self._call_auditor_llm(system_prompt, user_prompt, credentials)
        except Exception as exc:
            # T043 passo 6: infraestrutura falhou 4x -> AUDIT_INCONCLUSIVE
            # sem queimar attempt_count do ponto.
            reason = str(exc).strip() or type(exc).__name__
            return await self._record_inconclusive(research_id, point_id, reason[:200])

        # ------- Bloco 3 (gravação): sessão limpa, fechada antes do evento ---
        # Parse do JSON do auditor (tolerante a ```json ...```).
        try:
            payload = self._parse_auditor_json(llm_text)
        except (ValueError, json.JSONDecodeError) as exc:
            return await self._record_inconclusive(
                research_id, point_id, f"invalid auditor output ({type(exc).__name__})"
            )

        # Máquina de estados RN-302/RN-303/RN-305 (T041/T044).
        verdict = self._verdict_from_payload(payload, attempt_count=attempt)
        verdict.missing_research = ensure_concrete_missing_research_for_point(
            verdict, point_title
        )

        # Sanitização + persistência atômica (T044).
        async with self._session_factory() as session:
            from app.services.settings import runtime_settings

            keys, _models = await runtime_settings(session)
            sensitive_keys = [str(k) for k in keys.values() if k]

            audit_payload = {
                "checklist": verdict.checklist,
                "score": verdict.score,
                "approved": verdict.approved,
                "status": verdict.status,
                "is_caveat": verdict.is_caveat,
                "findings": verdict.findings,
                "contradictions": verdict.contradictions,
                "uncertainties": verdict.uncertainties,
                "missing_research": verdict.missing_research,
                "outline": verdict.outline,
                "attempt": attempt,
            }
            sanitized = sanitize_audit_dict(audit_payload, sensitive_keys)

            stored_point = await session.get(ResearchPoint, point_id)
            if stored_point is None:
                logger.error("Point %s vanished before verdict persistence", point_id)
                return self._inconclusive_verdict("point disappeared before persistence")

            session.add(
                AuditTrail(
                    research_id=research_id,
                    point_id=point_id,
                    stage=AUDITOR_STAGE,
                    attempt=attempt,
                    details=sanitized,
                )
            )
            stored_point.status = verdict.status
            stored_point.audit = sanitized
            await session.commit()

        # Evento público de veredito (persona="auditor").
        from app.services.research import add_event

        summary = f"Audit attempt {attempt}: {verdict.status} (score {verdict.score}/12)"
        await add_event(
            research_id,
            "auditor",
            "verdict_rendered",
            summary,
            {"attempt": attempt, "score": verdict.score, "status": verdict.status,
             "is_caveat": verdict.is_caveat},
            point_id=point_id,
            point_title=point_title,
            tool_type="auditor_verdict",
            round_no=attempt,
        )
        verdict.attempt = attempt if verdict.status != INCONCLUSIVE_STATUS else None
        return verdict

    # ------------------------------------------- transição research/WRITE --

    async def check_all_points_completed(
        self, session: AsyncSession, research_id: UUID
    ) -> bool:
        """Todos os pontos em estado conclusivo -> pesquisa transita para WRITE.

        Estados conclusivos: ``AUDIT_APPROVED`` e ``AUDIT_CAVEAT`` (RN-305).
        Sem pontos na pesquisa retorna False. Comita somente a transição.
        """
        rows = await session.scalars(select(ResearchPoint).where(ResearchPoint.research_id == research_id))
        points = list(rows)
        if not points:
            return False
        if not all(point.status in CONCLUSIVE_STATES for point in points):
            return False
        research = await session.get(Research, research_id)
        if research is None:
            return False
        if research.status != ResearchStatus.WRITE.value:
            research.status = ResearchStatus.WRITE.value
            await session.commit()
        return True

    # ------------------------------------------------ orquestração RN-301 --

    async def audit_research(self, research_id: UUID) -> list[tuple[UUID, AuditVerdict]]:
        """Audita todos os pontos elegíveis da pesquisa (RN-301, idempotente).

        Elegíveis: pontos em ``AUDIT_PENDING`` ou ``SCRAPER_RETRY``. Pontos
        já conclusivos (``AUDIT_APPROVED``/``AUDIT_CAVEAT``) não são
        re-auditados. Levanta ``LookupError`` se a pesquisa não existir.

        Retorna lista de tuplas ``(point_id, veredito)`` na ordem de posição
        do ponto na pesquisa.
        """
        async with self._session_factory() as session:
            research = await session.get(Research, research_id)
            if research is None:
                raise LookupError(f"Research not found: {research_id}")
            rows = await session.scalars(
                select(ResearchPoint)
                .where(ResearchPoint.research_id == research_id)
                .order_by(ResearchPoint.position.asc())
            )
            points = [
                (point.id, point.status)
                for point in rows
                if point.status in ("AUDIT_PENDING", SCRAPER_RETRY)
            ]
        results: list[tuple[UUID, AuditVerdict]] = []
        for point_id, _status in points:
            verdict = await self.audit_point(research_id, point_id)
            if verdict.status == SCRAPER_RETRY:
                # RN-303: reprovação incrementa attempt_count do ponto; o
                # re-disparo das personas é orquestrado pelo
                # InvestigationService (T047).
                await self.bump_retry_attempt(research_id, point_id)
            results.append((point_id, verdict))
        return results

    async def bump_retry_attempt(self, research_id: UUID, point_id: UUID) -> None:
        """RN-303: reprovação (SCRAPER_RETRY) incrementa attempt_count do ponto.

        Ponto único de contagem: consumido por ``audit_research`` e pelo
        ``InvestigationService`` (T046/T047) após um veredito de retry.
        """
        async with self._session_factory() as session:
            point = await session.get(ResearchPoint, point_id)
            if point is None or point.research_id != research_id:
                return
            point.attempt_count = int(point.attempt_count or 0) + 1
            await session.commit()


def ensure_concrete_missing_research_for_point(
    verdict: AuditVerdict, point_title: str
) -> list[str]:
    """Garante instruções concretas citando o título do ponto (RN-303)."""

    concrete = [m for m in verdict.missing_research if m.strip()]
    if concrete:
        return concrete
    synthesized: list[str] = []
    for finding in verdict.findings or []:
        text = str(finding or "").strip()
        if len(text) >= 12:
            synthesized.append(
                f'Investigar e corroborar com fonte específica citada verbatim + URL: "{text}" '
                f'(ponto "{point_title}")'
            )
    if not synthesized:
        synthesized.append(
            f'Reinvestigar o ponto "{point_title}" buscando fontes inéditas '
            "que cubram as lacunas detectadas nos 12 critérios canônicos, "
            "com citação verbatim e URL de origem."
        )
    return synthesized


__all__ = [
    "AUDIT_PENDING_STATUS",
    "AUDITOR_STAGE",
    "AuditorNotConfiguredError",
    "DEFAULT_AUDITOR_MODEL",
    "INCONCLUSIVE_STATUS",
    "AuditService",
    "ensure_concrete_missing_research_for_point",
]
