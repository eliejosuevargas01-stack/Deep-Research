import asyncio
import json
import unittest

import httpx

from app.briefing.domain import BriefingPoint, BriefingStatus
from app.briefing.serp_client import JinaSerpClient
from app.briefing.service import LLMAttemptError, generate_briefing

VALID_POINTS = [
    {"title": "Title 1", "description": "Desc 1"},
    {"title": "Title 2", "description": "Desc 2"},
    {"title": "Title 3", "description": "Desc 3"},
]
VALID_JSON = json.dumps(VALID_POINTS)
SERP_RESULTS = [{"title": "R", "url": "https://example.org", "description": "S"}]


class TestBriefingGenerationConcurrencyQA(unittest.IsolatedAsyncioTestCase):
    async def test_llm_retries_and_exhaustion_are_sequential_and_reuse_search_payload(self):
        for failures, expected_status in ((3, BriefingStatus.DRAFT), (4, BriefingStatus.FAILED)):
            with self.subTest(failures=failures):
                active = maximum_active = searches = 0
                calls = []

                async def search(theme):
                    nonlocal searches
                    searches += 1
                    return SERP_RESULTS

                async def llm(system, user):
                    nonlocal active, maximum_active
                    active += 1
                    maximum_active = max(maximum_active, active)
                    calls.append((system, user))
                    try:
                        await asyncio.sleep(0)
                        if len(calls) <= failures:
                            raise LLMAttemptError()
                        return VALID_JSON
                    finally:
                        active -= 1

                result = await generate_briefing(
                    "tema teste", serp_client=type("Client", (), {"search": staticmethod(search)})(),
                    llm_complete=llm, prompt_loader=lambda: "prompt",
                )
                self.assertEqual(len(calls), failures + (1 if failures == 3 else 0))
                self.assertEqual(maximum_active, 1)
                self.assertEqual(active, 0)
                self.assertEqual(searches, 1)
                self.assertEqual(len({payload for _, payload in calls}), 1)
                self.assertTrue(all(system == "prompt" for system, _ in calls))
                self.assertEqual(result.status, expected_status)
                if failures == 3:
                    self.assertEqual(len(result.points), 3)
                    self.assertEqual(
                        result.points,
                        tuple(BriefingPoint(p["title"], p["description"]) for p in VALID_POINTS),
                    )
                else:
                    self.assertEqual(result.error, "Geração de briefing indisponível")
                    self.assertEqual(result.points, ())

    async def test_external_task_cancellation_propagates_and_skips_failure_transition(self):
        started = asyncio.Event()
        cleanup = asyncio.Event()
        active = searches = llm_calls = fail_calls = 0
        from app.briefing import service
        real_fail = service.fail_briefing

        def observed_fail(*args, **kwargs):
            nonlocal fail_calls
            fail_calls += 1
            return real_fail(*args, **kwargs)

        service.fail_briefing = observed_fail

        async def search(theme):
            nonlocal searches
            searches += 1
            return SERP_RESULTS

        async def llm(system, user):
            nonlocal active, llm_calls
            active += 1
            llm_calls += 1
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                active -= 1
                cleanup.set()

        task = asyncio.create_task(generate_briefing(
            "tema teste", serp_client=type("Client", (), {"search": staticmethod(search)})(),
            llm_complete=llm, prompt_loader=lambda: "prompt",
        ))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(cleanup.is_set())
            self.assertEqual(active, 0)
            self.assertEqual(llm_calls, 1)
            self.assertEqual(searches, 1)
            self.assertEqual(fail_calls, 0)
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            service.fail_briefing = real_fail

    async def test_real_jina_client_exhaustion_composes_with_service_failure(self):
        requests = 0

        def handler(request):
            nonlocal requests
            requests += 1
            return httpx.Response(500, text="private transport detail")

        llm_calls = 0
        search_calls = 0

        async def llm(system, user):
            nonlocal llm_calls
            llm_calls += 1
            return VALID_JSON

        class CountingClient(JinaSerpClient):
            def __init__(self, api_key: str, http_client):
                super().__init__(api_key, http_client=http_client)
            async def search(self, theme: str):
                nonlocal search_calls
                search_calls += 1
                return await super().search(theme)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            result = await generate_briefing(
                "tema teste", serp_client=CountingClient("fake-key-only", http_client=http),
                llm_complete=llm, prompt_loader=lambda: "prompt",
            )
        self.assertEqual(search_calls, 1)
        self.assertEqual(requests, 4)
        self.assertEqual(llm_calls, 0)
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.error, "Busca SERP indisponível")
        self.assertEqual(result.points, ())
