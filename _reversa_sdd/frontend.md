# Spec: Módulo Frontend (frontend/src)

> Archaeologist — módulo 5 de 6  
> Confidência: 🟢 CONFIRMADO

## Estrutura (5.357 LOC)
| Arquivo | LOC | Papel |
|---------|-----|-------|
| `main.tsx` | 2.546 | **Monolítico** — toda UI React (login, briefing, pipeline, report, settings, SSE feed) |
| `style.css` | 2.014 | Tailwind + tokens dark mode (estilo Linear) |
| `research-utils.ts` | 549 | Cache IndexedDB + formatação + validação |
| `api.ts` | 132 | Cliente API + SSE + auto-reauth CSRF |
| `types.ts` | 83 | Contratos TS (Point, Research, Event, Audit) |
| `routes.ts` | 33 | React Router |

## `api.ts` (132 LOC)
- 🟢 `prepareHeaders`: **nunca envia** `X-Tenant-ID` (deleta sempre) — CRITERIA A4.
- CSRF token em módulo (não cookie), enviado como `X-CSRF-Token` em mutações.
- `api<T>()`: fetch wrapper com `credentials: 'same-origin'`; **auto-reauth**: 403 em mutação → refetch CSRF → retry único.
- `initializeSession`: `/api/auth/me` → `/api/auth/csrf`.
- SSE: `GET /api/research/{id}/events/stream` com `Last-Event-ID` resume.

## `types.ts` (83 LOC)
- `Point { title, description, dependencies, is_parallelizable }`.
- `Research` com `callback_status: 'pending' | 'delivered' | 'failed'`.
- `AuditFindingPoint` espelha backend `audit.deterministic/llm`.

## `research-utils.ts` (549 LOC)
- 🟢 Cache offline-first em IndexedDB (`clearAllDrCache`).
- Formatação de eventos/métricas, validação de briefing draft.

## Débito técnico (débito confirmado)
- 🔴 `main.tsx` 2.546 LOC monolítico — 6+ componentes inline, zero separação. Target de refactoring: componentes por feature (alinhado com actions.md T005).
- `style.css` 2.014 LOC inline tokens — aceitável para design system único.

## Lacunas 🔴
1. `app/prompts/__init__.py` vazio não afeta frontend — módulo morto backend-side. Frontend não consome.
