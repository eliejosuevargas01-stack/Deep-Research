---
schema_version: 1
id: BUG-20261023-EPVA
display_number: 1
title: WebhookClient marca respostas HTTP 4xx como entregue, mascarando rejeicao do receptor
status: resolved
phase: delivering
severity: critical
priority: P1
created: 2026-10-23
updated: 2026-10-23

origin:
  type: inspection
  external_ref: "_reversa_bugs/pipeline-de-pesquisa/inspections/varredura-sequencial-2026-10-22/achados/feature-002.yaml :: F2-CONTRACT-01"

area: pesquisa-profunda
module: integracao
feature: pipeline-autonomo-seguro
labels: []

visibility: normal
security_suspected: false

reproduction:
  classification: deterministic
  rate: "1/1"
  suspected_triggers: []

blocking: []

relationships: []

traceability:
  specs:
    - "_reversa_forward/002-pipeline-autonomo-seguro/requirements.md#rf-05"
    - "_reversa_forward/002-pipeline-autonomo-seguro/requirements.md#secao-4-cenarios-de-aceitacao"
  affected_code:
    - "app/services/webhook_client.py"
  root_cause:
    state: confirmed
    hypothesis: >-
      A classificacao de entrega reutiliza a decisao de retry. A condicao da
      linha 146 pergunta "o status e transitorio? devo tentar de novo?" e a
      ausencia de excecao acaba respondendo "a entrega aconteceu?", o que so e
      verdade para 2xx.
    causal_path:
      - "app/services/webhook_client.py:146 — o if cobre apenas 429 e 5xx (+ is_server_error) para retry"
      - "app/services/webhook_client.py:150 — qualquer status fora desse conjunto (inclusive 4xx) cai em status_result = 'entregue'"
      - "app/services/webhook_client.py:151 — webhook_status recebe 'entregue' e persiste a rejeicao como se fosse sucesso"
    evidence:
      - ref: "evidence/reproduction.md"
        observation: "receptor com 404 produziu status 'entregue' e exit code 1 antes da correcao"
      - ref: "evidence/gate1-red.md"
        observation: "5 casos de 4xx falharam com 'entregue' != 'falha_definitiva'"
      - ref: "evidence/gate2-green.md"
        observation: "mesmos 5 casos passam apos restringir 'entregue' a res.is_success"
    code_refs:
      - file: "app/services/webhook_client.py"
        symbol: "WebhookClient.send_webhook"
  reproduction_tests:
    - "reproduce.py"
    - "tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue"
  regression_tests:
    - "tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue"

spec_verdict: spec-correta

change_set:
  - id: CHG-001
    kind: code
    artifact: "app/services/webhook_client.py"
    purpose: >-
      Restringir 'entregue' a respostas 2xx (res.is_success); 4xx passa a gerar
      'falha_definitiva'. Politica de retry para 429 e 5xx permanece intacta.
    diff: "fix/CHG-001.diff"

closure:
  policy: local-software
  satisfied: true
  resolution_kind: fixed

express: true
---

# WebhookClient marca respostas HTTP 4xx como entregue, mascarando rejeicao do receptor

## Summary

O `WebhookClient.send_webhook` so trata como falha (disparando retry) os
status `429, 500, 502, 503, 504` e qualquer erro de servidor. Qualquer outra
resposta HTTP fora de 2xx cai direto no ramo que grava
`status_result = "entregue"`. Um receptor que rejeita o evento com
`400, 401, 403, 404` ou `422` tem essa rejeicao registrada como entrega bem
sucedida, tanto no retorno do metodo quanto na coluna `webhook_status` da
tabela `pesquisa`.

## Expected Behavior

Spec efetiva, `_reversa_forward/002-pipeline-autonomo-seguro/requirements.md`,
linha 23, RF-05 item 5:

> 5. Despacha o Dossiê Final assinado via HMAC-SHA256 para `CALLBACK_WEBHOOK_URL`.

Cenario de aceitacao, secao 4, linha 52:

> E o webhook de callback configurado recebe o evento "research.completed" com o dossiê final

O comportamento esperado e que o valor `entregue` so seja aplicado quando o
receptor confirmou o recebimento. Respostas 4xx sao rejeicao explicita do
receptor: nao confirmam entrega e devem ser classificadas como falha.
RNF-03 (linha 31) garante que a falha nao descarta o dossie persistido, o que
pressupoe que a falha seja reconhecivel; com o defeito, ela e invisivel.

## Actual Behavior

Em `app/services/webhook_client.py`, linhas 146 a 150:

```python
if res.status_code in (429, 500, 502, 503, 504) or res.is_server_error:
    res.raise_for_status()

# Entrega confirmada com sucesso (código 2xx)
status_result = "entregue"
```

Como o `if` nao cobre 4xx, uma resposta `404` (ou `400`, `401`, `403`, `422`)
nao levanta excecao, portanto nao entra no caminho de retry e chega a linha
150, que grava `entregue` e persiste em `webhook_status` com o corpo bruto da
rejeicao em `webhook_resposta`.

## Steps to Reproduce

```bash
# a partir da raiz do projeto
python _reversa_bugs/pipeline-de-pesquisa/bugs/BUG-20261023-EPVA-webhook-4xx-como-entregue/reproduce.py
```

O script simula um receptor que responde `404 Not Found` e verifica o status
gravado. Saida observada em 2026-10-23 (defeito confirmado):

```text
retorno do cliente: {'status': 'entregue', 'http_status_code': 404, 'tentativas': 1, 'resposta': '{"erro":"recurso nao encontrado"}'}
http_status_code observado: 404
status gravado: entregue
AssertionError: DEFEITO CONFIRMADO: receptor respondeu 404 (rejeitou o evento)
mas o cliente gravou 'entregue' em vez de 'falha_definitiva'.
```

Nao foi necessario banco de dados: `research_repo` fica `None` no script e o
`_update_repo_status` retorna sem efeito (linhas 93 e 94), o que isola
exatamente a logica de classificacao.

## Evidence

- `evidence/webhook_client.snippet.py`: trecho literal das linhas 137 a 162
- `evidence/spec-esperada.md`: trechos literais da spec (RF-05 e cenario de aceitacao)
- `evidence/testes-existentes.md`: levantamento dos testes atuais e lacuna de 4xx
- `reproduce.py`: reproducao executavel, ja executada com falha confirmada

## Suspected Area

`app/services/webhook_client.py`, metodo `send_webhook`, ramo de classificacao
de status (linhas 146 a 150). A correcao pertence a este ponto unico; nenhum
outro arquivo implementa classificacao de entrega de webhook.

## Acceptance Criteria

1. Respostas HTTP 4xxx do receptor resultam em `status: "falha_definitiva"`
   (ou status equivalente de nao entregue) no retorno do metodo, nunca
   `"entregue"`.
2. `webhook_status` nao recebe `"entregue"` quando o receptor responde 4xx.
3. Resposta 2xx continua resultando em `"entregue"`, sem regressao.
4. Respostas `429` e 5xx continuam usando retry 1 + 3 e esgotando em
   `"falha_definitiva"`, sem regressao.
5. Teste automatizado cobrindo 4xx (sugestao: `400/401/403/404/422`) somado a
   `tests/unit/test_webhook_client.py`, provando a correcao.
6. Suite de testes do projeto continua verde.

## Traceability

| Item | Valor |
|---|---|
| ID | BUG-20261023-EPVA |
| Origem | inspection (varredura sequencial 2026-10-22, achado F2-CONTRACT-01) |
| Spec efetiva | `_reversa_forward/002-pipeline-autonomo-seguro/requirements.md`, RF-05 item 5 (linha 23) e secao 4 (linha 52) |
| RNF relacionado | RNF-03, linha 31 (falha nao descarta o dossie persistido) |
| Codigo afetado | `app/services/webhook_client.py` linhas 146 a 150 |
| Causa raiz | a preencher pelo `/reversa-debugger-fix` |
| Teste de reproducao | `reproduce.py` (executado, falha confirmada) |
| Testes de regressao | a preencher pelo fix |

## Resolution

**Kind:** fixed
**Date:** 2026-10-23
**Policy applied:** local-software

Causa raiz confirmada: a classificacao de entrega reutilizava a decisao de
retry. A condicao de `app/services/webhook_client.py:146` pergunta "o status e
transitorio?" e a ausencia de excecao acabava respondendo "a entrega
aconteceu?", o que so e verdade para 2xx.

Correcao: `status_result` agora depende de `res.is_success`.

```python
status_result = "entregue" if res.is_success else "falha_definitiva"
```

Veredito de spec: `spec-correta`. A spec (RF-05 item 5, linha 23, e o cenario
de aceitacao da secao 4, linha 52) ja exigia que `entregue` so se aplicasse
quando o receptor recebesse o evento. O codigo divergia; nada muda na spec.

Testes de regressao: `tests/unit/test_webhook_client.py::test_webhook_send_4xx_is_not_entregue`
(parametrizado em 400, 401, 403, 404, 422). Testes preexistentes intactos;
politica de retry 1 + 3 para 429 e 5xx intacta (o `if` de `raise_for_status()`
nao foi alterado).

Evidencia:

- Vermelho: `evidence/gate1-red.md` — 5 failed, 5 passed
- Verde: `evidence/gate2-green.md` — 10 passed no arquivo alvo
- Regressao: `evidence/gate2-green.md` — 99 passed na suíte completa, exit 0
- Reproducao original: `evidence/reproduction.md` (exit 1 antes) e o mesmo
  script encerrando exit 0 apos a correcao

Ressalva honesta: a suíte completa foi executada sem rede externa e sem
banco real; a cobertura nao prova comportamento em producao contra um receptor
HTTP real, apenas contra o `MockNetwork` do projeto e contra o caminho
`research_repo=None`.

## Agent Notes

Restricoes para quem for corrigir:

1. Nao reescrever o cliente. O menor diff possivel: a condicao da linha 146
   precisa deixar claro o que conta como confirmacao de entrega, em vez de
   apenas enumerar os status que fazem retry.
2. A politica de retry atual (429 e 5xx, 1 tentativa + 3 retries com backoff
   exponencial) deve ser preservada; o defeito esta na classificacao do que
   nao entra nessa politica, nao no retry.
3. Nao alterar `tests/unit/test_webhook_client.py` existente; acrescentar
   casos novos para 4xx.
4. `RNF-03` exige que falha de webhook nunca levante excecao nem descarte o
   dossie; a correcao precisa manter esse contrato (nenhuma excecao vazando
   para o `pipeline_runner`).
5. Proposta de taxonomia: nenhum termo novo necessario; `area/module/feature`
   ja existem em `_reversa_bugs/taxonomy.yaml`.
6. Severidade `critical` e prioridade `P1` foram propostas pelo orquestrador e
   assumidas na rota expressa; confirmar com o usuario se ele discordar.
