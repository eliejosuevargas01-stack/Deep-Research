# Gate 1 - evidencia do VERMELHO (antes da correcao)

Comando executado (raiz do projeto):

```bash
python -m pytest tests/unit/test_webhook_client.py -q
```

Saida literal (2026-10-23):

```text
FAILED tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue[400]
FAILED tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue[401]
FAILED tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue[403]
FAILED tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue[404]
FAILED tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue[422]
5 failed, 5 passed in 0.21s
```

Trecho da assercao com falha:

```text
E       AssertionError: HTTP 422 do receptor foi classificado como 'entregue'; um 4xx é rejeição definitiva e não confirma entrega (BUG-20261023-EPVA).
E       assert 'entregue' == 'falha_definitiva'
```

Leitura:

- Os 5 casos novos falham exatamente no ponto declarado no bug.md: o cliente
  grava `entregue` quando o receptor responde 4xx.
- Os 5 testes preexistentes passam (`test_compute_hmac_sha256_signature`,
  `test_verify_signature_timing_safe`, `test_webhook_send_success_200`,
  `test_webhook_send_retry_then_success`,
  `test_webhook_send_exhausted_retries_marks_falha_definitiva`).
- Nao houve regressao por adicao de teste: a quebra veio do teste novo.
