---
schema_version: 1
id: BUG-20261005-7H2K
display_number: 1
context: research-pipeline
title: "Research inteiro falha com 503 após auditor bloquear round 4 de um ponto (Supabase extensões)"
status: fixed
phase: fix-applied
severity: high
priority: P1
security_suspected: false
visibility: public
area: research-pipeline
module:
  - research-orchestrator
  - audit-stage
  - llm-client
feature: deep-research-execution
origin:
  type: manual-report
  external_ref: "https://research.dominuslabs.online/research/04d6a0c7-0b45-4b3d-90a1-2616ee662695"
reported_by: "user (produção)"
reported_at: "2026-10-05T22:47:00-03:00"
environment:
  app: deep-research (research.dominuslabs.online)
  backend_image: "j0kvxhooxnusvlyoascewxvw_backend:9c8ded032efbf378ea0917bced296751b82af47c"
  database: postgres:16-alpine
traceability:
  specs:
    - "_reversa_sdd/architecture.md#audit-cycle"
    - "_reversa_sdd/code-analysis.md#audit-cycle"
    - "contracts.md#blocker-escalation"
  expected_behavior: |
    Ponto bloqueado após N tentativas deve ir para status `blocked`,研究员
    writer deve emitir relatório parcial com caveats. Research NÃO deve
    abortar com 503.
  affected_code:
    - "app/services/research.py:141" # except Exception genérico
    - "app/services/pipeline/audit_stage.py" # _audit_point
    - "app/services/pipeline/point_executor.py" # run_point
    - "app/services/llm.py:155-369" # retry/backoff
    - "app/services/audit.py:32" # next_audit_state
  tests_existing:
    - "tests/test_backend.py::test_audit_blocked_after_retries"
labels:
  - audit-blocked
  - resilience
  - service-unavailable
relations:
  - type: caused-by
    target: null # a confirmar: audit exhaustion vs LLM gateway 503
    state: proposed
    note: "Need depth-inspection to choose between (a) pipeline faltando catch de 'blocked' e (b) LLM gateway realmente returning 503."
express: false
---

# Resumo
Pesquisa "PostgreSQL vs Supabase" (id `04d6a0c7-0b45-4b3d-90a1-2616ee662695`) recolheu 80 evidências, o auditor bloqueou a round 4 do ponto *"Supabase Postgres inclui extensões úteis pré-instaladas"* e imediatamente depois o research **inteiro** transitou para `failed` com a mensagem `ServiceUnavailableError (status=503): research execution failed` exposa no banner do frontend.

# Esperado vs Observado
- **Esperado**: 
  1. O ponto vai a `blocked` após `MAX_AUDIT_ATTEMPTS` falhas (contrato `audit.py:next_audit_state`).
  2. O orquestrador deixa outros pontos avançarem / agrega relatório parcial.
  3. A research termina em `partial` ou `complete-with-blocked`, nunca `failed` por motivo transitório.
- **Observado**: a research termina em `failed`; todos os pontos restantes ficam sem veredicto. Mensagem genérica "ServiceUnavailableError (status=503)" esconde causa real (LLM gateway? rate-limit? auditor que chama de novo?).

# Passos para reproduzir
1. Criar nova research com brief de 5 pontos.
2. Provocar auditor sempre a reprovar um ponto (fontes fraca, sem quote exato) até round 4.
3. Esperar pela quarta tentativa; imediatamente após o evento `verdict_rendered` com `state=blocked`, observar se pipeline chama outro LLM e explode.

# Frequência
Primeiro relato. Pode ser determinístico por design (ausência de catch para `blocked`) ou espúrio (LLM gateway 503 real). Necessário depth-inspection.

# Evidências
- `screenshot-20261006-004444.png` — banner de erro no frontend.
- Backend log não contém a string `503` porque `sanitize_error` remove detalhe antes de dar raise evento; log original vem de `LiteLLM` mas foi capturado apenas pelo `LiteLLM.Info: ... use litellm._turn_on_debug()` no stdout.
- `backend-j0kvxhooxnusvlyoascewxvw-211937762008` mostra 10+ blocos LiteLLM a engolir traceback durante a janela do research.

# Análise rápida (a confirmar no fix)
Dois caminhos possíveis geram o mesmo `ServiceUnavailableError(status=503)`:

1. **LLM gateway** (Render router / OpenAI / LiteLLM self-hosted) respondeu 5xx a uma das chamadas pós-audit; o retry em `llm.py::_call` estourou e a excepção subiu até `run_research`, matando a research inteira em vez de ser scoped a um ponto.
2. **Auditor loop**: attempt=4 não approved → `_audit_point` retorna `False`. `_run_point` (`pipeline/point_executor.py`) não lida com `False` como status terminal — pode tentar mais uma iteração (ver contrato `contracts.md#blocker-escalation` "research should mark point as blocked and continue") e falhar com excepção interna qual a `ServiceUnavailableError` é atribuída por `liteLLM` no retry.

Ambas violam o princípio **Graceful Degradation** (`.reversa/principles.md`) e o requisito de relatório parcial.

# Agent Notes (rota expressa não usada — fluxo completo)
- Severidade `high` escolhida porque bug destrói o resultado de ~20 min de pesquisa.
- `spec-gap` parcial: `contracts.md#blocker-escalation` menciona "If a point fails audit after 3 attempts: block it and continue", mas behavior exato (status final da research) não está especificado → pode ser necessário adendo.
- Próximo passo recomendado: `/reversa-debugger-fix` com modo investigação para distinguir causa raiz (auditor-blocked vs llm-retry-exhaustion).

# Relações propostas
- **caused-by**: TBD (proposed) — necessário inspeção profunda.
- **blocked-by**: nenhum.
- **related-to**: potencial futuro bug sobre "Audit round 4 em ponto sobre Supabase extensions" (pode ser padrão recorrente).
