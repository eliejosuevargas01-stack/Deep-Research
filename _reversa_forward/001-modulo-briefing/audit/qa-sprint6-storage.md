# QA Sprint 6 — storage T020–T022

## Veredicto
**PASS_LOCAL**. QA posterior à implementação/auditoria, sem alegação TDD. Quatro métodos novos passaram; baseline explícito 14/14 passou. Nenhum finding comportamental confirmado. QA não fecha ações nem aprova integração geral.

## Preflight e isolamento
Root `/root/projects/deep-research`, branch `main`, feature `001-modulo-briefing`, estágio ativo `coding`. `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json` e execution-policy lidos; configuração permite paths locais. Estado global `forward-complete` anterior não substitui feature ativa. Worktree já suja; nenhuma limpeza/index/commit/push.

Escritas exclusivas: `tests/test_briefing_storage_qa.py` e este relatório. Produção, migração e baseline congelados. DB novo SQLite em memória, somente tabelas `briefings` e `briefing_versions`; sessões via context managers, engine com `addAsyncCleanup`, listener removido em `finally`. Baseline migração usa SQLite temporário sob TMPDIR scratch existente. Sem cliente HTTP, rede, DB externo ou leitura de `.env` pelo agente. Não houve discovery ou leitura/teste de service/binding/suítes sibling.

## Critério → símbolo real → teste mantido
Todos os métodos pertencem a `tests.test_briefing_storage_qa.TestBriefingStorageQA`.

| Critério | Símbolos executados | Método / linha |
|---|---|---|
| RF-05: edição salva, conteúdo exato/reordenado, UUID, versões monotônicas e consulta após fechar sessão escritora | `edit_briefing`, `save_briefing_transition`, `get_briefing` | `test_saved_edit_approve_reopen_history_is_immutable:63` |
| RF-06 / RF-09: aprovação, edição proibida no domínio aprovado, reabertura remove aprovação e permite nova edição salva | `approve_briefing`, `reopen_briefing`, `edit_briefing`, storage | mesmo método `:63` |
| D2: histórico ASC, snapshots anteriores completos intactos, timestamp aprovado histórico preservado após reabrir | `get_briefing_versions`, `BriefingVersion` | mesmo método `:63` |
| D3: CAS obsoleto não muda current/history vencedor | `save_briefing_transition`, `BriefingVersionConflictError` | `test_stale_cas_keeps_exact_winner_and_history:99` |
| D3: falha real durante flush INSERT histórico reverte UPDATE já observado na mesma conexão/transação; caller recupera sessão | `save_briefing_transition`, evento ORM `BriefingVersion.before_insert`, `AsyncSession.rollback` | `test_history_insert_failure_rolls_back_update_with_caller_rollback:113` |
| D2 / dados limpos: canary presente em campos extras de input, ausente na serialização de todas as colunas current/history | `edit_briefing`, `points_to_json`, `BriefingRecord`, `BriefingVersion` | `test_raw_canary_excluded_from_current_and_history_serialization:142` |
| T020/T021 baseline: conversores/constraints, upgrade/downgrade 0006 em SQLite | conversores storage, ORM, Alembic `0006` | 7 métodos converters + 3 migration + 4 storage existentes |

Escopo RF é persistência local do ciclo válido, não matriz completa de validação/API. History inicia na transição v2; ciclo verifica v2–v6. Timestamp fixo sem timezone deliberado: SQLite comprova valor wall-time, não round-trip PostgreSQL TIMESTAMPTZ. Canary fictício somente em extras; não afirma sanitização de segredo em title/description legítimos ou saída de provedor.

## Execução e contagens
- Novo arquivo: 4 métodos async mantidos (AST), 4 executados, 0 falhas/erros/skips, 0 contextos/subtests. Loop de ciclo não contado como métodos ou subtests.
- Baseline explícito: 14 métodos executados, 0 falhas/erros/skips. Fonte converters declara 4 subtests de estados em um método; runner `unittest -v` não fornece total de subtests, portanto não contabilizados como métodos.
- Baseline combinado 118 informado pelo parent não foi reexecutado neste recorte; não agregado aos resultados locais.

### QA — exit 0
`python3 -B -m unittest tests.test_briefing_storage_qa -v`
```text
test_history_insert_failure_rolls_back_update_with_caller_rollback (tests.test_briefing_storage_qa.TestBriefingStorageQA.test_history_insert_failure_rolls_back_update_with_caller_rollback) ... ok
test_raw_canary_excluded_from_current_and_history_serialization (tests.test_briefing_storage_qa.TestBriefingStorageQA.test_raw_canary_excluded_from_current_and_history_serialization) ... ok
test_saved_edit_approve_reopen_history_is_immutable (tests.test_briefing_storage_qa.TestBriefingStorageQA.test_saved_edit_approve_reopen_history_is_immutable) ... ok
test_stale_cas_keeps_exact_winner_and_history (tests.test_briefing_storage_qa.TestBriefingStorageQA.test_stale_cas_keeps_exact_winner_and_history) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.287s

OK
```

### Baseline — exit 0
`python3 -B -m unittest tests.test_briefing_storage_converters tests.test_briefing_migration tests.test_briefing_storage -v`
```text
test_round_trip_all_states (tests.test_briefing_storage_converters.TestBriefingConverters.test_round_trip_all_states) ... ok
test_timestamps (tests.test_briefing_storage_converters.TestBriefingConverters.test_timestamps) ... ok
test_version_dict (tests.test_briefing_storage_converters.TestBriefingConverters.test_version_dict) ... ok
test_tables_and_columns (tests.test_briefing_storage_converters.TestOrmMapping.test_tables_and_columns) ... ok
test_version_constraints_and_isolation (tests.test_briefing_storage_converters.TestOrmMapping.test_version_constraints_and_isolation) ... ok
test_round_trip (tests.test_briefing_storage_converters.TestPointsConverters.test_round_trip) ... ok
test_tuple_isolation (tests.test_briefing_storage_converters.TestPointsConverters.test_tuple_isolation) ... ok
test_tables_absent_after_downgrade (tests.test_briefing_migration.BriefingMigrationTests.test_tables_absent_after_downgrade) ... /root/.hermes/tools/python-3.14.7+202****0901-linux-x64/lib/python3.14/site-packages/alembic/config.py:604: DeprecationWarning: No path_separator found in configuration; falling back to legacy splitting on spaces, commas, and colons for prepend_sys_path.  Consider adding path_separator=os to Alembic config.
  util.warn_deprecated(
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial durable research schema
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, append-only audit decisions and operational callback outcomes
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, add callback_url and openai_base_url to app_settings
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, add jina_base_url to app_settings for custom Cloudflare Worker proxy
INFO  [alembic.runtime.migration] Running upgrade 0004 -> 0005, add jina_proxy_url and jina_proxy_timeout_seconds to app_settings
INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0006, create briefings and briefing_versions tables
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 0006 -> 0005, create briefings and briefing_versions tables
ok
test_tables_present_after_upgrade (tests.test_briefing_migration.BriefingMigrationTests.test_tables_present_after_upgrade) ... INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial durable research schema
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, append-only audit decisions and operational callback outcomes
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, add callback_url and openai_base_url to app_settings
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, add jina_base_url to app_settings for custom Cloudflare Worker proxy
INFO  [alembic.runtime.migration] Running upgrade 0004 -> 0005, add jina_proxy_url and jina_proxy_timeout_seconds to app_settings
INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0006, create briefings and briefing_versions tables
ok
test_upgrade_and_downgrade_reversible (tests.test_briefing_migration.BriefingMigrationTests.test_upgrade_and_downgrade_reversible) ... INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial durable research schema
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, append-only audit decisions and operational callback outcomes
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, add callback_url and openai_base_url to app_settings
INFO  [alembic.runtime.migration] Running upgrade 0003 -> 0004, add jina_base_url to app_settings for custom Cloudflare Worker proxy
INFO  [alembic.runtime.migration] Running upgrade 0004 -> 0005, add jina_proxy_url and jina_proxy_timeout_seconds to app_settings
INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0006, create briefings and briefing_versions tables
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 0006 -> 0005, create briefings and briefing_versions tables
ok
test_full_cycle_generating_draft_edit_approved (tests.test_briefing_storage.TestStorageCycle.test_full_cycle_generating_draft_edit_approved) ... ok
test_get_missing_returns_none_and_history_empty (tests.test_briefing_storage.TestStorageCycle.test_get_missing_returns_none_and_history_empty) ... ok
test_points_json_only_clean_points_and_uuid_preserved (tests.test_briefing_storage.TestStorageCycle.test_points_json_only_clean_points_and_uuid_preserved) ... ok
test_stale_cas_raises_and_preserves_state (tests.test_briefing_storage.TestStorageCycle.test_stale_cas_raises_and_preserves_state) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.837s

OK
```

### Sintaxe — exit 0, stdout vazio
`PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/qa-sprint6-pycache python3 -B -m py_compile tests/test_briefing_storage_qa.py`

### Diff — exit 0, stdout vazio
`git diff --check`

Ocorrências locais: primeira gravação do teste tinha lixo na última linha; lint detectou SyntaxError, corrigido somente no arquivo QA antes de execução. Nenhum teste falhou. Aviso Alembic `No path_separator found in configuration` não bloqueante, sem alteração da configuração. Duas chamadas iniciais de skill com nome incorreto falharam; skills obrigatórias carregadas corretamente antes do preflight.

## SHA-256 antes/depois
Captura anterior à escrita do teste; recaptura após QA, baseline, sintaxe e diff. Todos 16 paths idênticos. Hashes representam preservação do readset deste QA, não snapshot histórico de outros workers.

| Path | Antes | Depois |
|---|---|---|
| `AGENTS.md` | `9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844` | `9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844` |
| `.reversa/state.json` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` |
| `.reversa/active-requirements.json` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` |
| `.reversa/reversa-config.json` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` |
| `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` |
| `app/briefing/storage.py` | `48f9411ababa036e00f013e8db03dc86d5ca765bde74c99cc37235802a3e1ab0` | `48f9411ababa036e00f013e8db03dc86d5ca765bde74c99cc37235802a3e1ab0` |
| `app/models/domain_models.py` | `4ac806852b283f0d2c6bed1622124989ce51aa0025a7db6c0bea260f97f20fa1` | `4ac806852b283f0d2c6bed1622124989ce51aa0025a7db6c0bea260f97f20fa1` |
| `app/models/__init__.py` | `6cf0a07d11bf0f320d2e9c914ca6c30aa0eb4fd5af18dced373be1fb569b9e1c` | `6cf0a07d11bf0f320d2e9c914ca6c30aa0eb4fd5af18dced373be1fb569b9e1c` |
| `alembic/versions/0006_briefing_storage.py` | `8356e2859adf03d5833e80a2110d5c24e79ea31ba7df65ba6fae98d51ee90f5d` | `8356e2859adf03d5833e80a2110d5c24e79ea31ba7df65ba6fae98d51ee90f5d` |
| `alembic/env.py` | `e3dd27422ab3eeb232610a8038cc42138bcf2f792c420521e2f09b5dc7a1f315` | `e3dd27422ab3eeb232610a8038cc42138bcf2f792c420521e2f09b5dc7a1f315` |
| `tests/test_briefing_storage_converters.py` | `1433dd34263b979e2532929b464e573e5945ed593634f55d1b5a5dc2b804a6db` | `1433dd34263b979e2532929b464e573e5945ed593634f55d1b5a5dc2b804a6db` |
| `tests/test_briefing_migration.py` | `1b42690c0f6f969c38965dc5ef14bba3f088968585d67bf5bef6a907ce1c6fc5` | `1b42690c0f6f969c38965dc5ef14bba3f088968585d67bf5bef6a907ce1c6fc5` |
| `tests/test_briefing_storage.py` | `a4082c88ba74652168a16210ccc9d4da3ff3bddee97760e10442cf3e5943c174` | `a4082c88ba74652168a16210ccc9d4da3ff3bddee97760e10442cf3e5943c174` |
| `_reversa_forward/001-modulo-briefing/requirements.md` | `4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5` | `4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5` |
| `_reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md` | `fd679e6a53f017fbc160a0f1352b471f40c3efa971b74a4122b1f2d7423e04bf` | `fd679e6a53f017fbc160a0f1352b471f40c3efa971b74a4122b1f2d7423e04bf` |
| `_reversa_forward/001-modulo-briefing/execution-policy.md` | `4a40e628d7e89f61859a7b6975a28d710ee062575143a6c4dbd25fb49a4ecb74` | `4a40e628d7e89f61859a7b6975a28d710ee062575143a6c4dbd25fb49a4ecb74` |

## Limitações e encaminhamento
Sem PostgreSQL, provider real, API/HTTP, integração geral, processos/conexões concorrentes, crash ou cancelamento. CAS simula escritor obsoleto sequencial. Atomicidade comprovada com falha ORM antes de INSERT e UPDATE observado, seguida de rollback explícito do caller; storage não possui rollback genérico próprio e não se afirma recuperação automática. Histórico append-only comprovado nas operações exercitadas, não proteção contra edição SQL direta.

Sem findings a reparar. Nenhum registro Bugs, actions, progress, legacy-impact, regression-watch ou skill alterado. Orchestrator verifica artefatos e integra gates sibling; ações permanecem sob sua responsabilidade.
