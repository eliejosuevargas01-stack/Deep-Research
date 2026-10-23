"""Testes unitários para LLMClient (OpenAI-Compatible).

Cobre inferências leve e forte via rota /v1/chat/completions, parsing JSON
estruturado, resiliência com 1+3 retries e configuração estrita sem fallbacks.
Atende a DT-11, RN-02 e RNF-11.
"""

import json
import pytest
from tests.mocks.http_mock import MockNetwork, create_mock_transport


@pytest.mark.asyncio
async def test_llm_missing_config_raises_explicit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica recusa explícita se API key ou modelo estiverem ausentes (RN-02)."""
    from app.tools.llm_client import LLMClient

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Configuração ausente|OPENAI_API_KEY"):
        LLMClient(api_key=None)


@pytest.mark.asyncio
async def test_llm_chat_completion_light_model() -> None:
    """Verifica inferência com modelo leve enviando parâmetros OpenAI-compatible."""
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    client = LLMClient(
        api_key="sk-test-mock-key",
        base_url="https://api.openai.com/v1",
        model_light="gpt-4o-mini",
        model_strong="gpt-4o",
        transport=transport,
    )

    messages = [{"role": "user", "content": "Formule os pontos da pesquisa"}]
    resposta = await client.generate_light(messages=messages)

    assert isinstance(resposta, str)
    assert len(mock_net.requests) == 1

    req_json = json.loads(mock_net.requests[0].content.decode("utf-8"))
    assert req_json["model"] == "gpt-4o-mini"
    assert req_json["messages"] == messages


@pytest.mark.asyncio
async def test_llm_chat_completion_strong_model() -> None:
    """Verifica inferência com modelo forte para raciocínio analítico denso."""
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    client = LLMClient(
        api_key="sk-test-mock-key",
        base_url="https://api.openai.com/v1",
        model_light="gpt-4o-mini",
        model_strong="gpt-4o",
        transport=transport,
    )

    messages = [{"role": "user", "content": "Audite criticamente o material com as 12 perguntas"}]
    resposta = await client.generate_strong(messages=messages)

    assert isinstance(resposta, str)
    req_json = json.loads(mock_net.requests[0].content.decode("utf-8"))
    assert req_json["model"] == "gpt-4o", "Deve utilizar o modelo forte configurado"


@pytest.mark.asyncio
async def test_llm_json_structured_output_parsing() -> None:
    """Verifica inferência com response_format={'type': 'json_object'} e parsing estruturado."""
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    client = LLMClient(
        api_key="sk-test-mock-key",
        base_url="https://api.openai.com/v1",
        model_light="gpt-4o-mini",
        model_strong="gpt-4o",
        transport=transport,
    )

    messages = [{"role": "user", "content": "planejador: gere 5 pontos em json"}]
    parsed_dict = await client.generate_json(model_type="light", messages=messages)

    assert isinstance(parsed_dict, dict)
    assert "pontos" in parsed_dict
    assert len(parsed_dict["pontos"]) == 5


@pytest.mark.asyncio
async def test_llm_retry_1_plus_3_on_rate_limit_429() -> None:
    """Verifica retries 1+3 automáticos em erro 429 Too Many Requests (DT-11, RNF-06)."""
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    mock_net.set_llm_status_sequence([429, 200])
    transport = create_mock_transport(mock_net)

    client = LLMClient(
        api_key="sk-test-mock-key",
        transport=transport,
    )

    resposta = await client.generate_light(messages=[{"role": "user", "content": "teste"}])
    assert isinstance(resposta, str)
    assert len(mock_net.requests) == 2


@pytest.mark.asyncio
async def test_llm_exhausted_retries_raises_exception() -> None:
    """Verifica lançamento de erro após 4 tentativas falhas (1 tentativa inicial + 3 retries)."""
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    mock_net.set_llm_status_sequence([500, 500, 500, 500])
    transport = create_mock_transport(mock_net)

    client = LLMClient(
        api_key="sk-test-mock-key",
        transport=transport,
    )

    with pytest.raises(Exception):
        await client.generate_light(messages=[{"role": "user", "content": "teste"}])

    assert len(mock_net.requests) == 4
