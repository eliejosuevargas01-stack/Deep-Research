"""Testes do binding LiteLLM one-attempt da role scout (T023, D5). Sem I/O real."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import litellm
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from litellm.llms.openai.common_utils import BaseOpenAILLM

import app.services.llm as llm_service
from app.briefing.llm_binding import _enforce_safe_transport, make_scout_complete
from app.briefing.service import LLMAttemptError
from app.services.llm import ProviderConfigurationError


def _db(keys, models, base_url=None):
    return SimpleNamespace(
        get=lambda *a, **k: None,
    ), keys, models, base_url


def _make_fake_session_factory():
    """Fábrica de sessão assíncrona compatível com `async with session_factory() as session`."""
    fake_session = AsyncMock()
    fake_session.close = AsyncMock()

    class _ContextManager:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await fake_session.close()

    factory = MagicMock(side_effect=_ContextManager)
    factory.fake_session = fake_session
    return factory


def _patch_rt(monkey_keys, monkey_models, base_url=None):
    async def fake_runtime(db):
        return dict(monkey_keys), dict(monkey_models)

    async def fake_record(db):
        return SimpleNamespace(openai_base_url=base_url)

    return fake_runtime, fake_record


def _resp(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class BindingTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_call_with_scout_model_and_key(self):
        keys = {"gemini": "g-key"}
        models = {"scout": "gemini/gemini-3.1-flash-lite-preview"}
        fr, fg = _patch_rt(keys, models)
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp("ok"))) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport") as st,
        ):
            fn = make_scout_complete(_make_fake_session_factory(), default_timeout_s=30.0)
            self.assertEqual(await fn("sys", "usr"), "ok")
            self.assertEqual(ac.await_count, 1)
            kw = ac.await_args.kwargs
            self.assertEqual(kw["model"], models["scout"])
            self.assertEqual(kw["api_key"], "g-key")
            self.assertEqual(kw["timeout"], 30.0)
            self.assertEqual(kw["messages"], [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}])
            self.assertNotIn("api_base", kw)
            st.assert_called_once_with()

    async def test_timeout_override_passed_through(self):
        keys = {"gemini": "g-key"}
        fr, fg = _patch_rt(keys, {"scout": "gemini/m"})
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp("ok"))) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            fn = make_scout_complete(_make_fake_session_factory(), default_timeout_s=30.0)
            await fn("s", "u", timeout_s=7.5)
            self.assertEqual(ac.await_args.kwargs["timeout"], 7.5)

    async def test_missing_model_and_key_raise_config_directly(self):
        fr, fg = _patch_rt({"gemini": "k"}, {})
        with patch("app.briefing.llm_binding.runtime_settings", fr), patch(
            "app.briefing.llm_binding.get_record", fg
        ), patch("app.briefing.llm_binding._enforce_safe_transport"):
            with self.assertRaises(ProviderConfigurationError):
                await make_scout_complete(_make_fake_session_factory())("s", "u")
        fr2, fg2 = _patch_rt({}, {"scout": "gemini/m"})
        with patch("app.briefing.llm_binding.runtime_settings", fr2), patch(
            "app.briefing.llm_binding.get_record", fg2
        ), patch("app.briefing.llm_binding._enforce_safe_transport"):
            with self.assertRaises(ProviderConfigurationError):
                await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_api_connection_error_becomes_safe_attempt_error(self):
        fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
        sentinel = "SENTINEL_SECRET_CONNECTION_PAYLOAD"
        exc = litellm.exceptions.APIConnectionError(sentinel, "openai", "model")
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            try:
                await make_scout_complete(_make_fake_session_factory())("s", "u")
            except LLMAttemptError as caught:
                import traceback
                rendered = "".join(traceback.format_exception(caught))
                self.assertEqual(str(caught), "Geração de briefing indisponível")
                self.assertEqual(caught.args, ("Geração de briefing indisponível",))
                self.assertIsNone(caught.__cause__)
                self.assertTrue(caught.__suppress_context__)
                self.assertNotIn(sentinel, rendered)
                self.assertNotIn(sentinel, str(caught))
            else:
                self.fail("APIConnectionError elegível deve virar LLMAttemptError")
            self.assertEqual(ac.await_count, 1)

    async def test_internal_server_error_becomes_attempt_error(self):
        fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
        exc = litellm.exceptions.InternalServerError("provider failed", "openai", "model")
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            with self.assertRaises(LLMAttemptError):
                await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_httpx_transports_and_builtin_timeouts_are_eligible(self):
        request = httpx.Request("GET", "https://example.invalid")
        errors = [
            httpx.ConnectError("connect", request=request),
            httpx.ConnectTimeout("connect timeout", request=request),
            httpx.ReadTimeout("read timeout", request=request),
            httpx.WriteTimeout("write timeout", request=request),
            httpx.PoolTimeout("pool timeout", request=request),
            TimeoutError("sdk timeout"),
        ]
        for exc in errors:
            with self.subTest(type=type(exc).__name__):
                fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
                with (
                    patch("app.briefing.llm_binding.runtime_settings", fr),
                    patch("app.briefing.llm_binding.get_record", fg),
                    patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
                    patch("app.briefing.llm_binding._enforce_safe_transport"),
                ):
                    with self.assertRaises(LLMAttemptError):
                        await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_http_status_error_retry_requires_numeric_recognized_status(self):
        request = httpx.Request("GET", "https://example.invalid")
        for status in (429, 500, 502, 503, 504):
            response = httpx.Response(status, request=request)
            exc = httpx.HTTPStatusError("status failure", request=request, response=response)
            with self.subTest(status=status):
                fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
                with (
                    patch("app.briefing.llm_binding.runtime_settings", fr),
                    patch("app.briefing.llm_binding.get_record", fg),
                    patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
                    patch("app.briefing.llm_binding._enforce_safe_transport"),
                ):
                    with self.assertRaises(LLMAttemptError):
                        await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_api_error_retry_uses_numeric_status_not_message(self):
        for status in (429, 500, 502, 503, 504):
            exc = litellm.exceptions.APIError(status, "provider error", "openai", "model")
            with self.subTest(status=status):
                fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
                with (
                    patch("app.briefing.llm_binding.runtime_settings", fr),
                    patch("app.briefing.llm_binding.get_record", fg),
                    patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
                    patch("app.briefing.llm_binding._enforce_safe_transport"),
                ):
                    with self.assertRaises(LLMAttemptError):
                        await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_unknown_and_bad_request_preserve_identity(self):
        exceptions = [
            RuntimeError("timeout quota 429 503"),
            TypeError("timeout quota 429 503"),
            litellm.exceptions.BadRequestError("timeout 503", "model", "openai"),
            litellm.exceptions.APIError("503", "provider error", "openai", "model"),
            litellm.exceptions.APIError(True, "provider error", "openai", "model"),
        ]
        for exc in exceptions:
            with self.subTest(type=type(exc).__name__, status=getattr(exc, "status_code", None)):
                fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
                with (
                    patch("app.briefing.llm_binding.runtime_settings", fr),
                    patch("app.briefing.llm_binding.get_record", fg),
                    patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
                    patch("app.briefing.llm_binding._enforce_safe_transport"),
                ):
                    with self.assertRaises(type(exc)) as caught:
                        await make_scout_complete(_make_fake_session_factory())("s", "u")
                    self.assertIs(caught.exception, exc)
                    self.assertNotIsInstance(caught.exception, LLMAttemptError)

    async def test_litellm_timeout_becomes_attempt_error(self):
        fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
        exc = litellm.exceptions.Timeout("request timed out", "model", "openai")
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            with self.assertRaises(LLMAttemptError):
                await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_permission_denied_and_auth_status_preserve_identity(self):
        request = httpx.Request("GET", "https://example.invalid")
        errors = [litellm.exceptions.PermissionDeniedError("denied", "openai", "model", httpx.Response(403, request=request))]
        errors.extend(
            httpx.HTTPStatusError("auth failure", request=request, response=httpx.Response(status, request=request))
            for status in (401, 403)
        )
        for exc in errors:
            with self.subTest(type=type(exc).__name__):
                fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
                with (
                    patch("app.briefing.llm_binding.runtime_settings", fr),
                    patch("app.briefing.llm_binding.get_record", fg),
                    patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
                    patch("app.briefing.llm_binding._enforce_safe_transport"),
                ):
                    with self.assertRaises(type(exc)) as caught:
                        await make_scout_complete(_make_fake_session_factory())("s", "u")
                    self.assertIs(caught.exception, exc)
                    self.assertNotIsInstance(caught.exception, LLMAttemptError)

    async def test_all_eligible_errors_render_safe_without_sentinel_leak(self):
        request = httpx.Request("GET", "https://example.invalid")
        sentinel = "LEAK_SECRET_TOKEN_XYZ_12345"
        eligible_cases = [
            litellm.exceptions.APIConnectionError(sentinel, "openai", "model"),
            litellm.exceptions.Timeout(sentinel, "model", "openai"),
            litellm.exceptions.InternalServerError(sentinel, "openai", "model"),
            litellm.exceptions.RateLimitError(sentinel, "openai", "model"),
            litellm.exceptions.ServiceUnavailableError(sentinel, "openai", "model"),
            litellm.exceptions.APIError(500, sentinel, "openai", "model"),
            httpx.ConnectError(sentinel, request=request),
            httpx.ConnectTimeout(sentinel, request=request),
            httpx.ReadTimeout(sentinel, request=request),
            httpx.WriteTimeout(sentinel, request=request),
            httpx.PoolTimeout(sentinel, request=request),
            httpx.HTTPStatusError(sentinel, request=request, response=httpx.Response(503, request=request)),
            TimeoutError(sentinel),
        ]
        import traceback
        for exc in eligible_cases:
            with self.subTest(case=type(exc).__name__):
                fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
                with (
                    patch("app.briefing.llm_binding.runtime_settings", fr),
                    patch("app.briefing.llm_binding.get_record", fg),
                    patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)),
                    patch("app.briefing.llm_binding._enforce_safe_transport"),
                ):
                    try:
                        await make_scout_complete(_make_fake_session_factory())("s", "u")
                    except LLMAttemptError as caught:
                        rendered = "".join(traceback.format_exception(caught))
                        self.assertEqual(str(caught), "Geração de briefing indisponível")
                        self.assertEqual(caught.args, ("Geração de briefing indisponível",))
                        self.assertIsNone(caught.__cause__)
                        self.assertTrue(caught.__suppress_context__)
                        self.assertNotIn(sentinel, rendered)
                        self.assertNotIn(sentinel, str(caught))
                    else:
                        self.fail(f"{type(exc).__name__} did not raise LLMAttemptError")

    async def test_transient_becomes_attempt_error_no_retry(self):
        fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
        for exc in (
            litellm.exceptions.RateLimitError("rate limit 429", "openai", "model"),
            litellm.exceptions.ServiceUnavailableError("503 unavailable", "openai", "model"),
            TimeoutError("timeout"),
        ):
            with (
                patch("app.briefing.llm_binding.runtime_settings", fr),
                patch("app.briefing.llm_binding.get_record", fg),
                patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=exc)) as ac,
                patch("app.briefing.llm_binding._enforce_safe_transport"),
            ):
                with self.assertRaises(LLMAttemptError):
                    await make_scout_complete(_make_fake_session_factory())("s", "u")
                self.assertEqual(ac.await_count, 1)

    async def test_auth_error_propagates_unmasked(self):
        fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
        sentinel = "MY_SECRET_SENTINEL_TOKEN"
        auth_exc = litellm.exceptions.AuthenticationError(sentinel, "openai", "model")
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=auth_exc)),
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            with self.assertRaises(litellm.exceptions.AuthenticationError) as ctx:
                await make_scout_complete(_make_fake_session_factory())("s", "u")
            self.assertIs(ctx.exception, auth_exc)
            self.assertNotIsInstance(ctx.exception, LLMAttemptError)

    async def test_config_error_from_provider_propagates(self):
        fr, fg = _patch_rt({"gemini": "k"}, {"scout": "gemini/m"})
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=ProviderConfigurationError("bad"))),
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            with self.assertRaises(ProviderConfigurationError):
                await make_scout_complete(_make_fake_session_factory())("s", "u")

    async def test_secret_in_output_blocked_by_guardrail(self):
        secret = "«redacted:sk-…»"
        fr, fg = _patch_rt({"gemini": secret}, {"scout": "gemini/m"})
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp(f"leak {secret}"))),
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            with self.assertRaises(RuntimeError):
                await make_scout_complete(_make_fake_session_factory())("s", "u")

    def test_default_timeout_validation_overflow_and_invalid(self):
        invalid_defaults = [
            10**1000,
            -10**1000,
            True,
            False,
            0,
            0.0,
            -5.0,
            float("nan"),
            float("inf"),
            float("-inf"),
            "invalid",
        ]
        for val in invalid_defaults:
            with self.subTest(val=val):
                with self.assertRaises(ValueError) as ctx:
                    make_scout_complete(_make_fake_session_factory(), default_timeout_s=val)
                self.assertEqual(
                    str(ctx.exception),
                    "Configuração de timeout LLM inválida (default_timeout_s)",
                )

    async def test_timeout_override_validation_early_abort_zero_boundary_calls(self):
        mock_rt = AsyncMock()
        mock_gr = AsyncMock()
        mock_st = AsyncMock()
        mock_ac = AsyncMock()

        fn = make_scout_complete(_make_fake_session_factory(), default_timeout_s=30.0)

        invalid_timeouts = [
            10**1000,
            -10**1000,
            True,
            False,
            0,
            0.0,
            -5.0,
            float("nan"),
            float("inf"),
            float("-inf"),
            "invalid",
        ]

        with (
            patch("app.briefing.llm_binding.runtime_settings", mock_rt),
            patch("app.briefing.llm_binding.get_record", mock_gr),
            patch("app.briefing.llm_binding._enforce_safe_transport", mock_st),
            patch("app.briefing.llm_binding.litellm.acompletion", mock_ac),
        ):
            for val in invalid_timeouts:
                with self.subTest(val=val):
                    with self.assertRaises(ValueError) as ctx:
                        await fn("s", "u", timeout_s=val)
                    self.assertEqual(
                        str(ctx.exception),
                        "Configuração de timeout LLM inválida (timeout_s)",
                    )

            self.assertEqual(mock_rt.await_count, 0)
            self.assertEqual(mock_gr.await_count, 0)
            self.assertEqual(mock_st.call_count, 0)
            self.assertEqual(mock_ac.await_count, 0)

    async def test_valid_timeout_above_30_accepted(self):
        keys = {"gemini": "g-key"}
        fr, fg = _patch_rt(keys, {"scout": "gemini/m"})
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp("ok"))) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            fn = make_scout_complete(_make_fake_session_factory(), default_timeout_s=30.0)
            for valid_val in (45.0, 120.0):
                with self.subTest(valid_val=valid_val):
                    res = await fn("sys", "usr", timeout_s=valid_val)
                    self.assertEqual(res, "ok")
                    self.assertEqual(ac.await_args.kwargs["timeout"], valid_val)

    async def test_no_internal_retries_on_503_openai_sdk(self):
        """F-CONTRACT-01: litellm.acompletion must receive num_retries=0 and max_retries=0.
        With HTTPX MockTransport returning 503, exactly ONE request should be made (no SDK retries)."""
        # Snapshot global clients' follow_redirects BEFORE any helper calls
        orig_mod_aclient_fr = getattr(getattr(getattr(litellm, "module_level_aclient", None), "client", None), "follow_redirects", None)
        orig_mod_client_fr = getattr(getattr(getattr(litellm, "module_level_client", None), "client", None), "follow_redirects", None)

        req_count = 0

        def handler(request):
            nonlocal req_count
            req_count += 1
            return httpx.Response(
                503,
                json={"error": {"message": "Service Unavailable", "type": "server_error"}}
            )

        mock_transport = httpx.MockTransport(handler)

        keys = {"openai": "sk-test-mock-key-123"}
        models = {"scout": "openai/gpt-4o-mini"}

        async def fake_runtime(db):
            return dict(keys), dict(models)

        async def fake_record(db):
            return SimpleNamespace(openai_base_url=None)

        # Snapshot transport state before test
        orig_async_create = AsyncHTTPHandler.create_client
        orig_sync_create = HTTPHandler.create_client
        orig_openai_sync = BaseOpenAILLM._get_sync_http_client
        orig_safe_active = llm_service._SAFE_TRANSPORT_ACTIVE
        orig_safe_error = llm_service._SAFE_TRANSPORT_ERROR

        def cleanup_transport():
            AsyncHTTPHandler.create_client = orig_async_create
            HTTPHandler.create_client = orig_sync_create
            BaseOpenAILLM._get_sync_http_client = orig_openai_sync
            llm_service._SAFE_TRANSPORT_ACTIVE = orig_safe_active
            llm_service._SAFE_TRANSPORT_ERROR = orig_safe_error
            if hasattr(litellm, "module_level_aclient") and litellm.module_level_aclient and orig_mod_aclient_fr is not None:
                litellm.module_level_aclient.client.follow_redirects = orig_mod_aclient_fr
            if hasattr(litellm, "module_level_client") and litellm.module_level_client and orig_mod_client_fr is not None:
                litellm.module_level_client.client.follow_redirects = orig_mod_client_fr

        self.addCleanup(cleanup_transport)

        async with httpx.AsyncClient(transport=mock_transport, follow_redirects=False) as client:
            with (
                patch("app.briefing.llm_binding.runtime_settings", fake_runtime),
                patch("app.briefing.llm_binding.get_record", fake_record),
                patch.object(BaseOpenAILLM, "_get_async_http_client", return_value=client),
                patch.object(litellm, "suppress_debug_info", True),
                patch.object(litellm, "turn_off_message_logging", True, create=True),
                patch.object(litellm, "telemetry", False, create=True),
            ):
                _enforce_safe_transport()
                fn = make_scout_complete(_make_fake_session_factory(), default_timeout_s=30.0)
                with self.assertRaises(LLMAttemptError):
                    await fn("sys", "usr")

        # The SDK must NOT retry internally: exactly 1 HTTP request
        self.assertEqual(req_count, 1, f"Expected 1 HTTP request, got {req_count}")

    async def test_kwargs_include_no_retry_controls(self):
        """Verify num_retries=0 and max_retries=0 are passed to litellm.acompletion in happy path."""
        keys = {"gemini": "g-key"}
        models = {"scout": "gemini/gemini-3.1-flash-lite-preview"}
        fr, fg = _patch_rt(keys, models)
        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp("ok"))) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            fn = make_scout_complete(_make_fake_session_factory(), default_timeout_s=30.0)
            await fn("sys", "usr")
            kw = ac.await_args.kwargs
            self.assertEqual(kw.get("num_retries"), 0)
            self.assertEqual(kw.get("max_retries"), 0)
            self.assertEqual(kw["model"], models["scout"])
            self.assertEqual(kw["api_key"], "g-key")
            self.assertEqual(kw["timeout"], 30.0)
            self.assertEqual(kw["messages"], [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}])


    async def test_session_lifecycle_closed_before_network_call(self):
        """Verifica que a sessão aberta é fechada ANTES de acompletion ser invocado."""
        call_order = []

        fake_session = AsyncMock()

        async def fake_close():
            call_order.append("session_close")

        fake_session.close = AsyncMock(side_effect=fake_close)

        class _ContextManager:
            async def __aenter__(self):
                call_order.append("session_enter")
                return fake_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                await fake_session.close()
                call_order.append("session_exit")

        factory = MagicMock(side_effect=_ContextManager)

        async def fake_acompletion(**kwargs):
            call_order.append("litellm_acompletion")
            return _resp("ok")

        keys = {"gemini": "g-key"}
        models = {"scout": "gemini/gemini-3.1-flash-lite-preview"}
        fr, fg = _patch_rt(keys, models)

        with (
            patch("app.briefing.llm_binding.runtime_settings", fr),
            patch("app.briefing.llm_binding.get_record", fg),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(side_effect=fake_acompletion)),
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            fn = make_scout_complete(factory, default_timeout_s=30.0)
            result = await fn("sys", "usr")
            self.assertEqual(result, "ok")

        self.assertIn("session_exit", call_order)
        self.assertIn("litellm_acompletion", call_order)
        self.assertLess(
            call_order.index("session_exit"),
            call_order.index("litellm_acompletion"),
            f"Sessão deve ser fechada antes da chamada de rede: {call_order}",
        )
        self.assertFalse(hasattr(fake_session, "commit") and fake_session.commit.called)
        self.assertFalse(hasattr(fake_session, "rollback") and fake_session.rollback.called)

    async def test_session_factory_never_invoked_on_early_timeout_abort(self):
        """Verifica que session_factory nunca é chamada quando timeout_s é inválido."""
        factory = MagicMock()
        fn = make_scout_complete(factory, default_timeout_s=30.0)

        for invalid_val in [0, -1.0, float("nan"), float("inf"), True, "10"]:
            with self.subTest(invalid_val=invalid_val):
                with self.assertRaises(ValueError):
                    await fn("sys", "usr", timeout_s=invalid_val)
        self.assertEqual(factory.call_count, 0)

    async def test_integrated_sqlite_settings_read_and_no_spurious_persistence(self):
        """D3: get_record(session) cria AppSettings via flush transitório em banco vazio,
        mas fechamento da sessão isolada sem commit reverte inserção; zero linhas persistem."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import StaticPool
        from sqlalchemy import select
        from app.models.domain_models import AppSettings, Base

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        # Injeta variáveis de ambiente simuladas nas settings para scout
        with (
            patch("app.services.settings.settings.SCOUT_MODEL", "gemini/gemini-3.1-flash-lite-preview"),
            patch("app.services.settings.settings.GEMINI_API_KEY", "gemini-integrated-key"),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp("ok"))) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            fn = make_scout_complete(session_factory, default_timeout_s=30.0)
            res = await fn("sys_test", "usr_test")
            self.assertEqual(res, "ok")
            kw = ac.await_args.kwargs
            self.assertEqual(kw["model"], "gemini/gemini-3.1-flash-lite-preview")
            self.assertEqual(kw["api_key"], "gemini-integrated-key")

        # Verifica se banco continua vazio após chamada (nenhuma linha AppSettings salva)
        async with session_factory() as check_session:
            rows = (await check_session.execute(select(AppSettings))).scalars().all()
            self.assertEqual(
                len(rows),
                0,
                f"Nenhuma linha AppSettings deve ser persistida silenciosamente, encontrado: {rows}",
            )

        await engine.dispose()

    async def test_scout_role_defaults_to_gemini_3_8_flash_when_unconfigured(self):
        """E001: Quando scout não está configurado em AppSettings.models e nem via
        variável de ambiente SCOUT_MODEL, runtime_settings aplica o fallback padrão
        gemini/gemini-3.8-flash."""
        from app.services.settings import DEFAULT_ROLE_MODELS, runtime_settings
        self.assertEqual(DEFAULT_ROLE_MODELS.get("scout"), "gemini/gemini-3.8-flash")
        factory = MagicMock()
        fake_session = AsyncMock()
        fake_record = MagicMock()
        fake_record.encrypted_credentials = {"gemini": "fake-enc"}
        fake_record.models = {}
        fake_record.openai_base_url = None
        fake_session.get.return_value = fake_record
        fake_session.__aenter__.return_value = fake_session
        fake_session.__aexit__.return_value = None
        factory.return_value = fake_session

        with (
            patch("app.services.settings.settings.SCOUT_MODEL", None),
            patch("app.services.settings.decrypt_secret", return_value="gemini-key"),
            patch("app.briefing.llm_binding.litellm.acompletion", new=AsyncMock(return_value=_resp("ok"))) as ac,
            patch("app.briefing.llm_binding._enforce_safe_transport"),
        ):
            keys, models = await runtime_settings(fake_session)
            self.assertEqual(models.get("scout"), "gemini/gemini-3.8-flash")
            fn = make_scout_complete(factory, default_timeout_s=30.0)
            res = await fn("sys_test", "usr_test")
            self.assertEqual(res, "ok")
            kw = ac.await_args.kwargs
            self.assertEqual(kw["model"], "gemini/gemini-3.8-flash")


if __name__ == "__main__":
    unittest.main()
