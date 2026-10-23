# Evidencia 3 - cobertura de testes existente (lacuna de 4xx)

Arquivo: `tests/unit/test_webhook_client.py`
Levantamento por `grep -n "def test\|status_code=\|entregue\|falha"` em 2026-10-23.

Casos existentes:

| Linha | Teste | Cobre |
|---|---|---|
| 54 | `test_webhook_send_success_200` | HTTP 200 -> "entregue" |
| 92 | `test_webhook_send_retry_then_success` | 5xx com retry e depois sucesso |
| 113 | `test_webhook_send_exhausted_retries_marks_falha_definitiva` | 5xx esgotando 1+3 -> "falha_definitiva" |

Lacuna: nenhum teste exercita resposta HTTP 4xx (400, 401, 403, 404, 422).
Por isso o defeito passou: a suite prova o caminho 200 e o caminho 5xx,
mas o comportamento para 4xx nunca foi fixado por teste.
