# S1 — Núcleo & Persistência
> Reversa SDD · doc_level=2 · organização: módulo

## Arquivos & LOC
| Arquivo | LOC | Responsabilidade |
|---------|-----|------------------|
| `app/core/config.py` | 57 | Settings Pydantic, validações de env |
| `app/core/security.py` | 114 | Auth JWT Cookie + CSRF, Bearer, API-Key |
| `app/db/database.py` | 48 | Engine async SQLAlchemy + session scope |
| `app/models/domain_models.py` | 128 | 8 entidades Declarative Base |
| `app/schemas/__init__.py` | 157 | Pydantic request/response |
| `alembic/versions/0001–0005` | ~160 | Migrations iniciais + jina proxy |
| **Total S1** | **~724** | |

## Superfície (classes, enums, tabelas)

### config.py
- **Settings** — Pydantic model com `env` (development), `database_url`, `cors_origins`, `jina_base_url`, `jina_proxy_url`, `jina_proxy_timeout_seconds`, `session_secret`, `session_ttl_hours`
- 🟢 Confirma: `jina_proxy_url` e `jina_proxy_timeout_seconds` existem em config e em `AppSettings` (migration 0005) — consistentes

### security.py
- **COOKIE = "dr_session"** — nome do cookie de sessão
- **MUTATIONS** — `{"POST","PUT","PATCH","DELETE"}` — métodos que exigem CSRF
- **Principal** — dataclass: `session: AdminSession | None`, `via_bearer`, `via_api_key`
- **digest()** — HMAC-SHA256 de `jti` com `settings.SESSION_SECRET`
- **require_admin()** — logic de auth: rejeita múltiplos credentials simultâneos, valida Bearer/API-Key/cookie, check CSRF em mutações
- 🟡 Inferido: `via_api_key=True` — X-API-Key usa `settings.API_AUTH_SECRET` (mesmo secret que Bearer), não há key separada por tenant

### database.py
- **get_db()** — dependência FastAPI, yield `AsyncSession`
- **create_async_engine()** — pool_size=20, max_overflow=10 (limites de concorrência do banco)
- 🟢 Confirma: pool_size=20 alinha com semâforo de 20 pesquisadores (MA-01)

### domain_models.py — 8 entidades
1. **ResearchStatus** (enum) — `scouting`, `pending_approval`, `revising`, `approved`, `in_progress`, `completed`, `completed_but_callback_failed`, `blocked`, `failed`, `interrupted`
   - 🟢 `revising` **já existe** no enum (LACUNA 1 do code-analysis está obsoleta)
2. **Research** — id(UUID), theme(500), callback_url(2048), status(32), briefing_draft(JSON), error(Text), approved_at, created_at, updated_at
3. **ResearchPoint** — id, research_id(FK CASCADE), position, title(500), description, dependencies(JSON), is_parallelizable, status(32), attempt_count, audit(JSON)
4. **Evidence** — id, research_point_id(FK CASCADE), persona(24), source_url(Text), source_title, excerpt, claim, analysis, accessed_at, version (optimistic locking)
   - **UniqueConstraint(research_point_id, persona, source_url)** — `uq_evidence_source`
5. **Event** (tabela `agent_event_logs`) — id(int auto), research_id(FK CASCADE), persona(24), event_type(64), summary(500), metrics(JSON), created_at
6. **Report** — id, research_id(FK CASCADE, **unique**), content_markdown, citation_metrics(JSON), audit_findings(JSON), generated_at
7. **AuditTrail** — id(int auto), research_id(FK CASCADE), point_id(FK nullable), stage(32), attempt(int nullable), details(JSON), created_at
8. **AdminSession** — id(UUID), token_hash(64, unique, index), csrf_hash(64), expires_at, revoked_at(nullable), created_at
9. **AppSettings** — id(int, PK=1 singleton), encrypted_credentials(JSON), models(JSON), callback_url(2048), openai_base_url(2048), jina_base_url(2048), jina_proxy_url(2048), jina_proxy_timeout_seconds(int), updated_at

> ⚠️ domain_models tem **9 classes** (8 entidades + Base) mas `AppSettings` faz o nono papel de entidade; `Event` é a entidade de streaming SSE

### Migrations 0001→0005
| Mig | Cria | Diff SDD vs código |
|-----|------|--------------------|
| 0001 | Todas as tabelas iniciais | 🟢 Confirma |
| 0002 | `audit_trails` + índice | 🟢 Confirma |
| 0003 | `callback_url` + `openai_base_url` em app_settings | 🟢 Confirma |
| 0004 | `jina_base_url` em app_settings | 🟢 Confirma |
| 0005 | `jina_proxy_url` + `jina_proxy_timeout_seconds` em app_settings | 🟢 Confirma |

### Schemas
**Enums:**
- `PointStatus` — pending, in_progress, approved, blocked, failed
- `Personas` — historian, skeptic, pragmatist, futurist

**Core Models:**
- `ResearchCreate` — theme (min 3, max 500), callback_url (validade de URL)
- `BriefingApproval` — approved(bool) + notes
- `PointDetail` — id, title, description, status, attempt_count, is_parallelizable
- `EvidencePayload` — persona, source_url, source_title, excerpt (min 40), claim, analysis
- `EventOut` — id, persona, event_type, summary, metrics
- `AuditPayload` — approved, findings (12 itens), outline, feedback
- `SessionSettings` — session_secret, session_ttl_hours, cors_origins
- `SettingsUpdate` — api_key, models dict, callback_url, openai_base_url, jina_base_url, jina_proxy_url, jina_proxy_timeout_seconds
- `CallbackSettings` — callback_url
- `SettingsView` — models, callback_url, openai_base_url, jina_base_url, jina_proxy_url, jina_proxy_timeout_seconds, has_api_key

## Gaps
| # | Tipo | Descrição |
|---|------|-----------|
| G1 | 🟡 | `settings.py` no services faz hot-reload de `jina_base_url`/`jina_proxy_url` mas `AppSettings` não tem campo `jina_proxy_timeout_seconds` com default — migration 0005 não define `server_default` |
| G2 | 🔴 | `AppSettings.id` é `Integer PK=1` (singleton) mas migration 0001 não explicitamente mostra `pk=1` default — verificar seed |
| G3 | 🟡 | `domain.md` lista "8 entidades" mas `domain_models.py` tem 9 classes (Base excluída); `Event` (agent_event_logs) é a 9ª |
