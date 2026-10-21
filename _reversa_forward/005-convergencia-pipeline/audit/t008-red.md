# T008 — autoria RED persistência/barreira e migration

> 🟡 Relatório autoral de autoria RED (T008 / S08). Prova pré-implementação de storage por rodada, barreira de merge e migração Alembic. Nenhum código de produto nem migração implementados nesta sprint.

## 1. Escopo e arquivos do lote

Arquivos criados na sprint:
- `tests/investigation/test_round_storage.py`: 11 testes unitários do contrato de storage por rodada e barreira de 4 personas.
- `tests/investigation/test_round_migration.py`: 3 testes programáticos de migração Alembic em SQLite isolado.
- `_reversa_forward/005-convergencia-pipeline/audit/t008-red.md`: este relatório.

Todos os arquivos de produto (`app/*`) e migrações (`alembic/versions/*`) permaneceram inalterados.

## 2. Contratos exercitados (data-delta.md §§2-3 e actions T008/T011)

1. **Storage por rodada**:
   - `save_step_result` passa a exigir `round` inteiro positivo (`round > 0`).
   - `round=None`, `round=0`, `round=-1` e `round=True` (bool) devem ser rejeitados.
   - Associação `step_id` pertencente a `research_id` deve ser validada antes de persistir.
2. **Barreira de 4 personas por rodada**:
   - Registros legados com `round=None` são consultáveis, mas inelegíveis para a barreira da rodada ativa.
   - Barreira exige 4 personas válidas no **mesmo** `round` positivo para liberar o merge (`check_merge_barrier`).
   - Três de quatro personas ou personas em rodadas diferentes bloqueiam o avanço.
3. **Persistência de Merge**:
   - Tabela `investigation_merges` e função `save_investigation_merge`.
   - Unicidade estrita `(research_id, step_id, round)`.
4. **Migração Alembic**:
   - Próxima revisão (0008) adiciona `research_points.investigation_round`, `research_step_results.round`, índices e tabela `investigation_merges`.
   - Downgrade para 0007 remove novas estruturas sem afetar histórico.

## 3. Comando e resultado da execução

Comando isolado (sem banco real, sem rede):
```bash
python -B - <<'PY'
import os, sys, base64, secrets, pytest
os.environ.update(
    ENVIRONMENT='test',
    DATABASE_URL='sqlite+aiosqlite:///:memory:',
    ADMIN_PASSWORD=secrets.token_urlsafe(32),
    SESSION_SECRET=secrets.token_urlsafe(48),
    API_AUTH_SECRET=secrets.token_urlsafe(32),
    APP_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
    PYTHONDONTWRITEBYTECODE='1'
)
rc = pytest.main(['-q', '--assert=plain', '-p', 'no:cacheprovider', '-p', 'anyio.pytest_plugin', 'tests/investigation/test_round_storage.py', 'tests/investigation/test_round_migration.py'])
print('TOTAL RC:', rc)
PY
```

Resultado real:
- **9 failed, 5 passed in 1.24s**
- **Exit code**: `1` (comportamento RED confirmado)

### Falhas comportamentais RED identificadas:
1. `test_save_step_result_accepts_round_one`: `save_step_result() got an unexpected keyword argument 'round'`
2. `test_save_step_result_rejects_mismatched_research_id`: `save_step_result() got an unexpected keyword argument 'round'`
3. `test_historical_null_round_readable_but_not_in_barrier`: `'ResearchStepResult' object has no attribute 'round'`
4. `test_barrier_requires_four_personas_same_round`: `cannot import name 'check_merge_barrier' from 'app.investigation.storage'`
5. `test_barrier_rejects_three_of_four`: `cannot import name 'check_merge_barrier' from 'app.investigation.storage'`
6. `test_barrier_rejects_different_rounds`: `cannot import name 'check_merge_barrier' from 'app.investigation.storage'`
7. `test_save_investigation_merge_writes_and_unique`: `cannot import name 'save_investigation_merge' from 'app.investigation.storage'`
8. `test_upgrade_0007_to_0008_creates_columns_index_and_merges_table`: `'investigation_round' not found in research_points`
9. `test_reupgrade_after_downgrade_restores_structure`: `'investigation_round' not found in research_points`

## 4. Limites do lote

- Nenhuma alteração em código de produto ou migrações foi efetuada.
- Os testes representam especificação executável prévia (RED) para a sprint de implementação S11 (T011).
- Gates `actions.md` e `progress.jsonl` consolidados pelo Orchestrator.
