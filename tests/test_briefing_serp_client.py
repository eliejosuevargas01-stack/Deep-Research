import asyncio
import json
import unittest

import httpx

from app.briefing.serp_client import JinaSerpClient, SerpSearchError


CANARY = "FAKE-CANARY-DO-NOT-LEAK"


def payload(data=None):
    return {"data": data if data is not None else [{
        "title": "Title", "url": "https://example.org/path", "description": "Snippet",
        "content": CANARY, "publishedTime": CANARY, "usage": {"tokens": 8},
    }]}


class JinaSerpClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_posts_only_to_jina_and_exports_required_fields(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=payload())

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            result = await JinaSerpClient(api_key="test-key", http_client=http).search("  tema válido  ")
            self.assertFalse(http.is_closed)

        self.assertEqual(len(seen), 1)
        request = seen[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url), "https://s.jina.ai/")
        self.assertEqual(json.loads(request.content), {"q": "tema válido"})
        self.assertEqual(request.headers["authorization"], "Bearer test-key")
        self.assertEqual(request.headers["accept"], "application/json")
        self.assertEqual(request.headers["content-type"], "application/json")
        self.assertEqual(request.headers["x-respond-with"], "no-content")
        self.assertEqual(request.extensions["timeout"]["write"], 30.0)
        self.assertEqual(result, [{"title": "Title", "url": "https://example.org/path", "description": "Snippet"}])
        self.assertNotIn(CANARY, repr(result))

    async def test_retries_sequentially_at_most_four_total_then_succeeds(self):
        calls = 0
        active = 0
        max_active = 0

        async def handler(request):
            nonlocal calls, active, max_active
            calls += 1
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0)
                return httpx.Response(503 if calls < 4 else 200, json=payload())
            finally:
                active -= 1

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            result = await JinaSerpClient(api_key="test-key", http_client=http).search("tema válido")
        self.assertEqual(len(result), 1)
        self.assertEqual(calls, 4)
        self.assertEqual(max_active, 1)

    async def test_exhaustion_raises_safe_error_with_real_attempt_count(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(503, text=CANARY)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with self.assertRaises(SerpSearchError) as raised:
                await JinaSerpClient(api_key="test-key", http_client=http).search("tema válido")
        self.assertEqual(calls, 4)
        self.assertEqual(raised.exception.attempts, 4)
        self.assertNotIn(CANARY, str(raised.exception))
        self.assertNotIn("test-key", str(raised.exception))

    async def test_invalid_json_shape_fields_and_empty_data_fail_safely(self):
        responses = [
            httpx.Response(200, text="not json"),
            httpx.Response(200, json={"data": []}),
            httpx.Response(200, json={"data": [{"title": "", "url": "https://example.org", "description": "x"}]}),
            httpx.Response(200, json={"data": [{"title": "x", "url": "javascript:alert(1)", "description": "y"}]}),
        ]
        for response in responses:
            calls = 0

            def handler(request, response=response):
                nonlocal calls
                calls += 1
                return response

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
                with self.assertRaises(SerpSearchError):
                    await JinaSerpClient(api_key="test-key", http_client=http).search("tema válido")
            self.assertEqual(calls, 4)

    async def test_invalid_theme_key_and_timeout_fail_before_io(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            for theme in ("  ", "ab", "x" * 301):
                with self.assertRaises(ValueError):
                    await JinaSerpClient(api_key="test-key", http_client=http).search(theme)
            for key, timeout in (("", 30), ("bad\nheader", 30), ("test-key", 0), ("test-key", float("inf"))):
                with self.assertRaises(ValueError):
                    JinaSerpClient(api_key=key, timeout=timeout, http_client=http)
        self.assertEqual(calls, 0)

    def test_api_key_validation_rejects_non_printable_ascii_control_whitespace_and_non_ascii(self):
        invalid_keys = [
            123,
            None,
            "",
            "   ",
            "\n",
            "\r",
            "\t",
            "\x00",
            "\x7f",
            "key with space",
            " key_with_leading_space",
            "key_with_trailing_space ",
            "chave_com_unicode_áêí",
            "key\x01with_control",
        ]
        for key in invalid_keys:
            with self.assertRaises(ValueError) as ctx:
                JinaSerpClient(api_key=key)
            self.assertEqual(str(ctx.exception), "Chave de API inválida")

    async def test_timeout_ends_attempt_then_retries_without_long_wait(self):
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                await asyncio.sleep(0.2)
            return httpx.Response(200, json=payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            result = await JinaSerpClient(api_key="test-key", timeout=0.02, http_client=http).search("tema válido")
        self.assertEqual(len(result), 1)
        self.assertEqual(calls, 2)

    async def test_two_operations_on_same_client_never_overlap(self):
        active = 0
        max_active = 0

        async def handler(request):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0.01)
                return httpx.Response(200, json=payload())
            finally:
                active -= 1

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = JinaSerpClient(api_key="test-key", http_client=http)
            await asyncio.gather(client.search("tema um"), client.search("tema dois"))
        self.assertEqual(max_active, 1)

    async def test_cancellation_propagates_and_releases_lock(self):
        started = asyncio.Event()
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                await asyncio.Event().wait()
            return httpx.Response(200, json=payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = JinaSerpClient(api_key="test-key", http_client=http)
            task = asyncio.create_task(client.search("tema um"))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(len(await client.search("tema dois")), 1)
        self.assertEqual(calls, 2)

    async def test_redirect_is_not_followed_and_does_not_leak_authorization(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(302, headers={"location": "https://attacker.invalid/"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
            with self.assertRaises(SerpSearchError):
                await JinaSerpClient(api_key="test-key", http_client=http).search("tema válido")
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(str(request.url) == "https://s.jina.ai/" for request in requests))


if __name__ == "__main__":
    unittest.main()
