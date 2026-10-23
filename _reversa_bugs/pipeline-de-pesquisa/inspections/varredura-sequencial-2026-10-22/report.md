# Relatório de Varredura Sequencial — 4 features

**Contexto:** `pipeline-de-pesquisa`
**Varredura:** `varredura-sequencial-2026-10-22`
**Skill:** `/reversa-depth-inspection` (somente diagnóstico; nenhuma correção aplicada)
**Data:** 2026-10-22/23

---

## 1. Mapa e método

A varredura foi executada **sequencialmente, da Feature 001 até a 004**, conforme instrução do usuário ("nas features em forma sequencial desde a 1 até a ultima").

| Feature | Spec efetiva | Código principal | Testes |
|---|---|---|---|
| 001 pesquisa-profunda-mvp | `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md` + addenda 001 | `app/core/planner.py`, `app/api/v1/endpoints/plan.py`, `app/tools/jina_client.py`, `app/tools/llm_client.py`, `app/db/research_repository.py` | `test_domain_modules.py`, `test_endpoints.py`, `test_edge_cases.py` |
| 002 pipeline-autonomo-seguro | `_reversa_forward/002-*/requirements.md` | `app/core/pipeline_runner.py`, `app/core/security.py`, `app/services/webhook_client.py`, `app/services/credential_resolver.py` | `test_security.py`, `test_webhook_client.py` |
| 003 streaming-reasoning-audit | `_reversa_forward/003-*/requirements.md` | `app/tools/llm_client.py`, `app/core/{searcher,auditor,writer}.py`, `app/db/models.py` | `test_streaming_reasoning.py`, `test_llm_client.py` |
| 004 falhas-de-coleta-e-diagnostico | `_reversa_forward/004-*/requirements.md` | `app/tools/jina_client.py`, `app/tools/errors.py`, `app/core/searcher.py` | `test_searcher_falha_coleta.py`, `test_jina_client.py` |

**Nota metodológica importante:** a Feature 004 **já está implementada** no código atual. A varredura dessa feature portanto não buscou "o defeito original descrito no incidente", e sim **se a correção está completa e propagou por todas as camadas**. Isso está declarado no topo de `achados/feature-004.yaml`.

**Dados:** banco SQLite `data/deep_research.db`, tabelas `pesquisa`, `pontos`, `conteudo_coletado`. Schema verificado diretamente via `PRAGMA table_info` (colunas `reasoning_*` e `status_pipeline` confirmadas existentes).

**Contratos externos:** Jina Reader/SERP (`app/tools/jina_client.py`), LLM router (`app/tools/llm_client.py`, base `https://api.openai.com/v1`), webhook HMAC-SHA256 (`app/services/webhook_client.py`).

---

## 2. Achados por lente e confiança

Total bruto: **95 achados** — após dedupe, **91 achados logicamente únicos**.

| Lente | 001 | 002 | 003 | 004 | Total |
|---|---|---|---|---|---|
| Conformidade com spec | 7 | 3 | 4 | 3 | 17 |
| Estados de erro e edge cases | 6 | 3 | 2 | 4 | 15 |
| Cobertura de testes | 7 | 3 | 2 | 2 | 14 |
| Fluxo de dados | 5 | 3 | 3 | 2 | 13 |
| Contratos e integrações | 6 | 2 | 2 | 2 | 12 |
| Concorrência e consistência | 6 | 2 | 2 | — | 10 |
| Observabilidade | 4 | 2 | 2 | 2 | 10 |
| Segurança e autorização | — | 2 | — | — | 2 |
| Desempenho e I/O | — | — | 2 | — | 2 |

**Por confiança:** alta 86 · média 6 · baixa 3
**Por severidade suspeita:** critical 7 · high 32 · medium 36 · low 20

Arquivos de achados (fonte primária, com evidência `arquivo:linha` por item):
- `achados/feature-001.yaml` (41)
- `achados/feature-002.yaml` (20)
- `achados/feature-003.yaml` (19)
- `achados/feature-004.yaml` (15)

---

## 3. Clusters (indício de causa estrutural)

### Cluster A — Propagação truncada da correção de falha (Feature 004)
`F4-SPEC-01` · `F4-SPEC-02` · `F4-SPEC-03` · `F4-OBS-02`

A correção do incidente original parou na **primeira camada**: o *ponto* passou a acusar `falha_coleta`, mas o dicionário de retorno do `Searcher`(`app/core/searcher.py:523-531`) continua declarando `status_pesquisa: "coletado"` fixo — `pontos_falhados` é calculado e descartado. A informação não sobe para o endpoint (`app/api/v1/endpoints/search.py` não referencia `falha_coleta`), nem para o pipeline, nem para a operação.

**Causa estrutural única provável:** o resultado do `Searcher` não tem contrato explícito de status agregado; cada consumidor lê o que quer e o agregado ninguém lê.

### Cluster B — Confiança da camada HTTP (Features 001, 002, 004)
`F-CONTRACT-02` · `F-ERR-01` · `F-CONC-01` · `F2-CONTRACT-01` · `F4-CONTRACT-02`

Falhas de rede/transporte não categorizadas em mais de um cliente, e classificação de sucesso que aceita 4xx como entrega. A mesma classe de defeito aparece em três clientes independentes (`jina_client`, `webhook_client`, `llm_client`).

### Cluster C — Máquina de estados sem cobertura (Features 002, 003)
`F3-TEST-01` · `F-CONC-05` · `F3-CONC-*`

`status_pipeline` é gravado em 6 estágios distintos e nenhum teste exercita a máquina de estados; ausência de recuperação após interrupção deixa registros presos em estágio intermediário.

---

## 4. Verificação de alegações (o que o orchestrator confirmou ou refutou)

A verificação independente mudou o resultado em 6 achados — registrado aqui para que ninguém promova um achado stale:

| Achado | Veredito | Evidência da verificação |
|---|---|---|
| `F-ERR-06` auth fail-open | **confirmado** | `app/core/security.py:38-40` retorna `True` quando não há chave configurada |
| `F2-SEG-01` fail-open | **confirmado** | mesmo caminho, `security.py:33-40` |
| `F2-CONTRACT-01` webhook 4xx = entregue | **confirmado** | `webhook_client.py:146-150`: só 429/5xx disparam `raise_for_status()` |
| `F-OBS-01` zero logging no planner | **confirmado** | `grep -c` retorna 0 ocorrências de logger/planner |
| `F-OBS-02` usage/tokens descartados | **confirmado** | nenhuma referência a `usage`/`prompt_tokens` em `llm_client.py` |
| `F-CONTRACT-02` Jina sem retry | **REFUTADO (stale)** | `jina_client.py:86-99` já implementa 4 tentativas com backoff e `classify_failure` |
| `F-CONTRACT-01` model light vs strong | **ENGANOSO** | `plan.py:65` injeta `model_light=plan_model` onde `plan_model = model_strong or model_light` (comentário "O plano utiliza o modelo forte"); comportamento efetivo está correto |
| `F2-SEG-02` exposição de HMAC secret | **REFUTADO** | `credentials_repository.py:99-125` descriptografa e aplica `_mask_value` (`[REDACTED]` ou `xxxx****xxxx`), com fallback em exceção |
| `F-CONC-05` status preso | **parcial** | update_pipeline_status existe; recuperação após crash não verificada — requer feature 002 |
| `searcher.py:529` `status_pesquisa` fixo | **confirmado (novo, F4-SPEC-01)** | lido diretamente; `pontos_falhados` computado em `:524` e ignorado |

---

## 5. Cobertura — o que NÃO foi varrido

Para evitar truncamento silencioso:

1. **Feature 004 — caminho inverso de sobrescrita** (`F4-ERR-03`): a direção "falha posterior sobrescreve evidência anterior" tem confiança média e **não foi confirmada**; apenas a direção oposta tem teste.
2. **Alcance dos fragmentos de prompt em `searcher.py:204` e `:361`** (`F4-ERR-04`): não determinei se são branches inativas após a guarda de evidência vazia. **Requer leitura humana do fluxo de prompt.**
3. **Lentes condicionais não ativadas:** configuração/migrations/flags (sem multi-ambiente detectado) e observabilidade nas Features 001/002 foi avaliada mas sem instrumentação real para medir.
4. **Bugs existenciais:** não havia bugs registrados em `_reversa_bugs/pipeline-de-pesquisa/bugs/` antes desta varredura (o diretório não existia); a seção 5 do mapa ficou sem base de comparação.
5. **Desempenho real:** nenhuma medição de latência ou N+1 foi executada; os achados de desempenho são estáticos.

---

## 6. Situação dos subagentes (transparência operacional)

A varredura foi despachada a 3 subagentes em background (`deleg_0c20b972`) após perda dos resultados anteriores no compaction. Estado observado:

- **Feature 003** (`sa-1-f806de18`): concluiu, 19 achados, arquivo escrito às 00:41.
- **Feature 002** (`sa-0-6a2188c2`): validou 20 achados e **parou 6 minutos sem escrever**; reanimado via steer, escreveu às 01:10 (18 KB). Resultado aproveitado.
- **Feature 004** (`sa-2-566c53f1`): morto em fase de leitura, sem IDs `F4-` gerados — **a varredura da Feature 004 foi executada diretamente pelo orchestrador** com evidência própria.

Nenhum subagente entrou em loop de raciocínio: os padrões de chamada eram legítimos (27-28 leituras, sem repetição circular). O problema foi *stall* antes da escrita, não loop.

---

## 7. Candidatos a bug (aguardando decisão do usuário)

A Etapa 3 do skill exige menu antes de registrar. **Nenhum bug foi criado ainda.**

Prioridade sugerida por impacto, para decisão:

1. **F2-CONTRACT-01** (critical) — webhook marca 4xx como `entregue`; cliente acredita que o dossiê foi recebido quando foi rejeitado.
2. **F-ERR-06 / F2-SEG-01** (critical) — fail-open de autenticação; sem `API_SECRET_KEY` a API fica inteiramente aberta. **Sinal de segurança: segue fluxo restrito.**
3. **F4-SPEC-01** (critical) — pesquisa com falha de coleta reporta `status_pesquisa: "coletado"`, exatamente o defeito que a Feature 004 prometeu eliminar.
4. **F3-SPEC-01** (critical) — webhook final omite `reasoning_auditoria` que a Feature 003 exige.
5. **F3-TEST-01** (critical) — cobertura zero da máquina de estados do streaming.
6. **F-ERR-04** (high) — `IntegrityError` não tratado vira HTTP 500 opaco.

Itens explicitamente **não** promovidos: `F-CONTRACT-02` (stale/refutado) e `F2-SEG-02` (refutado).

---

> Digite **CONTINUAR** para corrigir o bug de maior impacto com `/reversa-debugger-fix`, ou rode `/reversa-debugger-graph` para ver o panorama.
