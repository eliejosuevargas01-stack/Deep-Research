# Spec: Módulo Qualidade + Migrações (tests, alembic)

> Archaeologist — módulo 6 de 6  
> Confidência: 🟢 CONFIRMADO

## `tests/test_backend.py` (2.226 LOC) — Monolítico
- Testes de **integração + unitários mistos**, sem separação.
- Cobertura:
  - Auth: login, CSRF, logout, session expiry, ambiguous creds, `x-tenant-id` rejection.
  - Settings: encrypt/decrypt/mask, provider test, model discovery.
  - Scout: source selection (3+ sites distintos), `read_source`, `search_read`.
  - `run_point` pipeline: citation audit, retry attempts, evidence quality.
  - `run_research`: full pipeline happy path, failed callback transition.
  - SSRF: `validate_public_url` rejeita loopback/link-local/private.
- `pytest` não instalado no venv (exit 127) — 🔴 bloqueio verificação.

## `tests/test_e2e_criteria.py` (86 LOC)
- E2E baseado em `CRITERIA.md`. Valida caminhos reais de API (auth → scout → briefing → approve → report → callback).

## `tests/test_postgres.py` (presumido ~300 LOC)
- Fixtures de banco isolado para testes (Docker Postgres ou SQLite em memória).

## Migrations (`app/tools/search_pipeline.py`... não) `alembic/versions/`:
| Rev | Data | Mudança |
|-----|------|---------|
| `0001_initial` | Schema base | Research, ResearchPoints, Evidence, Events, Reports, AuditTrails, AdminSessions, AppSettings |
| `0002_audit_trails` | AuditTrail table + índice `ix_audit_trails_research_id` |
| `0003_callback_base_url` | `callback_url` + `openai_base_url` em AppSettings |

## Débito técnico
- 🔴 `test_backend.py` monolítico (2.226 LOC) — alvo separação unitários `test_units/` vs integração `test_integration/`.

## Lacunas 🔴
1. `pytest` não instalado — setup venv pendente. Ver `questions.md`.
