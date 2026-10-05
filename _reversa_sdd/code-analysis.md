# Code Analysis — Deep Research Engine

> Inspector — consolidação 6 módulos + métricas + débito  
> Doc level: Completo (métricas LOC, padrões, traceability)  
> Regenerado: 2026-10-05 (ciclo autônomo)

---

## 1. Estrutura de Módulos e LOC

| Módulo | Arquivos | LOC | Responsabilidade |
|--------|----------|-----|------------------|
| `app/core` | 2 | 229 | Settings + Auth/CSRF |
| `app/db` | 1 | 48 | Engine async + session |
| `app/models` | 1 | 124 | 8 entidades Declarative |
| `app/schemas` | 1 | 152 | Pydantic request/response |
| `app/routers` | 3 | 556 | Auth(49), Settings(80), Research(427) |
| `app/services` | 7 | 1,687 | Research(591), LLM(558), Settings(351), Crypto(32), Audit(35), Webhook(56) |
| `app/tools` | 2 | 278 | Search pipeline(227), Outbound(51) |
| `app/prompts` | 2 | personas.json | init vazio (0 bytes) |
| `frontend/src` | 6 | 5,357 | main.tsx(2546), style.css(2014), utils(549), api(132), types(83), routes(33) |
| `tests` | 3 | ~2,500 | test_backend(2226), test_e2e(86), test_postgres(~200) |
| `alembic` | 3 | ~100 | migrations 0001-0003 |

**Total backend Python**: ~3,074 LOC | **Frontend**: 5,357 LOC

## 2. Padrões de Segurança (🟢 confirmados)

| Padrão | Arquivo | Detalhe |
|--------|---------|---------|
| Output Guardrail | `llm.py:apply_output_guardrail` | Regex `sk|gsk|ghp|gho` + bearer/token/secret; redige antes de persistir |
| SSRF Defence | `outbound.py` | validate_public_url + PinnedResolver + no redirects (fail-closed) |
| LiteLLM SafeTransport | `llm.py:_enforce_safe_transport` | Monkey-patch follow_redirects=False, fail-closed |
| Concurrency | `research.py` | Semaphore(20), batches topológicos (MA-01) |
| Audit Cycle | `audit.py` + `remaining_attempts` | 4 execuções (1+3 retries); 4ª reprovação → BLOCKED |
| Verbatim Citation | `audit.py:deterministic_citation_audit` | claim.casefold() in excerpt.casefold() obrigatório |

## 3. Débito Técnico

| Área | Situação | Impacto | Plano |
|------|----------|---------|-------|
| Orquestrador monolítico | `research.py` 591 LOC | Difícil testar/modificar | T010: <200 LOC + workers/ |
| Frontend monolítico | `main.tsx` 2546 LOC | Zero separação | T005: componentes |
| Testes mistos | `test_backend.py` 2226 LOC | Sem isolamento | T011: separar |
| Search pipeline legado | `tools/search_pipeline.py` | Migração | T001: services/search.py |
| Prompts vazio | `prompts/__init__.py` | Dead code? | LACUNA 2 |
| pytest ausente | venv | Bloqueia testes | LACUNA 4 |
| Read source 8000 chars | `search_pipeline.py:205,217` | Perde citação em artigos longos | LACUNA 3 |
| Status revising fora enum | `domain_models.py:18-27` | Inconsistência | LACUNA 1 |

## 4. Padrões de Código

| Padrão | Onde | Status |
|--------|------|-------|
| Dependency Injection | FastAPI Depends | ✅ |
| Async Context Managers | session_scope | ✅ |
| Pydantic Validation | schemas + validate_base_url | ✅ |
| Optimistic Locking | Evidence.version | ✅ (sem teste concorrência) |
| Error Sanitization | sanitize_error/audit_dict | ✅ |
| Fail-closed SSRF | outbound + SafeTransport | ✅ |

## 5. Traceability

| Critério | Código | Evidência |
|----------|--------|------------|
| A-01 | `_scout_impl:149-159` site_map | distinct_sources >= 3 |
| A-02 | sanitize_error regex | test_sanitize_error |
| A-04 | security.py:32-34 + api.ts | test_auth_cookie_csrf_and_logout |
| A-05 | security.py:41-47 | test dedicated |
| D | outbound.py | test_ssrf_guard |
| MA-01 | ready_point_batches | topologia |
| MA-08 | audit.py:next_audit_state | retry concreto |

## 6. Lacunas → questions.md

1. LACUNA 1: ResearchStatus sem `revising`
2. LACUNA 2: prompts/__init__.py vazio
3. LACUNA 3: read_source 8000 chars vs verbatim contract
4. LACUNA 4: pytest não instalado
5. LACUNA 5: main.tsx monolítico (prioridade refactoring)

## 7. Recomendações

1. Instalar pytest no venv (habilita T001 checkpoint).
2. Adicionar `REVISING = "revising"` ao enum (baixo risco).
3. Remover `prompts/__init__.py` ou popular com prompts .md.
4. Avaliar truncamento 8000 → 20000 chars ou smart-truncate.
5. Iniciar T001: search_pipeline → services/search.py.
