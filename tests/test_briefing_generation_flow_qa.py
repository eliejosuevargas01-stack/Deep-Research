"""Fluxo QA O02/O03: canaries distintos nunca vazam; identidade real por fluxo.

Recorte A test-only. Sem patch de helpers de produto como SUT no teste de
canary; fábrica do teste de identidade delega a `new_briefing` real.
"""
import dataclasses
import json
import unittest
import unittest.mock as mock

from app.briefing import service as svc
from app.briefing.domain import BriefingStatus
from app.briefing.prompt_loader import PromptUnavailable
from app.briefing.serp_client import SerpSearchError
from app.briefing.service import LLMAttemptError, generate_briefing

VALID = json.dumps([{"title": f"T{i}", "description": f"D{i}"} for i in range(3)])
PROMPT_ERR = "Prompt de briefing indisponível"
SERP_ERR = "Busca SERP indisponível"
GEN_ERR = "Geração de briefing indisponível"


def _client(search):
    return type("S", (), {"search": staticmethod(search)})()


class FlowQaTests(unittest.IsolatedAsyncioTestCase):
    async def test_canaries_from_prompt_serp_and_raw_never_leak(self):
        prompt_canary = "FLOWQA-PROMPT-CANARY-7f3a"
        serp_canary = "FLOWQA-SERP-CANARY-9c1e"
        raw_canary = "FLOWQA-RAW-CANARY-4b8d"
        searches, attempts, seen = [], [], {}

        async def search(theme):
            searches.append(theme)
            return [{"title": "R", "url": "https://example.org/x",
                     "description": f"snippet {serp_canary}"}]

        async def llm(system, user):
            attempts.append(1)
            seen["system"] = system
            seen["user"] = json.loads(user)
            self.assertIn(prompt_canary, system)
            descs = [r["description"] for r in seen["user"]["resultados_serp"]]
            self.assertTrue(any(serp_canary in d for d in descs))
            return f"not-json-at-all {{{raw_canary}}}"

        result = await generate_briefing(
            "theme ok", serp_client=_client(search), llm_complete=llm,
            prompt_loader=lambda: f"system {prompt_canary}")
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.error, GEN_ERR)
        self.assertEqual(result.points, ())
        self.assertEqual(len(searches), 1)
        self.assertEqual(len(attempts), 4)
        leaked = repr(result) + str(result.error) + json.dumps(
            dataclasses.asdict(result), default=str)
        for canary in (prompt_canary, serp_canary, raw_canary):
            self.assertNotIn(canary, leaked)

    async def test_prompt_unavailable_detail_never_leaks_and_no_external_io(self):
        detail_canary = "FLOWQA-PROMPT-DETAIL-CANARY-2a6f"
        seen = []

        def loader():
            raise PromptUnavailable(f"internal detail {detail_canary}")

        async def search(theme):
            seen.append("search")
            return []

        async def llm(system, user):
            seen.append("llm")
            return VALID

        result = await generate_briefing(
            "theme ok", serp_client=_client(search), llm_complete=llm,
            prompt_loader=loader)
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.error, PROMPT_ERR)
        self.assertEqual(result.points, ())
        self.assertEqual(seen, [])
        self.assertNotIn(detail_canary, repr(result) + str(result.error))

    async def test_real_factory_identity_preserved_per_flow(self):
        real_new = svc.new_briefing
        cases = [
            ("direct_success", "llm_ok", 1, 1, BriefingStatus.DRAFT, None),
            ("retry_success", "llm_retry", 1, 3, BriefingStatus.DRAFT, None),
            ("exhaust_llm", "llm_exhaust", 1, 4, BriefingStatus.FAILED, GEN_ERR),
            ("prompt_failure", "prompt_fail", 0, 0, BriefingStatus.FAILED, PROMPT_ERR),
            ("serp_failure", "serp_fail", 1, 0, BriefingStatus.FAILED, SERP_ERR),
        ]
        for name, mode, want_search, want_llm, want_status, want_err in cases:
            with self.subTest(flow=name):
                created, searches, attempts = [], [], []

                def factory(theme):
                    briefing = real_new(theme)
                    created.append((briefing, dataclasses.asdict(briefing)))
                    return briefing

                async def search(theme):
                    searches.append(theme)
                    if mode == "serp_fail":
                        raise SerpSearchError(4)
                    return [{"title": "R", "url": "https://example.org/x",
                             "description": "S"}]

                async def llm(system, user):
                    attempts.append(1)
                    if mode == "llm_retry" and len(attempts) < 3:
                        raise LLMAttemptError()
                    if mode == "llm_exhaust":
                        raise LLMAttemptError()
                    return VALID

                def loader():
                    if mode == "prompt_fail":
                        raise PromptUnavailable("detail")
                    return "prompt"

                with mock.patch.object(svc, "new_briefing", side_effect=factory):
                    result = await generate_briefing(
                        "theme ok", serp_client=_client(search),
                        llm_complete=llm, prompt_loader=loader)
                self.assertEqual(len(created), 1)
                initial, snapshot = created[0]
                self.assertEqual(initial.status, BriefingStatus.GENERATING)
                self.assertEqual(initial.version, 1)
                self.assertEqual(initial.points, ())
                self.assertIsNone(initial.error)
                self.assertEqual(dataclasses.asdict(initial), snapshot)
                self.assertEqual(result.id, initial.id)
                self.assertEqual(result.version, 2)
                self.assertEqual(result.status, want_status)
                self.assertEqual(result.error, want_err)
                self.assertEqual(len(searches), want_search)
                self.assertEqual(len(attempts), want_llm)
                if want_status is BriefingStatus.DRAFT:
                    self.assertEqual(len(result.points), 3)
                    expected = [(item["title"], item["description"]) for item in json.loads(VALID)]
                    actual = [(p.title, p.description) for p in result.points]
                    self.assertEqual(actual, expected)
                else:
                    self.assertEqual(result.points, ())


if __name__ == "__main__":
    unittest.main()
