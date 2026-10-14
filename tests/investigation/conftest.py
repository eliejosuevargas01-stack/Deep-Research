"""Fixtures para os testes de investigação (T005, RN-05/RN-07/RN-08)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Callable, Sequence

import httpx
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.models.domain_models import Base


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --- Banco de Dados SQLite em Memória ---


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine SQLite assíncrono em memória (:memory:) isolado."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(sqlite_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Factory de sessões assíncronas limpa vinculada ao SQLite em memória."""
    return async_sessionmaker(sqlite_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Sessão assíncrona limpa com rollback/fechamento automático por teste."""
    async with session_factory() as session:
        yield session


# --- Fixtures Jina Search (MockTransport) ---


@pytest.fixture
def sample_jina_items() -> list[dict[str, Any]]:
    """Itens simulados com title, url, description, content."""
    return [
        {
            "title": "Primeiro Resultado de Teste",
            "url": "https://example.com/artigo-1",
            "description": "Descrição do primeiro artigo relevante.",
            "content": "Conteúdo integral do primeiro artigo retornado pela Jina.",
        },
        {
            "title": "Segundo Resultado de Teste",
            "url": "https://example.com/artigo-2",
            "description": "Descrição analítica do segundo artigo.",
            "content": "Conteúdo factual com evidências do segundo artigo retornado.",
        },
    ]


@pytest.fixture
def sample_jina_response_payload(
    sample_jina_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Corpo de resposta JSON simulado da Jina contendo chave data."""
    return {
        "code": 200,
        "status": 20000,
        "data": sample_jina_items,
    }


@pytest.fixture
def make_jina_mock_transport(
    sample_jina_response_payload: dict[str, Any],
) -> Callable[..., tuple[httpx.MockTransport, list[httpx.Request]]]:
    """
    Fábrica de MockTransport com rastreamento das requisições disparadas.
    Permite injetar fila de respostas (para simular retries 429 -> 200, etc.)
    ou resposta única com status e headers customizados.
    """
    def _factory(
        responses: Sequence[Any] | None = None,
        default_payload: dict[str, Any] | None = None,
        default_status: int = 200,
        default_headers: dict[str, str] | None = None,
    ) -> tuple[httpx.MockTransport, list[httpx.Request]]:
        recorded: list[httpx.Request] = []
        queue = list(responses) if responses is not None else None

        def _handler(request: httpx.Request) -> httpx.Response:
            recorded.append(request)
            if queue is not None:
                if not queue:
                    raise RuntimeError("Fila de respostas do MockTransport esgotada")
                item = queue.pop(0)
                if isinstance(item, Exception):
                    raise item
                if isinstance(item, httpx.Response):
                    return item
                if callable(item):
                    res = item(request)
                    if isinstance(res, httpx.Response):
                        return res
                    return httpx.Response(200, json=res)
                if isinstance(item, dict):
                    return httpx.Response(200, json=item)
            payload = (
                default_payload
                if default_payload is not None
                else sample_jina_response_payload
            )
            return httpx.Response(
                default_status,
                json=payload,
                headers=default_headers,
            )

        transport = httpx.MockTransport(_handler)
        return transport, recorded

    return _factory


@pytest.fixture
def jina_mock_transport(
    make_jina_mock_transport: Callable[..., tuple[httpx.MockTransport, list[httpx.Request]]],
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """MockTransport padrão com resposta 200 e payload da Jina."""
    return make_jina_mock_transport()


@pytest.fixture
def jina_async_client(
    jina_mock_transport: tuple[httpx.MockTransport, list[httpx.Request]],
) -> httpx.AsyncClient:
    """AsyncClient com transporte mock configurado para a Jina."""
    transport, _ = jina_mock_transport
    return httpx.AsyncClient(transport=transport)


# --- Mocks LiteLLM Function Calling (T005) ---


@pytest.fixture
def make_litellm_tool_call_response() -> Callable[[str, str], Any]:
    """Gera resposta simulada do LiteLLM emitindo tool call 'jina_search'."""
    def _factory(query: str, call_id: str = "call_jina_1") -> Any:
        function_call = SimpleNamespace(
            name="jina_search",
            arguments=json.dumps({"q": query}),
        )
        tool_call = SimpleNamespace(
            id=call_id,
            type="function",
            function=function_call,
        )
        message = SimpleNamespace(
            role="assistant",
            content=None,
            tool_calls=[tool_call],
        )
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    return _factory


@pytest.fixture
def make_litellm_final_response() -> Callable[[str, list[str], bool], Any]:
    """Gera resposta simulada do LiteLLM entregando JSON final da persona."""
    def _factory(result_text: str, used_urls: list[str], is_raw: bool = False) -> Any:
        if is_raw:
            payload = result_text
        else:
            payload = json.dumps({"result": result_text, "used_urls": used_urls})
        message = SimpleNamespace(
            role="assistant",
            content=payload,
            tool_calls=None,
        )
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    return _factory
