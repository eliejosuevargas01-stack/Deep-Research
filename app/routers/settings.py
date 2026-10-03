from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import Principal, require_admin
from app.db.database import get_db
from app.schemas import (
    ModelDiscoveryRequest,
    ModelDiscoveryResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    SettingsUpdate,
)
from app.services.llm import list_provider_models, test_provider_key
from app.services.settings import _UNSET, get_record, public_settings, runtime_settings, update_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(_: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await public_settings(db)


@router.put("")
async def put_settings(payload: SettingsUpdate, _: Principal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    callback_url = payload.callback_url if "callback_url" in payload.model_fields_set else _UNSET
    openai_base_url = payload.openai_base_url if "openai_base_url" in payload.model_fields_set else _UNSET
    try:
        res = await update_settings(
            db,
            payload.provider_keys,
            payload.models,
            callback_url=callback_url,
            openai_base_url=openai_base_url,
        )
        return res
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/test", response_model=ProviderTestResponse)
async def test_setting_key(payload: ProviderTestRequest, _: Principal = Depends(require_admin)):
    success, message = await test_provider_key(payload.provider, payload.api_key, payload.base_url)
    models: list[str] = []
    if success and payload.provider in {"openai", "anthropic", "gemini", "litellm"}:
        try:
            models = await list_provider_models(payload.provider, payload.api_key, payload.base_url)
        except Exception:
            models = []
    return ProviderTestResponse(success=success, message=message, models=models)


@router.post("/models", response_model=ModelDiscoveryResponse)
async def discover_models(payload: ModelDiscoveryRequest, _: Principal = Depends(require_admin)):
    try:
        models = await list_provider_models(payload.provider, payload.api_key, payload.base_url)
        return ModelDiscoveryResponse(provider=payload.provider, models=models)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to discover models: {type(exc).__name__}")


@router.get("/models")
async def get_provider_models(
    provider: str | None = Query(None, description="Provedor específico (ex: openai, anthropic, gemini, litellm)"),
    principal: Principal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    keys, models = await runtime_settings(db)
    record = await get_record(db)
    target_providers = [provider] if provider else ["openai", "anthropic", "gemini", "litellm"]
    catalog: dict[str, list[str]] = {}

    for p in target_providers:
        api_key = keys.get(p)
        base_url = record.openai_base_url if p == "openai" else None
        if api_key:
            catalog[p] = await list_provider_models(p, api_key, base_url)
        else:
            catalog[p] = []

    return {"models_by_provider": catalog}
