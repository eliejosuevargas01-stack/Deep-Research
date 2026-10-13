"""Orquestrador fan-out da investigação (T012, RN-02/RN-03/RN-09/RN-10)."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.investigation.prompts import PERSONA_NAMES
from app.investigation.storage import get_pending_workers_for_research, save_step_result
from app.models.domain_models import AppSettings
from app.services.crypto import decrypt_secret
from app.core.config import settings as app_config
from app.services.settings import PROVIDER_BASE_URLS, runtime_jina_proxy, runtime_settings
from app.investigation.tools import JinaToolAdapter


def _provider_for_model(model: str) -> str:
    return model.split("/", 1)[0].lower() if "/" in model else "openai"


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

    async def run_investigation(self, research_id: UUID) -> None:
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
            point_data = [(p.id, p.title) for p in points]
            jina_key, proxy_url, proxy_key, models = await _resolve_credentials(session)
            resolved_base = models.get("_provider_base_url") or None
            resolved_key = models.get("_provider_key") or None
            models = {key: value for key, value in models.items() if not key.startswith("_")}
            persona_credentials = await _resolve_persona_credentials(session, models)
            pending_workers = await get_pending_workers_for_research(session, research_id)
            if not pending_workers:
                return

        adapter = (
            self.jina_adapter
            if self.jina_adapter is not None
            else JinaToolAdapter(api_key=jina_key, proxy_url=proxy_url, proxy_key=proxy_key)
        )
        models["_credentials_by_persona"] = persona_credentials
        worker = PersonaWorker(
            adapter,
            app_settings_models=models,
            api_base=resolved_base if self.api_base is None else self.api_base,
            api_key=resolved_key if self.api_key is None else self.api_key,
        )

        async def _run_single(step_id: UUID, step_title: str, persona: str) -> None:
            res = await worker.execute(research_id, step_id, step_title, persona, theme)
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
                )

        tasks = [
            _run_single(item["step_id"], item["step_title"], item["persona"])
            for item in pending_workers
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        async with self.session_factory() as session:
            research = await session.get(Research, research_id)
            if research is None:
                return
            rows = await session.execute(
                select(ResearchPoint).where(ResearchPoint.research_id == research_id)
            )
            final_points = list(rows.scalars().all())
            if final_points and all(p.status == "SCRAPER_FAILED" for p in final_points):
                research.status = ResearchStatus.FAILED.value
            elif not final_points:
                research.status = ResearchStatus.FAILED.value
            else:
                research.status = ResearchStatus.AUDIT.value
            await session.commit()
