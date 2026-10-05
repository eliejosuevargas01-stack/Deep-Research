# Spec: Módulo API Ingress (routers, main)

> Archaeologist — módulo 2 de 6  
> Confidência: 🟢 CONFIRMADO

## `app/routers/auth.py` (49 LOC) — Auth endpoints
- `POST /api/auth/login`: valida `ADMIN_PASSWORD`, cria session cookie HttpOnly (`dr_session`), `secure=production`, `samesite=lax`, CSRF token retornado no body (não no cookie).
- `GET /api/auth/me`: retorna `{authenticated, role}` se session válida.
- `GET /api/auth/csrf`: refresh CSRF token (requer session cookie, não Bearer).
- `POST /api/auth/logout`: revoga session + deleta cookie.

## `app/routers/settings.py` (80 LOC) — Settings management
- `GET /api/settings`: `public_settings(db)` — retorna chaves mascaradas + modelos + `callback_url` + `openai_base_url`.
- `PUT /api/settings`: `update_settings` — aceita `provider_keys`, `models`, `callback_url`, `openai_base_url`; criptografa chaves via AES-256-GCM.
- `POST /api/settings/test`: `test_provider_key` — testa credencial sem persistir; lista modelos se sucesso.
- `POST /api/settings/models`: discovery manual por provider.
- `GET /api/settings/models`: discovery dinâmico via `runtime_settings`.

## `app/routers/research.py` (427 LOC) — Research pipeline
- `POST /api/research` → cria `Research(status=scouting)`, agenda `run_scout`.
- `GET /api/research` / `GET /api/research/{id}` — listagem + status detalhado.
- `POST /api/research/{id}/briefing/edit` — edita draft, valida dependências, agenda `run_revision`.
- `POST /api/research/{id}/briefing/approve` — aprova, cria `ResearchPoint`s, agenda `run_research`.
- `GET /api/research/{id}/events` + `/stream` — SSE com `Last-Event-ID` para retomada.
- `GET /api/reports/{id}` — relatório por `research_id` ou `report_id`.
- `POST /api/reports/{id}/retry-callback` — reenvio webhook.

**Fluxo interno (lifespan em `main.py`):**
- `lifespan`: startup recovery varre `scouting`, `revising`, `approved/in_progress` → re-agenda jobs.

## `app/main.py` (81 LOC) — FastAPI app
- Lifespan com recovery automático.
- Middleware: CORS (origins do settings), exception handler 422 limpo.
- Health check: `SELECT 1` no DB.

## Lacunas 🔴
1. `ResearchStatus` enum não tem `revising` mas usado em lifespan recovery (`research.py:68` filtra por `status == "revising"`).
