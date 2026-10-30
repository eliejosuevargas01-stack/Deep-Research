# Contrato da API: Tratamento de Timeout e Cancelamento na Busca (/api/v1/search)

Este documento define o contrato oficial de erro e recuperação para timeout na etapa de busca web concorrente com personas (`POST /api/v1/search`), aplicável ao Checkpoint 1 (modo síncrono).

---

## 1. Comportamento do Backend em Caso de Timeout

Quando o processamento de um ponto de investigação ultrapassa o prazo limite configurado (`SEARCH_POINT_TIMEOUT_SECONDS`, padrão 480s):

1. **Cancelamento Seguro e Await de Tasks**:
   - Todas as tarefas concorrentes das personas (`_executar_persona`) ativas no ponto são explicitamente canceladas (`task.cancel()`) e aguardadas (`await asyncio.gather(..., return_exceptions=True)`).
   - Conexões HTTP (`httpx`/`httpcore`) e leituras em andamento são encerradas de forma limpa, sem deixar tarefas órfãs ou locks presos.

2. **Persistência Atômica do Estado Parcial**:
   - Todas as fontes e URLs lidas com sucesso até o momento do timeout são preservadas no banco de dados (`conteudo_coletado` e `pontos`).
   - O ponto é registrado com status `falha_coleta` (ou `parcial`, caso alguma persona tenha concluído), com diagnóstico descritivo explícito.
   - A reserva/lease do ponto é liberada (`reservado_ate` limpo), garantindo que o ponto **não fique preso em `em_andamento`**.

3. **Resposta HTTP 504 (Gateway Timeout)**:
   O endpoint `POST /api/v1/search` retorna HTTP 504 com payload tipado e sanitizado:

```json
{
  "detail": {
    "tipo": "TIMEOUT_ERROR",
    "mensagem": "Tempo limite de busca excedido (480.0s) no ponto 1. Coleta interrompida.",
    "diagnostico": "Interrupção por timeout (480.0s excedidos no ponto 1). O ponto foi registrado com falha_coleta e pode ser re-tentado.",
    "id_pesquisa": "0f1c33b4-6e97-4348-81a8-8d84e7fca8ac",
    "ponto_id": "af83cc21-dec0-4c34-9650-fac14effbd00",
    "ponto_n": 1,
    "timeout_segundos": 480.0,
    "re_tentavel": true
  }
}
```

---

## 2. Compatibilidade com o Frontend e `parseApiError`

O utilitário existente `parseApiError(response)` em `frontend/src/services/api.ts` já suporta objetos de erro estruturados com campos `mensagem` e `diagnostico`. A mensagem amigável apresentada ao usuário será formatada automaticamente:

> "Tempo limite de busca excedido (480.0s) no ponto 1. Coleta interrompida. — Diagnóstico: Interrupção por timeout (480.0s excedidos no ponto 1)..."

---

## 3. Fluxo de Retentativa (Retry)

A pesquisa e o plano original **não são descartados**. O usuário não precisa recriar o plano nem digitar novamente o tema:

1. **Retentativa da Busca Geral**:
   - Chamada: `POST /api/v1/search` com `{ "id_pesquisa": "<id_pesquisa>" }`.
   - O backend seleciona automaticamente os pontos com status diferente de `aprovado` (incluindo os pontos em `falha_coleta` por timeout) e reprocessa a busca.
   - As fontes e trechos já coletados anteriormente são mantidos e deduplicados.

2. **Retentativa Direcionada de um Ponto Específico**:
   - Chamada: `POST /api/v1/search` com `{ "id_pesquisa": "<id_pesquisa>", "ponto_id": "<ponto_id>" }`.
   - Reprocessa exclusivamente o ponto informado.

---

## 4. Garantias e Portões de Integridade (Audit e Writer)

- **Auditoria (`POST /api/v1/audit`)**: Se o usuário tentar auditar uma pesquisa com pontos em `falha_coleta` devido a timeout, a auditoria analisará os critérios com base estrita nas evidências reais coletadas.
- **Redação (`POST /api/v1/writer`)**: O Writer continua bloqueando estritamente com HTTP 400 (`UNAPPROVED_POINTS`) caso haja pontos não aprovados, impedindo relatórios falsos com evidências incompletas.
