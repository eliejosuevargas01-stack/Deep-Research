# Regression watch: 001-modulo-briefing (T001-T002)

- Risco baixo: sem alteração em código existente.
- Monitorar quando T007+ (persistência, router) integrarem `domain.py` e `schemas.py`.
- Self-check inline cobre fronteiras de tema (2/3/300/301), pontos (2/3/7/8), título vazio, transições.

## Histórico de re-extrações

(vazio)

## Arquivadas

(vazio)

## Observações — T014/T015 (2026-10-11)

Feature greenfield, sem regras 🟢 extraídas para vigiar; RFs implementados registram-se aqui sem peso de regressão até futura re-extração. Itens W003–W005 cobrem as correções F-01/F-02 e a decisão F-03.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W003 | requirements.md RN-03/RF-06; audit inspecao-t001-t002.md F-01 | `BriefingResponse.status` somente aceita `generating/draft/failed/approved`; JSON Schema expõe enum | Teste unittest `tests/test_briefing_schemas.py::test_states_serialize_and_json_schema_lists_enum`, `::test_unknown_status_is_rejected` | `BriefingResponse(status="banana")` validar; JSON Schema de status voltar a ser string livre |
| W004 | requirements.md RN-03/RN-05; audit inspecao-t001-t002.md F-02 | Respostas com conteúdo (`draft`/`approved` e `ApprovedBriefingResponse`) exigem 3–7 pontos; `generating`/`failed` aceitam lista vazia | Teste unittest `tests/test_briefing_schemas.py::test_draft_and_approved_require_three_to_seven_points`, `::test_approved_response_requires_three_to_seven_points`, `::test_generating_and_failed_allow_empty_points` | Resposta aprovada serializar 0/2/8 pontos; mínimo imposto a `generating`/`failed` |
| W005 | data-delta.md Decisão Arquitetural (F-03) | Entidade briefing isolada, sem `Research`/`ResearchPoint`/`ResearchStatus`; reutilização futura apenas de infraestrutura DB/auth | Revisão de artefato: data-delta.md + roadmap.md Persistência | T007/T011 introduzirem import de `Research`/`ResearchStatus` no módulo `app/briefing/` ou migration editando modelos legados |

## Observações — T008 (2026-10-11)

Feature greenfield, sem regras 🟢 extraídas para vigiar; RFs implementados registram-se aqui sem peso de regressão até futura re-extração.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W001 | requirements.md RF-04 (RN-04) | Prompt de briefing lido do disco a cada chamada, sem cache entre gerações | Teste unittest `tests/test_briefing_prompt_loader.py::test_each_call_reads_updated_file` | Edição do arquivo não refletir na próxima chamada de `load_briefing_prompt` |
| W002 | requirements.md RF-08 (interfaces/briefing-http.md Erros) | Arquivo ausente/vazio levanta `PromptUnavailable` com mensagem fixa antes de qualquer chamada ao agente | Teste unittest `tests/test_briefing_prompt_loader.py::test_missing_prompt_raises_safe_configuration_error`, `::test_empty_prompt_raises_safe_configuration_error` | Caminho absoluto, conteúdo do prompt ou segredo aparecer na mensagem de erro; agente ser chamado com prompt inválido |

## Observações — T009 (2026-10-11)

Feature greenfield, sem regras 🟢 extraídas para vigiar; RFs implementados registram-se aqui sem peso de regressão até futura re-extração.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W006 | requirements.md RF-02/RN-02; interfaces/jina-serp.md §2 | `JinaSerpClient.search` faz POST exclusivamente em `https://s.jina.ai/` com `X-Respond-With: no-content`, sem Reader, sem visita às URLs retornadas, redirects desativados | Teste unittest `tests/test_briefing_serp_client.py::test_success_posts_only_to_jina_and_exports_required_fields`, `::test_redirect_is_not_followed_and_does_not_leak_authorization` | Requisição a `r.jina.ai` ou URL de resultado; header `no-content` ausente; redirect seguido |
| W007 | requirements.md RF-10 (RN-02); interfaces/jina-serp.md §6 | Até 4 tentativas totais sequenciais por operação; sucesso encerra imediatamente; uma chamada ativa por instância (lock asyncio) | Teste unittest `tests/test_briefing_serp_client.py::test_retries_sequentially_at_most_four_total_then_succeeds`, `::test_two_operations_on_same_client_never_overlap` | 5ª tentativa; chamadas sobrepostas na mesma instância; nova busca após sucesso |
| W008 | requirements.md RF-08; RNF-02 Segurança | Erro `SerpSearchError` com mensagem fixa e tentativas reais; sem chave, corpo bruto, URL query ou exceção repr em erro/log | Teste unittest `tests/test_briefing_serp_client.py::test_exhaustion_raises_safe_error_with_real_attempt_count`, `::test_invalid_theme_key_and_timeout_fail_before_io` (canary FICTÍCIO via assert bool) | Segredo, tema ou corpo de resposta aparecer em `str(exc)`/logs; erro de programação convertido em retentativa externa |

## Observações — T016

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W009 | actions.md T016; interfaces/jina-serp.md §7 | `JinaSerpClient.__init__` rejeita chave vazia, não-ASCII, espaços e controles antes de I/O, com mensagem fixa `Chave de API inválida` | Teste unittest `tests/test_briefing_serp_client.py::test_api_key_validation_rejects_non_printable_ascii_control_whitespace_and_non_ascii`; probe de zero chamadas ao transporte | Entrada inválida passar pelo construtor; mensagem incluir entrada; transporte chamado |

## Observações — T004/T005 RED local (2026-10-11)

Feature greenfield; regras registradas como contratos propostos do adendo T004/T005/T007, sem peso de regressão legada. T004/T005 continuam abertos até gates integrados de T010/T011.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W010 | data-delta.md § Contrato local puro T004/T005/T007; actions.md T004/T005 | Domínio puro valida/normaliza tema 3–300; ciclo immutable generating→draft/failed, draft→approved, approved→draft; pontos válidos 3–7; operações inválidas não alteram snapshot; ID/versão/isolamento/read-approved conforme contrato | Testes unittest `tests/test_briefing_validation.py` e `tests/test_briefing_lifecycle.py` contra domínio real | Símbolos ausentes ou contrato violado; T010 não comprova rejeição antes de I/O; T011 continua responsável por consulta durável/versão persistida |

## Observações — T007 GREEN local (2026-10-11)

Feature greenfield; regra registra o contrato implementado do adendo T004/T005/T007, sem peso de regressão legada. Persistência durável, histórico consultável, transação, concorrência e idempotência permanecem T011 e não foram implementadas.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W011 | data-delta.md § Contrato local puro T004/T005/T007; actions.md T007 | `app/briefing/domain.py` puro stdlib: `Briefing`/`BriefingPoint` frozen, operações `new_briefing`/`complete_briefing`/`fail_briefing`/`edit_briefing`/`approve_briefing`/`reopen_briefing`/`read_approved` preservam ID, incrementam versão uma única vez por operação aceita, recusadas preservam snapshot, validam atomicamente 3–7 via `validate_points`, aceitam Sequence de BriefingPoint/Mapping recusando str/bytes/não-sequência e itens inválidos com `InvalidContent`, sem I/O/DB/rede/prompt | Testes unittest `tests/test_briefing_validation.py`, `tests/test_briefing_lifecycle.py`, `tests/test_briefing_domain.py` (46 testes verdes) | Operação aceita sem version+1; snapshot anterior mutado; alias mutável entre entrada e snapshot; `complete_briefing` aceitar não-GENERATING; `reopen_briefing` aceitar não-APPROVED; `read_approved` expor estado não aprovado; qualquer I/O introduzido no domínio |
| W012 | audit/qa-sprint4.md; data-delta.md adendo T004/T005/T007 | Operações edit_briefing e approve_briefing mantêm imutabilidade, ordem e contagens 3–7 em todas as faixas (3, 4, 5, 6, 7); fail_briefing version=2; reopen limpa timestamp; entradas mutáveis não vazam alias; snapshots rejeitados preservam estado anterior | Teste unittest tests/test_briefing_lifecycle_qa.py::BriefingLifecycleQATests (3 métodos; 49 testes na suíte) | Falha de assert em versão/snapshot; contaminação de entrada mutável pós-operação; regressão nos 49 testes |

## Observações — T006/T010 GREEN local (2026-10-11)

Feature greenfield; regra registra o contrato implementado do adendo T006/T010 do roadmap, sem peso de regressão legada. Binding LLM real, persistência e QA runtime permanecem T011/T012.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W013 | roadmap.md § Adendo T006/T010; data-delta.md § Contrato de geração; actions.md T006/T010 | `generate_briefing` valida config (attempts int não-bool 1..4, timeout finito >0) antes de I/O; tema inválido com zero chamadas loader/SERP/LLM; loader inválido/`PromptUnavailable` → FAILED antes de SERP/LLM preservando system válido; `search` exatamente 1 vez por geração (retry interno do cliente); loop ≤4 sequencial reusa mesma SERP; timeout por tentativa via `asyncio.timeout` com `.expired()`; `CancelledError` propaga sem retry/fail; parse JSON puro ou cerca ```json única exata, lista integral; `complete_briefing` valida 3–7; erros fixos sem payload/segredo; sequencial por invocação sem lock global | Testes unittest `tests/test_briefing_generation.py` (29 testes: matriz a–m, timeout, cancel, concorrência por invocação, composição real `JinaSerpClient` com MockTransport, loader real tempfile) | Segundo `search` por geração; retry além de 4; `TimeoutError` do callable tratado como tentativa; cerca parcial/garbage aceito; payload/segredo em `Briefing.error`; capture ampla de `Exception`/`TypeError` escondendo bug; lock global de serviço introduzido |

## Observações — T017 Fronteira numérica timeout (2026-10-11)

Feature greenfield; regra registra a correção F-contratos-01 da inspeção, sem peso de regressão legada.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W014 | _reversa_bugs/modulo-briefing/inspections/t006-t010-service/report.md F-contratos-01; actions.md T017 | `_valid_config` converte `llm_timeout_s` para float tratando `OverflowError` (inteiros extremos ±10**1000) e lança `ValueError("Configuração de timeout LLM inválida")` antes de `math.isfinite`; zero I/O | Teste unittest `tests/test_briefing_generation.py::GenerationTests::test_extreme_numeric_timeout_values_raise_value_error_before_io` (subtests -10**1000, +10**1000) | `OverflowError` vazar; `ValueError` não lançado; chamada I/O (loader/SERP/LLM) ocorrer antes da validação |

## Observações — T020 ORM + conversores (2026-10-11)

Feature greenfield; regra registra ORM isolado e conversores puros D1/D2, sem peso de regressão legada. Migração real (T021) e storage assíncrono (T022) pendentes.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W015 | audit/t011-integration-decomposition.md D2; actions.md T020 | `briefings`/`briefing_versions` existem com UUID pk uuid4, `uq_briefing_version(briefing_id, version)`, índice `(briefing_id, version)`, FK cascade só para `briefings`; nenhuma FK para `research`/`research_points` | Teste unittest `tests/test_briefing_storage_converters.py::TestOrmMapping` | FK para pesquisa; constraint/índice ausente; coluna theme/status com tamanho errado |
| W016 | audit/t011-integration-decomposition.md D1/D2; actions.md T020 | Conversores puros fazem round-trip exato (id/theme/status/version/points/error/approved_at) em generating/draft/failed/approved; tupla imutável sem alias; UUID nativo preservado | Teste unittest `tests/test_briefing_storage_converters.py::TestBriefingConverters`, `::TestPointsConverters` | Snapshot mutado; alias de entrada; status string em vez de `BriefingStatus`; approved_at perdido |

## Observações — T021 Migração Alembic 0006 (2026-10-11)

Feature greenfield; regra registra migração Alembic 0006 aditiva para persistência SQL de briefings, sem peso de regressão legada.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W017 | audit/t011-integration-decomposition.md D2; actions.md T021 | Migração 0006 cria tabelas `briefings` e `briefing_versions` com colunas/tipos/constraints exatos do D2, upgrade/downgrade reversíveis sem tocar DB real | Teste unittest `tests/test_briefing_migration.py::BriefingMigrationTests` (3 testes) | Downgrade falhar; tabelas ausentes pós-upgrade; índice ou FK com nome/relação incorreta |

## Observações — T022 Storage assíncrono Tx1/CAS Tx2 (2026-10-11)

Feature greenfield; regra registra storage assíncrono com transações atômicas curtas e CAS, sem peso de regressão legada. Binding LLM (T023), orquestração persistida (T024) e API (T025/T026) pendentes.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W018 | audit/t011-integration-decomposition.md D1/D3; actions.md T022 | `create_generating_briefing` faz Tx1 única (INSERT generating v1 + commit imediato liberando conexão); `get_briefing` retorna snapshot corrente ou None; `get_briefing_versions` retorna histórico `version ASC` | Teste unittest `tests/test_briefing_storage.py::TestStorageCycle::test_full_cycle_generating_draft_edit_approved`, `::test_get_missing_returns_none_and_history_empty` (aiosqlite :memory:) | Commit ausente ou transação longa; histórico desordenado; get sem isolamento |
| W019 | audit/t011-integration-decomposition.md D2/D3; actions.md T022 | `save_briefing_transition` CAS: UPDATE `WHERE id AND version=old_v`; `rowcount != 1` → rollback limpo + `BriefingVersionConflictError` preservando estado anterior; sucesso grava `briefing_versions` atomicamente na mesma Tx2; `points_json` persiste apenas pontos limpos `{title, description}` e UUID preservado | Teste unittest `tests/test_briefing_storage.py::TestStorageCycle::test_stale_cas_raises_and_preserves_state`, `::test_points_json_only_clean_points_and_uuid_preserved` | Estado corrompido pós-conflito; versão sobrescrita sem CAS; payload bruto/segredo em `points_json`; UUID alterado |

## Observações — T023 Binding LiteLLM one-attempt (2026-10-11)

Feature greenfield; regra registra o contrato do binding one-attempt D5, sem peso de regressão legada. Orquestração persistida (T024), API (T025/T026) e QA runtime com binding real (T012) pendentes.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W020 | audit/t011-integration-decomposition.md D5; actions.md T023 | `make_scout_complete(db)` retorna callable que faz exatamente 1 `litellm.acompletion` com modelo role `scout`, chave do provedor, `timeout = timeout_s or default_timeout_s`, mensagens system+user, `api_base` apenas openai/litellm validado, `_enforce_safe_transport()` aplicado; sem retry/router/sleep | Teste unittest `tests/test_briefing_llm_binding.py::BindingTests::test_single_call_with_scout_model_and_key`, `::test_timeout_override_passed_through` | 2ª chamada `acompletion` após falha; sleep/backoff; timeout default ignorado; `api_base` passado sem validação |
| W021 | audit/t011-integration-decomposition.md D5; actions.md T023 | Erro transitório (429/5xx/timeout/rede) vira `LLMAttemptError` (mensagem fixa, sem traceback/segredo); 401/403/`ProviderConfigurationError` propagam diretamente sem máscara `LLMAttemptError` | Teste unittest `tests/test_briefing_llm_binding.py::BindingTests::test_transient_becomes_attempt_error_no_retry`, `::test_auth_error_propagates_unmasked`, `::test_config_error_from_provider_propagates`, `::test_missing_model_and_key_raise_config_directly` | Traceback ou segredo em `str(exc)`; auth error convertido em `LLMAttemptError`; configuração ausente mascarada |
| W022 | audit/t011-integration-decomposition.md D5; actions.md T023 | Saída do LLM passa por `apply_output_guardrail` com `extra_sensitive_values` = chaves configuradas; segredo configurado em `str(exc)` do RuntimeError do guardrail; chave/bearer/prompt interno bloqueado | Teste unittest `tests/test_briefing_llm_binding.py::BindingTests::test_secret_in_output_blocked_by_guardrail` | Saída com chave de API retornada como texto; valores extras ausentes do guardrail |

## Observações T027/T028 — gates locais (sem peso de regressão legada)

- RF-03/RF-10: JSON parseável inválido consome tentativa LLM; SERP obtida reutilizada. Regressões: `test_persisted_invalid_content_retry_then_success`, `test_persisted_invalid_content_exhaustion`.
- Timeout configurável: extremos de ambos sinais produzem ValueError seguro; override rejeitado antes de settings e transporte; positivos finitos acima de 30s aceitos. Regressões: `test_default_timeout_validation_overflow_and_invalid`, `test_timeout_override_validation_early_abort_zero_boundary_calls`, `test_valid_timeout_above_30_accepted`.
- Gates Sprint7 independentes pendentes; unitários não verificam provider real, API ou toda política de transação.

### Qualificação de observações históricas (sem apagar história)

- **W020/W021 (históricas)**: alegação "exatamente 1 `litellm.acompletion`" e "erro transitório vira `LLMAttemptError`" eram incompletas. Auditor confirmou em `_reversa_bugs/modulo-briefing/inspections/t023-t028-binding/report.md`: F-CONTRACT-01 — SDK faz 3 requests 503 por `acompletion` (retry interno não zerado); F-CONSISTENCY-01 — transação DB ativa durante chamada LLM; F-ERROR-01 — `APIConnectionError`/`InternalServerError` (500) não viram `LLMAttemptError`, propagam exceção bruta com segredo fictício. T028 timeout pré-I/O passou.

T029 (2026-10-11) encerra parcialmente **W020 F-CONTRACT-01**: `make_scout_complete` agora passa `num_retries=0` e `max_retries=0` a `litellm.acompletion`, reduzindo para exatamente 1 request HTTP em 503 (verificado via `httpx.MockTransport` + patch `BaseOpenAILLM._get_async_http_client`). Teste mantido `test_no_internal_retries_on_503_openai_sdk` (RED 3→GREEN 1). **W020 permanece parcialmente aberta**: W021/W022 (guardrail/erro) e W020 (segunda chamada `acompletion` após falha) continuam pendentes para T024 orquestração — T029 não altera retry/loop lifecycle que ainda é do orquestrador (T030 matriz de erros). **Histórico IDs preservado**.

### Sprint 6 Storage QA — 4 métodos exatos (AST `tests/test_briefing_storage_qa.py::TestBriefingStorageQA`)

| ID | Método (linha) | Critério |
|---|---|---|
| W023 | `test_saved_edit_approve_reopen_history_is_immutable:63` | RF-05/RF-06/RF-09/D2/D3: edição salva conteúdo exato/reordenado, UUID, versões monotônicas, consulta pós-fechar sessão; aprovação, edição proibida, reabertura remove aprovação; histórico ASC, snapshots intactos, timestamp aprovado preservado; CAS obsoleto não muda vencedor |
| W024 | `test_stale_cas_keeps_exact_winner_and_history:99` | D3: CAS obsoleto não muda current/history vencedor |
| W025 | `test_history_insert_failure_rolls_back_update_with_caller_rollback:113` | D3: falha INSERT histórico reverte UPDATE observado na mesma conexão/transação; caller recupera sessão |
| W026 | `test_raw_canary_excluded_from_current_and_history_serialization:142` | D2/dados limpos: canário em extras ausente na serialização de colunas current/history |

Baseline explícito: 14 métodos `tests/test_briefing_storage_converters` (7), `tests/test_briefing_migration` (3), `tests/test_briefing_storage` (4) — 14/14 PASS. QA storage gate: `PASS_LOCAL`.

### Sprint 7 Orquestração Persistida QA — 4 métodos exatos (AST `tests/test_briefing_persisted_orchestration_qa.py::TestPersistedOrchestrationQA`)

| ID | Método (linha) | Critério |
|---|---|---|
| W027 | `test_success_preserves_exact_points_in_return_current_and_history:87` | F-test-01: sucesso com igualdade exata de `BriefingPoint` em retorno, corrente e histórico |
| W028 | `test_invalid_content_retry_preserves_exact_recovered_points:95` | F-test-01: recuperação pós-falha inválida sem resíduos parciais |
| W029 | `test_four_domain_invalid_attempts_append_failed_safe_history:146` | F-test-02: exaustão 4 tentativas com histórico v2 failed e erro seguro |
| W030 | `test_external_cancellation_after_llm_entry_commits_emergency_history:152` | F-test-03: cancelamento via `asyncio.Event` com transação de emergência e histórico v2 |

QA orquestração gate: `PASS_LOCAL` para conteúdo/histórico/cancelamento solicitados; não cobre todo F-test-03 nem fecha orquestração geral. Novos 4 métodos de storage + 4 de persistência são artefatos mantidos da suíte, NÃO 31 probes temporários.

### Qualificação de observações históricas (sem apagar história)

- **W020/W021 (históricas)**: alegação "exatamente 1 `litellm.acompletion`" e "erro transitório vira `LLMAttemptError`" eram incompletas. Auditor confirmou em `_reversa_bugs/modulo-briefing/inspections/t023-t028-binding/report.md`: F-CONTRACT-01 — SDK faz 3 requests 503 por `acompletion` (retry interno não zerado); F-CONSISTENCY-01 — transação DB ativa durante chamada LLM; F-ERROR-01 — `APIConnectionError`/`InternalServerError` (500) não viram `LLMAttemptError`, propagam exceção bruta com segredo fictício. T028 timeout pré-I/O passou.
- **W022 (redação)**: "segredo configurado em `str(exc)` do RuntimeError do guardrail" — adendo explícito: o probe no parent confirmou apenas que o segredo literal NÃO aparece em `str(exc)` nem em `repr(e.args)`; o guardrail bloqueia o vazamento sem incluir o segredo literal na mensagem ou argumentos da exceção. Leitura da função fonte `apply_output_guardrail` (`app/services/llm.py:141-161`, sem segredos nem configuração) confirma o ramo de segredo configurado (`:155`): `RuntimeError("Guardrail: agent output contained sensitive configured secrets or credentials")`, e o ramo regex (`:159`): `RuntimeError("Guardrail: agent output contained secrets or internal prompt material")` — mensagens fixas genéricas, sem o valor sensível. Teste fixture alterada (`«redacted:sk-…»`) confirma força do guardrail sem falso positivo regex genérica.

### Adendo T029 — qualificação vigente; parágrafo :129 supersedido/qualificado (2026-10-11)

- **T024/T027 implementadas** com QA persistido local em `audit/qa-sprint7-persisted.md` (fonte congelada) e actions `[X]`. T029 corrigiu retries SDK no recorte OpenAI 503; auditor **produto PASS**, evidência **CONDITIONAL**, QA T029 pendente. **Não inventar pendência T024 "segunda acompletion"**.
- **T030** matriz segura e **T031** ownership/settings continuam `[ ]`; **T025** API ainda bloqueada.
- **T032** observado como ação corretiva aberta (cleanup O-TEST-01), não como entregue.
- **W020** não integralmente aprovado: parent fará closure após gates. Preserve texto histórico e IDs W020/W021/W022; append permitido por skill. Nenhum novo watch ID necessário.

### Adendo T029/T032/T033 — encerramento comprovado (2026-10-11)

**O-TEST-01 (T032), O-DOC-01 (T033), O-DOC-02 (T033) COMPROVADAS SANADAS** pela reauditoria `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-recheck/report.md` (3 LOW sanadas, confiança alta, `promoted_to: null`, zero defeitos de produto, zero bugs promovidos) e confirmadas pela QA `_reversa_bugs/modulo-briefing/inspections/t029-sdk-retries-qa/report.md` (**PASS_LOCAL**: 12/12 métodos binding OK, dois runs independentes SDK real com 1 POST `/v1/chat/completions`, `LLMAttemptError`, estados restaurados, zero findings novos).

- **O-TEST-01**: Probe isolamento (seeds False/True) exit 0; descriptors/flags/attrs/redirects restaurados; telemetry só no escopo do teste; helper real preservado; count 1 POST `/v1/chat/completions` + `LLMAttemptError`.
- **O-DOC-01**: `audit/t029-execution.md` qualifica RED/GREEN histórico vs teste atual (helper real), contraprova auditor não reexecutada, discover físico zero barras, checks semânticos exit 0.
- **O-DOC-02**: `regression-watch.md:158–163` supersede :129; T024/T027 `[X]` e QA persistido local referenciados; T030/T031/API abertos mantidos; T032 gate aberto não nega implementação.

**Status actions.md**: T029 `[X]`, T032 `[X]`, T033 `[X]`. **T030 e T031 permanecem como ações abertas** (matriz erros F-ERROR-01 e ownership/settings factory).

IDs históricos preservados. Nenhum novo watch ID.

---

## Adendo T030/T031 pós-QA — rastreabilidade mecânica (2026-10-11)

**T030 e T031 FECHADAS por inspeção/QA** — `actions.md [X]` confirmado.
- T030 (matriz erros F-ERROR-01): QA `_reversa_bugs/modulo-briefing/inspections/t030-error-matrix-qa/report.md` — **PASS_LOCAL** 21/21 binding, 137 briefing (T030 fase); 21 elegíveis → `LLMAttemptError` fixa, 19 negativos identidade, 13 status estritos, T029 mantido, 99 hashes.
- T031 (ownership F-CONSISTENCY-01): QA `_reversa_bugs/modulo-briefing/inspections/t031-session-factory-qa/report.md` — **PASS_LOCAL** 24/24 binding, 140 briefing; sessão curta fechada antes LLM; zero commit/rollback; early abort 0 factory calls; D3 flush revertido; 102 hashes.

**Factory vigente** (referência para watches futuros):
- `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s=30.0)` → `scout_complete(system, user, timeout_s=None)`.
- Validação `timeout_s` override **antes** de sessão/I/O (early abort, `factory.call_count == 0`).
- Sessão própria `async with session_factory() as session:` → `runtime_settings` + `get_record` → copia escalares → close **antes** de transporte/LLM.
- Zero `commit()`/`rollback()` caller-owned; flush first-use revertido.
- Preservados: `num_retries=0`, `max_retries=0` (T029), matriz T030, guardrail, `_enforce_safe_transport()`, validação T028.

**Desbloqueios/pendências**:
- T025 **desbloqueada mas NÃO entregue** (coding gate bloqueado até delta S8 auditado).
- T026, T012, T013 pendentes.

**Histórico IDs W preservado** (append-only, sem apagar observações antigas). Contexto greenfield mantido em `legacy-impact.md`. Contagens 24 bindings / 140 briefing são evidência parent/QA já gravada. Não afirmar rede real nem banco real; sem segredos.

## Observações — Entrega HTTP final (T037, 2026-10-11)

Feature greenfield; registra componentes finais entregues, sem peso de regressão legada. Suíte briefing 183 testes verdes (reexecutada na convergência T037). Gates independentes (T012 runtime provedor real, T013 segurança) permanecem abertos.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| W031 | actions.md T025/T026/T035/T036; interfaces/briefing-http.md § Rotas canônicas | API `/briefings` entrega D1/D3/D4: POST síncrono via `orchestrate_persisted_briefing`, PATCH somente draft com CAS 409, approve/reopen body no-op/422, `GET /briefings/approved/{id}` read-only 409 em draft, `GET /briefings/{id}/versions` ASC v2+ | Testes unittest `tests/test_briefing_api.py` (12 testes) + `tests/test_briefing_acceptance.py` (10 cenários Gherkin) | Rota ausente; 409 sem CAS; versions listando v1; approved consultável em draft sem 409 |
| W032 | actions.md T035; audit/t011-integration-decomposition.md D4 | Schemas D4 vigentes: `BriefingResponse` com `version/error/approved_at`, `BriefingVersionResponse` com `created_at` obrigatório, `ApprovedBriefingResponse` 3–7 pontos | Testes unittest `tests/test_briefing_schemas.py` | Campo D4 ausente; approved com <3 pontos; extra aceito |
