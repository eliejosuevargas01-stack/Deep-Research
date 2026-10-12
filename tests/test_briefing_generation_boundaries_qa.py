import json
import math
import unittest

from app.briefing.domain import BriefingStatus, InvalidContent
from app.briefing.service import generate_briefing

VALID_POINTS = [
    {"title": "Title 1", "description": "Desc 1"},
    {"title": "Title 2", "description": "Desc 2"},
    {"title": "Title 3", "description": "Desc 3"},
]
VALID_JSON = json.dumps(VALID_POINTS)
SERP_RESULTS = [{"title": "R", "url": "https://example.org", "description": "S"}]


def client_for(search_func):
    return type("FakeSerpClient", (), {"search": staticmethod(search_func)})()


class TestBriefingGenerationBoundariesQA(unittest.IsolatedAsyncioTestCase):
    async def test_theme_boundaries_and_types_enforce_domain_or_draft_with_zero_or_exact_io(self):
        invalid_themes = [
            "ab",
            "   ab   ",
            "a" * 301,
            "  " + "a" * 301 + "  ",
            "",
            "   \t\n ",
            None,
            0,
            True,
            [],
            {},
        ]
        for theme in invalid_themes:
            with self.subTest(invalid_theme=theme):
                loader_calls, search_calls, llm_calls = [], [], []

                async def fake_search(t):
                    search_calls.append(t)
                    return SERP_RESULTS

                async def fake_llm(s, u):
                    llm_calls.append((s, u))
                    return VALID_JSON

                def fake_loader():
                    loader_calls.append(1)
                    return "prompt"

                with self.assertRaises(InvalidContent):
                    await generate_briefing(
                        theme,
                        serp_client=client_for(fake_search),
                        llm_complete=fake_llm,
                        prompt_loader=fake_loader,
                    )
                self.assertEqual(len(loader_calls), 0)
                self.assertEqual(len(search_calls), 0)
                self.assertEqual(len(llm_calls), 0)

        valid_themes = [
            ("  abc  ", "abc"),
            ("  " + "a" * 300 + "  ", "a" * 300),
        ]
        for raw_theme, expected_theme in valid_themes:
            with self.subTest(valid_theme=raw_theme):
                loader_calls, search_calls, llm_calls = [], [], []

                async def fake_search(t):
                    search_calls.append(t)
                    return SERP_RESULTS

                async def fake_llm(s, u):
                    llm_calls.append((s, u))
                    return VALID_JSON

                def fake_loader():
                    loader_calls.append(1)
                    return "prompt"

                result = await generate_briefing(
                    raw_theme,
                    serp_client=client_for(fake_search),
                    llm_complete=fake_llm,
                    prompt_loader=fake_loader,
                )
                self.assertEqual(result.status, BriefingStatus.DRAFT)
                self.assertEqual(result.theme, expected_theme)
                self.assertEqual(len(result.points), 3)
                self.assertEqual(len(loader_calls), 1)
                self.assertEqual(search_calls, [expected_theme])
                self.assertEqual(len(llm_calls), 1)

    async def test_config_invalid_types_and_nonfinite_timeouts_raise_value_error_zero_io(self):
        invalid_attempts = ["0", "5", True, 1.5, "4", None, [], {}]
        invalid_timeouts = ["0", "-1", True, math.nan, math.inf, -math.inf, None, "30"]

        for bad_att in invalid_attempts:
            with self.subTest(bad_attempts=bad_att):
                loader_calls, search_calls, llm_calls = [], [], []

                async def fake_search(t):
                    search_calls.append(t)
                    return SERP_RESULTS

                async def fake_llm(s, u):
                    llm_calls.append((s, u))
                    return VALID_JSON

                def fake_loader():
                    loader_calls.append(1)
                    return "prompt"

                with self.assertRaises(ValueError) as exc_att:
                    await generate_briefing(
                        "valid theme",
                        serp_client=client_for(fake_search),
                        llm_complete=fake_llm,
                        prompt_loader=fake_loader,
                        llm_attempts=bad_att,
                    )
                self.assertEqual(
                    str(exc_att.exception),
                    "Configuração de tentativas LLM inválida",
                )
                self.assertEqual(len(loader_calls), 0)
                self.assertEqual(len(search_calls), 0)
                self.assertEqual(len(llm_calls), 0)

        for bad_to in invalid_timeouts:
            with self.subTest(bad_timeout=bad_to):
                loader_calls, search_calls, llm_calls = [], [], []

                async def fake_search(t):
                    search_calls.append(t)
                    return SERP_RESULTS

                async def fake_llm(s, u):
                    llm_calls.append((s, u))
                    return VALID_JSON

                def fake_loader():
                    loader_calls.append(1)
                    return "prompt"

                with self.assertRaises(ValueError) as exc_to:
                    await generate_briefing(
                        "valid theme",
                        serp_client=client_for(fake_search),
                        llm_complete=fake_llm,
                        prompt_loader=fake_loader,
                        llm_timeout_s=bad_to,
                    )
                self.assertEqual(
                    str(exc_to.exception),
                    "Configuração de timeout LLM inválida",
                )
                self.assertEqual(len(loader_calls), 0)
                self.assertEqual(len(search_calls), 0)
                self.assertEqual(len(llm_calls), 0)

        for att, to in [(1, 30.0), (4, 60.0)]:
            with self.subTest(valid_cfg=(att, to)):
                async def fake_search(t):
                    return SERP_RESULTS

                async def fake_llm(s, u):
                    return VALID_JSON

                result = await generate_briefing(
                    "valid theme",
                    serp_client=client_for(fake_search),
                    llm_complete=fake_llm,
                    prompt_loader=lambda: "prompt",
                    llm_attempts=att,
                    llm_timeout_s=to,
                )
                self.assertEqual(result.status, BriefingStatus.DRAFT)

    async def test_single_invalid_field_in_3point_payload_exhausts_retries_to_failed(self):
        invalid_field_values = [
            "MISSING",
            "",
            "   ",
            None,
            123,
            True,
            [],
            {},
        ]

        for field in ("title", "description"):
            for val in invalid_field_values:
                for idx in range(3):
                    with self.subTest(field=field, val=val, idx=idx):
                        points_copy = [
                            {"title": "Title 1", "description": "Desc 1"},
                            {"title": "Title 2", "description": "Desc 2"},
                            {"title": "Title 3", "description": "Desc 3"},
                        ]
                        if val == "MISSING":
                            del points_copy[idx][field]
                        else:
                            points_copy[idx][field] = val
                        payload = json.dumps(points_copy)

                        search_calls, llm_calls = [], []

                        async def fake_search(t):
                            search_calls.append(t)
                            return SERP_RESULTS

                        async def fake_llm(s, u):
                            llm_calls.append((s, u))
                            return payload

                        result = await generate_briefing(
                            "valid theme",
                            serp_client=client_for(fake_search),
                            llm_complete=fake_llm,
                            prompt_loader=lambda: "prompt",
                        )
                        self.assertEqual(result.status, BriefingStatus.FAILED)
                        self.assertEqual(result.error, "Geração de briefing indisponível")
                        self.assertEqual(result.points, ())
                        self.assertEqual(len(search_calls), 1)
                        self.assertEqual(len(llm_calls), 4)

    async def test_fences_and_raw_json_formatting_rules(self):
        invalid_raws = [
            f"```json\n{VALID_JSON}\n```\n```json\n{VALID_JSON}\n```",
            f"```javascript\n{VALID_JSON}\n```",
            f"```python\n{VALID_JSON}\n```",
            f"```json\n{VALID_JSON}\n``` extra garbage",
            f"Prefix text {VALID_JSON}",
        ]

        for bad_raw in invalid_raws:
            with self.subTest(bad_raw=bad_raw[:30]):
                search_calls, llm_calls = [], []

                async def fake_search(t):
                    search_calls.append(t)
                    return SERP_RESULTS

                async def fake_llm(s, u):
                    llm_calls.append((s, u))
                    return bad_raw

                result = await generate_briefing(
                    "valid theme",
                    serp_client=client_for(fake_search),
                    llm_complete=fake_llm,
                    prompt_loader=lambda: "prompt",
                )
                self.assertEqual(result.status, BriefingStatus.FAILED)
                self.assertEqual(result.error, "Geração de briefing indisponível")
                self.assertEqual(len(search_calls), 1)
                self.assertEqual(len(llm_calls), 4)

        valid_fenced = f"```json\n{VALID_JSON}\n```"
        search_calls, llm_calls = [], []

        async def fake_search(t):
            search_calls.append(t)
            return SERP_RESULTS

        async def fake_llm(s, u):
            llm_calls.append((s, u))
            return valid_fenced

        result = await generate_briefing(
            "valid theme",
            serp_client=client_for(fake_search),
            llm_complete=fake_llm,
            prompt_loader=lambda: "prompt",
        )
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(len(result.points), 3)


if __name__ == "__main__":
    unittest.main()
