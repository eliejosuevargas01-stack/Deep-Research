"""T026: credenciais por persona no despacho real, sem rede nem banco real."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.investigation.llm_binding import LLMCallError
from app.investigation.service import InvestigationService
from app.models.domain_models import (
    AppSettings,
    Base,
    Research,
    ResearchPoint,
    ResearchStepResult,
)
from app.services.crypto import encrypt_secret

OPENAI_KEY = "sk-synthetic-openai-dispatch"
ANTHROPIC_KEY = "sk-synthetic-anthropic-dispatch"
BEARER_TOKEN = "synthetic-bearer-dispatch"
OPENAI_BASE = "https://openai.example.invalid/v1"
MODELS = {
    "scout": "openai/scout",
    "historian": "openai/hist",
    "skeptic": "anthropic/skeptic",
    "pragmatist": "openai/prag",
    "futurist": "anthropic/fut",
}
PERSONAS = ("historian", "skeptic", "pragmatist", "futurist")


class FakeJina:
    async def search(self, query):
        raise AssertionError("Resposta final não deve solicitar busca Jina")


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["per_provider", "scout_fallback", "missing_credential"])
async def test_persona_credential_dispatch(
    case, tmp_path, monkeypatch, make_litellm_final_response,
):
    models = dict(MODELS)
    keys = {"openai": OPENAI_KEY, "anthropic": ANTHROPIC_KEY}
    if case == "scout_fallback":
        del models["futurist"]
    elif case == "missing_credential":
        del keys["anthropic"]

    # Falha explícita se ambiente fornecer credenciais/modelos ao cenário ausente.
    # Nenhum valor real é incluído na mensagem de falha.
    from app.core.config import settings

    if case == "scout_fallback":
        assert not bool(getattr(settings, "FUTURIST_MODEL", None)), "Ambiente define FUTURIST_MODEL"
    if case == "missing_credential":
        assert not bool(getattr(settings, "ANTHROPIC_API_KEY", None)), "Ambiente define chave Anthropic"
    assert not bool(getattr(settings, "ANTHROPIC_BASE_URL", None)), "Ambiente define base Anthropic"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'persona_dispatch.db'}",
        poolclass=NullPool,
        connect_args={"timeout": 60},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    research_id, step_id = uuid4(), uuid4()
    calls = []

    async def fake_llm(*, model, messages, tools, api_key, api_base):
        calls.append((model, api_key, api_base))
        if case == "missing_credential" and model.startswith("anthropic/"):
            raise LLMCallError(
                3, f"missing credential; api_key={OPENAI_KEY}; Bearer {BEARER_TOKEN}"
            )
        # Simulate CoT leakage in raw content to prove it's stripped by JSON extraction
        raw_response_content = (
            "Pensamento: Vou usar a ferramenta Jina... não, melhor entregar direto.\n"
            f"```json\n{{\"result\": \"Resultado de {model}\", \"used_urls\": []}}\n```"
        )
        return make_litellm_final_response(raw_response_content, [], is_raw=True)

    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", fake_llm)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_factory() as db:
            db.add(AppSettings(
                id=1,
                models=models,
                encrypted_credentials={provider: encrypt_secret(key) for provider, key in keys.items()},
                openai_base_url=OPENAI_BASE,
            ))
            db.add(Research(id=research_id, theme="Tema sintético", status="SCRAPER"))
            db.add(ResearchPoint(
                id=step_id, research_id=research_id, position=1,
                title="Ponto sintético", description="", status="SCRAPER_PENDING",
            ))
            await db.commit()

        returned = await InvestigationService(
            session_factory, jina_adapter=FakeJina(),
        ).run_investigation(research_id)
        assert returned is None

        expected_models = {persona: models.get(persona) or models["scout"] for persona in PERSONAS}
        expected_calls = []
        for model in expected_models.values():
            provider = model.split("/", 1)[0]
            expected_calls.append((model, keys.get(provider), OPENAI_BASE if provider == "openai" else None))
        assert sorted(calls) == sorted(expected_calls)
        assert len(calls) == 4
        for model, key, base in calls:
            if model.startswith("anthropic/"):
                assert key != OPENAI_KEY
                assert base is None
                if case == "missing_credential":
                    assert key is None
            else:
                assert key == OPENAI_KEY
                assert key != ANTHROPIC_KEY
                assert base == OPENAI_BASE

        async with session_factory() as db:
            rows = list((await db.scalars(
                select(ResearchStepResult).where(ResearchStepResult.research_id == research_id)
            )).all())
        assert len(rows) == 4
        assert {row.worker for row in rows} == set(PERSONAS)
        for row in rows:
            assert row.step_id == step_id
            assert row.used_urls == []
            assert row.read_urls == []
            model = expected_models[row.worker]
            if case == "missing_credential" and model.startswith("anthropic/"):
                assert row.status == "FAILED"
                assert "missing credential" in row.result
                assert "api_key=***" in row.result
                assert "Bearer ***" in row.result
            else:
                assert row.status == "AUDIT_PENDING"
                assert row.result == f"Resultado de {model}"
            for secret in (OPENAI_KEY, ANTHROPIC_KEY, BEARER_TOKEN):
                assert secret not in row.result
                assert secret not in str(returned)

            # Assert isolation of prompt and CoT strings from final result
            assert "Instruções Operacionais Obrigatórias" not in row.result
            assert "Pensamento: Vou usar a ferramenta Jina" not in row.result
    finally:
        await engine.dispose()
