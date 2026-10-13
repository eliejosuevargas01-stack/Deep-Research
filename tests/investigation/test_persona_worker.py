"""Testes unitários do PersonaWorker (T007, RN-06/RN-07/RN-10/RN-13/RN-14)."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.investigation.llm_binding import LLMCallError
from app.investigation.tools import (
    JinaSearchError,
    JinaSearchResult,
    JinaToolAdapter,
)
from app.investigation.worker import (
    _CEILING_MSG,
    _CORRECTION_MSG,
    PersonaWorker,
    _sanitize_error,
)


@pytest.mark.anyio
async def test_worker_voluntary_early_stop(
    make_litellm_tool_call_response,
    make_litellm_final_response,
    monkeypatch,
):
    """
    RN-06, RF-05: Parada antecipada voluntária.
    Modelo realiza 1 busca, recebe evidências, encerra voluntariamente entregando JSON final.
    Valida success=True, used_urls populado, read_urls com todas as URLs e sem buscas extras.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)
    mock_adapter.search.return_value = JinaSearchResult(
        content="Evidência histórica relevante sobre agentes cognitivos.",
        urls=["https://example.com/artigo-historico", "https://example.com/fonte-2"],
    )

    llm_mock = AsyncMock(
        side_effect=[
            make_litellm_tool_call_response("agentes cognitivos historia"),
            make_litellm_final_response(
                "Síntese analítica consistente da persona.",
                ["https://example.com/artigo-historico"],
            ),
        ]
    )
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    res_id = uuid4()
    step_id = uuid4()

    result = await worker.execute(
        research_id=res_id,
        step_id=step_id,
        step_title="Evolução histórica de agentes autônomos",
        persona="historian",
    )

    assert result.success is True
    assert result.result == "Síntese analítica consistente da persona."
    assert result.used_urls == ["https://example.com/artigo-historico"]
    assert result.read_urls == [
        "https://example.com/artigo-historico",
        "https://example.com/fonte-2",
    ]
    assert result.error is None
    assert mock_adapter.search.await_count == 1
    mock_adapter.search.assert_awaited_once_with("agentes cognitivos historia")
    assert llm_mock.await_count == 2


@pytest.mark.anyio
async def test_worker_strict_search_ceiling_blocks_fourth_search(
    make_litellm_tool_call_response,
    make_litellm_final_response,
    monkeypatch,
):
    """
    RN-06, RF-05: Teto rígido de 3 buscas.
    Modelo tenta emitir 4 buscas consecutivas. A 4ª busca não é executada na Jina,
    o harness adiciona a mensagem de aviso do teto e exige JSON final.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)
    mock_adapter.search.side_effect = [
        JinaSearchResult(content="Resultado 1", urls=["https://ex.com/1"]),
        JinaSearchResult(content="Resultado 2", urls=["https://ex.com/2"]),
        JinaSearchResult(content="Resultado 3", urls=["https://ex.com/3"]),
    ]

    llm_mock = AsyncMock(
        side_effect=[
            make_litellm_tool_call_response("busca 1", call_id="c1"),
            make_litellm_tool_call_response("busca 2", call_id="c2"),
            make_litellm_tool_call_response("busca 3", call_id="c3"),
            make_litellm_tool_call_response("busca 4 que deve ser barrada", call_id="c4"),
            make_litellm_final_response(
                "Análise final forçada pelo teto.",
                ["https://ex.com/1", "https://ex.com/3"],
            ),
        ]
    )
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    res_id = uuid4()
    step_id = uuid4()

    result = await worker.execute(
        research_id=res_id,
        step_id=step_id,
        step_title="Análise de viabilidade técnica",
        persona="pragmatist",
    )

    assert result.success is True
    assert result.result == "Análise final forçada pelo teto."
    assert result.used_urls == ["https://ex.com/1", "https://ex.com/3"]
    assert result.read_urls == [
        "https://ex.com/1",
        "https://ex.com/2",
        "https://ex.com/3",
    ]
    assert result.error is None

    # Jina adapter executado exatamente 3 vezes (4a busca bloqueada)
    assert mock_adapter.search.await_count == 3
    assert mock_adapter.search.await_args_list[0].args[0] == "busca 1"
    assert mock_adapter.search.await_args_list[1].args[0] == "busca 2"
    assert mock_adapter.search.await_args_list[2].args[0] == "busca 3"

    # Valida que na 5a chamada ao LLM a mensagem de teto atingido foi repassada
    fifth_call_messages = llm_mock.await_args_list[4].kwargs["messages"]
    tool_ceiling_messages = [
        m for m in fifth_call_messages if m.get("role") == "tool" and m.get("tool_call_id") == "c4"
    ]
    assert len(tool_ceiling_messages) == 1
    assert tool_ceiling_messages[0]["content"] == _CEILING_MSG


@pytest.mark.anyio
async def test_worker_technical_retry_does_not_consume_search_quota(
    make_jina_mock_transport,
    make_litellm_tool_call_response,
    make_litellm_final_response,
    monkeypatch,
):
    """
    RN-06: Repetição técnica de busca não consome cota.
    Falha transitória na Jina dispara retry interno do adapter.
    O consumo de cota perante o modelo conta apenas 1 busca, permitindo
    que o modelo realize suas 3 buscas completas se desejar.
    """
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    # 1a busca sofre 500 transitório e recupera na 2a tentativa HTTP.
    # 2a e 3a buscas respondem 200 de imediato.
    transport, recorded = make_jina_mock_transport(
        responses=[
            httpx.Response(500, headers={"Content-Type": "application/json"}),
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "Recuperado após 500",
                            "url": "https://ex.com/recuperado",
                            "content": "Conteúdo 1",
                        }
                    ]
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "Busca 2 OK",
                            "url": "https://ex.com/busca2",
                            "content": "Conteúdo 2",
                        }
                    ]
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "title": "Busca 3 OK",
                            "url": "https://ex.com/busca3",
                            "content": "Conteúdo 3",
                        }
                    ]
                },
            ),
        ]
    )

    llm_mock = AsyncMock(
        side_effect=[
            make_litellm_tool_call_response("busca com retry", call_id="c1"),
            make_litellm_tool_call_response("busca normal dois", call_id="c2"),
            make_litellm_tool_call_response("busca normal tres", call_id="c3"),
            make_litellm_final_response(
                "Análise final com 3 buscas legítimas executadas.",
                ["https://ex.com/recuperado", "https://ex.com/busca3"],
            ),
        ]
    )
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    async with httpx.AsyncClient(transport=transport) as http_client:
        adapter = JinaToolAdapter(api_key="jina-test-key", http_client=http_client)
        worker = PersonaWorker(jina_adapter=adapter)

        result = await worker.execute(
            research_id=uuid4(),
            step_id=uuid4(),
            step_title="Robustez e falhas transitórias",
            persona="skeptic",
        )

        assert result.success is True
        assert result.result == "Análise final com 3 buscas legítimas executadas."
        # HTTP client registrou 4 requisições (1 falha + 1 retry + 2 buscas seguintes)
        assert len(recorded) == 4
        # Perante o modelo, todas as 3 buscas foram atendidas com sucesso
        assert result.read_urls == [
            "https://ex.com/recuperado",
            "https://ex.com/busca2",
            "https://ex.com/busca3",
        ]


@pytest.mark.anyio
async def test_worker_json_autocorrection_recovers_from_plain_text(
    make_litellm_final_response,
    monkeypatch,
):
    """
    RN-13, RF-08: Autocorreção de JSON (sucesso).
    Modelo responde inicialmente com texto puro sem JSON. O harness detecta,
    envia instrução de correção e o modelo corrige formatando JSON válido.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)

    # Turno 1: texto puro sem JSON
    msg_raw = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content="Esta é uma análise pura em prosa sem qualquer JSON.",
                    tool_calls=None,
                )
            )
        ]
    )
    # Turno 2: modelo corrige com JSON em markdown
    msg_fixed = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=(
                        "```json\n"
                        '{"result": "Síntese corrigida com sucesso.", "used_urls": ["https://ex.com/doc"]}\n'
                        "```"
                    ),
                    tool_calls=None,
                )
            )
        ]
    )

    llm_mock = AsyncMock(side_effect=[msg_raw, msg_fixed])
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Análise de viabilidade",
        persona="futurist",
    )

    assert result.success is True
    assert result.result == "Síntese corrigida com sucesso."
    assert result.used_urls == ["https://ex.com/doc"]
    assert result.error is None
    assert llm_mock.await_count == 2

    # Verifica se a mensagem de correção foi injetada no segundo envio
    second_call_messages = llm_mock.await_args_list[1].kwargs["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"] == _CORRECTION_MSG


@pytest.mark.anyio
async def test_worker_json_autocorrection_recovers_from_schema_validation_error(
    make_litellm_final_response,
    monkeypatch,
):
    """
    RN-13, RF-08: Autocorreção de JSON (schema inválido).
    Modelo retorna JSON válido mas com formato incorreto (sem a chave 'result').
    O harness detecta a falha de schema e pede correção.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)

    msg_invalid_schema = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=json.dumps({"resumo": "faltando campo result", "used_urls": []}),
                    tool_calls=None,
                )
            )
        ]
    )
    msg_valid = make_litellm_final_response("Resultado correto", ["https://ex.com/valido"])

    llm_mock = AsyncMock(side_effect=[msg_invalid_schema, msg_valid])
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Investigação de premissas",
        persona="skeptic",
    )

    assert result.success is True
    assert result.result == "Resultado correto"
    assert result.used_urls == ["https://ex.com/valido"]
    assert llm_mock.await_count == 2


@pytest.mark.anyio
async def test_worker_json_autocorrection_exhausts_three_attempts_and_fails(
    monkeypatch,
):
    """
    RN-13, RF-08: Autocorreção de JSON (esgotamento de tentativas).
    Modelo falha sucessivamente em 4 turnos (resposta inicial + 3 correções pedidas).
    Worker encerra com success=False e mensagem de erro registrada.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)

    def _make_invalid_msg(txt: str):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        role="assistant",
                        content=txt,
                        tool_calls=None,
                    )
                )
            ]
        )

    llm_mock = AsyncMock(
        side_effect=[
            _make_invalid_msg("resposta 1 sem json"),
            _make_invalid_msg("resposta 2 ainda sem json"),
            _make_invalid_msg("resposta 3 ainda texto livre"),
            _make_invalid_msg("resposta 4 falhou novamente"),
        ]
    )
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Análise com erro de formatação",
        persona="skeptic",
    )

    assert result.success is False
    assert result.result == "Invalid JSON response after 3 corrections"
    assert result.error == "Invalid JSON response after 3 corrections"
    assert result.used_urls == []
    # 1 resposta inicial + 3 correções pedidas = 4 chamadas ao LLM
    assert llm_mock.await_count == 4


@pytest.mark.anyio
async def test_worker_global_timeout_handling(monkeypatch):
    """
    RN-07: Timeout global de 600s.
    Simula estouro de timeout global: worker captura a exceção,
    encerra com success=False e mensagem sanitizada.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)

    llm_mock = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Investigação com timeout",
        persona="pragmatist",
    )

    assert result.success is False
    assert result.error is not None
    assert "timeout" in result.error.lower()
    assert result.result == result.error
    assert result.used_urls == []


@pytest.mark.anyio
async def test_worker_error_sanitization_masks_bearer_and_api_secrets(monkeypatch):
    """
    Requisito Não Funcional (Segurança de Segredos):
    Simula exceção do LiteLLM contendo Bearer token e chaves de API.
    Valida que o resultado registrado mascara credenciais e não vaza segredos.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)

    leaked_secret = "sk-proj-12345abcdefghijklmnopqrstuvwxyz"
    leaked_token = "Bearer secret-jwt-token-abcdef12345"
    err_msg = f"Falha na API: {leaked_token} com api_key={leaked_secret}"

    llm_mock = AsyncMock(side_effect=LLMCallError(3, err_msg))
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Investigação com erro crítico",
        persona="historian",
    )

    assert result.success is False
    assert result.error is not None
    assert leaked_secret not in result.error
    assert leaked_secret not in result.result
    assert "secret-jwt-token" not in result.error
    assert "Bearer ***" in result.error
    assert "api_key=***" in result.error


def test_sanitize_error_comprehensive():
    """
    Valida unitariamente a função _sanitize_error em múltiplos padrões de segredo:
    Bearer tokens, sk- keys, api_key, URLs com credenciais, e truncamento a 500 chars.
    """
    # Bearer tokens
    assert _sanitize_error("Error: Bearer sk-proj-12345") == "Error: Bearer ***"
    assert _sanitize_error("auth Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9") == "auth Bearer ***"

    # sk- prefixes
    assert _sanitize_error("Invalid key sk-abcdef1234567890") == "Invalid key ***"

    # api_key / token patterns
    assert _sanitize_error("api_key: super_secret_123") == "api_key: ***"
    assert _sanitize_error("token=xyz987;") == "token=***;"

    # URLs com credenciais
    assert (
        _sanitize_error("Connect failed: https://usuario:senha123@api.openai.com/v1")
        == "Connect failed: https://***@api.openai.com/v1"
    )

    # String vazia
    assert _sanitize_error("") == "Worker failed"

    # Truncamento a 500 caracteres
    long_msg = "X" * 1000
    sanitized_long = _sanitize_error(long_msg)
    assert len(sanitized_long) == 500


@pytest.mark.anyio
@pytest.mark.parametrize(
    "persona,app_settings_models,expected_model",
    [
        # 1. Modelo específico configurado para a persona
        (
            "historian",
            {"historian": "openai/gpt-4o", "scout": "openai/gpt-4o-mini"},
            "openai/gpt-4o",
        ),
        (
            "futurist",
            {"futurist": "anthropic/claude-3-5-sonnet", "scout": "openai/gpt-4o-mini"},
            "anthropic/claude-3-5-sonnet",
        ),
        # 2. Persona sem modelo -> fallback para o scout
        (
            "skeptic",
            {"scout": "openai/gpt-4o-mini"},
            "openai/gpt-4o-mini",
        ),
        (
            "pragmatist",
            {"pragmatist": "", "scout": "openai/gpt-4o-mini"},
            "openai/gpt-4o-mini",
        ),
        # 3. Persona sem modelo e sem scout -> fallback para openai/implement
        (
            "skeptic",
            {},
            "openai/implement",
        ),
        (
            "pragmatist",
            None,
            "openai/implement",
        ),
        (
            "historian",
            {"historian": "   ", "scout": "   "},
            "openai/implement",
        ),
    ],
)
async def test_worker_model_resolution_and_dispatch(
    persona: str,
    app_settings_models: dict | None,
    expected_model: str,
    make_litellm_final_response,
    monkeypatch,
):
    """
    RN-10: Resolução de modelo por persona com fallbacks definidos.
    Valida que o PersonaWorker repassa o modelo correto ao LiteLLM binding.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)
    llm_mock = AsyncMock(
        return_value=make_litellm_final_response("Resultado da persona", [])
    )
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(
        jina_adapter=mock_adapter,
        app_settings_models=app_settings_models,
    )

    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Análise de modelos",
        persona=persona,
    )

    assert result.success is True
    assert llm_mock.await_count == 1
    assert llm_mock.await_args is not None
    passed_model = llm_mock.await_args.kwargs["model"]
    assert passed_model == expected_model


@pytest.mark.anyio
async def test_worker_handles_empty_search_query_without_calling_jina(
    make_litellm_tool_call_response,
    make_litellm_final_response,
    monkeypatch,
):
    """
    Valida que chamada de tool com query vazia ('q': '') não dispara busca no Jina
    e retorna aviso explicativo no histórico de mensagens.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)

    llm_mock = AsyncMock(
        side_effect=[
            make_litellm_tool_call_response("", call_id="c_empty"),
            make_litellm_final_response("Final após query vazia", []),
        ]
    )
    monkeypatch.setattr("app.investigation.worker.call_llm_with_retries", llm_mock)

    worker = PersonaWorker(jina_adapter=mock_adapter)
    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Investigação com query vazia",
        persona="skeptic",
    )

    assert result.success is True
    assert mock_adapter.search.await_count == 0

    # Verifica mensagem enviada na ferramenta
    second_call_messages = llm_mock.await_args_list[1].kwargs["messages"]
    tool_msg = [m for m in second_call_messages if m.get("role") == "tool"][0]
    assert "Query vazia" in tool_msg["content"]


@pytest.mark.anyio
async def test_worker_unknown_persona_fails_gracefully():
    """
    Valida que passar persona desconhecida captura ValueError e retorna
    PersonaExecutionResult com success=False e erro sanitizado.
    """
    mock_adapter = AsyncMock(spec=JinaToolAdapter)
    worker = PersonaWorker(jina_adapter=mock_adapter)

    result = await worker.execute(
        research_id=uuid4(),
        step_id=uuid4(),
        step_title="Ponto qualquer",
        persona="persona_desconhecida",
    )

    assert result.success is False
    assert result.error is not None
    assert "Persona desconhecida" in result.error
