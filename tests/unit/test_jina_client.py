"""Testes unitários para JinaClient (Jina SERP e Jina Reader).

Cobre isolamento de metadados na SERP (proibido download de corpo), raspagem
integral sem truncamento via Reader e política de 1+3 retentativas com backoff.
Atende a DT-06, DT-11, RN-03, RN-05 e RNF-06.
"""

import pytest
from tests.mocks.http_mock import MockNetwork, create_mock_transport


@pytest.mark.asyncio
async def test_jina_serp_metadata_isolation() -> None:
    """Verifica consulta restrita a metadados da SERP na etapa de planejamento (RN-03, DT-06)."""
    from app.tools.jina_client import JinaClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    client = JinaClient(api_key="jina-test-key", transport=transport)
    resultados = await client.search("Impacto da IA na Educação")

    assert len(resultados) > 0
    primeiro = resultados[0]

    # Metadados obrigatórios presentes
    assert "title" in primeiro
    assert "url" in primeiro
    assert "description" in primeiro

    # Vedado download ou presença de corpo de página completo na SERP (RN-03)
    assert "conteudo_integral" not in primeiro
    assert "body_html" not in primeiro
    assert "markdown_body" not in primeiro

    # Verifica headers da requisição disparada
    req = mock_net.requests[0]
    assert req.headers.get("Accept") == "application/json"
    assert req.headers.get("X-Retain-Images") == "none"


@pytest.mark.asyncio
async def test_jina_reader_integral_markdown_scrape() -> None:
    """Verifica raspagem completa via Jina Reader sem truncamento sintático (RN-05)."""
    from app.tools.jina_client import JinaClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    client = JinaClient(api_key="jina-test-key", transport=transport)
    target_url = "https://unesdoc.unesco.org/ark:/48223/pf0000377897"
    conteudo_md = await client.read(target_url)

    assert isinstance(conteudo_md, str)
    assert len(conteudo_md) > 50
    assert "Conteúdo Web Integral Coletado" in conteudo_md

    req = mock_net.requests[0]
    assert req.headers.get("Accept") == "text/markdown" or "text/markdown" in req.headers.get("Accept", "")


@pytest.mark.asyncio
async def test_jina_retry_1_plus_3_on_429() -> None:
    """Verifica resiliência com retries 1+3 em resposta 429 Too Many Requests (DT-11, RNF-06)."""
    from app.tools.jina_client import JinaClient

    mock_net = MockNetwork()
    # Simula 429 nas duas primeiras tentativas e sucesso na terceira
    mock_net.set_jina_status_sequence([429, 429, 200])
    transport = create_mock_transport(mock_net)

    client = JinaClient(api_key="jina-test-key", transport=transport)
    resultados = await client.search("Consulta com retry")

    assert len(resultados) > 0
    assert len(mock_net.requests) == 3


@pytest.mark.asyncio
async def test_jina_retry_exhausted_on_5xx_raises_error() -> None:
    """Verifica que 4 falhas consecutivas (1 inicial + 3 retries) levantam erro de indisponibilidade."""
    from app.tools.jina_client import JinaClient

    mock_net = MockNetwork()
    # Simula 502 contínuo por 4 tentativas
    mock_net.set_jina_status_sequence([502, 502, 502, 502])
    transport = create_mock_transport(mock_net)

    client = JinaClient(api_key="jina-test-key", transport=transport)

    with pytest.raises(Exception):  # Exception de gateway ou retry esgotado
        await client.search("Consulta que vai falhar")

    assert len(mock_net.requests) == 4  # 1 inicial + 3 retries


@pytest.mark.asyncio
async def test_jina_402_e_terminal_sem_retry() -> None:
    """RF-01/CA-01.1, RF-02/CA-02.1: 402 levanta JinaError billing com 1 só chamada."""
    import httpx

    from app.tools.errors import JinaError
    from app.tools.jina_client import JinaClient

    chamadas = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(402, json={
            "code": 402,
            "message": "Account balance not enough to run this query, please recharge.",
        })

    client = JinaClient(
        api_key="chave-de-teste",
        transport=httpx.MockTransport(handler),
        min_backoff=0.0,
    )
    try:
        with pytest.raises(JinaError) as exc:
            await client.search("consulta com saldo insuficiente")
    finally:
        await client.aclose()

    assert exc.value.categoria == "billing"
    assert exc.value.terminal is True
    assert "saldo" in exc.value.acao_corretiva.lower()
    # CA-01.6: nunca expõe a chave
    assert "chave-de-teste" not in str(exc.value)
    assert chamadas == 1  # CA-02.1: terminal, sem retry


@pytest.mark.asyncio
async def test_jina_401_sem_retry_no_reader() -> None:
    """RF-01/DÚVIDA-01: o Reader tem o mesmo defeito de classe e agora também classifica."""
    import httpx

    from app.tools.errors import JinaError
    from app.tools.jina_client import JinaClient

    chamadas = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(401, text="unauthorized")

    client = JinaClient(
        api_key="chave-de-teste",
        transport=httpx.MockTransport(handler),
        min_backoff=0.0,
    )
    try:
        with pytest.raises(JinaError) as exc:
            await client.read("https://exemplo.com/pagina")
    finally:
        await client.aclose()

    assert exc.value.categoria == "autenticacao"
    assert chamadas == 1


@pytest.mark.asyncio
async def test_jina_missing_api_key_or_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica recusa com erro explícito se chaves ou URLs forem nulas (RN-02)."""
    from app.tools.jina_client import JinaClient

    monkeypatch.delenv("Jina_API_KEY", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    with pytest.raises(ValueError):
        JinaClient(api_key=None)
