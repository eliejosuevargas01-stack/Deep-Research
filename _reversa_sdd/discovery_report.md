# DISCOVERY REPORT — Deep Research Engine

Total de Arquivos: 24
Carga Lógica (Loc): 5578

| Arquivo | Linhas | Classes | Funções |
|---|---|---|---|
| tests/test_backend.py | 2226 |  | init_test_db, client, login |
| app/services/research.py | 591 |  | extract_site_domain, sanitize_audit_dict, point_dependencies |
| app/services/llm.py | 558 | ProviderConfigurationError | _enforce_safe_transport, apply_output_guardrail, _provider |
| app/routers/research.py | 427 |  | schedule, run_scout, schedule_scout |
| app/services/settings.py | 351 |  | _allowed_base_url_ports, _is_trusted_proxy_url, _is_private_dns_allowed |
| app/tools/search_pipeline.py | 227 | Source, SearchProviderError | _get, _apify_search, _duckduckgo_search |
| app/models/domain_models.py | 124 | Base, ResearchStatus, Research | now |
| app/CRITERIA.md | 120 |  |  |
| tests/test_postgres.py | 116 |  | _isolated_postgres_url, _remove_test_research, isolated_research |
| app/core/security.py | 114 | Principal | digest, require_admin, new_session_values |
| tests/test_e2e_criteria.py | 86 |  | test_criteria_full_flow |
| app/main.py | 81 |  | lifespan, validation_exception_handler, health |
| app/routers/settings.py | 80 |  | get_settings, put_settings, test_setting_key |
| alembic/versions/0001_initial.py | 60 |  | upgrade, downgrade |
| app/core/config.py | 57 | Settings | get_settings |
| app/services/webhook.py | 56 |  | dispatch_callback, add_callback_event |
| app/tools/outbound.py | 51 | SSRFSecurityViolation, PinnedResolver | _validate_ip, validate_public_url |
| app/routers/auth.py | 49 |  | login, me, refresh_csrf |
| app/db/database.py | 48 |  | get_db, session_scope |
| alembic/env.py | 38 |  | run_migrations_offline, do_run_migrations, run_async_migrations |
| app/services/audit.py | 35 |  | deterministic_citation_audit, audit_approves, next_audit_state |
| app/services/crypto.py | 32 |  | _key, encrypt_secret, decrypt_secret |
| alembic/versions/0002_audit_trails.py | 29 |  | upgrade, downgrade |
| alembic/versions/0003_settings_callback_and_base_url.py | 22 |  | upgrade, downgrade |

## Principais Pontos de Incentivo ao Refactoring
1. **Arquitetura Backend Modular (app/services/research.py):**
   - O arquivo contém pipeline de 4 fases acoplada (Scout, Workers, Auditor, Redator) tratando concorrência, banco e APIs externas.
   - ~592 lines sugerem alta complexidade.

2. **Interface Frontend Grande (frontend/src/DataPanel.tsx):**
   - Arquivo monolítico com gerenciamento de estado, carregamento via POST/SSE, filtragem e renderização visual.

## Próximos Passos Guiados
Vamos agora identificar os **principais requisitos** para cobrir as lacunas deste Discovery Report.