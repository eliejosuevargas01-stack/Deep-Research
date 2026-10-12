# Relatório de QA — Sprint 7 (Orquestração Persistida)

## Resumo e veredito
**PASS no recorte F-test-01..03 solicitado.** Suíte mantida `tests/test_briefing_persisted_orchestration_qa.py` criada com 4 métodos assíncronos limpos, cobrindo os cenários identificados na inspeção independente (`F-test-01`, `F-test-02` e `F-test-03`). Zero alterações em código de produção (`app/briefing/service.py`, `storage.py`), suíte existente (`tests/test_briefing_persisted_orchestration.py`), `actions.md` ou `progress.jsonl`. Todos os checks executados com exit code 0.

## Cobertura dos cenários

### 1. F-test-01 — Comparação exata de pontos em fluxo de sucesso e recuperação pós-falha
- **Métodos**: `test_success_preserves_exact_points_in_return_current_and_history` (linha 87) e `test_invalid_content_retry_preserves_exact_recovered_points` (linha 95).
- **Critérios**:
  - Comparação de igualdade exata de tupla/lista de `BriefingPoint` preservando ordem, `title` e `description`.
  - Verificação de consistência entre o retorno em memória, o registro corrente (`BriefingRecord.points_json`) e o registro histórico (`BriefingVersion.points_json`).
  - No fluxo de recuperação com tentativa inválida inicial, confirmação de que dados parciais ou canários não vazam para a persistência nem para o histórico.

### 2. F-test-02 — Histórico append-only na exaustão de 4 tentativas LLM
- **Método**: `test_four_domain_invalid_attempts_append_failed_safe_history` (linha 146).
- **Critérios**:
  - Exaustão com 4 chamadas LLM e 1 busca SERP.
  - Verificação do histórico append-only: versão histórica v2 gravada com `status='failed'`, `points_json=[]` e mensagem de erro exata e segura (`Geração de briefing indisponível`), idêntica ao registro corrente.
  - Snapshot de histórico preexistente preservado sem mutações colaterais.

### 3. F-test-03 — Cancelamento externo síncrono e transação de emergência via `asyncio.Event`
- **Método**: `test_external_cancellation_after_llm_entry_commits_emergency_history` (linha 152).
- **Critérios**:
  - Sincronização determinística sem sleep cego: spy do LLM dispara `entered.set()`, caller aguarda `entered.wait()` e aciona `task.cancel()`.
  - Propagação correta de `asyncio.CancelledError`.
  - Execução da transação de emergência: registro corrente com `status='failed'`, `points_json=[]` e `error='Processamento abortado ou cancelado'`.
  - Versão histórica correspondente v2 gravada no banco com os mesmos campos.

## Métodos da suíte criada
| Método | Linha | Foco |
|---|---|---|
| `test_success_preserves_exact_points_in_return_current_and_history` | 87 | F-test-01: Sucesso com igualdade exata de `BriefingPoint` em retorno, corrente e histórico |
| `test_invalid_content_retry_preserves_exact_recovered_points` | 95 | F-test-01: Recuperação pós-falha inválida sem resíduos parciais |
| `test_four_domain_invalid_attempts_append_failed_safe_history` | 146 | F-test-02: Exaustão em 4 tentativas com histórico v2 failed e erro seguro |
| `test_external_cancellation_after_llm_entry_commits_emergency_history` | 152 | F-test-03: Cancelamento via `asyncio.Event` com transação de emergência e histórico v2 |

## Execução e evidências de checagem
Ambiente: SQLite `:memory:` isolado assíncrono (`sqlite+aiosqlite:///:memory:`). Sem rede externa, sem credenciais reais.

1. `python3 -B -m unittest tests.test_briefing_persisted_orchestration_qa -v`
   - Exit code: 0
   - Resultado: Ran 4 tests in 0.408s, OK.
2. `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python3 -B -m py_compile tests/test_briefing_persisted_orchestration_qa.py`
   - Exit code: 0 (sem erros de compilação ou sintaxe).
3. `git diff --check`
   - Exit code: 0. Valida diff rastreado; arquivos novos untracked não são cobertos por esse comando.
4. `python3 -B -m unittest tests.test_briefing_persisted_orchestration -v`
   - Exit code: 0
   - Resultado: Ran 5 tests in 0.479s, OK (suíte existente intacta).
