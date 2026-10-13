"""Authenticated HTTP API for persisted briefings."""
import math
from datetime import datetime, timezone
from uuid import UUID

import httpx
import litellm.exceptions as litellm_exceptions
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.domain import (
    BriefingStatus,
    InvalidContent,
    InvalidTransition,
    approve_briefing,
    edit_briefing,
    read_approved,
    reopen_briefing,
)
from app.briefing.llm_binding import make_scout_complete
from app.briefing.prompt_loader import PromptUnavailable, load_briefing_prompt
from app.briefing.schemas import (
    ApprovedBriefingResponse,
    BriefingApproveRequest,
    BriefingCreateRequest,
    BriefingFeedbackRequest,
    BriefingPoint,
    BriefingReopenRequest,
    BriefingResponse,
    BriefingVersionResponse,
)
from app.briefing.serp_client import JinaSerpClient, SerpSearchError
from app.briefing.service import (
    BriefingRevisionError,
    LLMAttemptError,
    orchestrate_persisted_briefing,
    revise_briefing_with_feedback,
)
from app.briefing.storage import (
    BriefingVersionConflictError,
    get_briefing,
    get_briefing_versions,
    save_briefing_transition,
)
from app.core.security import Principal, require_admin
from app.core.config import settings
from app.db.database import AsyncSessionLocal, get_db
from app.services.llm import ProviderConfigurationError
from app.services.settings import runtime_settings

router = APIRouter(tags=["briefings"])


def _response(briefing) -> BriefingResponse:
    return BriefingResponse(
        research_id=briefing.id,
        theme=briefing.theme,
        status=briefing.status,
        points=[BriefingPoint(title=p.title, description=p.description) for p in briefing.points],
        version=briefing.version,
        error=briefing.error,
        approved_at=briefing.approved_at,
    )


def _http_error(status: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status, detail=detail)


async def _runtime_jina_key() -> str:
    async with AsyncSessionLocal() as session:
        keys, _ = await runtime_settings(session)
        return keys.get("jina", "")


def _resolve_briefing_timeout() -> float:
    """Timeout único por tentativa (SERP/LLM/serviço), lido de settings e validado.

    Sem fallback silencioso: bool, tipo inválido, zero, negativo, NaN/inf
    abortam antes de credenciais, construção de cliente e I/O externo.
    """
    raw = settings.SEARCH_TIMEOUT_SECONDS
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Configuração de timeout de briefing inválida")
    try:
        value = float(raw)
    except (OverflowError, ValueError):
        raise ValueError("Configuração de timeout de briefing inválida") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Configuração de timeout de briefing inválida")
    return value


def _build_serp_client(api_key: str, timeout: float) -> JinaSerpClient:
    return JinaSerpClient(api_key, timeout=timeout)


def _build_llm_complete(timeout: float):
    return make_scout_complete(AsyncSessionLocal, default_timeout_s=timeout)


async def _release_auth_transaction(db: AsyncSession) -> None:
    if db.in_transaction():
        await db.rollback()


async def _load(db: AsyncSession, briefing_id: UUID):
    briefing = await get_briefing(db, briefing_id)
    if briefing is None:
        raise _http_error(404, "Briefing não encontrado")
    return briefing


def _parse_empty_body(raw: bytes, model):
    if not raw:
        return model()
    try:
        import json
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise _http_error(422, "Corpo inválido") from None
    if value is None:
        return model()
    if not isinstance(value, dict):
        raise _http_error(422, "Corpo inválido")
    try:
        return model.model_validate(value)
    except ValidationError:
        raise _http_error(422, "Corpo inválido") from None


async def _change(db: AsyncSession, old, new):
    try:
        return await save_briefing_transition(db, old, new)
    except BriefingVersionConflictError:
        raise _http_error(409, "Conflito de versão do briefing") from None


@router.post("/briefings", response_model=BriefingResponse, status_code=201)
async def create_briefing(
    payload: BriefingCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    await _release_auth_transaction(db)
    try:
        timeout = _resolve_briefing_timeout()
    except ValueError:
        raise _http_error(500, "Erro interno ao gerar briefing") from None
    api_key = await _runtime_jina_key()
    try:
        serp_client = _build_serp_client(api_key, timeout=timeout)
    except ValueError:
        raise _http_error(500, "Erro interno ao gerar briefing") from None
    llm_complete = _build_llm_complete(timeout=timeout)
    try:
        result = await orchestrate_persisted_briefing(
            AsyncSessionLocal,
            payload.theme,
            serp_client=serp_client,
            llm_complete=llm_complete,
            prompt_loader=load_briefing_prompt,
            llm_timeout_s=timeout,
        )
    except (PromptUnavailable,):
        raise _http_error(500, "Prompt de briefing indisponível") from None
    except SerpSearchError:
        raise _http_error(503, "Busca SERP indisponível") from None
    except LLMAttemptError:
        raise _http_error(503, "Geração de briefing indisponível") from None
    except (InvalidContent,):
        raise _http_error(422, "Conteúdo de briefing inválido") from None
    except (InvalidTransition, BriefingVersionConflictError):
        raise _http_error(409, "Estado ou versão de briefing incompatível") from None
    except ProviderConfigurationError:
        raise _http_error(500, "Erro interno ao gerar briefing") from None
    except (litellm_exceptions.AuthenticationError, litellm_exceptions.PermissionDeniedError):
        raise _http_error(500, "Erro interno ao gerar briefing") from None
    except litellm_exceptions.APIError as exc:
        code = getattr(exc, "status_code", None)
        if isinstance(code, int) and not isinstance(code, bool) and code in (401, 403):
            raise _http_error(500, "Erro interno ao gerar briefing") from None
        raise
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if isinstance(code, int) and not isinstance(code, bool) and code in (401, 403):
            raise _http_error(500, "Erro interno ao gerar briefing") from None
        raise
    if result.status.value == "failed":
        if result.error == "Prompt de briefing indisponível":
            raise _http_error(500, "Prompt de briefing indisponível")
        if result.error == "Busca SERP indisponível":
            raise _http_error(503, "Busca SERP indisponível")
        raise _http_error(503, "Geração de briefing indisponível")
    response.status_code = 201
    return _response(result)


@router.get("/briefings/approved/{research_id}", response_model=ApprovedBriefingResponse)
async def get_approved_briefing(
    research_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    await _release_auth_transaction(db)
    briefing = await _load(db, research_id)
    try:
        approved = read_approved(briefing)
    except InvalidTransition:
        raise _http_error(409, "Briefing não está aprovado") from None
    return ApprovedBriefingResponse(
        research_id=approved.id,
        theme=approved.theme,
        points=[BriefingPoint(title=p.title, description=p.description) for p in approved.points],
        approved_at=approved.approved_at,
    )


@router.get("/briefings/{research_id}", response_model=BriefingResponse)
async def get_current_briefing(
    research_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    await _release_auth_transaction(db)
    return _response(await _load(db, research_id))


@router.patch("/briefings/{research_id}", response_model=BriefingResponse)
async def patch_briefing(
    research_id: UUID,
    payload: BriefingFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    await _release_auth_transaction(db)
    briefing = await _load(db, research_id)
    if briefing.status != BriefingStatus.DRAFT:
        raise _http_error(409, "Apenas briefings em rascunho podem ser revisados")
    try:
        timeout = _resolve_briefing_timeout()
    except ValueError:
        raise _http_error(500, "Erro interno ao revisar briefing") from None
    api_key = await _runtime_jina_key()
    try:
        serp_client = _build_serp_client(api_key, timeout=timeout)
    except ValueError:
        raise _http_error(500, "Erro interno ao revisar briefing") from None
    llm_complete = _build_llm_complete(timeout=timeout)
    try:
        revised = await revise_briefing_with_feedback(
            db,
            briefing,
            payload.note,
            serp_client=serp_client,
            llm_complete=llm_complete,
            llm_timeout_s=timeout,
        )
    except BriefingRevisionError as exc:
        if exc.args and exc.args[0] == "Prompt de briefing indisponível":
            raise _http_error(500, "Prompt de briefing indisponível") from None
        if exc.args and exc.args[0] == "Busca SERP indisponível":
            raise _http_error(503, "Busca SERP indisponível") from None
        raise _http_error(502, "Geração de briefing indisponível") from None
    except (InvalidContent,):
        raise _http_error(422, "Conteúdo de briefing inválido") from None
    except (InvalidTransition, BriefingVersionConflictError):
        raise _http_error(409, "Estado ou versão de briefing incompatível") from None
    except ProviderConfigurationError:
        raise _http_error(500, "Erro interno ao revisar briefing") from None
    except (litellm_exceptions.AuthenticationError, litellm_exceptions.PermissionDeniedError):
        raise _http_error(500, "Erro interno ao revisar briefing") from None
    except litellm_exceptions.APIError as exc:
        code = getattr(exc, "status_code", None)
        if isinstance(code, int) and not isinstance(code, bool) and code in (401, 403):
            raise _http_error(500, "Erro interno ao revisar briefing") from None
        raise
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if isinstance(code, int) and not isinstance(code, bool) and code in (401, 403):
            raise _http_error(500, "Erro interno ao revisar briefing") from None
        raise
    return _response(revised)


@router.post("/briefings/{research_id}/approve", response_model=BriefingResponse)
async def approve_briefing_route(
    research_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    _parse_empty_body(await request.body(), BriefingApproveRequest)
    await _release_auth_transaction(db)
    briefing = await _load(db, research_id)
    try:
        changed = approve_briefing(briefing, datetime.now(timezone.utc))
    except InvalidContent:
        raise _http_error(422, "Conteúdo de briefing inválido") from None
    except InvalidTransition:
        raise _http_error(409, "Briefing não pode ser aprovado neste estado") from None
    return _response(await _change(db, briefing, changed))


@router.post("/briefings/{research_id}/reopen", response_model=BriefingResponse)
async def reopen_briefing_route(
    research_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    _parse_empty_body(await request.body(), BriefingReopenRequest)
    await _release_auth_transaction(db)
    briefing = await _load(db, research_id)
    if briefing.status == BriefingStatus.APPROVED:
        raise _http_error(409, "Briefing aprovado não pode ser reaberto")
    try:
        changed = reopen_briefing(briefing)
    except InvalidTransition:
        raise _http_error(409, "Briefing não pode ser reaberto neste estado") from None
    return _response(await _change(db, briefing, changed))


@router.get("/briefings/{research_id}/versions", response_model=list[BriefingVersionResponse])
async def list_briefing_versions(
    research_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin),
):
    await _release_auth_transaction(db)
    await _load(db, research_id)
    versions = await get_briefing_versions(db, research_id)
    return [
        BriefingVersionResponse(
            version=item.version,
            status=item.status,
            points=[BriefingPoint(**p) for p in item.points_json],
            error=item.error,
            approved_at=item.approved_at,
            created_at=item.created_at,
        )
        for item in versions
    ]
