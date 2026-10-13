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
)


@pytest.mark.anyio
async def test_jina_search_success_direct_contract_and_payload(
    make_jina_mock_transport,
):
    """
    RN-05, RF-06: Sucesso na busca direta.
    Valida POST https://s.jina.ai/, payload {"q": query}, headers exigidos,
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
        assert sent_payload == {"q": query}

        assert req.headers.get("Accept") == "application/json"
        assert req.headers.get("X-Engine") == "direct"
        assert req.headers.get("Authorization") == "Bearer jina-secret-api-key-123"
        assert req.headers.get("Content-Type") == "application/json"

        # Conteúdo montado a partir de title, description, content
        assert "Primeiro Resultado de Teste" in result.content
        assert "Segundo Resultado de Teste" in result.content
        assert "Conteúdo integral do primeiro artigo" in result.content
        assert "Conteúdo factual com evidências" in result.content

        # URLs extraídas
        assert result.urls == [
            "https://example.com/artigo-1",
            "https://example.com/artigo-2",
        ]


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
        assert sent_payload == {"q": query}

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
    make_jina_mock_transport, monkeypatch
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
                    ]
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
        assert result.urls == ["https://example.com/recuperado"]

        # Delays default: 2.0s na primeira falha, 4.0s na segunda falha
        assert sleep_mock.await_count == 2
        assert sleep_mock.await_args_list[0].args[0] == 2.0
        assert sleep_mock.await_args_list[1].args[0] == 4.0


@pytest.mark.anyio
async def test_jina_search_retry_after_header_respected(
    make_jina_mock_transport, monkeypatch
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
                    ]
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
async def test_jina_search_recursive_url_extraction_and_deduplication(
    make_jina_mock_transport,
):
    """
    RN-08, RF-07: Extração recursiva de URLs nos campos data, url, link, href
    com deduplicação integral preservando ordem.
    """
    payload_complexo = {
        "code": 200,
        "status": 20000,
        "data": [
            {
                "title": "Documento Principal",
                "url": "https://example.com/artigo-principal",
                "description": "Resumo do documento",
                "content": "Texto com link",
                "metadata": {
                    "source": {
                        "link": "https://example.com/fonte-secundaria",
                        "href": "https://example.com/artigo-principal",  # duplicata
                    },
                    "referencias": [
                        {"url": "https://example.com/referencia-1"},
                        "https://example.com/artigo-direto-em-string",
                        "https://example.com/fonte-secundaria",  # duplicata
                        "ftp://protocolo-invalido.com",
                        "string-que-nao-e-url",
                        None,
                        123,
                    ],
                },
            }
        ],
        "links_adicionais": {
            "link": "https://example.com/rodape"
        },
    }

    transport, _ = make_jina_mock_transport(default_payload=payload_complexo)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = JinaToolAdapter(api_key="jina-key-test", http_client=client)
        result = await adapter.search("extração de fontes")

        expected_urls = [
            "https://example.com/artigo-principal",
            "https://example.com/fonte-secundaria",
            "https://example.com/referencia-1",
            "https://example.com/artigo-direto-em-string",
            "https://example.com/rodape",
        ]

        assert result.urls == expected_urls
        # Deduplicação verificada
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
    make_jina_mock_transport, monkeypatch
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
                    ]
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

