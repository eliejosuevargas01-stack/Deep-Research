# -*- coding: utf-8 -*-
"""Regressao: Jina responde {"code":401,"data":null} e o cliente nao pode estourar.

Cobre o defeito em que data.get("data", []) devolvia None quando a chave existe
com valor null, transformando erro de autenticacao legivel em 500 opaco.

Substituicao consciente de contrato (feature 004): a resposta HTTP 200 com
corpo {"code":401,"data":null} DEIXOU de ser tratada como resultado vazio
legitimo e passa a levantar JinaError categorizada. O teste antigo afirmava
`resultado == []`, ou seja, codificava a falha silenciosa. Ver regression-watch.md.
"""
import httpx
import pytest

from app.tools.errors import JinaError
from app.tools.jina_client import JinaClient


def _client(handler):
    return JinaClient(
        api_key="chave-de-teste",
        transport=httpx.MockTransport(handler),
        min_backoff=0.0,
    )


@pytest.mark.asyncio
async def test_search_com_code_401_em_http_200_levanta_jina_error():
    """HTTP 200 + {"code":401,"data":null} e falha, nao resultado vazio."""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 401, "data": None})

    client = _client(handler)
    try:
        with pytest.raises(JinaError) as exc:
            await client.search(query="tema de teste")
        assert exc.value.categoria == "autenticacao"
        assert exc.value.terminal is True
        assert "401" in str(exc.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_search_sem_chave_data_devolve_lista_vazia():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "sem resultados"})

    client = _client(handler)
    try:
        resultado = await client.search(query="tema de teste")
        assert resultado == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_search_com_resultados_validos_mantem_sanitizacao():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"title": "Titulo", "url": "https://exemplo.com/a", "description": "Resumo"},
        ]})

    client = _client(handler)
    try:
        resultado = await client.search(query="tema de teste")
        assert resultado == [
            {"title": "Titulo", "url": "https://exemplo.com/a", "description": "Resumo"},
        ]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_search_com_item_nao_dict_e_ignorado():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": ["lixo", {"title": "T", "url": "U"}]})

    client = _client(handler)
    try:
        resultado = await client.search(query="tema de teste")
        assert resultado == [{"title": "T", "url": "U", "description": ""}]
    finally:
        await client.aclose()
