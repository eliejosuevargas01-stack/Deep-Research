# Spec: Módulo Fundação (core, db, models, schemas)

> Archaeologist — módulo 1 de 6  
> Confidência: 🟢 CONFIRMADO (código lido diretamente)

## Componentes

### `app/core/config.py` (57 LOC) — Settings Pydantic
- `Settings(BaseSettings)` via `pydantic-settings`, lê `.env`.
- Campos: `DATABASE_URL`, `SESSION_SECRET`, `SESSION_TTL_HOURS`, `API_AUTH_SECRET`, `APP_ENCRYPTION_KEY`, `SEARCH_TIMEOUT_SECONDS`, `ENVIRONMENT`, `origins` (CORS).
- Singleton `get_settings()` com cache.

### `app/core/security.py` (114 LOC) — Auth e CSRF
- Cookie `dr_session` HttpOnly; JWT HS256 com `jti`.
- `require_admin(request, db) -> Principal`: dependency FastAPI.
  - 🟢 **Regra A-04:** header `x-tenant-id` é **proibido** → HTTP 400.
  - 🟢 Credenciais múltiplas (cookie + Bearer + API key simultâneos) → HTTP 400 "Ambiguous authentication".
  - Bearer/X-API-Key: `hmac.compare_digest` contra `API_AUTH_SECRET`.
  - Sessão: JWT decode → hash do `jti` → lookup em `admin_sessions`; revogada/expirada → 401.
  - 🟢 Mutations (POST/PUT/PATCH/DELETE) exigem `X-CSRF-Token` com `hmac.compare_digest` contra `csrf_hash`.
- `new_session_values()`: emite JWT + CSRF token + registro `AdminSession`.
- Fallback legado: token opaco tratado como `jti_digest = digest(raw_cookie)` (migração segura).

### `app/db/database.py` (48 LOC) — Engine assíncrono
- Engine SQLAlchemy async (`asyncpg` para Postgres, `aiosqlite` para SQLite) com `sessionmaker` async.
- `get_db`: dependency generator FastAPI; `session_scope`: context manager.

### `app/models/domain_models.py` (124 LOC) — 8 entidades
- `Research`, `ResearchPoint`, `Evidence`, `Event`, `Report`, `AuditTrail`, `AdminSession`, `AppSettings` (detalhes em `domain.md`).
- `ResearchStatus` enum: `scouting, pending_approval, approved, in_progress, completed, completed_but_callback_failed, blocked, failed, interrupted` (🟢; `revising` usado em `main.py` lifespan mas não no enum — 🔴 LACUNA, ver `questions.md`).

### `app/schemas/__init__.py` (152 LOC) — Schemas Pydantic
- Request/response para auth, settings, research (create, briefing edit/approve), events SSE, reports.
- 🟢 Validação `callback_url` via `validate_public_url` (import tardio para evitar ciclo).

## Dependências internas
```
config.py ← security.py, database.py (env), llm.py, crypto.py, settings service
database.py ← security.py, todos routers, services
domain_models.py ← security.py (AdminSession), todos services/routers
schemas ← routers (validação), frontend (contrato)
```

## Lacunas 🔴
1. `ResearchStatus` enum não contém `revising`, mas `main.py:25` filtra por `Research.status == "revising"` — valor vem do service, não do enum. Ver `_reversa_sdd/questions.md`.
