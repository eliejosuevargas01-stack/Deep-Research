import json
import tempfile
import unittest
from functools import partial
from pathlib import Path

from app.briefing.service import generate_briefing
from app.briefing.domain import BriefingStatus, InvalidContent


VALID = json.dumps([{"title": f"T{i}", "description": f"D{i}"} for i in range(3)])
SERP = [{"title": "Result", "url": "https://example.org", "description": "Snippet"}]


def client_for(search):
    return type("S", (), {"search": staticmethod(search)})()


class GenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_composes_prompt_search_and_llm_into_same_draft(self):
        calls = []
        async def search(theme):
            calls.append(("search", theme))
            return SERP
        async def llm(system, user):
            calls.append(("llm", system, json.loads(user)))
            return VALID
        result = await generate_briefing("  climate risk  ", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: " exact system \n")
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(result.theme, "climate risk")
        self.assertEqual(len(result.points), 3)
        self.assertEqual([c[0] for c in calls], ["search", "llm"])
        self.assertEqual(calls[0][1], "climate risk")
        self.assertEqual(calls[1][1], " exact system \n")
        self.assertEqual(calls[1][2], {"tema": "climate risk", "resultados_serp": SERP, "formato_saida": "Retorne exclusivamente uma lista JSON válida de objetos com 'title' e 'description', sem texto adicional."})

    async def test_invalid_theme_fails_before_any_io(self):
        seen = []
        async def search(theme): seen.append("search")
        async def llm(system, user): seen.append("llm")
        with self.assertRaises(InvalidContent):
            await generate_briefing("  ", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: seen.append("prompt"))
        self.assertEqual(seen, [])

    async def test_invalid_config_raises_before_any_io(self):
        for attempts, timeout in [(0, 30.0), (5, 30.0), (True, 30.0), (1.5, 30.0), (4, 0), (4, -1), (4, True), (4, float("nan")), (4, float("inf"))]:
            seen = []
            async def search(theme): seen.append("search")
            async def llm(system, user): seen.append("llm")
            with self.assertRaises(ValueError, msg=f"{attempts!r}/{timeout!r}"):
                await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: seen.append("prompt"), llm_attempts=attempts, llm_timeout_s=timeout)
            self.assertEqual(seen, [])

    async def test_valid_config_edges_pass(self):
        for attempts, timeout in [(1, 30.0), (4, 0.05), (4, 60.0)]:
            async def search(theme): return SERP
            async def llm(system, user): return VALID
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_attempts=attempts, llm_timeout_s=timeout)
            self.assertEqual(result.status, BriefingStatus.DRAFT)

    async def test_real_prompt_loader_rereads_file_per_generation(self):
        from app.briefing.prompt_loader import load_briefing_prompt
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir())) as tmp:
            path = Path(tmp) / "prompt.md"
            path.write_text("first system", encoding="utf-8")
            async def search(theme): return SERP
            async def llm(system, user):
                calls.append(system)
                return VALID
            calls = []
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=partial(load_briefing_prompt, str(path)))
            self.assertEqual(result.status, BriefingStatus.DRAFT)
            path.write_text("second system", encoding="utf-8")
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=partial(load_briefing_prompt, str(path)))
            self.assertEqual(calls, ["first system", "second system"])

    async def test_invalid_prompt_marks_failed_before_any_external_io(self):
        from app.briefing.prompt_loader import PromptUnavailable
        for bad in [lambda: "", lambda: "   \n\t", lambda: None, lambda: 123]:
            seen = []
            async def search(theme): seen.append("search")
            async def llm(system, user): seen.append("llm")
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=bad)
            self.assertEqual(result.status, BriefingStatus.FAILED)
            self.assertEqual(seen, [])
        def raise_unavailable():
            raise PromptUnavailable("Prompt de briefing indisponível ou inválido")
        seen = []
        async def search(theme): seen.append("search")
        async def llm(system, user): seen.append("llm")
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=raise_unavailable)
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(seen, [])

    async def test_unknown_prompt_loader_error_propagates(self):
        def boom():
            raise RuntimeError("disk on fire")
        seen = []
        async def search(theme): seen.append("search")
        async def llm(system, user): seen.append("llm")
        with self.assertRaises(RuntimeError):
            await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=boom)
        self.assertEqual(seen, [])

    async def test_serp_failure_marks_failed_without_llm(self):
        from app.briefing.serp_client import SerpSearchError
        seen = []
        async def search(theme):
            seen.append(theme)
            raise SerpSearchError(4)
        async def llm(system, user): seen.append("llm")
        first = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
        self.assertEqual(first.status, BriefingStatus.FAILED)
        self.assertEqual(first.error, "Busca SERP indisponível")
        self.assertEqual(seen, ["theme ok"])

    async def test_llm_known_failure_retries_reusing_serp_and_succeeds(self):
        from app.briefing.service import LLMAttemptError
        searches, attempts = [], []
        async def search(theme):
            searches.append(theme)
            return SERP
        async def llm(system, user):
            attempts.append(user)
            if len(attempts) < 3:
                raise LLMAttemptError()
            return VALID
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(len(searches), 1)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(len({a for a in attempts}), 1)

    async def test_llm_exhaustion_marks_failed_with_safe_error(self):
        from app.briefing.service import LLMAttemptError
        searches, attempts = [], []
        async def search(theme):
            searches.append(theme)
            return SERP
        async def llm(system, user):
            attempts.append(1)
            raise LLMAttemptError()
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.error, "Geração de briefing indisponível")
        self.assertEqual(len(searches), 1)
        self.assertEqual(len(attempts), 4)

    async def test_llm_invalid_output_counts_attempt_and_can_recover(self):
        searches, attempts = [], []
        async def search(theme):
            searches.append(theme)
            return SERP
        async def llm(system, user):
            attempts.append(1)
            if len(attempts) == 1:
                return "not json at all"
            return VALID
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(len(searches), 1)
        self.assertEqual(len(attempts), 2)

    async def test_llm_wrong_list_shapes_exhaust_to_failed(self):
        from app.briefing.domain import InvalidContent
        bads = ["null", "{}", "[1,2,3]", json.dumps([{"title": "T", "description": "D"}] * 2), json.dumps([{"title": "T", "description": "D"}] * 8), json.dumps([{"title": "T"}]), json.dumps([{"description": "D"}]), json.dumps([{"title": "  ", "description": "D"}])]
        for bad in bads:
            searches, attempts = [], []
            async def search(theme):
                searches.append(theme)
                return SERP
            async def llm(system, user):
                attempts.append(1)
                return bad
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
            self.assertEqual(result.status, BriefingStatus.FAILED, msg=bad)
            self.assertEqual(len(searches), 1)
            self.assertEqual(len(attempts), 4)

    async def test_nonstring_llm_return_counts_attempt(self):
        for bad in [None, {"a": 1}, 42]:
            searches, attempts = [], []
            async def search(theme):
                searches.append(theme)
                return SERP
            async def llm(system, user):
                attempts.append(1)
                return bad
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
            self.assertEqual(result.status, BriefingStatus.FAILED)
            self.assertEqual(len(attempts), 4)

    async def test_llm_attempts_cap_respects_custom_values(self):
        from app.briefing.service import LLMAttemptError
        for cap, expected in [(1, 1), (2, 2)]:
            async def search(theme): return SERP
            async def llm(system, user):
                attempts.append(1)
                raise LLMAttemptError()
            attempts = []
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_attempts=cap)
            self.assertEqual(len(attempts), expected)
            self.assertEqual(result.status, BriefingStatus.FAILED)

    async def test_llm_timeout_retries_until_draft(self):
        calls = []
        async def search(theme): return SERP
        async def llm(system, user):
            calls.append(1)
            if len(calls) == 1:
                import asyncio
                await asyncio.sleep(0.05)
            return VALID
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_timeout_s=0.01)
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(len(calls), 2)

    async def test_callable_timeout_error_without_deadline_propagates(self):
        calls = []
        async def search(theme): return SERP
        async def llm(system, user):
            calls.append(1)
            raise TimeoutError("callable timeout")
        with self.assertRaisesRegex(TimeoutError, "callable timeout"):
            await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_timeout_s=1)
        self.assertEqual(len(calls), 1)

    async def test_callable_invalidcontent_and_runtimeerror_propagate_without_retry(self):
        from app.briefing.domain import InvalidContent
        for error in [InvalidContent("bad provider"), RuntimeError("provider crash")]:
            calls = []
            async def search(theme): return SERP
            async def llm(system, user):
                calls.append(1)
                raise error
            with self.assertRaises(type(error)):
                await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
            self.assertEqual(len(calls), 1)

    async def test_cancelled_llm_propagates_without_retry(self):
        import asyncio
        calls = []
        async def search(theme): return SERP
        async def llm(system, user):
            calls.append(1)
            raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
        self.assertEqual(len(calls), 1)

    async def test_json_fence_is_accepted_but_garbage_is_rejected(self):
        fenced = f"```json\n{VALID}\n```"
        async def search(theme): return SERP
        async def llm(system, user): return fenced
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt")
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        async def garbage(system, user): return f"prefix {VALID}"
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=garbage, prompt_loader=lambda: "prompt", llm_attempts=1)
        self.assertEqual(result.status, BriefingStatus.FAILED)

    async def test_accepts_all_in_range_counts(self):
        for count in (3, 4, 5, 6, 7):
            payload = json.dumps([{"title": f"T{i}", "description": f"D{i}"} for i in range(count)])
            async def search(theme): return SERP
            async def llm(system, user, payload=payload): return payload
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_attempts=1)
            self.assertEqual(len(result.points), count)

    async def test_concurrent_invocations_overlap_llm_without_service_lock(self):
        import asyncio
        async def search(theme): return SERP
        active = {"n": 0, "max": 0}
        async def slow(system, user):
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            await asyncio.sleep(0.02)
            active["n"] -= 1
            return VALID
        results = await asyncio.gather(*[generate_briefing("theme ok", serp_client=client_for(search), llm_complete=slow, prompt_loader=lambda: "prompt") for _ in range(3)])
        self.assertTrue(all(r.status == BriefingStatus.DRAFT for r in results))
        self.assertGreater(active["max"], 1)

    async def test_attempts_within_one_invocation_never_overlap(self):
        import asyncio
        async def search(theme): return SERP
        active = {"n": 0, "max": 0}
        async def slow(system, user):
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            await asyncio.sleep(0.02)
            active["n"] -= 1
            raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=slow, prompt_loader=lambda: "prompt")
        self.assertEqual(active["max"], 1)

    async def test_timeout_exhaustion_marks_failed(self):
        import asyncio
        calls = []
        async def search(theme): return SERP
        async def slow(system, user):
            calls.append(1)
            await asyncio.sleep(0.05)
            return VALID
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=slow, prompt_loader=lambda: "prompt", llm_timeout_s=0.01)
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(len(calls), 4)

    async def test_unknown_serp_error_and_cancel_propagate(self):
        import asyncio
        async def boom_search(theme): raise RuntimeError("search impl bug")
        async def llm(system, user): raise AssertionError("llm must not run")
        with self.assertRaises(RuntimeError):
            await generate_briefing("theme ok", serp_client=client_for(boom_search), llm_complete=llm, prompt_loader=lambda: "prompt")
        async def cancelled_search(theme): raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await generate_briefing("theme ok", serp_client=client_for(cancelled_search), llm_complete=llm, prompt_loader=lambda: "prompt")

    async def test_real_jina_client_composition_retries_internally_behind_single_search(self):
        import httpx
        from app.briefing.serp_client import JinaSerpClient
        transport_calls = []

        def handler(request):
            transport_calls.append(1)
            if len(transport_calls) < 4:
                return httpx.Response(500)
            return httpx.Response(200, json={"data": [{"title": "R", "url": "https://example.org/x", "description": "S"}]})

        client = JinaSerpClient(api_key="test-key", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        service_calls = []

        class CountingClient:
            async def search(self, theme):
                service_calls.append(theme)
                return await client.search(theme)
        async def llm(system, user):
            return VALID
        try:
            result = await generate_briefing("theme ok", serp_client=CountingClient(), llm_complete=llm, prompt_loader=lambda: "prompt")
            self.assertEqual(result.status, BriefingStatus.DRAFT)
            self.assertEqual(service_calls, ["theme ok"])
            self.assertEqual(len(transport_calls), 4)
        finally:
            await client._http_client.aclose()

    async def test_prompt_failure_message_is_fixed_and_distinct(self):
        from app.briefing.prompt_loader import PromptUnavailable
        def raise_unavailable():
            raise PromptUnavailable("detalhe interno qualquer")
        async def search(theme): raise AssertionError("search must not run")
        async def llm(system, user): raise AssertionError("llm must not run")
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=raise_unavailable)
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.error, "Prompt de briefing indisponível")
        self.assertNotIn("detalhe interno", result.error)

    async def test_unclosed_json_fence_is_rejected(self):
        async def search(theme): return SERP
        async def llm(system, user): return f"```json\n{VALID}"
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_attempts=1)
        self.assertEqual(result.status, BriefingStatus.FAILED)

    async def test_failed_and_draft_preserve_identity_and_fixed_messages(self):
        import unittest.mock as mock
        import uuid as uuid_mod
        probe = uuid_mod.UUID(int=1234)
        with mock.patch("app.briefing.service.new_briefing") as wrapped:
            from app.briefing.domain import new_briefing as real_new
            def factory(theme):
                created = real_new(theme)
                return created.__class__(id=probe, theme=created.theme, status=created.status, points=created.points, version=created.version, approved_at=created.approved_at, error=created.error)
            wrapped.side_effect = factory
            async def search(theme): return SERP
            async def llm(system, user): return "garbage"
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=lambda: "prompt", llm_attempts=1)
            self.assertEqual(wrapped.call_count, 1)
            self.assertEqual(result.id, probe)
            self.assertEqual(result.version, 2)
            self.assertEqual(result.error, "Geração de briefing indisponível")
        with mock.patch("app.briefing.service.new_briefing", wraps=real_new) as wrapped:
            async def search(theme): return SERP
            async def ok(system, user): return VALID
            result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=ok, prompt_loader=lambda: "prompt", llm_attempts=1)
            self.assertEqual(result.version, 2)
            self.assertEqual(result.points[0].title, "T0")

    async def test_error_paths_never_leak_raw_output_or_provider_data(self):
        from app.briefing.service import LLMAttemptError
        canary = "RAW-PROVIDER-CANARY-DO-NOT-LEAK"
        def bad_loader():
            return "good prompt"
        async def search(theme): return SERP
        async def llm(system, user):
            raise LLMAttemptError()
        result = await generate_briefing("theme ok", serp_client=client_for(search), llm_complete=llm, prompt_loader=bad_loader)
        self.assertNotIn(canary, repr(result) + str(result.error))
        self.assertEqual(str(LLMAttemptError()), "Geração de briefing indisponível")


    async def test_extreme_numeric_timeout_values_raise_value_error_before_io(self):
        for bad_timeout in (-10**1000, 10**1000):
            seen = []
            async def search(theme): seen.append("search")
            async def llm(system, user): seen.append("llm")
            with self.assertRaisesRegex(ValueError, "Configuração de timeout LLM inválida"):
                await generate_briefing(
                    "valid theme",
                    serp_client=client_for(search),
                    llm_complete=llm,
                    prompt_loader=lambda: seen.append("prompt"),
                    llm_timeout_s=bad_timeout,
                )
            self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
