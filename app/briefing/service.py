"""Orquestração local da geração de briefing (T010)."""

import asyncio
import json
import math
from dataclasses import replace

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.domain import (
    Briefing,
    InvalidContent,
    complete_briefing,
    fail_briefing,
    new_briefing,
)
from app.briefing.prompt_loader import PromptUnavailable, load_briefing_prompt
from app.briefing.serp_client import JinaSerpClient, SerpSearchError


_PROMPT_ERROR = "Prompt de briefing indisponível"
_SERP_ERROR = "Busca SERP indisponível"
_GENERATION_ERROR = "Geração de briefing indisponível"
_INVALID_OUTPUT = "Saída LLM inválida"

_OUTPUT_FORMAT = (
    "Retorne exclusivamente uma lista JSON válida de objetos com "
    "'title' e 'description', sem texto adicional."
)


class LLMAttemptError(Exception):
    """Falha externa de LLM com mensagem fixa e segura (sem payload)."""

    def __init__(self):
        super().__init__(_GENERATION_ERROR)


def _valid_config(llm_attempts: int, llm_timeout_s: float) -> None:
    if isinstance(llm_attempts, bool) or not isinstance(llm_attempts, int) or not 1 <= llm_attempts <= 4:
        raise ValueError("Configuração de tentativas LLM inválida")
    if isinstance(llm_timeout_s, bool) or not isinstance(llm_timeout_s, (int, float)):
        raise ValueError("Configuração de timeout LLM inválida")
    try:
        timeout_float = float(llm_timeout_s)
    except (OverflowError, ValueError):
        raise ValueError("Configuração de timeout LLM inválida")
    if not math.isfinite(timeout_float) or timeout_float <= 0:
        raise ValueError("Configuração de timeout LLM inválida")


def _parse_points(raw: str) -> list:
    """JSON puro ou cerca ```json única exata; lista integral exigida."""
    if not isinstance(raw, str):
        raise InvalidContent(_INVALID_OUTPUT)
    text = raw.strip()
    if text.startswith("```json"):
        if not text.endswith("```"):
            raise InvalidContent(_INVALID_OUTPUT)
        text = text[len("```json"):-len("```")].strip()
    value = json.loads(text)
    if not isinstance(value, list):
        raise InvalidContent(_INVALID_OUTPUT)
    return value


async def generate_briefing(
    theme: str,
    *,
    serp_client,
    llm_complete,
    prompt_loader=load_briefing_prompt,
    llm_attempts: int = 4,
    llm_timeout_s: float = 30.0,
):
    """Gera briefing em memória; I/O externo injetado, nunca implícito."""
    _valid_config(llm_attempts, llm_timeout_s)
    briefing = new_briefing(theme)
    try:
        system = prompt_loader()
        if not isinstance(system, str) or not system.strip():
            raise PromptUnavailable(_PROMPT_ERROR)
    except PromptUnavailable:
        return fail_briefing(briefing, _PROMPT_ERROR)
    try:
        serp_results = await serp_client.search(briefing.theme)
    except SerpSearchError:
        return fail_briefing(briefing, _SERP_ERROR)
    user = json.dumps(
        {"tema": briefing.theme, "resultados_serp": serp_results, "formato_saida": _OUTPUT_FORMAT},
        ensure_ascii=False,
    )
    for _ in range(llm_attempts):
        deadline = asyncio.timeout(llm_timeout_s)
        try:
            async with deadline:
                raw = await llm_complete(system, user)
        except asyncio.CancelledError:
            raise
        except LLMAttemptError:
            continue
        except TimeoutError:
            if deadline.expired():
                continue
            raise
        try:
            return complete_briefing(briefing, _parse_points(raw))
        except (json.JSONDecodeError, InvalidContent):
            continue
    return fail_briefing(briefing, _GENERATION_ERROR)


_REVISION_PROMPT_NOTE_MAX = 4000


class BriefingRevisionError(Exception):
    """Falha do Scout na revisão por feedback (mensagem fixa e segura)."""

    def __init__(self, error: str = _GENERATION_ERROR):
        super().__init__(error)
        self.error = error


def _revision_error_message(exc: BaseException) -> str:
    if isinstance(exc, PromptUnavailable):
        return _PROMPT_ERROR
    if isinstance(exc, SerpSearchError):
        return _SERP_ERROR
    return _GENERATION_ERROR


async def _mark_failed(db: AsyncSession, briefing: Briefing, error: str) -> None:
    """Sinaliza briefing e pesquisa como FAILED, com versão incrementada."""
    from app.briefing.domain import BriefingStatus
    from app.briefing.storage import BriefingVersionConflictError, save_briefing_transition
    from app.models.domain_models import Research, ResearchStatus, now

    failed = replace(briefing, status=BriefingStatus.FAILED,
                     points=(), error=error, version=briefing.version + 1)
    try:
        await save_briefing_transition(db, briefing, failed)
    except BriefingVersionConflictError:
        await db.rollback()
    await db.execute(
        update(Research)
        .where(Research.id == briefing.id)
        .values(status=ResearchStatus.FAILED, error=error, updated_at=now())
    )
    await db.commit()


async def revise_briefing_with_feedback(
    db: AsyncSession,
    briefing: Briefing,
    note: str,
    serp_client: JinaSerpClient,
    llm_complete,
    llm_attempts: int = 4,
    llm_timeout_s: float = 30.0,
) -> Briefing:
    """Reexecuta o Scout combinando tema, rascunho atual e nota de feedback (T016).

    I/O externo fora da transação; persistência atômica em Tx única com CAS
    por versão. Em falha: briefing marcado FAILED (versão incrementada) e
    erro levantado para a rota mapear a matriz de status HTTP.
    """
    from app.briefing.domain import BriefingStatus, edit_briefing
    from app.briefing.storage import (
        BriefingVersionConflictError,
        save_briefing_transition,
    )
    from app.models.domain_models import Research, ResearchStatus, now

    normalized_note = note.strip()
    if len(normalized_note) < 3:
        raise InvalidContent("Feedback deve conter pelo menos 3 caracteres")
    previous_points = [
        {"title": p.title, "description": p.description} for p in briefing.points
    ]
    try:
        system = load_briefing_prompt()
        if not isinstance(system, str) or not system.strip():
            raise PromptUnavailable(_PROMPT_ERROR)
    except PromptUnavailable:
        await _mark_failed(db, briefing, _PROMPT_ERROR)
        raise BriefingRevisionError(_PROMPT_ERROR) from None
    try:
        serp_results = await serp_client.search(briefing.theme)
    except SerpSearchError:
        await _mark_failed(db, briefing, _SERP_ERROR)
        raise BriefingRevisionError(_SERP_ERROR) from None
    user = json.dumps(
        {
            "tema": briefing.theme,
            "resultados_serp": serp_results,
            "rascunho_atual": previous_points,
            "feedback": normalized_note[:_REVISION_PROMPT_NOTE_MAX],
            "formato_saida": _OUTPUT_FORMAT,
        },
        ensure_ascii=False,
    )
    for _ in range(llm_attempts):
        deadline = asyncio.timeout(llm_timeout_s)
        try:
            async with deadline:
                raw = await llm_complete(system, user)
        except asyncio.CancelledError:
            raise
        except LLMAttemptError:
            continue
        except TimeoutError:
            if deadline.expired():
                continue
            raise
        try:
            points = _parse_points(raw)
            revised = edit_briefing(briefing, points)
            persisted = await save_briefing_transition(db, briefing, revised)
            await db.execute(
                update(Research)
                .where(Research.id == briefing.id)
                .values(status=ResearchStatus.PENDING_APPROVAL, updated_at=now())
            )
            await db.commit()
            return persisted
        except (json.JSONDecodeError, InvalidContent):
            continue
    await _mark_failed(db, briefing, _GENERATION_ERROR)
    raise BriefingRevisionError(_GENERATION_ERROR)


async def orchestrate_persisted_briefing(
    session_factory,
    theme: str,
    *,
    serp_client,
    llm_complete,
    prompt_loader=load_briefing_prompt,
    llm_attempts: int = 4,
    llm_timeout_s: float = 30.0,
):
    """Orquestração com persistência Tx1 curta, I/O fora de Tx e CAS Tx2."""
    from app.briefing.storage import (
        create_generating_briefing,
        save_briefing_transition,
    )

    _valid_config(llm_attempts, llm_timeout_s)
    initial_briefing = new_briefing(theme)

    # Tx1: reserva inicial em banco
    async with session_factory() as session:
        await create_generating_briefing(session, initial_briefing)

    final_briefing = None
    try:
        # I/O fora de qualquer transação de banco de dados
        try:
            system = prompt_loader()
            if not isinstance(system, str) or not system.strip():
                raise PromptUnavailable(_PROMPT_ERROR)
        except PromptUnavailable:
            final_briefing = fail_briefing(initial_briefing, _PROMPT_ERROR)
        else:
            try:
                serp_results = await serp_client.search(initial_briefing.theme)
            except SerpSearchError:
                final_briefing = fail_briefing(initial_briefing, _SERP_ERROR)
            else:
                user = json.dumps(
                    {
                        "tema": initial_briefing.theme,
                        "resultados_serp": serp_results,
                        "formato_saida": _OUTPUT_FORMAT,
                    },
                    ensure_ascii=False,
                )
                success_points = None
                final_briefing = None
                for _ in range(llm_attempts):
                    deadline = asyncio.timeout(llm_timeout_s)
                    try:
                        async with deadline:
                            raw = await llm_complete(system, user)
                    except asyncio.CancelledError:
                        raise
                    except LLMAttemptError:
                        continue
                    except TimeoutError:
                        if deadline.expired():
                            continue
                        raise
                    try:
                        success_points = _parse_points(raw)
                        final_briefing = complete_briefing(initial_briefing, success_points)
                        break
                    except (json.JSONDecodeError, InvalidContent):
                        continue

                if final_briefing is None:
                    final_briefing = fail_briefing(initial_briefing, _GENERATION_ERROR)

        # Tx2: transição atômica CAS
        async with session_factory() as session:
            persisted = await save_briefing_transition(
                session, initial_briefing, final_briefing
            )
        return persisted

    except BaseException:
        # Política de órfãos: marca failed na emergência se Tx2 não ocorreu
        try:
            emergency_briefing = fail_briefing(
                initial_briefing, "Processamento abortado ou cancelado"
            )
            async with session_factory() as session:
                await save_briefing_transition(
                    session, initial_briefing, emergency_briefing
                )
        except Exception:
            pass
        raise
