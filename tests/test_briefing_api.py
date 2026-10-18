"""HTTP contracts for briefing routes; isolated SQLite and real admin auth."""
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.update({
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "ADMIN_PASSWORD": "correct horse battery staple",
    "SESSION_SECRET": "s" * 32,
    "APP_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "ENVIRONMENT": "test",
    "API_AUTH_SECRET": "test-api-secret-0123456789",
})

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.briefing.domain import BriefingPoint, approve_briefing, complete_briefing, new_briefing
from app.briefing.storage import (
    BriefingVersionConflictError,
    create_generating_briefing,
    get_briefing,
    get_briefing_versions,
    save_briefing_transition,
)
from app.core.security import new_session_values
from app.db.database import get_db
from app.main import app
from app.models.domain_models import Base, BriefingRecord

POINTS = [{"title": f"P{i}", "description": f"Description {i}"} for i in range(3)]
SECRET_CANARY = "provider-secret-canary"


class FakeSerp:
    def __init__(self, error=None):
        self.calls = 0
        self.queries = []
        self.error = error

    async def search(self, theme):
        self.calls += 1
        self.queries.append(theme)
        if self.error:
            raise self.error
        return [{"title": "result", "url": "https://example.test", "description": "evidence"}]


class FakeLLM:
    def __init__(self, error=None, responses=None):
        self.calls = 0
        self.error = error
        self._responses = list(responses or [])

    async def __call__(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        if self._responses:
            item = self._responses.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return json.dumps(POINTS)


class BriefingAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from app.core.config import settings
        import app.core.security as security

        for config in (settings, security.settings):
            original = config.API_AUTH_SECRET
            config.API_AUTH_SECRET = "test-api-secret-0123456789"
            self.addCleanup(setattr, config, "API_AUTH_SECRET", original)

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def db_override():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = db_override
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.serp = FakeSerp()
        self.llm = FakeLLM()
        self.serp_builder = patch("app.briefing.router._build_serp_client", return_value=self.serp)
        self.serp_builder.start()
        self.key_patch = patch("app.briefing.router._runtime_jina_key", return_value="test-key")
        self.key_patch.start()
        self.factory_patch = patch("app.briefing.router.AsyncSessionLocal", self.sessions)
        self.factory_patch.start()
        self.inv_factory_patch = patch("app.investigation.router.AsyncSessionLocal", self.sessions)
        self.inv_factory_patch.start()
        # T040: neutraliza a execução real dos workers em background; o
        # despacho continua observável via await_count do mock.
        self.inv_mock = AsyncMock()
        self.inv_run_patch = patch(
            "app.investigation.service.InvestigationService.run_investigation",
            new=self.inv_mock,
        )
        self.inv_run_patch.start()
        self.llm_builder = patch("app.briefing.router._build_llm_complete", return_value=self.llm)
        self.llm_builder.start()

    async def asyncTearDown(self):
        self.serp_builder.stop()
        self.key_patch.stop()
        self.factory_patch.stop()
        self.inv_factory_patch.stop()
        self.inv_run_patch.stop()
        self.llm_builder.stop()
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()

    async def _seed(self, status="draft"):
        async with self.sessions() as db:
            initial = new_briefing("A valid briefing theme")
            await create_generating_briefing(db, initial)
            current = complete_briefing(initial, [BriefingPoint(**p) for p in POINTS])
            await save_briefing_transition(db, initial, current)
            if status == "approved":
                from datetime import datetime, timezone
                next_state = approve_briefing(current, datetime.now(timezone.utc))
                await save_briefing_transition(db, current, next_state)
                current = next_state
            return str(current.id)

    async def _snapshot(self, briefing_id):
        from uuid import UUID
        async with self.sessions() as db:
            current = await get_briefing(db, UUID(briefing_id))
            history = await get_briefing_versions(db, UUID(briefing_id))
            return current, [(x.version, x.status, x.points_json) for x in history]

    async def _count(self):
        async with self.sessions() as db:
            return await db.scalar(select(func.count()).select_from(BriefingRecord))

    async def _research_snapshot(self, briefing_id):
        """T040: estado de research + research_points após aprovação implícita."""
        from uuid import UUID

        from app.models.domain_models import Research, ResearchPoint

        async with self.sessions() as db:
            research = await db.get(Research, UUID(briefing_id))
            rows = await db.execute(
                select(ResearchPoint).where(ResearchPoint.research_id == UUID(briefing_id))
            )
            points = list(rows.scalars().all())
            return research, points

    async def _cookie_auth(self):
        token, csrf, record = new_session_values()
        async with self.sessions() as db:
            db.add(record)
            await db.commit()
        return {"dr_session": token}, csrf

    async def test_create_sync_returns_persisted_draft_and_reuses_serp(self):
        response = await self.client.post("/briefings", json={"theme": "A valid briefing theme"}, headers={"Authorization": "Bearer test-api-secret-0123456789"})
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual((body["status"], body["version"], len(body["points"])), ("draft", 2, 3))
        self.assertEqual((self.serp.calls, self.llm.calls), (1, 1))
        current, history = await self._snapshot(body["research_id"])
        self.assertEqual([v for v, _, _ in history], [2])

    async def test_create_invalid_rejected_before_generation(self):
        before = await self._count()
        response = await self.client.post("/briefings", json={"theme": "x"}, headers={"Authorization": "Bearer test-api-secret-0123456789"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual((self.serp.calls, self.llm.calls), (0, 0))
        self.assertEqual(await self._count(), before)

    async def test_auth_real_dependency_cookie_csrf_bearer_and_api_key(self):
        no_auth = await self.client.get("/briefings/00000000-0000-0000-0000-000000000001")
        self.assertEqual(no_auth.status_code, 401)
        bid = await self._seed()
        cookies, csrf = await self._cookie_auth()
        self.client.cookies.set("dr_session", cookies["dr_session"])
        denied = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"})
        self.assertEqual(denied.status_code, 403)
        denied = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers={"X-CSRF-Token": "bad"})
        self.assertEqual(denied.status_code, 403)
        good = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(good.status_code, 200)
        self.client.cookies.clear()
        bearer = await self.client.get(f"/briefings/{bid}", headers={"Authorization": "Bearer test-api-secret-0123456789"})
        api_key = await self.client.get(f"/briefings/{bid}", headers={"X-API-Key": "test-api-secret-0123456789"})
        self.assertEqual((bearer.status_code, api_key.status_code), (200, 200))

    async def test_read_edit_approve_reopen_approved_and_versions(self):
        # T036-T040 (Sprint C8): /approve extinto; PATCH revisa e aprova
        # automaticamente com auto-investigate; 2ª revisão bloqueada com 409.
        bid = await self._seed()
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        current = await self.client.get(f"/briefings/{bid}", headers=headers)
        self.assertEqual(current.json()["status"], "draft")
        before = await self._snapshot(bid)
        invalid = await self.client.patch(f"/briefings/{bid}", json={"note": "x"}, headers=headers)
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(await self._snapshot(bid), before)
        edited = await self.client.patch(f"/briefings/{bid}", json={"note": "Please add another supporting perspective"}, headers=headers)
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["status"], "approved")
        self.assertTrue(edited.json()["approved_at"])
        self.assertEqual(edited.json()["version"], 4)
        self.assertEqual(self.inv_mock.await_count, 1)
        research, points = await self._research_snapshot(bid)
        self.assertIn(research.status, ("SCRAPER",))
        self.assertEqual(len(points), 3)
        self.assertTrue(all(p.status == "SCRAPER_IN_PROGRESS" for p in points))
        # T036: rota /approve extinta retorna 404.
        gone = await self.client.post(f"/briefings/{bid}/approve", headers=headers)
        self.assertEqual(gone.status_code, 404, gone.text)
        before = await self._snapshot(bid)
        reopen = await self.client.post(f"/briefings/{bid}/reopen", json=None, headers=headers)
        self.assertEqual(reopen.status_code, 409, reopen.text)
        self.assertEqual(reopen.json()["detail"], "Briefing aprovado não pode ser reaberto")
        self.assertEqual(await self._snapshot(bid), before)
        for body in ([], "bad", 3, True, {"extra": "bad"}):
            response = await self.client.post(f"/briefings/{bid}/reopen", json=body, headers=headers)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(await self._snapshot(bid), before)
        approved = await self.client.get(f"/briefings/approved/{bid}", headers=headers)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(set(approved.json()), {"research_id", "theme", "points", "approved_at"})
        # E001: PATCH executa 1 chamada IA extra para formular a query SERP
        # (tema+feedback) antes da geração revisada.
        self.assertEqual(self.llm.calls, 2)
        # T039: segunda revisão por feedback bloqueada com 409.
        edit = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers=headers)
        self.assertEqual(edit.status_code, 409)
        self.assertEqual(self.inv_mock.await_count, 1)
        # Investigação já iniciada pelo PATCH: re-disparo via /investigate dá 409.
        conflict = await self.client.post(f"/briefings/{bid}/investigate", headers=headers)
        self.assertEqual(conflict.status_code, 409)
        history = await self.client.get(f"/briefings/{bid}/versions", headers=headers)
        versions = [x["version"] for x in history.json()]
        self.assertEqual(versions, sorted(versions))
        self.assertNotIn("briefing_id", history.json()[0])
        self.assertTrue(all("created_at" in x for x in history.json()))
        self.assertEqual(self.serp.calls, 1)
        # Current generating v1 has no history snapshot yet.
        async with self.sessions() as db:
            generating = new_briefing("Another valid briefing theme")
            await create_generating_briefing(db, generating)
        empty_history = await self.client.get(f"/briefings/{generating.id}/versions", headers=headers)
        self.assertEqual((empty_history.status_code, empty_history.json()), (200, []))

    async def test_missing_and_unapproved_errors_preserve_and_external_io_zero(self):
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        missing = "00000000-0000-0000-0000-000000000001"
        for method, path, kwargs in (
            (self.client.get, f"/briefings/{missing}", {}),
            (self.client.get, f"/briefings/{missing}/versions", {}),
            (self.client.get, f"/briefings/approved/{missing}", {}),
            (self.client.patch, f"/briefings/{missing}", {"json": {"note": "Valid feedback"}}),
            (self.client.post, f"/briefings/{missing}/approve", {}),
            (self.client.post, f"/briefings/{missing}/reopen", {}),
        ):
            response = await method(path, headers=headers, **kwargs)
            self.assertEqual(response.status_code, 404, response.text)
        # Keep the remaining rejection checks seeded and read-only.
        headers = {"X-API-Key": "test-api-secret-0123456789"}
        bid = await self._seed()
        before = await self._snapshot(bid)
        response = await self.client.get(f"/briefings/approved/{bid}", headers=headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(await self._snapshot(bid), before)
        self.assertEqual((self.serp.calls, self.llm.calls), (0, 0))

    async def test_generation_errors_are_safe_and_persisted(self):
        from app.briefing.prompt_loader import PromptUnavailable
        from app.briefing.serp_client import SerpSearchError
        from app.briefing.service import LLMAttemptError
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        cases = (
            ("prompt", PromptUnavailable(SECRET_CANARY), None, 500, "Prompt de briefing indisponível"),
            ("serp", None, SerpSearchError(4), 503, "Busca SERP indisponível"),
            ("llm", None, LLMAttemptError(), 503, "Geração de briefing indisponível"),
        )
        for label, prompt_error, io_error, status, expected in cases:
            with self.subTest(label=label):
                before = await self._count()
                prompt_patch = patch("app.briefing.router.load_briefing_prompt", side_effect=prompt_error) if prompt_error else None
                if prompt_patch:
                    prompt_patch.start()
                self.serp.error = io_error if label == "serp" else None
                self.llm.error = io_error if label == "llm" else None
                try:
                    response = await self.client.post("/briefings", json={"theme": "A valid briefing theme"}, headers=headers)
                finally:
                    if prompt_patch:
                        prompt_patch.stop()
                    self.serp.error = None
                    self.llm.error = None
                self.assertEqual(response.status_code, status, response.text)
                self.assertEqual(response.json()["detail"], expected)
                self.assertNotIn(SECRET_CANARY, response.text)
                after = await self._count()
                self.assertEqual(after, (before or 0) + 1)

    async def test_configuration_errors_map_to_generic_500(self):
        import httpx as _httpx
        import litellm.exceptions as litellm_exceptions
        from app.services.llm import ProviderConfigurationError

        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        before = await self._count()
        self.key_patch.stop()
        self.serp_builder.stop()
        invalid_key = patch("app.briefing.router._runtime_jina_key", return_value="bad key \n")
        invalid_key.start()
        try:
            response = await self.client.post("/briefings", json={"theme": "A valid briefing theme"}, headers=headers)
            self.assertEqual(response.status_code, 500, response.text)
            self.assertEqual(response.json()["detail"], "Erro interno ao gerar briefing")
            self.assertNotIn("bad key", response.text)
            self.assertEqual(await self._count(), before)
        finally:
            invalid_key.stop()
            self.key_patch.start()
            self.serp_builder.start()

        for exc in (
            ProviderConfigurationError(SECRET_CANARY),
            litellm_exceptions.AuthenticationError(message=SECRET_CANARY, llm_provider="openai", model="gpt"),
            litellm_exceptions.PermissionDeniedError(
                message=SECRET_CANARY, llm_provider="openai", model="gpt",
                response=_httpx.Response(403, request=_httpx.Request("POST", "https://x.test")),
            ),
            litellm_exceptions.APIError(status_code=401, message=SECRET_CANARY, llm_provider="openai", model="gpt"),
            _httpx.HTTPStatusError(message=SECRET_CANARY, request=_httpx.Request("POST", "https://x.test"), response=_httpx.Response(403)),
        ):
            with self.subTest(error=type(exc).__name__):
                self.llm.error = exc
                try:
                    response = await self.client.post("/briefings", json={"theme": "A valid briefing theme"}, headers=headers)
                finally:
                    self.llm.error = None
                self.assertEqual(response.status_code, 500, response.text)
                self.assertEqual(response.json()["detail"], "Erro interno ao gerar briefing")
                self.assertNotIn(SECRET_CANARY, response.text)

    async def test_rejected_bodies_do_not_mutate_state(self):
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        bid = await self._seed()
        before = await self._snapshot(bid)
        for path, bodies in (
            (f"/briefings/{bid}/reopen", [[], "bad", 3, True, {"extra": "bad"}]),
        ):
            for body in bodies:
                with self.subTest(path=path, body=body):
                    response = await self.client.post(path, json=body, headers=headers)
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(await self._snapshot(bid), before)
        # T036: /approve extinta — qualquer corpo retorna 404 sem mutar estado.
        for body in ([], "bad", 3, True, {"extra": "bad"}):
            with self.subTest(path="approve", body=body):
                response = await self.client.post(f"/briefings/{bid}/approve", json=body, headers=headers)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(await self._snapshot(bid), before)
        response = await self.client.post(f"/briefings/{bid}/approve", content=b"not-json", headers=headers)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(await self._snapshot(bid), before)
        self.assertEqual(self.inv_mock.await_count, 0)

    async def test_approve_extinct_and_investigate_implicit_approval(self):
        """T036/T037/T040: /approve retorna 404; /investigate sobre draft
        aprova implicitamente (202), persiste pontos SCRAPER_IN_PROGRESS e
        pesquisa SCRAPER; re-disparo retorna 409."""
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        bid = await self._seed()
        gone = await self.client.post(f"/briefings/{bid}/approve", headers=headers)
        self.assertEqual(gone.status_code, 404, gone.text)
        started = await self.client.post(f"/briefings/{bid}/investigate", headers=headers)
        self.assertEqual(started.status_code, 202, started.text)
        body = started.json()
        self.assertEqual(body["research_id"], bid)
        self.assertEqual(body["status"], "SCRAPER")
        self.assertEqual(body["message"], "Investigação iniciada em background")
        self.assertEqual(self.inv_mock.await_count, 1)
        research, points = await self._research_snapshot(bid)
        self.assertIn(research.status, ("SCRAPER",))
        self.assertEqual(len(points), 3)
        self.assertTrue(all(p.status == "SCRAPER_IN_PROGRESS" for p in points))
        self.assertTrue(all(p.attempt_count == 0 for p in points))
        current = await self.client.get(f"/briefings/{bid}", headers=headers)
        self.assertEqual(current.json()["status"], "approved")
        approved = await self.client.get(f"/briefings/approved/{bid}", headers=headers)
        self.assertEqual(approved.status_code, 200)
        again = await self.client.post(f"/briefings/{bid}/investigate", headers=headers)
        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(self.inv_mock.await_count, 1)
        edit = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers=headers)
        self.assertEqual(edit.status_code, 409)

    async def test_patch_revision_serp_uses_ai_formulated_query(self):
        """E001 (A-C8-01): SERP do PATCH recebe a query formulada pela IA a
        partir de tema+feedback — exatamente 1 busca, nunca o tema puro."""
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        bid = await self._seed()
        note = "Please add another supporting perspective"
        self.llm._responses = ["refined theme with extra perspective", json.dumps(POINTS)]
        edited = await self.client.patch(f"/briefings/{bid}", json={"note": note}, headers=headers)
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(self.serp.calls, 1)
        self.assertEqual(self.serp.queries, ["refined theme with extra perspective"])

    async def test_patch_revision_serp_falls_back_to_combined_theme_feedback(self):
        """E001 (A-C8-01): saída IA não-textual (JSON) recai no fallback
        combinado f"{theme} {feedback}", nunca no tema puro."""
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        bid = await self._seed()
        note = "Please add another supporting perspective"
        edited = await self.client.patch(f"/briefings/{bid}", json={"note": note}, headers=headers)
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(self.serp.calls, 1)
        self.assertEqual(self.serp.queries, [f"A valid briefing theme {note}"])
        self.assertNotEqual(self.serp.queries[0], "A valid briefing theme")

    async def test_patch_revision_errors_map_to_500_502_503(self):
        """E001 (A-C8-04): falhas terminais do PATCH — 500 prompt/config,
        502 LLM, 503 SERP — com FAILED persistido e sem auto-investigate."""
        from app.briefing.prompt_loader import PromptUnavailable
        from app.briefing.serp_client import SerpSearchError
        from app.briefing.service import LLMAttemptError
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}

        bid = await self._seed()
        self.serp.error = SerpSearchError(4)
        try:
            response = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers=headers)
        finally:
            self.serp.error = None
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Busca SERP indisponível")
        current, _ = await self._snapshot(bid)
        self.assertEqual(current.status.value, "failed")
        research, _ = await self._research_snapshot(bid)
        self.assertIn(research.status, ("FAILED",))
        self.assertEqual(self.inv_mock.await_count, 0)

        bid = await self._seed()
        self.llm.error = LLMAttemptError()
        try:
            response = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers=headers)
        finally:
            self.llm.error = None
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["detail"], "Geração de briefing indisponível")
        current, _ = await self._snapshot(bid)
        self.assertEqual(current.status.value, "failed")
        self.assertEqual(self.inv_mock.await_count, 0)

        bid = await self._seed()
        serp_before, llm_before = self.serp.calls, self.llm.calls
        with patch("app.briefing.service.load_briefing_prompt", side_effect=PromptUnavailable(SECRET_CANARY)):
            response = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers=headers)
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["detail"], "Prompt de briefing indisponível")
        self.assertNotIn(SECRET_CANARY, response.text)
        self.assertEqual((self.serp.calls, self.llm.calls), (serp_before, llm_before))
        current, _ = await self._snapshot(bid)
        self.assertEqual(current.status.value, "failed")
        self.assertEqual(self.inv_mock.await_count, 0)

    async def test_cas_conflict_maps_409_and_preserves_history(self):
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        bid = await self._seed()
        before = await self._snapshot(bid)
        with patch("app.briefing.storage.save_briefing_transition", side_effect=BriefingVersionConflictError("cas")):
            response = await self.client.patch(f"/briefings/{bid}", json={"note": "Please clarify supporting evidence"}, headers=headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["detail"], "Estado ou versão de briefing incompatível")
        self.assertEqual(await self._snapshot(bid), before)

    async def test_request_scoped_clients_use_fixed_runtime_contract(self):
        from unittest.mock import Mock
        import app.briefing.router as briefing_router
        self.serp_builder.stop()
        self.llm_builder.stop()
        serp_spy = Mock()
        llm_spy = Mock()
        try:
            with (
                patch.object(briefing_router, "JinaSerpClient", serp_spy),
                patch.object(briefing_router, "make_scout_complete", llm_spy),
            ):
                briefing_router._build_serp_client("test-key", timeout=12.5)
                briefing_router._build_llm_complete(timeout=12.5)
            serp_spy.assert_called_once_with("test-key", timeout=12.5)
            llm_spy.assert_called_once_with(briefing_router.AsyncSessionLocal, default_timeout_s=12.5)
        finally:
            self.serp_builder.start()
            self.llm_builder.start()

    async def test_configured_timeout_flows_to_builders_and_service(self):
        """T036: settings.SEARCH_TIMEOUT_SECONDS explícito é o mesmo valor em
        SERP client, binding LLM e llm_timeout_s do serviço; zero/None/NaN/inf
        e tipos inválidos abortam 500 antes de qualquer I/O ou credencial."""
        import app.briefing.router as briefing_router
        from app.core.config import settings
        from unittest.mock import AsyncMock, Mock

        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        self.serp_builder.stop()
        self.llm_builder.stop()
        key_patch = patch("app.briefing.router._runtime_jina_key", return_value="test-key")
        key_patch.start()
        try:
            for value in (45, 45.0, 12.5):
                with self.subTest(value=value):
                    from app.briefing.domain import BriefingPoint as _P, complete_briefing, new_briefing
                    serp_spy = Mock()
                    llm_spy = Mock()
                    success = complete_briefing(
                        new_briefing("A valid briefing theme"),
                        [_P(title=f"T{i}", description=f"D{i}") for i in range(3)],
                    )
                    service_spy = AsyncMock(return_value=success)
                    with (
                        patch.object(briefing_router, "JinaSerpClient", serp_spy),
                        patch.object(briefing_router, "make_scout_complete", llm_spy),
                        patch.object(briefing_router, "orchestrate_persisted_briefing", service_spy),
                        patch.object(settings, "SEARCH_TIMEOUT_SECONDS", value),
                    ):
                        response = await self.client.post(
                            "/briefings", json={"theme": "A valid briefing theme"}, headers=headers
                        )
                    self.assertEqual(response.status_code, 201, response.text)
                    serp_spy.assert_called_once_with("test-key", timeout=float(value))
                    llm_spy.assert_called_once_with(
                        briefing_router.AsyncSessionLocal, default_timeout_s=float(value)
                    )
                    self.assertEqual(
                        service_spy.call_args.kwargs["llm_timeout_s"], float(value)
                    )

            for bad in (0, 0.0, -3, -3.5, float("nan"), float("inf"), float("-inf"), True, "30", None):
                with self.subTest(bad=bad):
                    serp_spy = Mock()
                    llm_spy = Mock()
                    service_spy = Mock()
                    with (
                        patch.object(briefing_router, "JinaSerpClient", serp_spy),
                        patch.object(briefing_router, "make_scout_complete", llm_spy),
                        patch.object(briefing_router, "orchestrate_persisted_briefing", service_spy),
                        patch.object(settings, "SEARCH_TIMEOUT_SECONDS", bad),
                    ):
                        response = await self.client.post(
                            "/briefings", json={"theme": "A valid briefing theme"}, headers=headers
                        )
                    self.assertEqual(response.status_code, 500, response.text)
                    self.assertEqual(response.json()["detail"], "Erro interno ao gerar briefing")
                    serp_spy.assert_not_called()
                    llm_spy.assert_not_called()
                    service_spy.assert_not_called()
        finally:
            key_patch.stop()
            self.serp_builder.start()
            self.llm_builder.start()

    async def test_unknown_orchestration_error_propagates(self):
        headers = {"Authorization": "Bearer test-api-secret-0123456789"}
        self.llm.error = RuntimeError("programmer bug " + SECRET_CANARY)
        try:
            with self.assertRaises(RuntimeError):
                await self.client.post("/briefings", json={"theme": "A valid briefing theme"}, headers=headers)
        finally:
            self.llm.error = None


if __name__ == "__main__":
    unittest.main()
