# Evidencia 2 - spec efetiva que define o comportamento esperado

Arquivo: `_reversa_forward/002-pipeline-autonomo-seguro/requirements.md`
Extraido literalmente em 2026-10-23.

## Linha 23 (RF-05 item 5)

> 5. Despacha o Dossiê Final assinado via HMAC-SHA256 para `CALLBACK_WEBHOOK_URL`.

## Linha 52 (Cenario de aceitacao Gherkin, secao 4)

> E o webhook de callback configurado recebe o evento "research.completed" com o dossiê final

## Linha 31 (RNF-03)

> **RNF-03 (Resiliência do Webhook):** Falha no envio do webhook não descarta o dossiê final persistido no SQLite.

Interpretacao: o valor "entregue" so pode ser aplicado quando o receptor
CONFIRMOU o recebimento. Um 4xx significa que o receptor rejeitou o evento;
gravar "entregue" nesse caso contradiz o cenario de aceitacao da linha 52 e
destroi a telemetria que a RNF-03 pressupoe (nao ha como saber que falhou
se o sistema registra sucesso).
