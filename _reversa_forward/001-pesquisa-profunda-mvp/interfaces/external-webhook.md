# Interface: Notificação do Webhook de Callback (Entrega do Dossiê)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP POST (Emitido pelo sistema para serviço externo consumidor)
> Protocolo: HTTPS
> Referência SDD: `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#61-requisitos-principais`, `_reversa_forward/001-pesquisa-profunda-mvp/requirements.md#10-lacunas`

---

## 1. Visão Geral
Após persistir o dossiê finalizado na tabela `pesquisa`, o endpoint `POST /api/v1/writer` dispara automaticamente uma notificação HTTP POST para a URL configurada em `CALLBACK_WEBHOOK_URL`. Para assegurar integridade de trânsito e prevenir spoofing, a mensagem carrega uma assinatura criptográfica HMAC-SHA256 gerada com a chave secreta `WEBHOOK_HMAC_SECRET`.

---

## 2. Detalhes da Requisição Enviada

- **Método HTTP:** `POST`
- **Destino:** `{CALLBACK_WEBHOOK_URL}`
- **Cabeçalhos Enviados:**
  - `Content-Type: application/json`
  - `User-Agent: DeepResearch-Pipeline/1.0`
  - `X-Signature: sha256=<HMAC_HEX_DIGEST>`
  - `X-Event-Type: research.completed`
  - `X-Research-Id: <UUID>`
- **Timeout:** 30 segundos
- **Política de Retentativas:** 1 tentativa inicial + 3 retries com backoff exponencial

---

## 3. Especificação da Assinatura Criptográfica HMAC-SHA256

A assinatura é calculada sobre o **corpo cru (raw bytes)** da requisição JSON em UTF-8:
```python
import hashlib
import hmac

digest = hmac.new(
    key=webhook_hmac_secret.encode("utf-8"),
    msg=raw_request_body_bytes,
    digestmod=hashlib.sha256,
).hexdigest()

header_value = f"sha256={digest}"
```

### Validação Segura no Receptor
O serviço consumidor deve comparar a assinatura recebida no cabeçalho `X-Signature` utilizando comparação em tempo constante (`timing-safe`):
```python
# Exemplo no receptor Python
def verify_signature(secret: str, raw_body: bytes, header_signature: str) -> bool:
    if not header_signature.startswith("sha256="):
        return False
    expected_hex = header_signature[7:]
    calculated_hex = hmac.new(
        key=secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated_hex, expected_hex)
```

---

## 4. Payload Transmitido (Webhook Body)

```json
{
  "evento": "research.completed",
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
  "tema": "Impacto da Inteligência Artificial Generativa na Educação Básica",
  "concluido_em": "2026-10-21T18:40:00Z",
  "metricas": {
    "total_pontos": 5,
    "pontos_aprovados": 4,
    "pontos_reprovados": 1,
    "total_caracteres_dossier": 18450
  },
  "dossier": {
    "formato": "markdown",
    "conteudo": "# Dossiê Analítico: Impacto da IA na Educação\n\n## Sumário Executivo\n...\n## Referências Canônicas\n1. https://unesdoc.unesco.org/..."
  }
}
```

---

## 5. Tratamento de Erros e Resiliência
- Se o servidor receptor retornar código HTTP `2xx` (ex: 200, 201, 204), a entrega é marcada como `entregue` na tabela `pesquisa`.
- Se o servidor receptor responder com `5xx` ou falha de conexão, o sistema executa até 3 retries com backoff.
- Se todas as tentativas falharem, o sistema registra `webhook_status = 'falha_definitiva'` na tabela `pesquisa` sem abortar ou desfazer a gravação do dossiê já gerado.