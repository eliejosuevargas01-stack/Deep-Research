"""Suite de aceitacao funcional do modulo de briefing (T012, RF-01 a RF-10).

Cobre os 8 cenarios Gherkin de requirements.md:74-124 via HTTP real
(ASGITransport + app de app.main), SQLite :memory: isolado por teste,
SERP Jina real com HTTPX MockTransport (1 chamada, sem rede externa),
LLM injetado por teste, prompt real lido do disco.

Escopo do que este arquivo PROVA e do que NAO prova:
- PROVA (local): ciclo gerar/editar/aprovar/reabrir, rejeicao 422 com
  preservacao, FAILED persistido no mesmo registro, limite de 4
  tentativas, prompt ausente sem chamada LLM, contrato one-attempt do
  binding (num_retries=0/max_retries=0, 1 request via MockTransport).
- NAO PROVA / NAO EXECUTADO: geracao contra provedor LLM real
  (gate de runtime de provedor, com credencial e rede reais). T012
  permanece aberto quanto a esse gate; nada aqui o fecha.
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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

from app.briefing.prompt_loader import PromptUnavailable, load_briefing_prompt
from app.briefing.serp_client import JinaSerpClient, SerpSearchError
from app.briefing.service import LLMAttemptError
from app.db.database import get_db
from app.main import app
from app.models.domain_models import Base, BriefingRecord

HEADERS = {"Authorization": "Bearer test-api-secret-0123456789"}
SECRET_CANARY = "acceptance-secret-canary"
THEME = "A valid briefing theme for acceptance"


def _points(n):
    return [{"title": f"Focus {i}", "description": f"Description {i}"} for i in range(n)]


def _serp_body(n=3):
    return {"data": [
        {"title": f"Result {i}", "url": f"https://example.test/{i}", "description": f"Evidence {i}"}
        for i in range(n)
    ]}


def _fake_session_factory():
    fake_session = AsyncMock()
    fake_session.close = AsyncMock()

    class _Ctx:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, *exc):
            await fake_session.close()

    factory = MagicMock(side_effect=_Ctx)
    factory.fake_session = fake_session
    return factory


class _FakeLLM:
    """LLM injetado: conta chamadas, captura args, falha sob demanda."""

    def __init__(self, points=5, error=None, responses=None):
        self.calls = 0
        self.systems = []
        self.users = []
        self.payload = json.dumps(_points(points))
        self.error = error
        self._responses = list(responses or [])

    async def __call__(self, system, user):
        self.calls += 1
        self.systems.append(system)
        self.users.append(user)
        if self.error:
            raise self.error
        if self._responses:
            item = self._responses.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return self.payload


class BriefingAcceptance(unittest.IsolatedAsyncioTestCase):
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
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
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
        self.key_patch = patch(
            "app.briefing.router._runtime_jina_key", return_value="test-key"
        )
        self.key_patch.start()
        self._http_clients = []

    async def asyncTearDown(self):
        for client in self._http_clients:
            await client.aclose()
        self.factory_patch.stop()
        self.inv_factory_patch.stop()
        self.inv_run_patch.stop()
        self.key_patch.stop()
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()

    def _serp_client(self, body=None, status=200, error=None):
        """JinaSerpClient real sobre MockTransport; conta requests HTTP."""
        calls = []

        def handler(request):
            calls.append(request)
            if error:
                raise error
            return httpx.Response(status, json=body if body is not None else _serp_body())

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        self._http_clients.append(client)
        serp = JinaSerpClient("test-key", timeout=30, http_client=client)
        serp.http_calls = calls
        return serp

    def _patch_builders(self, serp, llm):
        serp_patch = patch("app.briefing.router._build_serp_client", return_value=serp)
        llm_patch = patch("app.briefing.router._build_llm_complete", return_value=llm)
        serp_patch.start()
        llm_patch.start()
        self.addCleanup(serp_patch.stop)
        self.addCleanup(llm_patch.stop)

    async def _count_records(self):
        async with self.sessions() as db:
            return await db.scalar(select(func.count()).select_from(BriefingRecord))

    async def _only_record(self):
        async with self.sessions() as db:
            return (await db.scalars(select(BriefingRecord))).one()

    async def _snapshot(self, briefing_id):
        from uuid import UUID

        from app.briefing.storage import get_briefing, get_briefing_versions

        async with self.sessions() as db:
            current = await get_briefing(db, UUID(briefing_id))
            history = await get_briefing_versions(db, UUID(briefing_id))
            return current, [(x.version, x.status, x.points_json) for x in history]

    async def _research_snapshot(self, briefing_id):
        """T040: estado de research + research_points após aprovação implícita."""
        from uuid import UUID

        from sqlalchemy import select

        from app.models.domain_models import Research, ResearchPoint

        async with self.sessions() as db:
            research = await db.get(Research, UUID(briefing_id))
            rows = await db.execute(
                select(ResearchPoint).where(ResearchPoint.research_id == UUID(briefing_id))
            )
            return research, list(rows.scalars().all())

    async def _create_draft(self, serp=None, llm=None):
        serp = serp or self._serp_client()
        llm = llm if llm is not None else _FakeLLM()
        self._patch_builders(serp, llm)
        response = await self.client.post(
            "/briefings", json={"theme": THEME}, headers=HEADERS
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json(), serp, llm

    async def test_gerar_rascunho(self):
        """Gherkin: Gerar rascunho — 1 chamada SERP, prompt de disco, 3-7 pontos."""
        serp = self._serp_client()
        llm = _FakeLLM(points=5)
        self._patch_builders(serp, llm)
        disk_prompt = load_briefing_prompt()

        response = await self.client.post(
            "/briefings", json={"theme": THEME}, headers=HEADERS
        )

        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["status"], "draft")
        self.assertTrue(3 <= len(body["points"]) <= 7)
        self.assertEqual(len(serp.http_calls), 1)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(llm.systems[0], disk_prompt)
        self.assertIn(THEME, llm.users[0])

    async def test_editar_rascunho(self):
        """Gherkin: Editar rascunho — revisão única com auto-aprovação e
        auto-investigate (T038): salva nova versão, aprova e despacha."""
        created, _, _ = await self._create_draft()
        bid, version = created["research_id"], created["version"]

        response = await self.client.patch(
            f"/briefings/{bid}", json={"note": "Add further supporting details"}, headers=HEADERS
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["version"], version + 2)
        self.assertEqual(body["status"], "approved")
        self.assertTrue(body["approved_at"])
        self.assertEqual(len(body["points"]), 5)
        self.assertEqual(self.inv_mock.await_count, 1)
        research, points = await self._research_snapshot(bid)
        self.assertIn(research.status, ("SCRAPER",))
        self.assertTrue(all(p.status == "SCRAPER_IN_PROGRESS" for p in points))
        _, history = await self._snapshot(bid)
        self.assertEqual([v for v, _, _ in history], sorted(v for v, _, _ in history))
        # T039: segunda revisão bloqueada com 409.
        second = await self.client.patch(
            f"/briefings/{bid}", json={"note": "Add even more details"}, headers=HEADERS
        )
        self.assertEqual(second.status_code, 409)

    async def test_patch_serp_query_combines_theme_and_feedback(self):
        """E001 (A-C8-01): PATCH executa exatamente 1 busca SERP real com a
        query combinada tema+feedback (fallback), nunca o tema puro."""
        note = "Add further supporting details"
        created, serp, _ = await self._create_draft()
        bid = created["research_id"]
        del serp.http_calls[:]

        response = await self.client.patch(
            f"/briefings/{bid}", json={"note": note}, headers=HEADERS
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(serp.http_calls), 1)
        sent = json.loads(serp.http_calls[0].content.decode("utf-8"))
        self.assertEqual(sent["q"], f"{THEME} {note}")
        self.assertNotEqual(sent["q"], THEME)

    async def test_patch_serp_query_uses_ai_formulation_when_textual(self):
        """E001 (A-C8-01): formulação IA textual é usada como query SERP."""
        note = "Add further supporting details"
        created, _, _ = await self._create_draft()
        bid = created["research_id"]
        serp = self._serp_client()
        llm = _FakeLLM(responses=["refined acceptance query", json.dumps(_points(5))])
        self._patch_builders(serp, llm)

        response = await self.client.patch(
            f"/briefings/{bid}", json={"note": note}, headers=HEADERS
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(serp.http_calls), 1)
        sent = json.loads(serp.http_calls[0].content.decode("utf-8"))
        self.assertEqual(sent["q"], "refined acceptance query")

    async def test_patch_feedback_terminal_errors(self):
        """E001 (A-C8-04/Q12): PATCH 500 prompt, 502 LLM, 503 SERP; FAILED
        persistido no mesmo registro, sem segredos, sem auto-investigate."""
        # 503: SERP sempre 500 no MockTransport (4 tentativas HTTP).
        created, _, _ = await self._create_draft()
        bid = created["research_id"]
        err_serp = self._serp_client(status=500)
        self._patch_builders(err_serp, _FakeLLM())
        response = await self.client.patch(
            f"/briefings/{bid}", json={"note": "Valid feedback note"}, headers=HEADERS
        )
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Busca SERP indisponível")
        self.assertEqual(len(err_serp.http_calls), 4)
        current, _ = await self._snapshot(bid)
        self.assertEqual(current.status.value, "failed")
        self.assertEqual(self.inv_mock.await_count, 0)

        # 502: LLM sempre falha (1 formulação com fallback + 4 tentativas).
        created, _, _ = await self._create_draft()
        bid = created["research_id"]
        ok_serp = self._serp_client()
        bad_llm = _FakeLLM(error=LLMAttemptError())
        self._patch_builders(ok_serp, bad_llm)
        response = await self.client.patch(
            f"/briefings/{bid}", json={"note": "Valid feedback note"}, headers=HEADERS
        )
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["detail"], "Geração de briefing indisponível")
        self.assertEqual(len(ok_serp.http_calls), 1)
        self.assertEqual(bad_llm.calls, 5)
        current, _ = await self._snapshot(bid)
        self.assertEqual(current.status.value, "failed")
        self.assertEqual(self.inv_mock.await_count, 0)

        # 500: prompt indisponível — sem I/O externo.
        created, _, _ = await self._create_draft()
        bid = created["research_id"]
        quiet_serp = self._serp_client()
        quiet_llm = _FakeLLM()
        self._patch_builders(quiet_serp, quiet_llm)
        with patch(
            "app.briefing.service.load_briefing_prompt",
            side_effect=PromptUnavailable(f"missing {SECRET_CANARY}"),
        ):
            response = await self.client.patch(
                f"/briefings/{bid}", json={"note": "Valid feedback note"}, headers=HEADERS
            )
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["detail"], "Prompt de briefing indisponível")
        self.assertNotIn(SECRET_CANARY, response.text)
        self.assertEqual(len(quiet_serp.http_calls), 0)
        self.assertEqual(quiet_llm.calls, 0)
        current, _ = await self._snapshot(bid)
        self.assertEqual(current.status.value, "failed")
        self.assertEqual(self.inv_mock.await_count, 0)

    async def test_rejeitar_quantidade_invalida(self):
        """Feedback PATCH exige nota 3..4000; falha 422 preserva estado."""
        created, _, _ = await self._create_draft()
        bid = created["research_id"]
        before = await self._snapshot(bid)

        for note in ("x", "f" * 4001):
            with self.subTest(note_length=len(note)):
                response = await self.client.patch(
                    f"/briefings/{bid}", json={"note": note}, headers=HEADERS
                )
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(await self._snapshot(bid), before)

        async with self.sessions() as db:
            db.add(BriefingRecord(
                theme=THEME, status="draft", version=1,
                points_json=_points(2), error=None, approved_at=None,
            ))
            await db.commit()
            invalid_id = (await db.scalars(
                select(BriefingRecord).order_by(BriefingRecord.created_at.desc())
            )).first().id
        invalid_before = await self._snapshot(str(invalid_id))
        # T036: /approve extinta retorna 404 preservando estado.
        response = await self.client.post(
            f"/briefings/{invalid_id}/approve", headers=HEADERS
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(await self._snapshot(str(invalid_id)), invalid_before)

    async def test_aprovar_briefing(self):
        """Gherkin (Sprint C8): /approve extinta (404); aprovação ocorre
        implicitamente via /investigate sobre draft (202 + SCRAPER)."""
        created, _, _ = await self._create_draft()
        bid = created["research_id"]

        gone = await self.client.post(f"/briefings/{bid}/approve", headers=HEADERS)
        self.assertEqual(gone.status_code, 404, gone.text)

        started = await self.client.post(f"/briefings/{bid}/investigate", headers=HEADERS)
        self.assertEqual(started.status_code, 202, started.text)
        self.assertEqual(started.json()["status"], "SCRAPER")
        self.assertEqual(self.inv_mock.await_count, 1)
        research, points = await self._research_snapshot(bid)
        self.assertIn(research.status, ("SCRAPER",))
        self.assertTrue(all(p.status == "SCRAPER_IN_PROGRESS" for p in points))
        current = await self.client.get(f"/briefings/{bid}", headers=HEADERS)
        self.assertEqual(current.json()["status"], "approved")
        edit = await self.client.patch(
            f"/briefings/{bid}", json={"note": "Please revise the draft"}, headers=HEADERS
        )
        self.assertEqual(edit.status_code, 409)
        approved = await self.client.get(f"/briefings/approved/{bid}", headers=HEADERS)
        self.assertEqual(approved.status_code, 200)
        again = await self.client.post(f"/briefings/{bid}/investigate", headers=HEADERS)
        self.assertEqual(again.status_code, 409)

    async def test_reabrir_briefing(self):
        """Briefing aprovado (via /investigate) não pode ser reaberto: 409."""
        created, _, _ = await self._create_draft()
        bid = created["research_id"]
        started = await self.client.post(f"/briefings/{bid}/investigate", headers=HEADERS)
        self.assertEqual(started.status_code, 202, started.text)

        reopen = await self.client.post(f"/briefings/{bid}/reopen", headers=HEADERS)

        self.assertEqual(reopen.status_code, 409, reopen.text)
        self.assertEqual(reopen.json()["detail"], "Briefing aprovado não pode ser reaberto")

    async def test_falha_na_busca(self):
        """Gherkin: Falha na busca — 4 tentativas, FAILED no mesmo registro, 503 seguro."""
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(500, json={"error": "down"})

        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(transport=transport)
        self._http_clients.append(http_client)
        serp = JinaSerpClient("test-key", timeout=30, http_client=http_client)
        llm = _FakeLLM()
        self._patch_builders(serp, llm)

        response = await self.client.post(
            "/briefings", json={"theme": THEME}, headers=HEADERS
        )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Busca SERP indisponível")
        self.assertEqual(len(calls), 4)
        self.assertEqual(llm.calls, 0)
        self.assertEqual(await self._count_records(), 1)
        record = await self._only_record()
        self.assertEqual(record.status, "failed")
        self.assertNotIn(SECRET_CANARY, response.text)

    async def test_retentar_sem_repetir_sucesso(self):
        """Gherkin: Retentar operacao sem repetir sucesso — SERP 1x, LLM ate 4x."""
        serp = self._serp_client()
        llm = _FakeLLM(error=LLMAttemptError())
        self._patch_builders(serp, llm)

        response = await self.client.post(
            "/briefings", json={"theme": THEME}, headers=HEADERS
        )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"], "Geração de briefing indisponível")
        self.assertEqual(len(serp.http_calls), 1)
        self.assertEqual(llm.calls, 4)
        self.assertEqual(await self._count_records(), 1)
        record = await self._only_record()
        self.assertEqual(record.status, "failed")

    async def test_prompt_ausente_ou_invalido(self):
        """Gherkin: Prompt ausente — sem chamada LLM, FAILED/500 seguro."""
        serp = self._serp_client()
        llm = _FakeLLM()
        self._patch_builders(serp, llm)

        with patch(
            "app.briefing.router.load_briefing_prompt",
            side_effect=PromptUnavailable(f"missing {SECRET_CANARY}"),
        ):
            response = await self.client.post(
                "/briefings", json={"theme": THEME}, headers=HEADERS
            )

        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["detail"], "Prompt de briefing indisponível")
        self.assertNotIn(SECRET_CANARY, response.text)
        self.assertEqual(len(serp.http_calls), 0)
        self.assertEqual(llm.calls, 0)
        self.assertEqual(await self._count_records(), 1)
        record = await self._only_record()
        self.assertEqual(record.status, "failed")
        with self.assertRaises(PromptUnavailable):
            load_briefing_prompt(path="/nonexistent-briefing-prompt/ausente.md")

    async def test_gate_transporte_do_binding_local(self):
        """Gate de transporte local do binding (NAO e provedor real).

        make_scout_complete real + SDK litellm real + MockTransport 503:
        prova num_retries=0/max_retries=0 e exatamente 1 request por
        tentativa do binding, sem rede. Gate contra provedor real
        (credencial + rede) NAO EXECUTADO aqui.
        """
        import litellm
        from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
        from litellm.llms.openai.common_utils import BaseOpenAILLM

        import app.services.llm as llm_service
        from app.briefing.llm_binding import _enforce_safe_transport, make_scout_complete

        req_count = 0

        def handler(request):
            nonlocal req_count
            req_count += 1
            return httpx.Response(
                503, json={"error": {"message": "Service Unavailable"}}
            )

        mock_transport = httpx.MockTransport(handler)
        keys = {"openai": "test-openai-key-0123456789abcdef"}
        models = {"scout": "openai/gpt-4o-mini"}

        async def fake_runtime(db):
            return dict(keys), dict(models)

        async def fake_record(db):
            return SimpleNamespace(openai_base_url=None)

        orig_async_create = AsyncHTTPHandler.create_client
        orig_sync_create = HTTPHandler.create_client
        orig_openai_sync = BaseOpenAILLM._get_sync_http_client
        orig_safe_active = llm_service._SAFE_TRANSPORT_ACTIVE
        orig_safe_error = llm_service._SAFE_TRANSPORT_ERROR
        orig_aclient_fr = getattr(
            getattr(getattr(litellm, "module_level_aclient", None), "client", None),
            "follow_redirects", None,
        )
        orig_client_fr = getattr(
            getattr(getattr(litellm, "module_level_client", None), "client", None),
            "follow_redirects", None,
        )

        def cleanup_transport():
            AsyncHTTPHandler.create_client = orig_async_create
            HTTPHandler.create_client = orig_sync_create
            BaseOpenAILLM._get_sync_http_client = orig_openai_sync
            llm_service._SAFE_TRANSPORT_ACTIVE = orig_safe_active
            llm_service._SAFE_TRANSPORT_ERROR = orig_safe_error
            if (
                hasattr(litellm, "module_level_aclient")
                and litellm.module_level_aclient
                and orig_aclient_fr is not None
            ):
                litellm.module_level_aclient.client.follow_redirects = orig_aclient_fr
            if (
                hasattr(litellm, "module_level_client")
                and litellm.module_level_client
                and orig_client_fr is not None
            ):
                litellm.module_level_client.client.follow_redirects = orig_client_fr

        self.addCleanup(cleanup_transport)

        with patch(
            "app.briefing.llm_binding.litellm.acompletion",
            new=AsyncMock(return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            )),
        ) as acu:
            with (
                patch("app.briefing.llm_binding.runtime_settings", fake_runtime),
                patch("app.briefing.llm_binding.get_record", fake_record),
                patch("app.briefing.llm_binding._enforce_safe_transport"),
            ):
                fn = make_scout_complete(_fake_session_factory(), default_timeout_s=30.0)
                self.assertEqual(await fn("sys", "usr"), "ok")
        kwargs = acu.await_args.kwargs
        self.assertEqual(kwargs.get("num_retries"), 0)
        self.assertEqual(kwargs.get("max_retries"), 0)

        async with httpx.AsyncClient(
            transport=mock_transport, follow_redirects=False
        ) as http_client:
            with (
                patch("app.briefing.llm_binding.runtime_settings", fake_runtime),
                patch("app.briefing.llm_binding.get_record", fake_record),
                patch.object(
                    BaseOpenAILLM, "_get_async_http_client", return_value=http_client
                ),
                patch.object(litellm, "suppress_debug_info", True),
                patch.object(litellm, "turn_off_message_logging", True, create=True),
                patch.object(litellm, "telemetry", False, create=True),
            ):
                _enforce_safe_transport()
                fn = make_scout_complete(_fake_session_factory(), default_timeout_s=30.0)
                with self.assertRaises(LLMAttemptError):
                    await fn("sys", "usr")
        self.assertEqual(req_count, 1)


class SerpFailureContract(unittest.TestCase):
    def test_serp_error_attempts_and_safe_message(self):
        err = SerpSearchError(4)
        self.assertEqual(err.attempts, 4)
        self.assertNotIn(SECRET_CANARY, str(err))


if __name__ == "__main__":
    unittest.main()
