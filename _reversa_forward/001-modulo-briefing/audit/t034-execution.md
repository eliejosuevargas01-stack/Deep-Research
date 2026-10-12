# Execução T034 — Alinhamento mecânico rastreabilidade T030/T031 pós-QA

**Data:** 2026-10-11  
**Feature:** _reversa_forward/001-modulo-briefing  
**Status:** Documental — sem autoaprovação de auditoria/QA; action T034 permanece aberta até parent + independente + QA aplicável.

## Fontes congeladas (suficientes)

- `actions.md` linha T034 e T030/T031 `[X]` (linha 85–86, 89)
- `progress.jsonl` linha 76–77 (frozen baseline L77)
- `app/briefing/llm_binding.py` (vigente)
- `tests/test_briefing_llm_binding.py` (vigente)
- `audit/t030-execution.md` (entrega T030)
- `audit/t031-execution.md` (entrega T031)
- `_reversa_bugs/modulo-briefing/inspections/t030-error-matrix/report.md` (inspeção — CONDITIONAL; observação O-CONTRACT-01 **não promovida a bug**; QA PASS_LOCAL) e `_reversa_bugs/modulo-briefing/inspections/t030-error-matrix-qa/report.md` (QA — PASS_LOCAL)
- `_reversa_bugs/modulo-briefing/inspections/t031-session-factory/report.md` (inspeção — PASS) e `_reversa_bugs/modulo-briefing/inspections/t031-session-factory-qa/report.md` (QA — PASS_LOCAL)
- `legacy-impact.md` (estado pré-T034)
- `regression-watch.md` (estado pré-T034)
- `audit/t029-t031-planning-delta.md` (D3/D5 vigentes)
- `audit/t011-integration-decomposition.md:99–110` (D3/D5 adendo)

## Alterações realizadas

### 1. `legacy-impact.md` — Adendo T030/T031 (linhas novas após linha 162)
- Registro factual: T030 (matriz de erros F-ERROR-01) e T031 (ownership de session_factory F-CONSISTENCY-01) **IMPLEMENTADAS**, parent verificou, auditoria e QA aprovadas (PASS_LOCAL).
- T025 desbloqueada mas **NÃO entregue** (coding gate bloqueado até delta S8 auditado).
- T026/T012/T013 pendentes.
- Factory vigente: `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s=30.0)` com callable `timeout_s` override; settings lidos em sessão própria curta fechada antes LLM; nenhuma finalização sessão caller-owned; flush first-use revertido.
- Assinaturas/execuções antigas marcadas como **históricas** com adendo vigente; evidências conservadas.
- Contagens exatas atuais: 24 bindings (1 sync, 23 async), 140 briefing — evidência parent/QA já gravada, não execução própria.
- Não afirmar rede real nem banco real; sem segredos.

### 2. `regression-watch.md` — Adendo T030/T031 (linhas novas após linha 177)
- IDs W mantidos (append-only, não apagar observações antigas).
- T030/T031 registradas como fechadas por inspeção/QA (`actions.md [X]`).
- T025 desbloqueada mas não entregue; T026/T012/T013 pendentes.
- Factory vigente documentada com assinatura, ciclo de vida, validação precoce, D3 (flush revertido).
- Preservar contexto greenfield em legacy-impact; regression-watch manter histórico e IDs W.

### 3. `audit/t034-execution.md` — Este relatório
- Arquivos/linhas/documentos fonte listados acima.
- Checks factuais: Markdown table delimiters, links novos, referências/símbolos, `git diff --check` (exit 0).

## Checks factuais

| Check | Resultado |
|-------|-----------|
| Markdown table delimiters (colunas = nº pipes por linha) | OK — tabelas têm nº consistente de colunas por linha |
| Links novos resolvem | OK (caminhos relativos internos) |
| Referências/símbolos (T030, T031, T025, T026, T012, T013, D3, D5, F-ERROR-01, F-CONSISTENCY-01, O-CONTRACT-01) | OK — todos definidos nas fontes congeladas |
| `git diff --check` nos arquivos alterados | Exit 0 (sem trailing whitespace, conflitos ou erro de formato) — **valida apenas arquivos tracked** |
| Contagens citadas (24 bindings, 140 briefing) | Confirmadas em `progress.jsonl:76` campo `parent_replay` texto `24/24 binding tests OK, 140 briefing tests OK` e QA reports |
| Factory assinatura | `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s=30.0)` — conferido em `llm_binding.py:101–103` e `audit/t031-execution.md:12` |
| Ciclo de vida sessão | `async with session_factory() as session:` → `runtime_settings` + `get_record` → copia escalares → fecha **antes** de `_enforce_safe_transport()` e `litellm.acompletion` — conferido em `llm_binding.py:113–119` e QA probe ordem `session_close/exit < litellm_acompletion` |
| Validação precoce timeout | `_checked_timeout` antes de abrir sessão; early abort com `session_factory.call_count == 0` — conferido em `llm_binding.py:108–112` e QA probes |
| Flush first-use revertido | SQLite `:memory:` + `StaticPool` + `get_record` flush → close sem commit → `select(AppSettings)` = 0 linhas — conferido em QA report probe D3 |
| Nenhum commit/rollback caller-owned | `fake_session.commit.call_count == 0`, `rollback.call_count == 0` — conferido em QA probes |

## Limites

- **Não produção, não testes**: apenas registro documental mecânico.
- **Não fechar T034**: action fica aberta até parent + independente + QA aplicável.
- **Não rede real, não DB real**: só mocks/SQLite memória nos probes citados.
- **Não substituir testemunho histórico por estado atual**: assinaturas/execuções antigas marcadas históricas com adendo vigente; evidências conservadas.
- **regression-watch**: append-only, IDs W preservados; preferir addendum que não apague observações antigas.
- **legacy-impact**: manter contexto greenfield.

## Próximos passos (fora deste relatório)

1. Parent/independente/QA aplicável validam e fecham T034.
2. T025 (router HTTP `/briefings`) inicia coding após delta S8 auditado (backend-high: `roadmap.md`, `interfaces/briefing-http.md`, `audit/t025-t026-planning-delta.md`).
3. T026/T012/T013 sequenciais.

---

## Adendo 2026-10-11 — Observações F-EVIDENCE-01/02 (T034 continua aberta aguardando recheck)

- **F-EVIDENCE-01 (LOW)**: Linha 15 original confundia promoção "O-CONTRACT-01 NÃO promovida a overall PASS_LOCAL". Corrigido para "inspeção CONDITIONAL (produto ordinário PASS); O-CONTRACT-01 não promovida a bug; QA PASS_LOCAL" com paths reais separados. Não transformar promoção de observação a bug em aprovação; sem claims de reachability global.

- **F-EVIDENCE-02 (LOW)**: `git diff --check` global tracked exit 0 não valida untracked; `git diff --no-index --check /dev/null _reversa_forward/001-modulo-briefing/audit/t034-execution.md` exit 3 aponta dois Markdown hard breaks intencionais em linhas 3/4 (trailing spaces como hard breaks documentais, não product defect). Qualificar: git diff check global tracked exit 0 não valida untracked; manual delims/path checks e noindex exit 3 dois Markdown hard breaks intencionais aceitos documentais. Reexecutar ambos checks para fatos e refletir exatos paths/linhas atuais se diferente. `git diff --no-index --check` exit 1 (diff found não whitespace) também possível; inspecionar output não assumir. T034 continua aberta aguardando recheck; NÃO alegar SANADO independentemente (feito aguarda recheck).