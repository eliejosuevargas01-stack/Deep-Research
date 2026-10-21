"""Testes unitários do JinaToolAdapter (T006, RN-05/RN-06/RN-07/RN-08, RF-06/RF-07)."""

from __future__ import annotations

import asyncio
import json
import traceback
from unittest.mock import AsyncMock

import httpx
import pytest

from app.investigation.tools import (
    ENDPOINT,
    JinaSearchError,
    JinaSearchResult,
    JinaToolAdapter,
    _parse_body,
)


@pytest.mark.anyio
async def test_jina_search_success_direct_contract_and_payload(
    make_jina_mock_transport, sample_jina_items,
):
    """
    RN-05, RF-06: Sucesso na busca direta.
    Valida POST https://s.jina.ai/, payload {"q": query, "num": 10}, headers exigidos,
    retorno de JinaSearchResult com content preenchido e URLs capturadas.
    """
    transport, recorded = make_jina_mock_transport()
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="jina-secret-api-key-123", http_client=client)
        query = "arquitetura distribuída de sistemas multiagente"
        result = await adapter.search(query)

        assert isinstance(result, JinaSearchResult)
        assert len(recorded) == 1

        req = recorded[0]
        assert str(req.url) == ENDPOINT
        assert str(req.url) == "https://s.jina.ai/"
        assert req.method == "POST"

        sent_payload = json.loads(req.content.decode("utf-8"))
        assert sent_payload == {"q": query, "num": 10}

        assert req.headers.get("Accept") == "application/json"
        assert req.headers.get("X-Engine") == "direct"
        assert req.headers.get("Authorization") == "Bearer jina-secret-api-key-123"
        assert req.headers.get("Content-Type") == "application/json"

        assert result.urls == [item["url"] for item in sample_jina_items]
        for item in sample_jina_items:
            assert item["content"] in result.content
            assert item["title"] in result.content
            assert item["url"] in result.content
        assert query in result.content



@pytest.mark.anyio
async def test_jina_search_with_proxy_configuration(make_jina_mock_transport):
    """
    RN-05, RF-06: Chamada direcionada ao proxy corporativo.
    Valida proxy_url e proxy_key aplicados com mesmos headers e payload.
    """
    proxy_url = "https://internal-gateway.corp.local/v1/jina"
    proxy_key = "proxy-auth-token-xyz"
    transport, recorded = make_jina_mock_transport()

    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(
            api_key="default-jina-key",
            proxy_url=proxy_url,
            proxy_key=proxy_key,
            http_client=client,
        )
        query = "consulta roteada via gateway proxy"
        result = await adapter.search(query)

        assert isinstance(result, JinaSearchResult)
        assert len(recorded) == 1

        req = recorded[0]
        assert str(req.url) == proxy_url
        assert req.method == "POST"

        sent_payload = json.loads(req.content.decode("utf-8"))
        assert sent_payload == {"q": query, "num": 10}

        assert req.headers.get("Authorization") == f"Bearer {proxy_key}"
        assert req.headers.get("Accept") == "application/json"
        assert req.headers.get("X-Engine") == "direct"
        assert req.headers.get("Content-Type") == "application/json"


@pytest.mark.anyio
async def test_jina_search_proxy_without_proxy_key_falls_back_to_api_key(
    make_jina_mock_transport,
):
    """Valida que ausência de proxy_key recorre à api_key principal no proxy."""
    proxy_url = "https://internal-gateway.corp.local/v1/jina"
    transport, recorded = make_jina_mock_transport()

    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(
            api_key="fallback-api-key-999",
            proxy_url=proxy_url,
            proxy_key=None,
            http_client=client,
        )
        await adapter.search("query fallback")

        assert len(recorded) == 1
        req = recorded[0]
        assert str(req.url) == proxy_url
        assert req.headers.get("Authorization") == "Bearer fallback-api-key-999"


@pytest.mark.anyio
async def test_jina_search_timeout_parameter_and_enforcement(
    make_jina_mock_transport, monkeypatch
):
    """
    RN-07, RF-06: Valida timeout de 90s respeitado no cliente e na requisição.
    """
    transport, recorded = make_jina_mock_transport()
    async with httpx.AsyncClient(transport=transport) as client:
        # Timeout padrão é 90.0
        adapter_default = JinaToolAdapter(api_key="key-test", http_client=client)
        assert adapter_default._timeout == 90.0

        await adapter_default.search("verificacao timeout default")
        assert len(recorded) == 1
        extensions_timeout = recorded[0].extensions.get("timeout", {})
        assert extensions_timeout.get("read") == 90.0
        assert extensions_timeout.get("connect") == 90.0

    # Valida timeout customizado
    transport_custom, recorded_custom = make_jina_mock_transport()
    async with httpx.AsyncClient(transport=transport_custom) as client_custom:
        adapter_custom = JinaToolAdapter(
            api_key="key-test", timeout=45.0, http_client=client_custom
        )
        assert adapter_custom._timeout == 45.0
        await adapter_custom.search("verificacao timeout custom")
        assert len(recorded_custom) == 1
        assert recorded_custom[0].extensions.get("timeout", {}).get("read") == 45.0


@pytest.mark.anyio
async def test_jina_search_retries_transient_failure_then_success(
    make_jina_mock_transport, monkeypatch, sample_jina_items
):
    """
    RN-07, RF-08: Simula 2 falhas transitórias (429 e erro de conexão) e sucesso na 3ª tentativa.
    Valida backoff padrão (2.0s e 4.0s) e retorno de sucesso sem esgotamento.
    """
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    transport, recorded = make_jina_mock_transport(
        responses=[
            httpx.Response(429, headers={"Content-Type": "application/json"}),
            httpx.ConnectError("Falha de conexão com s.jina.ai"),
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "Recuperado com sucesso na 3a tentativa",
                            "url": "https://example.com/recuperado",
                            "description": "Sucesso",
                            "content": "Conteúdo final disponível.",
                        }
                    ] + sample_jina_items[1:]
                },
            ),
        ]
    )

    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="key-retry-test", http_client=client)
        result = await adapter.search("busca resiliente")

        assert len(recorded) == 3
        assert isinstance(result, JinaSearchResult)
        assert "Recuperado com sucesso na 3a tentativa" in result.content
        assert result.urls == ["https://example.com/recuperado"] + [item["url"] for item in sample_jina_items[1:]]

        # Delays default: 2.0s na primeira falha, 4.0s na segunda falha
        assert sleep_mock.await_count == 2
        assert sleep_mock.await_args_list[0].args[0] == 2.0
        assert sleep_mock.await_args_list[1].args[0] == 4.0


@pytest.mark.anyio
async def test_jina_search_retry_after_header_respected(
    make_jina_mock_transport, monkeypatch, sample_jina_items
):
    """
    RN-07, RF-08: Simula resposta 429 com cabeçalho 'Retry-After: 1'.
    Valida que o delay informado é respeitado ao invés do backoff padrão.
    """
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    transport, recorded = make_jina_mock_transport(
        responses=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "Sucesso após Retry-After",
                            "url": "https://example.com/retry-after-ok",
                            "description": "Desc",
                            "content": "Conteúdo após esperar 1s.",
                        }
                    ] + sample_jina_items[1:]
                },
            ),
        ]
    )

    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="key-retry-after", http_client=client)
        result = await adapter.search("busca com retry after")

        assert len(recorded) == 2
        assert isinstance(result, JinaSearchResult)
        assert "Sucesso após Retry-After" in result.content

        # Delay respeitado do cabeçalho
        assert sleep_mock.await_count == 1
        assert sleep_mock.await_args_list[0].args[0] == 1.0


@pytest.mark.anyio
async def test_jina_search_exhaustion_raises_jina_search_error_no_secret_leak(
    make_jina_mock_transport, monkeypatch
):
    """
    RN-07, RF-08: Simula esgotamento de 3 tentativas técnicas.
    Valida lançamento de JinaSearchError(3) sem vazar api_key ou proxy_key.
    """
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    secret_api_key = "super-secret-jina-api-key-998877"
    secret_proxy_key = "super-secret-proxy-auth-key-665544"

    transport, recorded = make_jina_mock_transport(
        responses=[
            httpx.Response(500, json={"error": "Erro interno 1"}),
            httpx.Response(502, json={"error": "Bad gateway 2"}),
            httpx.Response(503, json={"error": "Service unavailable 3"}),
        ]
    )

    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(
            api_key=secret_api_key,
            proxy_url="https://proxy.example.com",
            proxy_key=secret_proxy_key,
            http_client=client,
        )

        with pytest.raises(JinaSearchError) as exc_info:
            await adapter.search("pesquisa que esgotara tentativas")

        err = exc_info.value
        assert err.attempts == 3
        assert len(recorded) == 3

        # Mensagem limpa
        err_str = str(err)
        err_repr = repr(err)
        assert "Busca Jina indisponível após 3 tentativas" in err_str

        # Nenhum segredo vazado em str, repr ou traceback
        assert secret_api_key not in err_str
        assert secret_proxy_key not in err_str
        assert secret_api_key not in err_repr
        assert secret_proxy_key not in err_repr

        tb_text = "".join(traceback.format_exception(err))
        assert secret_api_key not in tb_text
        assert secret_proxy_key not in tb_text


@pytest.mark.anyio
async def test_jina_search_recursive_url_extraction_and_deduplication(make_jina_mock_transport, sample_jina_items):
    """Referência recursiva não equivale a corpo lido; deduplicação preservada."""
    sample_jina_items[0]["metadata"] = {"link": "https://example.com/not-read", "href": sample_jina_items[0]["url"]}
    transport, recorded = make_jina_mock_transport(default_payload={"data": sample_jina_items})
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        result = await JinaToolAdapter(api_key="synthetic-key", http_client=client).search("fontes")
    assert len(recorded) == 1
    assert result.urls == [item["url"] for item in sample_jina_items]
    assert len(result.urls) == len(set(result.urls))


@pytest.mark.anyio
async def test_jina_search_input_validations():
    """Validações de entrada estritas do JinaToolAdapter."""
    # Chave de API inválida
    with pytest.raises(ValueError, match="Chave de API inválida"):
        JinaToolAdapter(api_key="")

    with pytest.raises(ValueError, match="Chave de API inválida"):
        JinaToolAdapter(api_key="chave com espaco")

    with pytest.raises(ValueError, match="Chave de API inválida"):
        JinaToolAdapter(api_key=None)  # type: ignore

    # Timeout inválido
    with pytest.raises(ValueError, match="Timeout inválido"):
        JinaToolAdapter(api_key="key", timeout=0)

    with pytest.raises(ValueError, match="Timeout inválido"):
        JinaToolAdapter(api_key="key", timeout=-10)

    with pytest.raises(ValueError, match="Timeout inválido"):
        JinaToolAdapter(api_key="key", timeout=True)  # type: ignore

    with pytest.raises(ValueError, match="Timeout inválido"):
        JinaToolAdapter(api_key="key", timeout=float("nan"))

    # Proxy URL inválida
    with pytest.raises(ValueError, match="URL de proxy inválida"):
        JinaToolAdapter(api_key="key", proxy_url="")

    with pytest.raises(ValueError, match="URL de proxy inválida"):
        JinaToolAdapter(api_key="key", proxy_url="   ")

    # Query de busca inválida
    adapter = JinaToolAdapter(api_key="valid-key")
    with pytest.raises(ValueError, match="Query inválida"):
        await adapter.search("")

    with pytest.raises(ValueError, match="Query inválida"):
        await adapter.search("   ")

    with pytest.raises(ValueError, match="Query inválida"):
        await adapter.search(None)  # type: ignore


@pytest.mark.anyio
async def test_jina_search_non_retryable_client_error(make_jina_mock_transport):
    """
    Erros de cliente 4xx não-429 (ex.: 400 ou 403) não executam retries
    e levantam JinaSearchError(1) imediatamente.
    """
    transport, recorded = make_jina_mock_transport(
        responses=[httpx.Response(400, json={"error": "Bad Request"})]
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="test-key", http_client=client)
        with pytest.raises(JinaSearchError) as exc_info:
            await adapter.search("termo incorreto")

        assert exc_info.value.attempts == 1
        assert len(recorded) == 1


@pytest.mark.anyio
async def test_jina_search_malformed_json_retries_then_succeeds(
    make_jina_mock_transport, monkeypatch, sample_jina_items
):
    """
    Corpo com JSON inválido dispara _AttemptFailed e tenta novamente.
    """
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    transport, recorded = make_jina_mock_transport(
        responses=[
            httpx.Response(200, content=b"<html>Bad Gateway HTML</html>"),
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "Recuperado após JSON inválido",
                            "url": "https://example.com/ok",
                            "content": "Texto válido.",
                        }
                    ] + sample_jina_items[1:]
                },
            ),
        ]
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="test-key", http_client=client)
        res = await adapter.search("query retry json")

        assert len(recorded) == 2
        assert "Recuperado após JSON inválido" in res.content
        assert sleep_mock.await_count == 1


@pytest.mark.anyio
async def test_jina_search_timeout_error_exhaustion(
    make_jina_mock_transport, monkeypatch
):
    """
    Timeout de requisição httpx em todas as tentativas esgota com JinaSearchError(3).
    """
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    transport, recorded = make_jina_mock_transport(
        responses=[
            httpx.ReadTimeout("Timeout na tentativa 1"),
            httpx.ReadTimeout("Timeout na tentativa 2"),
            httpx.ReadTimeout("Timeout na tentativa 3"),
        ]
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="test-key", http_client=client)
        with pytest.raises(JinaSearchError) as exc_info:
            await adapter.search("query timeout")

        assert exc_info.value.attempts == 3
        assert len(recorded) == 3


@pytest.mark.anyio
async def test_database_fixtures_smoke_test(sqlite_engine, session_factory, db_session):
    """
    Smoke test para garantir que as fixtures do SQLite em memória funcionam
    com engine, session_factory e db_session limpos e prontos para uso.
    """
    from sqlalchemy import select
    from app.models.domain_models import Research, ResearchStatus

    r = Research(theme="Pesquisa Teste Fixture", status=ResearchStatus.SCRAPER.value)
    db_session.add(r)
    await db_session.commit()

    async with session_factory() as s2:
        stmt = select(Research).where(Research.theme == "Pesquisa Teste Fixture")
        res = await s2.execute(stmt)
        found = res.scalar_one_or_none()
        assert found is not None
        assert found.status == "SCRAPER"
        assert found.theme == "Pesquisa Teste Fixture"


def test_conftest_litellm_mock_fixtures(
    make_litellm_tool_call_response, make_litellm_final_response
):
    """
    T005: Valida mocks de LiteLLM function calling e resposta final em conftest.py.
    """
    from app.investigation.schemas import JinaSearchArgs, PersonaResultPayload

    # Mock de tool call jina_search
    tool_resp = make_litellm_tool_call_response("mercado de semicondutores")
    msg = tool_resp.choices[0].message
    assert msg.role == "assistant"
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    call = msg.tool_calls[0]
    assert call.function.name == "jina_search"
    args = JinaSearchArgs.model_validate_json(call.function.arguments)
    assert args.q == "mercado de semicondutores"

    # Mock de resposta final da persona
    final_resp = make_litellm_final_response(
        "Analise sintetizada sobre o setor com dados solidos.",
        ["https://example.com/fonte-1", "https://example.com/fonte-2"],
    )
    final_msg = final_resp.choices[0].message
    assert final_msg.tool_calls is None
    payload = PersonaResultPayload.model_validate_json(final_msg.content)
    assert payload.result == "Analise sintetizada sobre o setor com dados solidos."
    assert payload.used_urls == [
        "https://example.com/fonte-1",
        "https://example.com/fonte-2",
    ]



@pytest.mark.anyio
async def test_jina_ten_complete_bodies_keep_attribution(make_jina_mock_transport, sample_jina_items):
    """RF-501: dez corpos integrais, associados a título/URL/query; API real existente."""
    transport, recorded = make_jina_mock_transport()
    query = "consulta sintética com atribuição"
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        result = await JinaToolAdapter(api_key="synthetic-key", http_client=client).search(query)
    assert len(recorded) == 1
    assert result.urls == [item["url"] for item in sample_jina_items]
    assert len(sample_jina_items) == 10
    positions = []
    for i, item in enumerate(sample_jina_items):
        assert item["content"].index(f"END_BODY_{i}") > 100000
        assert item["content"] in result.content
        positions.append(result.content.index(item["content"]))
    for i, item in enumerate(sample_jina_items):
        start = 0 if i == 0 else positions[i - 1] + len(sample_jina_items[i - 1]["content"])
        end = len(result.content) if i == 9 else positions[i + 1]
        section = result.content[start:end]
        assert item["title"] in section
        assert item["url"] in section
    assert query in result.content


@pytest.mark.anyio
@pytest.mark.parametrize("shape", ["nested", "malformed"])
async def test_jina_html_cleaning_preserves_useful_body(shape, make_jina_mock_transport, sample_jina_items):
    useful_bodies = [item["content"] for item in sample_jina_items]
    for item in sample_jina_items:
        opening = "<article><div><p>" if shape == "nested" else "<article><p><b>"
        closing = "</p></div></article>" if shape == "nested" else "</article>"
        item["content"] = (
            "<header><div>HEADER_NOISE</div></header><nav><a>NAV_NOISE</a></nav>"
            "<script>SCRIPT_NOISE</script><style>STYLE_NOISE</style>"
            '<aside class="advertisement" aria-label="advertisement">AD_NOISE</aside>'
            + opening + item["content"] + " &amp; texto &lt;útil&gt;" + closing
            + "<footer><span>FOOTER_NOISE</span></footer>"
        )
    transport, recorded = make_jina_mock_transport(default_payload={"data": sample_jina_items})
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        result = await JinaToolAdapter(api_key="synthetic-key", http_client=client).search("limpeza")
    assert len(recorded) == 1
    for noise in ("HEADER_NOISE", "NAV_NOISE", "SCRIPT_NOISE", "STYLE_NOISE", "AD_NOISE", "FOOTER_NOISE"):
        assert noise not in result.content
    for useful in useful_bodies:
        assert useful in result.content
    assert "& texto <útil>" in result.content
    assert "<article>" not in result.content


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["nine", "missing-body", "inaccessible", "snippets-only"])
async def test_jina_incomplete_collection_fails_safe(case, make_jina_mock_transport, sample_jina_items, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    if case == "nine":
        sample_jina_items.pop()
    elif case == "missing-body":
        sample_jina_items[-1].pop("content")
    elif case == "inaccessible":
        sample_jina_items[-1]["content"] = ""
        sample_jina_items[-1]["status"] = 403
    else:
        for i, item in enumerate(sample_jina_items):
            item.pop("content")
            item["snippet"] = f"SNIPPET_ONLY_{i}"
    transport, recorded = make_jina_mock_transport(default_payload={"data": sample_jina_items})
    key = "synthetic-secret-incomplete"
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        try:
            with pytest.raises(JinaSearchError) as exc:
                await JinaToolAdapter(api_key=key, http_client=client).search("coleta incompleta")
        finally:
            print(f"REQUESTS incomplete/{case}={len(recorded)}")
            assert len(recorded) == 1
    assert key not in "".join(traceback.format_exception(exc.value))
    assert "example.com" not in str(exc.value)


@pytest.mark.anyio
@pytest.mark.parametrize("unsafe_url", [
    "file:///etc/passwd", "ftp://example.com/page", "http://127.0.0.1/private",
    "http://169.254.169.254/latest/meta-data", "http://[::1]/private",
    "http://10.0.0.1/private", "http://localhost/private", "https://user:password@example.com/page",
])
async def test_jina_unsafe_source_url_fails_safe(unsafe_url, make_jina_mock_transport, sample_jina_items, monkeypatch):
    """Rejeição local; MockTransport não prova resolução DNS/pinning de produto."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    sample_jina_items[-1]["url"] = unsafe_url
    transport, recorded = make_jina_mock_transport(default_payload={"data": sample_jina_items})
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        try:
            with pytest.raises(JinaSearchError) as exc:
                await JinaToolAdapter(api_key="synthetic-key", http_client=client).search("segurança")
        finally:
            print(f"REQUESTS unsafe-source={len(recorded)}")
            assert len(recorded) == 1
    assert unsafe_url not in str(exc.value)


def test_parse_body_does_not_promote_snippets_or_recursive_urls(sample_jina_items):
    for item in sample_jina_items:
        item.pop("content")
        item["metadata"] = {"url": "https://example.com/not-read"}
    with pytest.raises(JinaSearchError):
        _parse_body({"data": sample_jina_items})


def test_stdlib_parser_keeps_tail_beyond_input_slice():
    from app.services.search import _safe_html_to_text
    useful = "BEGIN_LONG " + "useful " * 31000 + " END_AFTER_200000"
    raw = "<article>" + useful + "</article>"
    assert useful.index("END_AFTER_200000") > 200000
    assert useful == _safe_html_to_text(raw, max_chars=len(raw))
