# Impacto legado: 001-modulo-briefing (T001-T002, T003, T008, T009, T014-T016)

- Data: 2026-10-11
- Feature: 001-modulo-briefing
- Política: allowLegacyEdits=true; caminhos liberados incluem `app/**` e `tests/**`
- Âncora: feature greenfield (PRD + specs SDD). Sem extração de legado prévia.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/briefing/prompt_loader.py | Leitura de instrução do briefing (RF-04) | componente-novo | LOW | Loader novo, stdlib, leitura por chamada; sem mudança em regra existente |
| app/prompts/briefing.md | Prompt de sistema do briefing (RF-04, RF-03, RN-03) | componente-novo | LOW | Arquivo novo PT-BR, 3–7 pontos, alvo habitual 5; sem legado afetado |
| tests/test_briefing_prompt_loader.py | Teste isolado do loader (RF-04, RF-08) | componente-novo | LOW | Teste stdlib unittest com tempfile; sem dependência externa |
| app/briefing/__init__.py | Fronteira do módulo briefing (T001) | componente-novo | LOW | Pacote isolado, sem imports ou efeitos de execução de pesquisa |
| app/briefing/domain.py | Domínio do briefing (T001) | componente-novo | LOW | Limites de tema/pontos, estados e transições puros; sem I/O ou modelo legado |
| app/briefing/schemas.py | Contratos HTTP do briefing (F-01/F-02) | componente-novo | MEDIUM | T014 tipa `BriefingResponse.status` com `BriefingStatus` e impõe 3–7 pontos em `draft`/`approved` e em `ApprovedBriefingResponse`; fecha contratos permissivos, sem consumidor existente |
| tests/test_briefing_schemas.py | Regressão dos contratos de resposta (F-01/F-02) | componente-novo | LOW | Teste stdlib unittest cobrindo enum, limites 0/2/3/4/5/6/7/8, estados vazios, extra proibido |
| app/briefing/serp_client.py | Adapter SERP Jina isolado (T009/T016, RF-02/RF-10) | componente-novo | MEDIUM | Client reutilizável httpx/asyncio, retry 4 totais sequencial, lock por instância, erro seguro sem segredos; T016 restringe chave API a tokens ASCII imprimíveis (33–126); fronteira nova consumida por T010/T011 |
| tests/test_briefing_serp_client.py | Regressão do adapter SERP (T009/T016, RF-02/RF-08/RF-10) | componente-novo | LOW | unittest.IsolatedAsyncioTestCase + httpx.MockTransport; contrato, retry, segurança, timeout, serialização, cancelamento, redirect, ownership, validação estrita de chave ASCII imprimível |

## Diff conceitual

T001 criou fronteira/domínio próprios; T002 criou schemas, reforçados por T014 para estado enum e conteúdo 3–7. T003 verificou contrato Jina sem leitura de páginas (decisão do usuário 2026-10-11). T008 criou loader e prompt de arquivo. T009 criou adapter SERP `JinaSerpClient` isolado com retry 4 totais; T016 refinou validação de chave de API para proibir não-ASCII, controles e espaços antes de I/O. T015 registrou entidade isolada e correção append-only de proveniência. Nenhum modelo, storage, migration ou router foi criado nestas rodadas.

## Preservadas

Nenhuma regra legada extraída previamente para este módulo (feature greenfield).

## Modificadas

Nenhuma (somente criação; sem diff conceitual em componente existente).

## T007 — Domínio local puro (2026-10-11)

`app/briefing/domain.py` recebeu dataclasses congeladas `Briefing`/`BriefingPoint` e operações locais de ciclo, snapshot imutável, validação 3–7 e identidade/versão em memória. Componente novo greenfield; LOW; não modifica entidades ou fluxo de pesquisa existente. `Research`, persistência, storage, migração, router e consulta histórica durável permanecem fora deste recorte (T011). Nenhuma I/O, rede, DB, prompt ou serviço foi introduzido.

## Entrega RED local — T004/T005 (2026-10-11)

Somente testes novos, sem mutação de produção. Arquivos preservados de entregas anteriores: `app/briefing/domain.py`, `app/briefing/schemas.py`, `app/briefing/prompt_loader.py`, `app/briefing/serp_client.py`, `tests/test_briefing_domain.py`, `tests/test_briefing_schemas.py`, `tests/test_briefing_prompt_loader.py`, `tests/test_briefing_serp_client.py`.

## T007 GREEN local — 2026-10-11

Implementação limitada ao domínio puro em `app/briefing/domain.py`; helpers auditados preservados. GREEN: 46 testes da suíte `test_briefing_*.py`; baseline 30 testes existentes; compile e diff-check verdes. Probe complementar cobre edição/aprovação 3–7, retenção de espaços, entrada mutável e rejeição sem mutar snapshot. T004/T005 continuam abertos até gates integrados T010/T011; auditoria independente pós-implementação pendente.

## QA Sprint 4 (2026-10-11)

Suite de testes `tests/test_briefing_*.py` executa 49 testes verdes (baseline 30 + 19 novos). Cobertura: validação tema/pontos, ciclo completo geração→rascunho/aprovação/falha, edição/aprovação 3–7, snapshots imutáveis, identidade/versão/isolamento, rejeição de entradas inválidas e isolamento de entradas mutáveis, cópia defensiva de Mapping não-dict, domínio puro e testes QA locais sem I/O/DB/rede; suíte completa usa fixtures locais de prompt e transporte simulado, sem serviços externos reais. Compilação `python3 -B -m py_compile` e `git diff --check` limpos.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| tests/test_briefing_validation.py | Validação local do briefing (T004, RF-01) | componente-novo | LOW | Teste RED unittest stdlib contra contrato `new_briefing`/`validate_theme` do adendo T007; fronteiras 2/3/300/301, strip, tipos; sem I/O |
| tests/test_briefing_lifecycle.py | Ciclo local do briefing (T005, RF-05/RF-06/RF-09) | componente-novo | LOW | Teste RED unittest stdlib contra contrato de operações/snapshot/identidade/isolamento do adendo T007; sem implementação de domínio |
| tests/test_briefing_lifecycle_qa.py | QA complementar T007 e ciclo (T004/T005 local, RF-05/RF-06/RF-09) | componente-novo | LOW | Testes stdlib unittest cobrindo matriz de edição/aprovação 3–7, snapshots imutáveis, versões exatas e cópia de Mapping não-dict; sem I/O |


## T017 — Fronteira numérica de timeout (2026-10-11)

Correção do achado F-contratos-01 da inspeção em `app/briefing/service.py`: `_valid_config` captura `OverflowError` na conversão `float(llm_timeout_s)` e lança `ValueError("Configuração de timeout LLM inválida")` antes de chamar `math.isfinite`. Garante tratamento seguro e sem I/O para inteiros extremos (-10**1000, +10**1000). Teste unitário RED/GREEN adicionado em `tests/test_briefing_generation.py` (`test_extreme_numeric_timeout_values_raise_value_error_before_io`).

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/briefing/service.py | Validação de timeout LLM (T017, F-contratos-01) | regra-alterada | LOW | Conversão segura para float tratando OverflowError e lançando ValueError antes de math.isfinite |
| tests/test_briefing_generation.py | Teste de fronteira numérica timeout (T017) | componente-novo | LOW | Subtestes para -10**1000 e +10**1000 garantindo ValueError sem chamadas I/O |

## T020 — ORM briefing + conversores puros (2026-10-11)

`app/models/domain_models.py` recebe `BriefingRecord` (`briefings`) e `BriefingVersion` (`briefing_versions`) conforme D2: UUID pk default uuid4, theme String(300), status String(20), version Integer, points_json JSON default list, error Text, approved_at/created_at/updated_at TIMESTAMPTZ com `now()` tz-aware. `BriefingVersion` com FK `briefings.id` ondelete CASCADE, UniqueConstraint `uq_briefing_version(briefing_id, version)` e índice `(briefing_id, version)`. Nenhuma FK para `Research`/`ResearchPoint`. `app/models/__init__.py` exporta novos modelos. `app/briefing/storage.py` novo com conversores puros `briefing_to_record`/`record_to_briefing`/`briefing_to_version_dict`/`points_to_json`/`json_to_points`. Componente novo greenfield; sem migração real (T021), sem banco/rede.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/models/domain_models.py | ORM briefing persistente (T020, D2) | componente-novo | LOW | Duas tabelas isoladas do domínio pesquisa; sem tocar modelos legados |
| app/models/__init__.py | Exports dos modelos (T020) | regra-alterada | LOW | Adição de `BriefingRecord`, `BriefingVersion` a imports/`__all__`; demais exports intactos |
| app/briefing/storage.py | Conversores domain↔snapshot (T020) | componente-novo | LOW | Funções puras sem I/O/DB; round-trip preserva id/theme/status/version/points/error/approved_at |
| tests/test_briefing_storage_converters.py | Regressão dos conversores/ORM (T020) | componente-novo | LOW | 7 testes stdlib unittest: round-trip 4 estados, isolamento tupla, UUID nativo, timestamps, constraints e isolamento |

## T021 — Migração Alembic 0006 briefings + briefing_versions (2026-10-11)

`alembic/versions/0006_briefing_storage.py` cria as tabelas `briefings` e `briefing_versions` idênticas aos ORMs definidos em T020: `briefings` com `id` UUID pk, `theme` String(300), `status` String(20), `version` Integer, `points_json` JSON default `[]`, `error` Text, `approved_at/created_at/updated_at` TIMESTAMPTZ com `now()` tz-aware; `briefing_versions` com `id` UUID pk, `briefing_id` UUID FK `briefings.id` ondelete CASCADE, `version` Integer, `status` String(20), `points_json` JSON, `error` Text, `approved_at/created_at` TIMESTAMPTZ com `now()`, UniqueConstraint `uq_briefing_version(briefing_id, version)` e índice `ix_briefing_versions_briefing_id_version`. `downgrade()` remove índice, `briefing_versions`, `briefings` na ordem inversa. Testes isolados em `tests/test_briefing_migration.py` usam SQLite temporário via `sqlite+aiosqlite` com patch em `app.core.config.settings.DATABASE_URL`; 3 testes: upgrade/downgrade reversíveis, tabelas presentes pós-upgrade (colunas, constraint única, índice), tabelas ausentes pós-downgrade. Sem tocar banco real; sem alterar migrações 0001–0005.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| alembic/versions/0006_briefing_storage.py | Migração durável de briefing (T021, D2) | componente-novo | LOW | Migração aditiva isolada; sem tocar modelos/migrações legados |
| tests/test_briefing_migration.py | Regressão da migração (T021) | componente-novo | LOW | unittest stdlib com SQLite temporário; upgrade head + downgrade 0005 reversível; 3 testes |

## T022 — Storage assíncrono Tx1 / CAS Tx2 (2026-10-11)

`app/briefing/storage.py` expandido com funções assíncronas de persistência contra `AsyncSession` do SQLAlchemy: `create_generating_briefing` (Tx1: insere `BriefingRecord` inicial e `await db.commit()`), `get_briefing` (consulta via `db.get` e `record_to_briefing`), `get_briefing_versions` (consulta `BriefingVersion` filtrando por `briefing_id` ordenada por `version ASC`), `save_briefing_transition` (Tx2 CAS: executa `UPDATE briefings ... WHERE id=:id AND version=:old_v`, valida `rowcount == 1` — se colisão faz rollback e lança `BriefingVersionConflictError`, em sucesso insere `BriefingVersion` e faz `await db.commit()`). Suíte assíncrona focada em `tests/test_briefing_storage.py` usando `aiosqlite` em memória isolado via `create_async_engine('sqlite+aiosqlite:///:memory:')` e `Base.metadata.create_all`: ciclo completo generating→draft→edit→approve (versões monotônicas ordenadas ASC [2, 3, 4]), get inexistente retornando None/[], points_json limpo com UUID preservado, e colisão concorrente CAS disparando `BriefingVersionConflictError` e preservando estado anterior após rollback. Sem tocar banco real nem alterar outros módulos.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/briefing/storage.py | Storage assíncrono Tx1/CAS Tx2 (T022, D1/D2/D3) | regra-alterada | LOW | Expansão de módulo novo; adiciona persistência assíncrona sem tocar modelos legados |
| tests/test_briefing_storage.py | Regressão do storage assíncrono (T022) | componente-novo | LOW | 4 testes IsolatedAsyncioTestCase em SQLite memória isolado; ciclo completo, get_none, points_clean, CAS conflict |


## T023 — Binding LiteLLM role scout (2026-10-11)

`app/briefing/llm_binding.py` novo: fábrica `make_scout_complete(db, default_timeout_s=30.0)` retorna `scout_complete(system, user, timeout_s=None) -> Awaitable[str]`. Correção de evidência explícita T023: uma chamada `acompletion` mockada não provava requests isolados do SDK. Inspecionado por auditor (`_reversa_bugs/modulo-briefing/inspections/t023-t028-binding/report.md`): LiteLLM 1.104.0 com resposta 503 uniforme realiza 3 requests HTTP devido ao retry interno do SDK (`max_retries` não zerado no cliente async), transação do banco permanece ativa durante chamada LLM (`db.get` abre autobegin) e exceções `APIConnectionError` e `InternalServerError` (500) não viravam `LLMAttemptError` (propagavam exceção bruta com segredo fictício). T028 timeout local passou com validação pré-I/O. Gates T025/T026/T012/T013 continuam abertos.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/briefing/llm_binding.py | Binding LLM role scout (T023, D5) | componente-novo | MEDIUM | Fronteira de I/O externo; achados F-CONTRACT-01 (3 requests 503), F-CONSISTENCY-01 (DB transaction active during LLM) e F-ERROR-01 confirmados pelo auditor. |
| tests/test_briefing_llm_binding.py | Regressão do binding (T023) | componente-novo | LOW | 10 testes IsolatedAsyncioTestCase em mocks; não cobre retries internos do SDK nem transação ativa. |

## Evidência de QA — Sprint 6 e Sprint 7 (2026-10-11)

Gate `PASS_LOCAL` restrito aos recortes de testes em SQLite isolado e fakes locais em memória, sem PostgreSQL, sem API/HTTP, sem live providers nem rede. T029–T031 abertas e planning rejeitado; não se alega implementação dessas tarefas.

### Sprint 6 — Storage QA (T020–T022)
- Relatório de QA: `_reversa_forward/001-modulo-briefing/audit/qa-sprint6-storage.md`
- Inspeção profunda: `_reversa_bugs/modulo-briefing/inspections/t020-t022-storage/report.md` (PASS)
- Artefato de testes mantido: `tests/test_briefing_storage_qa.py` (4 métodos async AST mantidos: `test_saved_edit_approve_reopen_history_is_immutable`, `test_stale_cas_keeps_exact_winner_and_history`, `test_history_insert_failure_rolls_back_update_with_caller_rollback`, `test_raw_canary_excluded_from_current_and_history_serialization`).
- Evidência: 4/4 PASS_LOCAL + 14 baseline. Testa imutabilidade de histórico, CAS com rollback, rollback de transação em falha de INSERT histórico e exclusão de canários na serialização.

### Sprint 7 — Orquestração Persistida QA (T024/T027)
- Relatório de QA: `_reversa_forward/001-modulo-briefing/audit/qa-sprint7-persisted.md`
- Inspeção independente: `_reversa_bugs/modulo-briefing/inspections/t024-t027-persisted/report.md` (PASS funcional, achados de cobertura)
- Artefato de testes mantido: `tests/test_briefing_persisted_orchestration_qa.py` (4 métodos async AST mantidos: `test_success_preserves_exact_points_in_return_current_and_history`, `test_invalid_content_retry_preserves_exact_recovered_points`, `test_four_domain_invalid_attempts_append_failed_safe_history`, `test_external_cancellation_after_llm_entry_commits_emergency_history`).
- Evidência: 4/4 PASS_LOCAL (F-test-01 igualdade exata dos pontos retornados (3 pontos na fixture de teste) e recuperação pós-falha; F-test-02 histórico append-only na exaustão; F-test-03 cancelamento externo com transação de emergência via `asyncio.Event`). Não cobre todo F-test-03 nem fecha orquestração geral. Os novos 4 métodos de storage e 4 de persistência são artefatos mantidos da suíte, NÃO 31 probes temporários.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| tests/test_briefing_storage_qa.py | QA Storage Sprint 6 | componente-novo | LOW | Artefato de teste mantido; 4 métodos cobrindo imutabilidade, CAS, rollback e canários em SQLite |
| tests/test_briefing_persisted_orchestration_qa.py | QA Orquestração Persistida Sprint 7 | componente-novo | LOW | Artefato de teste mantido; 4 métodos cobrindo F-test-01, F-test-02 e F-test-03 via asyncio.Event |

## T029 — Desativar retries internos SDK (F-CONTRACT-01)

`app/briefing/llm_binding.py` (~linha 81-85): adicionados `"num_retries": 0` e `"max_retries": 0` ao dict `kwargs` de `make_scout_complete`. Comentário F-CONTRACT-01 / RF-10 explica: one-attempt scout; retry/loop lifecycle é do orquestrador, não do SDK.

`tests/test_briefing_llm_binding.py`: dois novos testes mantidos:
- `test_no_internal_retries_on_503_openai_sdk` — RED: 3 requests HTTP com 503 (SDK retry); GREEN: 1 request (num_retries=0 + max_retries=0). Usa `httpx.MockTransport` + patch `BaseOpenAILLM._get_async_http_client` + fixture runtime_settings/get_record. Cenário OpenAI (litellm 1.104.0, openai 2.54.0, httpx 0.28.1); não cobre todos providers.
- `test_kwargs_include_no_retry_controls` — verifica `num_retries=0` e `max_retries=0` em happy path com AsyncMock, sem enfraquecer asserts existentes.

Todas assinaturas, defaults (`default_timeout_s`), callable `timeout_s`, guardrail, provider/model/auth preservados. Timeout override >30s continua OK (`test_valid_timeout_above_30_accepted`).

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/briefing/llm_binding.py | Binding LLM role scout (T023/D5 → T029 F-CONTRACT-01) | regra-alterada | LOW | Apenas 2 kwargs adicionados; sem mudança em comportamento/assinatura/defaults/guardrail/provider/model/auth |
| tests/test_briefing_llm_binding.py | Regressão do binding (T029) | componente-novo | LOW | 2 testes mantidos (RED/GREEN); suíte binding 12 testes; discover 128 testes; py_compile/diff-check verdes |

T030 (matriz de erros) e T031 (factory session ownership) permanecem abertas — dependências binding; API/QA/provedores não aprovados. História IDs preservada.

---

## T029 — Desativar retries internos SDK (F-CONTRACT-01) — CONCLUÍDA (2026-10-11)

- **Arquivos**: `app/briefing/llm_binding.py` (kwargs `num_retries=0`, `max_retries=0` adicionados em `make_scout_complete`), `tests/test_briefing_llm_binding.py` (2 testes mantidos: `test_no_internal_retries_on_503_openai_sdk` RED→GREEN 1 request, `test_kwargs_include_no_retry_controls`)
- **Reauditoria**: `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-recheck/report.md` — 3 observações LOW (O-TEST-01, O-DOC-01, O-DOC-02) **SANADAS**, confiança alta, `promoted_to: null`, zero defeitos de produto, zero bugs promovidos. Checks: unittest 12/12 OK, probe isolamento (seeds False/True) exit 0, `git diff --check` exit 0, baseline 95/95 SHA-256.
- **QA**: `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-qa/report.md` — **PASS_LOCAL**: 12/12 métodos binding OK, dois runs independentes SDK real (seeds False/False e True/True) com exatamente 1 POST `/v1/chat/completions`, `LLMAttemptError`, cliente HTTPX fechado, estados restaurados. Zero findings novos.
- **Status actions.md**: T029 `[X]`.

## T032 — Isolamento redirects (O-TEST-01) — CONCLUÍDA (2026-10-11)

- **Arquivo**: `tests/test_briefing_llm_binding.py` — cleanup restaura `follow_redirects` dos dois clientes globais LiteLLM mesmo semeados True, telemetry desativado só no escopo do teste, helper real preservado, `LLMAttemptError`/count1 mantidos.
- **Evidência**: Reauditoria `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-recheck/report.md` confirma O-TEST-01 SANADA (probe descriptors/flags/attrs/restaurados, exit 0). QA `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-qa/report.md` confirma isolamento em dois seeds (PASS_LOCAL).
- **Status actions.md**: T032 `[X]`.

## T033 — Documentação (O-DOC-01, O-DOC-02) — CONCLUÍDA (2026-10-11)

- **Arquivos**: `_reversa_forward/001-modulo-briefing/audit/t029-execution.md` (qualifica RED/GREEN histórico vs teste atual, helper real, contraprova auditor não reexecutada, discover físico zero barras), `_reversa_forward/001-modulo-briefing/regression-watch.md` (supersede parágrafo histórico :129, registra T024/T027 `[X]` e QA persistido local, mantém T030/T031/API abertos, T032 gate aberto não nega implementação).
- **Evidência**: Reauditoria `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-recheck/report.md` confirma O-DOC-01/O-DOC-02 SANADAS (leitura semântica, tabelas, referências, exit 0). QA `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-qa/report.md` valida checks documentais (PASS_LOCAL).
- **Status actions.md**: T033 `[X]`.

**T030 em execução** (matriz de erros F-ERROR-01: `APIConnectionError`/`InternalServerError` 500 → `LLMAttemptError` seguro). **T031 pendente** (ownership/settings factory, depende T030). API (T025/T026) bloqueada.

---

## Adendo T030/T031 pós-QA — vigente (2026-10-11)

**T030 e T031 IMPLEMENTADAS** — parent verificou, auditoria e QA aprovadas (`PASS_LOCAL`).
- T030 (matriz de erros F-ERROR-01): `_reversa_bugs/modulo-briefing/inspections/t030-error-matrix-qa/report.md` — 21/21 testes binding, 21 elegíveis → `LLMAttemptError`, 19 negativos propagam identidade, 13 status estritos, T029 preservado, 99/99 hashes congelados.
- T031 (ownership session_factory F-CONSISTENCY-01): `_reversa_bugs/modulo-briefing/inspections/t031-session-factory-qa/report.md` — 24/24 testes binding, 140 briefing; sessão própria curta fechada antes LLM; zero commit/rollback caller; early abort timeout com 0 chamadas factory; D3 SQLite flush revertido (0 linhas `AppSettings`); 102/102 hashes congelados.
- T025 **desbloqueada mas NÃO entregue** (coding gate bloqueado até delta S8 auditado).
- T026, T012, T013 pendentes.

**Factory vigente** (não substituir por estado anterior):
- `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s=30.0)` → callable `scout_complete(system, user, timeout_s=None)`.
- Validação `timeout_s` override **antes** de abrir sessão (early abort, zero boundary calls).
- Settings lidos em sessão própria curta (`async with session_factory() as session:`) → `runtime_settings` + `get_record` → copia escalares imutáveis (`keys`, `models`, `openai_base_url`) → fecha sessão **antes** de `_enforce_safe_transport()` e `litellm.acompletion`.
- Nenhuma finalização sessão caller-owned; `flush` first-use revertido pelo close sem commit.
- Preservados: `num_retries=0` + `max_retries=0` (T029), matriz T030, guardrail, `_enforce_safe_transport()`, validação T028.

**Assinaturas/execuções antigas** (ex.: status anterior "T030 em execução", "T031 pendente" acima) marcadas como **históricas** com adendo vigente; evidências conservadas nos relatórios de auditoria/QA e `progress.jsonl`.

**Contagens exatas atuais** (evidência parent/QA já gravada, não execução própria):
- 24 bindings (1 sync, 23 async) — `progress.jsonl:76` e `audit/t031-execution.md:8`.
- 140 briefing — `progress.jsonl:76` e QA reports.

**Não afirmar rede real nem banco real**; sem segredos.

---

## Entrega HTTP final T025/T026/T035/T036 (2026-10-11)

Suíte briefing: 183 testes verdes (`audit/t012-t036-execution.md:58`).

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/briefing/router.py | API canônica `/briefings` (D1, D3, D4) | componente-novo | MEDIUM | Rotas criar/obter/editar/aprovar/reabrir/consumir/versões; integrada em `app/main.py` via `include_router(briefing_router)` |
| app/briefing/schemas.py | Schemas D4 (T035) | regra-alterada | LOW | `BriefingResponse` com `version/error/approved_at`; `BriefingVersionResponse` criada |
| app/briefing/service.py | Orquestração de geração e persistida (T006/T010/T024/T027) | regra-alterada | LOW | `generate_briefing` (4 tentativas, reuso SERP, timeout por tentativa) e `orchestrate_persisted_briefing` (Tx1 reserva, Tx2 CAS; emergência `FAILED` best-effort) |
| app/briefing/storage.py | Persistência Tx1/CAS Tx2 (T022/T024) | regra-alterada | LOW | `create_generating_briefing`, `get_briefing`, `save_briefing_transition`; sem orquestração |
| app/briefing/llm_binding.py | Binding scout (T029–T031) | regra-alterada | LOW | `session_factory`, `num_retries=0`/`max_retries=0`, matriz T030 |

---

Âncora de produto: PRD + spec briefing; implementação local não fecha gates de API ou provedor real.

## E001 — Padrão scout/briefing Gemini 3.8 Flash

O pedido de modo Jina sem chave foi retirado pelo operador após GET e POST anônimos em `s.jina.ai` responderem 401 `AuthenticationRequiredError`; cliente Jina e autenticação da API permanecem intactos. Emenda vigente altera somente o padrão scout. Modelos explícitos no banco ou em `SCOUT_MODEL` mantêm precedência; configurações existentes e demais roles não são migradas.

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| app/services/settings.py | Resolução de modelo scout | regra-alterada | LOW | `DEFAULT_ROLE_MODELS["scout"]` passa a `gemini/gemini-3.8-flash`; `runtime_settings()` usa esse fallback somente na ausência de modelo scout no banco e ambiente. |
| tests/test_briefing_llm_binding.py | Regressão E001 | regra-alterada | LOW | Teste durável invoca `runtime_settings()` e `make_scout_complete()` reais com sessão/transporte simulados; RED: padrão antigo; GREEN: novo padrão chega a `acompletion`. |

Evidência local: teste E001 falhou com `AssertionError` (exit 1) antes das duas linhas de produção; depois passou (exit 0). Suíte briefing: 184 testes OK (exit 0). Três testes de configurações HTTP em `tests/test_backend.py` passaram (exit 0). Seleção mais ampla `-k 'settings or model'` também incluiu pipeline legado: 6 passaram e 1 falhou em `tests/test_backend.py:316` (`failed` versus `pending_approval`). A mesma falha foi reproduzida em cópia isolada no scratch com apenas as duas linhas E001 revertidas; não foi corrigida nesta emenda. `git diff --check` limpo.

Limites: default e encaminhamento ao SDK comprovados localmente; geração autenticada com provedor LLM real não executada. E001 implementada não fecha T012, QA final independente ou sync.
