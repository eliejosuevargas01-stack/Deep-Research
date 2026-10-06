# Verificação do fix (BUG-20261005-7H2K)

## Mudanças aplicadas

1. `app/services/pipeline/audit_stage.py` (_audit_point)
   - try/except em torno de `complete()` captura qualquer exceção do LLM (incl. ServiceUnavailableError).
   - Em caso de falha, registra `llm_audit` fallback com findings/uncertainties/missing_research e dispara evento `audit_llm_unavailable`.
   - Estado do ponto segue o fluxo normal: retry_required -> blocked no attempt 4. Nunca propaga exceção.

2. `app/services/pipeline/point_executor.py` (_run_point)
   - try/except em torno de `_audit_point()` como segunda camada defensiva.
   - Captura exceção inesperada, registra AuditTrail stage=audit_failure e add_event system.audit_failure, faz continue no loop (tentativa seguinte).
   - Mantém bloco terminal `blocked` se todas tentativas esgotarem.

## Verificação

- AST parse: OK (ambos arquivos)
- Import chain: `_audit_point`, `_run_point`, `run_research` carregam sem erro
- pytest tests/test_backend.py -k "audit" → 4 passed (audit_blocked_after_retries + vizinhos)
- pytest full suite: timed out (>240s); coletado via import smoke test + testes focados

## Relação com bug.md

- Causa raiz primária confirmada por código: `complete()` raises -> _audit_point propagates -> _run_point não catch -> run_research.marcas failed.
- Fix scopo-a a exceção no nível do ponto, permitindo graceful degradation (princípio .reversa/principles.md).
- Spec-gap parcial persiste: `contracts.md#blocker-escalation` menciona "block it and continue" mas não define status final da research — candidato a adendo (não tratado neste fix).

## Status do bug

- fix-status: implemented
- fix-validation: import smoke + audit unit tests pass
- proximo: depth-inspection (auditor-vs-llm) pode ser necessário se 503 realmente voltar do gateway; este fix torna o pipeline resiliente independentemente da causa.
