# Actions — Falhas de Coleta e Diagnóstico

**Feature 004 · deep-research · 2026-10-22**

## Sprint 1 — Cliente Jina à prova de falha silenciosa (RF-01, RF-02, DÚVIDA-01)

| ID | Ação | Status |
|----|------|--------|
| A001 | Criar `app/tools/errors.py` com `JinaError` tipada (código HTTP, categoria, mensagem, ação corretiva) e classificador `classify_jina_failure(status, body)`. Categorias: `billing` (402), `autenticacao` (401/403), `rate_limit` (429), `indisponibilidade` (5xx), `desconhecido`. | [ ] |
| A002 | Em `app/tools/jina_client.py`, `search()`: substituir o filtro `in (429, 500, 502, 503, 504) or res.is_server_error` por classificação geral de falha; levantar `JinaError` para billing/autenticação sem retry; manter retry 1+3 para rate_limit/indisponibilidade e re-levantar a `JinaError` categorizada ao esgotar. | [ ] |
| A003 | Em `app/tools/jina_client.py`, `read()`: aplicar o mesmo classificador, eliminando o retorno do corpo de erro como Markdown legítimo. | [ ] |
| A004 | Substituir em `tests/unit/test_regressao_data_null.py` as asserções que codificam o defeito (`data:null` → lista vazia) por asserções do novo contrato: `401` levanta `JinaError` categoria `autenticacao` sem retry. Registrar a substituição em `regression-watch.md`. | [ ] |
| A005 | Adicionar em `tests/unit/test_jina_client.py`: 402 com `InsufficientBalanceError` levanta `JinaError` categoria `billing` com 1 requisição apenas (CA-01.1, CA-02.1, CA-02.2); mensagem nunca contém a chave (CA-01.6). | [ ] |
| A006 | Rodar `pytest tests/unit/test_jina_client.py tests/unit/test_regressao_data_null.py` e confirmar verde. | [ ] |

## Sprint 2 — Detecção de coleta vazia no Searcher (RF-03, RF-05)

| ID | Ação | Status |
|----|------|--------|
| A007 | Em `app/core/searcher.py`, `_executar_persona`: capturar `JinaError` do `jina_client.search()`, registrar em `erro_provedor`, e abortar o loop sem emitir síntese quando `raw_evidence_chunks` estiver vazio. Retornar `evidencia_vazia: true`, `erro_provedor`, `urls_lidas: []`. | [ ] |
| A008 | Em `app/core/searcher.py`, substituir o prompt de síntese sem evidência (linhas 317-325): quando não há evidência, não chamar LLM; devolver texto declarando a falha com categoria e ação corretiva. | [ ] |
| A009 | Em `app/core/searcher.py`, `_processar_ponto`: calcular `total_urls_lidas_efetivas` (soma das URLs realmente lidas pelas personas) e marcar `falha_coleta` quando zero. Persistir status `falha_coleta` e justificativa em `pontos_fracos` sem apagar coletas anteriores. | [ ] |
| A010 | Escrever `tests/unit/test_searcher_falha_coleta.py`: mock devolve 402 na SERP; assertar `falha_coleta=true`, `diagnostico` com categoria `billing`, nenhuma síntese inventada, ponto com status `falha_coleta` e justificativa persistida. | [ ] |
| A011 | Rodar suíte completa e confirmar que os testes existentes de personas/deduplicação seguem verdes. | [ ] |

## Sprint 3 — Persistência e exposição do diagnóstico (RF-04, RF-06)

| ID | Ação | Status |
|----|------|--------|
| A012 | Em `app/schemas/search.py`: adicionar a `SearchColetaResumo` os campos opcionais `falha_coleta: bool = False` e `diagnostico: Optional[str] = None`; adicionar `falha_coleta` e `diagnostico` também a `PersonaColetaItem`. | [ ] |
| A013 | Em `app/db/research_repository.py`, `save_collected_content`: aceitar `status` e `pontos_fracos` opcionais, gravando `falha_coleta` quando informado, preservando `coletado` no caminho normal. | [ ] |
| A014 | Em `app/db/research_repository.py`, `get_read_urls`/`get_collected_content_for_point`: expor o último status de coleta para que a auditoria delibere sem nova consulta. | [ ] |
| A015 | Atualizar `tests/unit/test_schemas.py` e `tests/unit/test_database.py` com o novo contrato. | [ ] |

## Sprint 4 — Deliberação determinística (RF-07, RF-08)

| ID | Ação | Status |
|----|------|--------|
| A016 | Em `app/core/auditor.py`: antes de chamar o LLM, verificar se a última coleta do ponto tem zero URLs lidas ou status `falha_coleta`; se sim, reprovar deterministicamente sem chamada ao LLM, com `pontos_fracos` descrevendo a categoria e a ação corretiva, e incrementar `tentativas_auditoria`. | [ ] |
| A017 | Em `app/core/writer.py`: levantar `ValueError("NO_EVIDENCE_COLLECTED: ...")` quando todos os pontos do escopo estão em falha de coleta; permitir redação se ao menos um ponto tem evidência real. | [ ] |
| A018 | Testes: auditoria reprova sem LLM (mock conta chamadas LLM = 0); writer bloqueia com todos em falha e prossegue com pelo menos um ponto válido. | [ ] |

## Sprint 5 — Diagnóstico no pipeline e observabilidade (RF-09, RF-10)

| ID | Ação | Status |
|----|------|--------|
| A019 | Em `app/core/pipeline_runner.py`: propagar o diagnóstico em `erro_pipeline` (categoria + ação corretiva), logar com identificador da pesquisa, e não re-tentar falha terminal de billing/autenticação. | [ ] |
| A020 | Criar `app/api/v1/endpoints/health.py` com `GET /api/v1/health/providers`: executa chamada real de baixo custo à Jina (curta, `include_content=False`) e ao LLM configurado; devolve por provedor `status` e `detalhe` com categoria da falha; nunca expõe chaves. | [ ] |
| A021 | Registrar a rota em `app/api/v1/router.py`. | [ ] |
| A022 | Teste de integração do novo endpoint com `MockTransport`, cobrindo `ok` e `erro` por provedor. | [ ] |

## Sprint 6 — Verificação

| ID | Ação | Status |
|----|------|--------|
| A023 | Rodar suíte completa `pytest` e confirmar taxa de aprovação e ausência de regressão. | [ ] |
| A024 | Exercitar o container na porta 8085 com chamada real: confirmar que saldo Jina insuficiente produz diagnóstico explícito e não dossiê inventado. | [ ] |
| A025 | Atualizar `progress.jsonl`, `regression-watch.md` e `legacy-impact.md` da feature. | [ ] |
