# Roadmap — Falhas de Coleta e Diagnóstico

**Feature 004 · deep-research · 2026-10-22**

## Estratégia

Consertar de dentro para fora, na ordem em que a falha é produzida e depois propagada:

1. **Fonte da falha** — tornar o cliente Jina incapaz de transformar erro em resultado vazio.
2. **Detecção** — tornar o Searcher incapaz de sintetizar sem evidência.
3. **Propagação** — expor, persistir e deliberar sobre a falha (schema, repositório, auditoria, redação).
4. **Observabilidade** — endpoint que verifica provedores de verdade.

A ordem é obrigatória: corrigir o cliente sem corrigir a detecção ainda permite dossiê inventado por outras rotas (ex.: SERP responde 200 mas devolve zero itens).

## Fases

### Fase 1 — Cliente Jina à prova de falha silenciosa (RF-01, RF-02, DÚVIDA-01)

Introduzir erro tipado com categoria e ação corretiva, compartilhado por `search()` e `read()`. Falhas de billing/autenticação tornam-se terminais; rate limit e indisponibilidade seguem com retry 1+3.

**Arquivos:** `app/tools/jina_client.py`, `tests/unit/test_regressao_data_null.py`, `tests/unit/test_jina_client.py`

**Risco:** os testes de regressão em `test_regressao_data_null.py` afirmam que `{"code":401,"data":null}` devolve lista vazia. Esses testes *codificam o defeito* e serão substituídos por asserções do novo contrato; a substituição é registrada em `regression-watch.md`.

### Fase 2 — Detecção de coleta vazia no Searcher (RF-03, RF-05)

A persona passa a abortar a síntese sem evidência, devolvendo um resultado marcado como falha com o erro do provedor preservado. A consolidação por ponto passa a classificar `falha_coleta`.

**Arquivos:** `app/core/searcher.py`

**Risco:** nenhum teste existente cobre o caminho de "SERP vazia por falha", então o comportamento atual não estava protegido. Novo teste cobre.

### Fase 3 — Persistência e exposição do diagnóstico (RF-04, RF-06)

Schema da resposta ganha `falha_coleta` e `diagnostico`. Repositório passa a aceitar status `falha_coleta` e justificativa, sem apagar coletas anteriores.

**Arquivos:** `app/schemas/search.py`, `app/db/research_repository.py`

**Risco:** campos novos são opcionais com default, então o contrato publicado do webhook permanece intacto.

### Fase 4 — Deliberação determinística (RF-07, RF-08)

Auditoria reprova sem evidência sem gastar chamada de LLM. Writer bloqueia redação sem nenhuma evidência.

**Arquivos:** `app/core/auditor.py`, `app/core/writer.py`

**Risco:** `tests/integration/test_endpoints.py` tem o ciclo plan→search→audit→writer. Com o mock atual a Jina sempre devolve 3 itens, então o caminho continua tendo evidência e os testes seguem verdes. Será validado por execução real.

### Fase 5 — Diagnóstico no pipeline e observabilidade (RF-09, RF-10)

`PipelineRunner` registra a causa sem mascará-la e não re-tenta falha terminal. Novo endpoint `GET /api/v1/health/providers` faz chamada real de baixo custo a cada provedor.

**Arquivos:** `app/core/pipeline_runner.py`, `app/api/v1/endpoints/health.py`, `app/api/v1/router.py`

**Risco:** endpoint novo, sem consumidor existente; não altera rotas publicadas.

## Ordem de execução

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5
```

Cada fase termina com suíte de testes verde e teste novo do requisito entregue. Nenhuma fase depende de dado externo real para ser validada (tudo verificável com `MockTransport`), exceto Fase 5, que adicionalmente será exercida contra os provedores reais via container na porta 8085.

## Não objetivos

- Trocar provedor de busca.
- Alterar personas, número de queries ou desenho do loop ReAct.
- Migração de banco ou nova tabela.
- Alterar modelos LLM configurados.
