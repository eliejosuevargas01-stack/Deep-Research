# Auditoria Reversa — Forward Artifacts

> Verificação cross-artifact de `_reversa_forward/` (requirements.md ↔ roadmap.md ↔ actions.md)  
> Data: 2026-10-05 | Emissor: Orchestrator autônomo | Confidência: 🟢 CONFIRMADO (código) + 🟡 INFERIDO (consistência)

---

## Resultado

| Severidade | Count |
|-----------:|-------|
| CRITICAL | 0 |
| **HIGH** | 1 |
| **MEDIUM** | 3 |
| **LOW** | 1 |
| **Total** | **5 findings** |

---

## Findings

### [HIGH] AC-02 — Prompts .md não criados
**Eixo:** coerência-legado  
**Descoberta:** `actions.md` T003-T008 exigem `app/prompts/{persona}.md` (scout.md, auditor.md, writer.md, etc.) extraídos de `personas.json`, mas:
- `app/prompts/__init__.py` está vazio (0 bytes).
- Nenhum `.md` existe.
- Nenhuma ação T cria explicitamente esses templates.

**Impacto:** Modularização dos workers (T002-T009) depende de prompts carregáveis em `.md`, que não existem. Refactoring falhará em runtime.

**Correção esperada:** Adicionar ação explícita na fase de workers: *"Criar `app/prompts/{scout,historian,skeptic,pragmatist,futurist,auditor,writer}.md` extraindo de personas.json"* — sugerido em T002 (BaseWorker setup) ou nova ação T002.5.

---

### [MEDIUM] AC-01 — Referência ghost a DataPanel.tsx
**Eixo:** consistência  
**Descoberta:** `requirements.md §3` cita *"Frontend/observability — `frontend/src/DataPanel.tsx` → componentes"* como fora de escopo, mas `DataPanel.tsx` não existe. O arquivo monolítico real é `main.tsx` (2546 LOC).

**Impacto:** Confusão na fronteira de escopo; `actions.md` T005 ("Refatorar frontend em componentes") referencia um arquivo inexistente.

**Correção esperada:** Substituir `DataPanel.tsx` → `main.tsx` em `requirements.md §3`.

---

### [MEDIUM] AC-03 — Estrutura alvo desatualizada
**Eixo:** consistência  
**Descoberta:** `requirements.md §2.1` mostra estrutura alvo: *"search_pipeline.py (movido para app/tools/ ou mantido)"* — decisão já resolvida em `actions.md` T001 (mover para `app/services/search.py`), mas estrutura no requirements não atualizada.

**Correção esperada:** Atualizar estrutura alvo: `services/search.py # (movido de app/tools/search_pipeline.py)`.

---

### [MEDIUM] AC-06 — Inconsistência revising enum
**Eixo:** coerência-legado  
**Descoberta:** `requirements.md §2.5` exige backwards-compat de lifespan recovery para status `revising`, mas `ResearchStatus` enum (`domain_models.py:18-27`) **não contém** `REVISING` — mesma LACUNA 1 em `questions.md`. Refactoring do scheduler herdará essa inconsistência.

**Correção esperada:** Resolver LACUNA 1 (adicionar `REVISING = "revising"` ao enum) **antes** de T010 — propor nova ação T001.5 "Corrigir ResearchStatus enum".

---

### [LOW] AC-05 — Schema de log não formalizado
**Eixo:** consistência  
**Descoberta:** `requirements.md §2.5` e `actions.md Notas #4` exigem logging estruturado (JSON) com campos implícitos (`research_id`, `point_id`, `persona`) — mas schema não formalizado.

**Correção esperada:** Formalizar schema de log em T002 (BaseWorker): `BaseWorker._log_structured(stage, persona, metrics, research_id, point_id)`.

---

## Verificações APROVADAS (PASS)

| Check | Status | Evidência |
|-------|--------|-----------|
| **Cobertura** (REQ→T) | 🟢 PASS | REQ-01→T002-09, REQ-02→T010, REQ-03→T003-09, REQ-04→T011, REQ-05→T012, REQ-06→T012, REQ-07→T013 |
| **Sanidade actions** | 🟢 PASS | Todas refs T### existem; sem ciclos (`T010→T011→T012→T013`) |
| **Dependências válidas** | 🟢 PASS | T001→T002→T003-09(paralelo)→T010→T011→T012→T013 |
| **Roadmap prazo** | 🟢 PASS | 4 fases/5 semanas resolvem audit LOW prior (gap prazo) |
| **Gap analysis** | 🟢 PASS | 4 perguntas do requirements-audit incorporadas |

---

## Recomendação para Fase Forward

Corrigir **AC-02** (prompts .md) e **AC-06** (enum revising) **antes** iniciar T001-T010 execution — ambas são blockers arquiteturais raiz-para-refactoring. Propostas:

| ID | Ação | Prioridade |
|----|------|-----------|
| ACT-1 | `pip install -r requirements.txt` (resolver LACUNA 4) | ⚡ Imediata |
| ACT-2 | Adicionar `REVISING` ao enum (resolver LACUNA 1) | Alta |
| ACT-3 | Criar `app/prompts/*.md` extraindo personas.json | Alta |
| ACT-4 | Deletar `app/prompts/__init__.py` vazio (resolver LACUNA 2) | Alta |

---

> 🚨 **Status da auditoria**: `REJECTED`  
> **Próximo passo**: Corrigir ACT-1/ACT-2/ACT-3/ACT-4 → Worker (repair) → novo ciclo auditoria.
>
> `audit_findings.json` — artefato completo para processamento.
