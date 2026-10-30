"""Testes de aceitação para o Envelope LLM e resiliência (DR-005, DR-013, DR-014).

Cobre:
- Envelopes concorrentes sem contaminação entre chamadas.
- Captura de usage e finish_reason autêntico (nunca finish_reason or 'stop').
- Identificação de fim ausente, length e chunks corrompidos no streaming.
- Falha imediata em HTTP 4xx (400, 401, 403) sem retries.
- Segregação de reasoning-only (nunca promovido a content).
- Higienização de mensagens para remoção de segredos.
- Cálculo de custos apenas para modelos conhecidos com tokens informados.
"""

import asyncio
import json
from typing import Any, Dict, List
import httpx
import pytest

from app.tools.errors import LLMCallError
from app.tools.llm_client import LLMClient
from app.tools.llm_types import (
    ModelPriceConfig,
    PricingRegistry,
    compute_prompt_hash,
    estimate_cost,
    redact_sensitive_string,
    sanitize_messages_for_audit,
)
from tests.mocks.http_mock import MockNetwork, create_mock_transport


@pytest.mark.asyncio
async def test_concurrent_envelopes_no_crosstalk() -> None:
    """Verifica isolamento estrito entre envelopes em chamadas concorrentes de personas (DR-005)."""
    mock_net = MockNetwork()
    personas = ["Historiador", "Visionario", "Cetico", "Futurista"]
    token_map = {
        "Historiador": 111,
        "Visionario": 222,
        "Cetico": 333,
        "Futurista": 444,
    }

    def persona_dispatch_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        messages = payload.get("messages", [])
        user_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content = m.get("content", "")
        # Determina a persona estritamente pela mensagem da request
        matched_persona = None
        for p in personas:
            if p in user_content:
                matched_persona = p
                break
        assert matched_persona is not None, f"Persona não identificada na requisição: {user_content}"
        token_count = token_map[matched_persona]
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-{matched_persona}",
                "model": payload.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Resposta da persona {matched_persona}",
                            "reasoning_content": f"Raciocínio da persona {matched_persona}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": token_count,
                    "completion_tokens": token_count * 2,
                    "total_tokens": token_count * 3,
                },
            },
        )

    # Handler único, concorrente e imutável baseado estritamente na request recebida
    mock_net.custom_handlers["chat/completions"] = persona_dispatch_handler

    client = LLMClient(
        api_key="sk-test-key",
        transport=httpx.MockTransport(lambda req: mock_net.handle_request(req)),
    )

    async def call_persona(name: str):
        envelope = await client.call_envelope(
            model=f"model-{name.lower()}",
            messages=[{"role": "user", "content": f"Investigação {name}"}],
        )
        return name, envelope

    results = await asyncio.gather(*(call_persona(p) for p in personas))

    # Valida isolamento exato de conteúdo, modelo e usage por persona
    for name, env in results:
        expected_tokens = token_map[name]
        assert env.model_requested == f"model-{name.lower()}"
        assert env.content_final == f"Resposta da persona {name}"
        assert env.reasoning_content == f"Raciocínio da persona {name}"
        assert env.finish_reason == "stop"
        assert env.is_regular_finish is True
        assert env.usage == {
            "prompt_tokens": expected_tokens,
            "completion_tokens": expected_tokens * 2,
            "total_tokens": expected_tokens * 3,
        }


@pytest.mark.asyncio
async def test_stream_usage_and_authentic_finish_reason() -> None:
    """Verifica que o envelope de streaming lê usage e preserva finish_reason real sem 'or stop'."""
    sse_lines = [
        'data: {"choices": [{"delta": {"role": "assistant", "content": "Primeira parte"}}]}\n\n',
        'data: {"choices": [{"delta": {"content": " e segunda parte"}}]}\n\n',
        'data: {"choices": [{"finish_reason": "length"}]}\n\n',
        'data: {"choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 150, "total_tokens": 200}}\n\n',
        'data: [DONE]\n\n',
    ]

    async def sse_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="".join(sse_lines),
            headers={"Content-Type": "text/event-stream"},
        )

    registry = PricingRegistry()
    registry.register(
        ModelPriceConfig(
            model_exact="gpt-4o-mini",
            prompt_price_per_token=0.00000015,
            completion_price_per_token=0.00000060,
        )
    )
    client = LLMClient(
        api_key="sk-test-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(sse_handler)),
        pricing_registry=registry,
    )

    # Força stream=True
    envelope = await client.call_envelope(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Teste stream"}],
        stream=True,
    )

    assert envelope.content_final == "Primeira parte e segunda parte"
    assert envelope.finish_reason == "length", "Deve capturar o finish_reason real 'length'"
    assert envelope.is_regular_finish is False, "finish_reason 'length' não pode certificar término regular"
    assert envelope.usage is not None
    assert envelope.usage.get("total_tokens") == 200
    assert envelope.cost_estimated is not None
    assert envelope.cost_estimated > 0.0


@pytest.mark.asyncio
async def test_stream_missing_finish_reason_leaves_it_none() -> None:
    """Verifica que stream finalizado sem finish_reason não fabrica 'stop' (DR-005)."""
    sse_lines = [
        'data: {"choices": [{"delta": {"role": "assistant", "content": "Texto incompleto"}}]}\n\n',
        'data: [DONE]\n\n',
    ]

    async def sse_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="".join(sse_lines),
            headers={"Content-Type": "text/event-stream"},
        )

    client = LLMClient(
        api_key="sk-test-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(sse_handler)),
    )

    envelope = await client.call_envelope(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Teste stream sem finish"}],
        stream=True,
    )

    assert envelope.content_final == "Texto incompleto"
    assert envelope.finish_reason is None, "Nunca deve fabricar 'stop' quando não informado"
    assert envelope.is_regular_finish is False, "Ausência de finish_reason impede certificação regular"


@pytest.mark.asyncio
async def test_stream_malformed_chunk_recorded_in_errors() -> None:
    """Verifica que erro de JSON em chunk SSE fica registrado no envelope e impede regularidade."""
    sse_lines = [
        'data: {"choices": [{"delta": {"content": "Trecho 1"}}]}\n\n',
        'data: {JSON QUEBRADO MALFORMADO\n\n',
        'data: {"choices": [{"finish_reason": "stop"}]}\n\n',
        'data: [DONE]\n\n',
    ]

    async def sse_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="".join(sse_lines),
            headers={"Content-Type": "text/event-stream"},
        )

    client = LLMClient(
        api_key="sk-test-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(sse_handler)),
    )

    envelope = await client.call_envelope(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Teste malformado"}],
        stream=True,
    )

    assert len(envelope.errors) > 0
    assert any(e.get("error_type") == "MalformedSSEChunk" for e in envelope.errors)
    assert envelope.is_regular_finish is False, "Stream com chunk corrompido não é regular"


@pytest.mark.asyncio
async def test_stream_error_chunk_invalidates_regular_finish() -> None:
    """Verifica que erro SSE em chunk, mesmo seguido por finish 'stop', invalida is_regular_finish (DR-005)."""
    sse_lines = [
        'data: {"choices": [{"delta": {"content": "Início da resposta"}}]}\n\n',
        'data: {"error": {"message": "Internal error occurred mid-stream", "code": 500}}\n\n',
        'data: {"choices": [{"finish_reason": "stop"}]}\n\n',
        'data: [DONE]\n\n',
    ]

    async def sse_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="".join(sse_lines),
            headers={"Content-Type": "text/event-stream"},
        )

    client = LLMClient(
        api_key="sk-test-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(sse_handler)),
    )

    envelope = await client.call_envelope(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Teste erro no stream"}],
        stream=True,
    )

    assert envelope.finish_reason == "stop"
    assert envelope.is_regular_finish is False, "Stream com chunk de erro SSE não pode ser certificado como regular"
    assert any(e.get("error_type") == "StreamErrorChunk" for e in envelope.errors)


@pytest.mark.asyncio
async def test_http_4xx_fails_immediately_without_retrying() -> None:
    """Verifica que erros HTTP 400, 401 e 403 lançam erro imediatamente sem gastar retries (DR-005, DR-013)."""
    call_count = 0

    def error_401_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    client = LLMClient(
        api_key="sk-invalid",
        transport=httpx.MockTransport(error_401_handler),
    )

    with pytest.raises(LLMCallError) as exc_info:
        await client.call_envelope(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Olá"}],
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.envelope is not None
    assert exc_info.value.envelope.attempts == 1
    assert exc_info.value.envelope.is_regular_finish is False
    assert call_count == 1, "Não deve realizar retries em erro 401"


@pytest.mark.asyncio
async def test_exhausted_retries_preserves_envelope_on_exception() -> None:
    """Verifica que quando retries são esgotados, a exceção preserva o envelope com histórico (DR-005, DR-013)."""
    call_count = 0

    def error_500_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, json={"error": {"message": f"Server crash attempt {call_count}"}})

    client = LLMClient(
        api_key="sk-test",
        transport=httpx.MockTransport(error_500_handler),
        min_backoff=0.001,
    )

    with pytest.raises(LLMCallError) as exc_info:
        await client.call_envelope(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Olá 500"}],
        )

    assert call_count == 4
    envelope = exc_info.value.envelope
    assert envelope is not None
    assert envelope.attempts == 4
    assert envelope.is_regular_finish is False
    assert len(envelope.errors) == 4
    assert envelope.downstream_router_mutations == "explicitly_unobserved"


@pytest.mark.asyncio
async def test_reasoning_only_never_promoted_to_content() -> None:
    """Garante que reasoning_content isolado nunca vira content_final nem resposta JSON (DR-001)."""
    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "Pensamento privado interno do modelo",
                    },
                    "finish_reason": "stop",
                }
            ]
        },
    )

    client = LLMClient(
        api_key="sk-test",
        transport=create_mock_transport(mock_net),
    )

    envelope = await client.call_envelope(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Pergunta teste"}],
    )
    assert envelope.content_final is None
    assert envelope.reasoning_content == "Pensamento privado interno do modelo"

    # 1. Projeção chat_completion deve retornar string vazia
    chat_resp = await client.chat_completion(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Pergunta teste"}],
    )
    assert chat_resp == ""
    assert "Pensamento privado" not in chat_resp

    # 2. generate_json deve rejeitar expressamente por falta de content
    with pytest.raises(ValueError, match="Modelo não emitiu conteúdo final"):
        await client.generate_json(
            model_type="strong",
            messages=[{"role": "user", "content": "Gere JSON"}],
        )


def test_sanitize_messages_removes_sensitive_secrets() -> None:
    """Verifica higienização de tokens, chaves e credenciais em URLs das mensagens enviadas."""
    messages = [
        {"role": "system", "content": "Instrução do sistema"},
        {
            "role": "user",
            "content": "Acesse com Authorization: Bearer secret_token_12345678 e sk-abcdef12345678901234567890",
        },
        {"role": "user", "api_key": "chave_secreta_super_privada"},
        {"role": "user", "url": "https://admin:senha123@api.provedor.com/v1/search"},
    ]

    client_key = "chave_secreta_super_privada"
    sanitized = sanitize_messages_for_audit(messages, client_api_key=client_key)
    sanitized_str = json.dumps(sanitized)

    assert "secret_token_12345678" not in sanitized_str
    assert "sk-abcdef12345678901234567890" not in sanitized_str
    assert "chave_secreta_super_privada" not in sanitized_str
    assert "senha123" not in sanitized_str
    assert "[REDACTED]" in sanitized_str
    assert "[REDACTED_API_KEY]" in sanitized_str or "[REDACTED]" in sanitized_str
    assert "[REDACTED_PASS]" in sanitized_str


def test_estimate_cost_only_for_known_models_with_tokens() -> None:
    """Verifica que custo só é calculado para modelos com tabela de preços operacional configurada (DR-013)."""
    # 1. Sem registro configurado (padrão): mesmo modelos conhecidos retornam None
    cost_default = estimate_cost("gpt-4o-mini", {"prompt_tokens": 1000, "completion_tokens": 2000})
    assert cost_default is None

    # 2. Com tabela sintética configurada explicitamente
    registry = PricingRegistry()
    registry.register(
        ModelPriceConfig(
            model_exact="gpt-4o-mini",
            prompt_price_per_token=0.00000015,
            completion_price_per_token=0.00000060,
            currency="USD",
            source="test_config",
        )
    )

    expected_cost = round(1000 * 0.00000015 + 2000 * 0.00000060, 8)
    cost = estimate_cost(
        "gpt-4o-mini",
        {"prompt_tokens": 1000, "completion_tokens": 2000},
        pricing_registry=registry,
    )
    assert cost == expected_cost

    # 3. Modelo não configurado no registro retorna None (sem alias presumido)
    cost_unknown = estimate_cost(
        "modelo-personalizado-local",
        {"prompt_tokens": 1000, "completion_tokens": 2000},
        pricing_registry=registry,
    )
    assert cost_unknown is None

    # 4. Modelo com tokens ausentes ou dicionário vazio retorna None
    cost_no_tokens = estimate_cost("gpt-4o-mini", {}, pricing_registry=registry)
    assert cost_no_tokens is None

    # 5. Valores inválidos na configuração de preços são rejeitados
    with pytest.raises(ValueError, match="Preço por token não pode ser negativo"):
        ModelPriceConfig(
            model_exact="modelo-teste",
            prompt_price_per_token=-0.01,
            completion_price_per_token=0.02,
        )

    with pytest.raises(ValueError, match="model_exact não pode ser vazio"):
        ModelPriceConfig(
            model_exact="",
            prompt_price_per_token=0.01,
            completion_price_per_token=0.02,
        )


@pytest.mark.asyncio
async def test_secrets_sanitization_diverse_formats_and_llm_call_error() -> None:
    """Verifica higienização de segredos em formatos diversos (sk-proj, AIza, headers, urls) e LLMCallError (F-07)."""
    synthetic_key = "sk-client-key-synthetic-12345"
    proj_key = "sk-proj-ABCDEFGHIJKLMNOPQRST12345"
    aiza_key = "AIzaSyD-1234567890abcdefghijklmnopqr"
    x_api_key = "secret_x_api_key_987654321"

    # Provedor responde 200 com payload contendo segredos no error message
    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: httpx.Response(
        200,
        json={
            "error": {
                "message": f"Chave inválida: {synthetic_key} e {proj_key} e {aiza_key} e x-api-key: {x_api_key}",
                "code": "invalid_api_key",
            }
        },
    )
    client = LLMClient(api_key=synthetic_key, transport=create_mock_transport(mock_net))

    with pytest.raises(LLMCallError) as exc_info:
        await client.call_envelope(model="gpt-4o", messages=[{"role": "user", "content": "Olá"}])

    err_str = str(exc_info.value)
    assert synthetic_key not in err_str
    assert proj_key not in err_str
    assert aiza_key not in err_str
    assert x_api_key not in err_str

    envelope = exc_info.value.envelope
    assert envelope is not None
    assert envelope.errors
    for err in envelope.errors:
        msg = err.get("message", "")
        assert synthetic_key not in msg
        assert proj_key not in msg
        assert aiza_key not in msg
        assert x_api_key not in msg


@pytest.mark.asyncio
async def test_retry_semantics_404_422_fail_immediately_429_retries() -> None:
    """Verifica que apenas 408/429/5xx são retentados; 404/422 falham na 1ª tentativa e capturam corpo de erro (F-08)."""
    # 1. HTTP 404 falha imediatamente (call_count == 1)
    call_count_404 = 0

    def handler_404(request: httpx.Request) -> httpx.Response:
        nonlocal call_count_404
        call_count_404 += 1
        return httpx.Response(404, text='{"error": {"message": "Endpoint ou modelo não encontrado"}}')

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = handler_404
    client = LLMClient(api_key="sk-test", transport=create_mock_transport(mock_net))

    with pytest.raises(LLMCallError) as exc_404:
        await client.call_envelope(model="gpt-4o", messages=[{"role": "user", "content": "Teste 404"}])

    assert call_count_404 == 1
    assert "Endpoint ou modelo não encontrado" in str(exc_404.value)
    assert exc_404.value.envelope.attempts == 1

    # 2. HTTP 422 falha imediatamente (call_count == 1)
    call_count_422 = 0

    def handler_422(request: httpx.Request) -> httpx.Response:
        nonlocal call_count_422
        call_count_422 += 1
        return httpx.Response(422, text='{"error": {"message": "Parâmetro inválido na requisição"}}')

    mock_net2 = MockNetwork()
    mock_net2.custom_handlers["chat/completions"] = handler_422
    client2 = LLMClient(api_key="sk-test", transport=create_mock_transport(mock_net2))

    with pytest.raises(LLMCallError) as exc_422:
        await client2.call_envelope(model="gpt-4o", messages=[{"role": "user", "content": "Teste 422"}])

    assert call_count_422 == 1
    assert "Parâmetro inválido" in str(exc_422.value)

    # 3. HTTP 429 seguido de 200 é retentado (call_count == 2)
    call_count_429 = 0

    def handler_429(request: httpx.Request) -> httpx.Response:
        nonlocal call_count_429
        call_count_429 += 1
        if call_count_429 == 1:
            return httpx.Response(429, text='{"error": {"message": "Rate limit atingido"}}')
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Sucesso após 429"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )

    mock_net3 = MockNetwork()
    mock_net3.custom_handlers["chat/completions"] = handler_429
    client3 = LLMClient(api_key="sk-test", transport=create_mock_transport(mock_net3))

    envelope_429 = await client3.call_envelope(model="gpt-4o", messages=[{"role": "user", "content": "Teste 429"}])
    assert call_count_429 == 2
    assert envelope_429.is_regular_finish is True
    assert envelope_429.content_final == "Sucesso após 429"
    assert len(envelope_429.errors) == 1
    assert envelope_429.errors[0]["status_code"] == 429


@pytest.mark.asyncio
async def test_stream_options_request_payload_and_metadata_provenance() -> None:
    """Verifica envio de stream_options.include_usage e registro de request_params e proveniência (F-09, F-10)."""
    last_request_body = None

    def capture_handler(request: httpx.Request) -> httpx.Response:
        nonlocal last_request_body
        last_request_body = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
            },
        )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = capture_handler
    client = LLMClient(api_key="sk-test", transport=create_mock_transport(mock_net))

    # Teste de parâmetros gravados no envelope e hash diferenciado por response_format
    env1 = await client.call_envelope(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Pergunta 1"}],
        response_format={"type": "json_object"},
        reasoning_effort="high",
    )
    assert env1.request_params.get("response_format") == {"type": "json_object"}
    assert env1.request_params.get("reasoning_effort") == "high"

    env2 = await client.call_envelope(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Pergunta 1"}],
        response_format=None,
        reasoning_effort="low",
    )
    # Mudar response_format ou reasoning_effort deve alterar o prompt_hash
    assert env1.prompt_hash != env2.prompt_hash


@pytest.mark.asyncio
async def test_sse_parsing_no_space_and_malformed_handling() -> None:
    """Verifica data: sem espaço, SSE error chunk e payload não-dict em modo sem stream (F-16)."""
    mock_net_arr = MockNetwork()
    mock_net_arr.custom_handlers["chat/completions"] = lambda r: httpx.Response(200, text="[]")
    client_arr = LLMClient(api_key="sk-test", transport=create_mock_transport(mock_net_arr))

    with pytest.raises(LLMCallError) as exc_arr:
        await client_arr.call_envelope(model="gpt-4o", messages=[{"role": "user", "content": "Array"}])
    assert exc_arr.value.envelope is not None
    assert exc_arr.value.envelope.is_regular_finish is False
    assert len(exc_arr.value.envelope.errors) > 0


def test_url_redaction_preserves_json_evidence_and_ledger_without_secrets() -> None:
    """[REPRODUÇÃO R4 - ITEM 1] JSON de evidências com URLs normais e e-mails não pode ser corrompido.
    
    Demonstra a falha da regex atual que atravessa JSON de uma URL comum até um e-mail posterior,
    eliminando campos, objetos e quebrando a integridade do ledger e dos textos.
    """
    # 1. Caso mínimo de 2 trechos (reprodução direta do search-redaction-url-proof.json)
    fixture_min = {
        "evidencias": [
            {
                "chunk_id": "chk_1",
                "url": "https://example.org/a",
                "texto": "Texto público normal.",
            },
            {
                "chunk_id": "chk_2",
                "url": "https://example.org/b",
                "texto": "Contato público: mantenedor@example.org",
            },
        ],
        "ledger": {
            "selected_chunk_ids": ["chk_1", "chk_2"],
        },
    }
    json_min = json.dumps(fixture_min, indent=2)
    redacted_min_str = redact_sensitive_string(json_min)

    parsed_min = json.loads(redacted_min_str)
    assert len(parsed_min["evidencias"]) == 2, (
        f"DEFEITO CONFIRMADO (R4): redact_sensitive_string corrompeu o JSON e reduziu de 2 para "
        f"{len(parsed_min['evidencias'])} evidências!"
    )
    assert parsed_min["evidencias"][0]["chunk_id"] == "chk_1"
    assert parsed_min["evidencias"][0]["texto"] == "Texto público normal."
    assert parsed_min["evidencias"][0]["url"] == "https://example.org/a"
    assert parsed_min["evidencias"][1]["chunk_id"] == "chk_2"
    assert parsed_min["evidencias"][1]["texto"] == "Contato público: mantenedor@example.org"
    assert parsed_min["ledger"]["selected_chunk_ids"] == ["chk_1", "chk_2"]
    assert redacted_min_str == json_min

    # 2. Caso com 16 entradas de evidências, URLs comuns, e-mails públicos e ledger com 16 IDs
    chunks_16 = []
    ledger_ids_16 = []
    for i in range(1, 17):
        cid = f"chk_{i:02d}"
        ledger_ids_16.append(cid)
        texto = f"Evidência documental e pública sobre o tópico {i}."
        if i % 3 == 0:
            texto += f" Para dúvidas consulte contato_{i}@example.org ou suporte@dominio-publico.gov.br."
        chunks_16.append({
            "chunk_id": cid,
            "url": f"https://example.org/docs/item_{i}",
            "texto": texto,
            "source_id": f"src_{(i % 4) + 1}",
        })

    fixture_16 = {
        "evidencias": chunks_16,
        "ledger": {
            "selected_chunk_ids": ledger_ids_16,
            "total_chunks": 16,
        },
    }
    json_16 = json.dumps(fixture_16, indent=2, ensure_ascii=False)
    redacted_16_str = redact_sensitive_string(json_16)

    # A redação sem segredos deve manter igualdade completa do JSON e todos os campos/textos/IDs
    assert redacted_16_str == json_16, (
        "DEFEITO CONFIRMADO (R4): JSON com 16 evidências foi alterado pela higienização sem segredos!"
    )
    parsed_16 = json.loads(redacted_16_str)
    assert parsed_16 == fixture_16
    assert len(parsed_16["evidencias"]) == 16
    assert [c["chunk_id"] for c in parsed_16["evidencias"]] == ledger_ids_16
    assert parsed_16["ledger"]["selected_chunk_ids"] == ledger_ids_16
    assert "[REDACTED" not in redacted_16_str


def test_url_redaction_normal_urls_and_synthetic_credentials() -> None:
    """[REPRODUÇÃO R4 - ITEM 2] URLs com porta, IPv6, dois-pontos e emails não são confundidas com credenciais.
    
    Garante que URLs normais com porta, IPv6, colons em path/query não acionam a redação,
    enquanto credenciais sintéticas autênticas user:password@host continuam devidamente redigidas.
    """
    # 1. URLs normais variadas acompanhadas de email público em outro campo ou no mesmo texto
    normal_cases = [
        # Porta e email em texto posterior
        (
            '{"url": "https://example.org:8080/api/v1", "email": "contato@example.org"}',
            "porta padrão",
        ),
        # Porta sem path
        (
            '{"url": "https://example.org:8443", "email": "suporte@empresa.com"}',
            "porta sem path",
        ),
        # IPv6
        (
            '{"url": "https://[2001:db8::1]:8080/status", "contato": "admin@example.org"}',
            "IPv6 com porta",
        ),
        (
            '{"url": "http://[::1]:8000/", "email": "dev@localhost.net"}',
            "IPv6 localhost",
        ),
        # Dois-pontos no path
        (
            '{"url": "https://example.org/wiki/Special:Search", "email": "user@wiki.org"}',
            "dois-pontos no path",
        ),
        (
            '{"url": "https://example.org:8080/path:with:colons", "author": "dev@domain.com"}',
            "porta e dois-pontos no path",
        ),
        # Dois-pontos na query
        (
            '{"url": "https://example.org/search?q=filter:recent&tag:news", "email": "news@example.org"}',
            "dois-pontos na query",
        ),
    ]

    for payload, desc in normal_cases:
        redacted = redact_sensitive_string(payload)
        assert "[REDACTED_USER]" not in redacted, f"Falso positivo de redação em {desc}: {redacted}"
        assert "[REDACTED_PASS]" not in redacted, f"Falso positivo de redação em {desc}: {redacted}"
        assert redacted == payload, f"Payload normal alterado indevidamente ({desc}): {redacted}"

    # 2. Credenciais sintéticas autênticas user:password@host DEVEM continuar redigidas
    cred_cases = [
        (
            "https://synthetic_user:synth_secret_pass123@api.internal.org/data",
            "https://[REDACTED_USER]:[REDACTED_PASS]@api.internal.org/data",
        ),
        (
            "http://db_admin:super_secret_passwd@db.internal.net:5432/query",
            "http://[REDACTED_USER]:[REDACTED_PASS]@db.internal.net:5432/query",
        ),
        (
            "https://alice:topsecret_pass@[2001:db8::1]:8080/secure",
            "https://[REDACTED_USER]:[REDACTED_PASS]@[2001:db8::1]:8080/secure",
        ),
    ]

    for raw, expected in cred_cases:
        redacted = redact_sensitive_string(raw)
        assert redacted == expected, f"Falha na redação de credencial sintética: esperava {expected}, obteve {redacted}"
        assert "secret" not in redacted

    # 3. Mensagens serializadas em JSON contendo credenciais sintéticas e emails públicos legítimos
    msg_dict = {
        "role": "user",
        "url_com_segredo": "https://service_bot:token_pass_999@auth.provedor.com/oauth/token",
        "texto_com_email": "Para suporte acesse a URL acima ou contate sac@provedor.com.",
    }
    msg_json = json.dumps(msg_dict)
    redacted_json = redact_sensitive_string(msg_json)
    assert "token_pass_999" not in redacted_json
    assert "service_bot" not in redacted_json
    assert "https://[REDACTED_USER]:[REDACTED_PASS]@auth.provedor.com/oauth/token" in redacted_json
    assert "sac@provedor.com" in redacted_json
    parsed_msg = json.loads(redacted_json)
    assert parsed_msg["url_com_segredo"] == "https://[REDACTED_USER]:[REDACTED_PASS]@auth.provedor.com/oauth/token"
    assert "sac@provedor.com" in parsed_msg["texto_com_email"]


@pytest.mark.asyncio
async def test_llm_client_real_path_mock_transport_preserves_messages_sent_and_redacts_credentials() -> None:
    """[REPRODUÇÃO R4 - ITEM 3] Caminho real do LLMClient com MockTransport preserva messages_sent sem segredos.
    
    Verifica que:
    1. Quando não há segredos: payload enviado pela rede é capturado pelo MockTransport e
       messages_sent no envelope é estritamente igual, preservando todos os 16 trechos e ledger,
       mantendo prompt_hash e métricas íntegros.
    2. Quando há credenciais sintéticas: o payload de rede recebe as mensagens brutas,
       enquanto messages_sent no envelope higieniza user:pass@host sem enfraquecer o histórico.
    """
    captured_requests: List[httpx.Request] = []

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test-r4",
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Conclusão consolidada com base em 16 evidências documentais.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1250,
                    "completion_tokens": 85,
                    "total_tokens": 1335,
                },
            },
        )

    client = LLMClient(
        api_key="sk-test-client-key-12345",
        transport=httpx.MockTransport(mock_transport_handler),
    )

    # 1. Caso sem segredos: 16 evidências com URLs normais e e-mails públicos no texto
    evidence_items = []
    chunk_ids = []
    for i in range(1, 17):
        cid = f"chk_{i:02d}"
        chunk_ids.append(cid)
        evidence_items.append({
            "chunk_id": cid,
            "url": f"https://example.org/articles/doc_{i}",
            "texto": f"Trecho público documental {i}. Contato para revisão: mantenedor_{i}@example.org",
        })

    content_payload = json.dumps({
        "evidencias": evidence_items,
        "ledger": {
            "selected_chunk_ids": chunk_ids,
            "total_chunks": 16,
        },
    }, indent=2, ensure_ascii=False)

    messages = [
        {"role": "system", "content": "Você é um pesquisador imparcial."},
        {"role": "user", "content": content_payload},
    ]

    envelope = await client.call_envelope(
        model="gpt-4o",
        messages=messages,
    )

    # Valida captura do payload real enviado pela rede
    assert len(captured_requests) == 1
    sent_wire_body = json.loads(captured_requests[0].content.decode("utf-8"))
    sent_wire_messages = sent_wire_body["messages"]

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL R4):
    # O código atual sanitiza messages_sent via sanitize_messages_for_audit.
    # Como a regex corrompe o JSON do user content de 16 evidências para 5 evidências,
    # envelope.messages_sent NÃO é igual a sent_wire_messages!
    assert envelope.messages_sent == sent_wire_messages, (
        "DEFEITO CONFIRMADO (R4): envelope.messages_sent divergiu do payload de rede "
        "mesmo sem conter qualquer segredo!"
    )
    assert envelope.messages_sent == messages

    # Valida preservação completa dos 16 trechos e IDs no messages_sent do envelope
    user_sent_str = envelope.messages_sent[1]["content"]
    parsed_user_sent = json.loads(user_sent_str)
    assert len(parsed_user_sent["evidencias"]) == 16, (
        f"DEFEITO CONFIRMADO (R4): envelope.messages_sent reteve apenas "
        f"{len(parsed_user_sent['evidencias'])} de 16 evidências!"
    )
    assert [c["chunk_id"] for c in parsed_user_sent["evidencias"]] == chunk_ids
    assert parsed_user_sent["ledger"]["selected_chunk_ids"] == chunk_ids

    # Valida integridade do prompt_hash e das métricas
    assert envelope.prompt_hash != ""
    assert envelope.finish_reason == "stop"
    assert envelope.is_regular_finish is True
    assert envelope.usage == {
        "prompt_tokens": 1250,
        "completion_tokens": 85,
        "total_tokens": 1335,
    }

    # 2. Caso com credenciais sintéticas: rede envia dados brutos, envelope redige no histórico
    cred_messages = [
        {"role": "system", "content": "Sistema seguro."},
        {
            "role": "user",
            "content": "Acesse https://my_user:secret_pass_xyz@internal.corp/resource e consulte equipe@corp.com",
        },
    ]
    env_cred = await client.call_envelope(
        model="gpt-4o",
        messages=cred_messages,
    )
    assert len(captured_requests) == 2
    wire_cred_body = json.loads(captured_requests[1].content.decode("utf-8"))
    # Rede enviou dados brutos normalmente
    assert "secret_pass_xyz" in wire_cred_body["messages"][1]["content"]

    # messages_sent redigiu as credenciais mas preservou o email legítimo
    sanitized_user_msg = env_cred.messages_sent[1]["content"]
    assert "secret_pass_xyz" not in sanitized_user_msg
    assert "my_user" not in sanitized_user_msg
    assert "https://[REDACTED_USER]:[REDACTED_PASS]@internal.corp/resource" in sanitized_user_msg
    assert "equipe@corp.com" in sanitized_user_msg

