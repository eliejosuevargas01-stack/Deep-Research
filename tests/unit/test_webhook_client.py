"""Testes unitários para WebhookClient.

Cobre cálculo da assinatura HMAC-SHA256 no header X-Signature sobre raw bytes,
validação timing-safe com hmac.compare_digest e tratamento de códigos 2xx versus
5xx com registro de falha_definitiva sem perda de dados.
Atende a DT-04, RN-09 e RF-10.
"""

import hashlib
import hmac
import json
import pytest
from tests.mocks.http_mock import MockNetwork, create_mock_transport


def test_compute_hmac_sha256_signature() -> None:
    """Verifica formatação padrão da assinatura HMAC-SHA256: 'sha256=<hex>'."""
    from app.services.webhook_client import WebhookClient

    secret = "minha-chave-secreta-webhook"
    corpo_raw = b'{"evento": "research.completed", "id_pesquisa": "123"}'

    assinatura = WebhookClient.compute_signature(secret, corpo_raw)
    assert assinatura.startswith("sha256=")

    # Cálculo independente para conferência
    digest_esperado = hmac.new(secret.encode("utf-8"), corpo_raw, hashlib.sha256).hexdigest()
    assert assinatura == f"sha256={digest_esperado}"


def test_verify_signature_timing_safe() -> None:
    """Verifica validação timing-safe contra adulteração de corpo, segredo ou prefixo."""
    from app.services.webhook_client import WebhookClient

    secret = "chave-super-secreta"
    corpo_raw = b'{"dossier": "conteudo analitico"}'
    assinatura_valida = WebhookClient.compute_signature(secret, corpo_raw)

    # 1. Corpo íntegro e segredo correto
    assert WebhookClient.verify_signature(secret, corpo_raw, assinatura_valida) is True

    # 2. Corpo adulterado
    corpo_adulterado = b'{"dossier": "conteudo ADULTERADO"}'
    assert WebhookClient.verify_signature(secret, corpo_adulterado, assinatura_valida) is False

    # 3. Segredo incorreto
    assert WebhookClient.verify_signature("outra-chave", corpo_raw, assinatura_valida) is False

    # 4. Formato de cabeçalho sem prefixo sha256=
    assert WebhookClient.verify_signature(secret, corpo_raw, "invalido") is False


@pytest.mark.asyncio
async def test_webhook_send_success_200() -> None:
    """Verifica disparo de webhook com sucesso 200, headers obrigatórios e status 'entregue'."""
    from app.services.webhook_client import WebhookClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    secret = "webhook-hmac-secret-123"
    client = WebhookClient(secret=secret, transport=transport)

    payload = {
        "evento": "research.completed",
        "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
        "dossier": "# Dossiê Final",
    }

    resultado = await client.send_webhook(
        url="https://callback.test/webhooks/pesquisa",
        payload=payload,
        id_pesquisa="550e8400-e29b-41d4-a716-446655440000",
    )

    assert resultado["status"] == "entregue"
    assert resultado["http_status_code"] == 200
    assert resultado["tentativas"] == 1

    # Verificação dos cabeçalhos da requisição transmitida
    assert len(mock_net.requests) == 1
    req = mock_net.requests[0]
    assert req.headers.get("X-Signature", "").startswith("sha256=")
    assert req.headers.get("X-Event-Type") == "research.completed"
    assert req.headers.get("X-Research-Id") == "550e8400-e29b-41d4-a716-446655440000"

    # Confere integridade da assinatura enviada
    assert WebhookClient.verify_signature(secret, req.content, req.headers["X-Signature"]) is True


@pytest.mark.asyncio
async def test_webhook_send_retry_then_success() -> None:
    """Verifica retries em resposta 5xx transitória culminando em entrega (RNF-06)."""
    from app.services.webhook_client import WebhookClient

    mock_net = MockNetwork()
    mock_net.set_webhook_status_sequence([500, 200])
    transport = create_mock_transport(mock_net)

    client = WebhookClient(secret="secret", transport=transport)
    resultado = await client.send_webhook(
        url="https://callback.test/retry",
        payload={"evento": "research.completed"},
        id_pesquisa="123",
    )

    assert resultado["status"] == "entregue"
    assert resultado["tentativas"] == 2
    assert len(mock_net.requests) == 2


@pytest.mark.asyncio
async def test_webhook_send_exhausted_retries_marks_falha_definitiva() -> None:
    """Verifica que esgotadas as 4 tentativas (1+3), registra 'falha_definitiva' sem lançar exceção."""
    from app.services.webhook_client import WebhookClient

    mock_net = MockNetwork()
    mock_net.set_webhook_status_sequence([500, 502, 503, 500])
    transport = create_mock_transport(mock_net)

    client = WebhookClient(secret="secret", transport=transport)
    resultado = await client.send_webhook(
        url="https://callback.test/fail",
        payload={"evento": "research.completed"},
        id_pesquisa="123",
    )

    # Não deve levantar exceção não tratada; preserva integridade do dossiê já persistido
    assert resultado["status"] == "falha_definitiva"
    assert resultado["tentativas"] == 4
    assert len(mock_net.requests) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_webhook_send_4xx_is_not_entregue(status: int) -> None:
    """BUG-20261023-EPVA: resposta 4xx é rejeição do receptor e não pode virar 'entregue'.

    RF-05 exige que o valor 'entregue' só seja aplicado quando o receptor confirmou
    o recebimento. Um 4xx rejeita o evento, portanto o status resultante deve ser
    'falha_definitiva'.
    """
    from app.services.webhook_client import WebhookClient

    mock_net = MockNetwork()
    mock_net.set_webhook_status_sequence([status])
    transport = create_mock_transport(mock_net)

    client = WebhookClient(secret="secret", transport=transport)
    resultado = await client.send_webhook(
        url="https://callback.test/webhooks/pesquisa",
        payload={"evento": "research.completed"},
        id_pesquisa="123",
    )

    assert resultado["http_status_code"] == status, "o mock deveria ter devolvido o status"
    assert resultado["status"] == "falha_definitiva", (
        f"HTTP {status} do receptor foi classificado como {resultado['status']!r}; "
        "um 4xx é rejeição definitiva e não confirma entrega (BUG-20261023-EPVA)."
    )
