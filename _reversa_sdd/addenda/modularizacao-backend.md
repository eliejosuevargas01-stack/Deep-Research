# Adendo — Modularização Backend (modularizacao-backend)

**Feature**: `modularizacao-backend` (REQ-01..REQ-07)
**Data**: 2026-10-06
**Cenário**: legado

## Vigência

Vigente desde 2026-10-06.

## Resumo da entrega

Objetivo (do requirements.md): modularizar o pipeline cognitivo monolítico em `app/services/research.py` (591 LOC) em uma arquitetura de agentes desacoplados, testáveis e extensíveis, mantendo compatibilidade total com a API, banco de dados e contrato de eventos SSE existentes.

Ações concluídas: **53/53** (T001–T013 + T011-FIX + 4 sprints frontend).
- T001–T009: extração dos 5 workers + auditor + writer para `app/services/workers/`
- T010: refatoração do orquestrador `research.py` 591 → 161 LOC, estágios movidos para `app/services/pipeline/`
- T011: teste E2E integração completa (fixado em T011-FIX)
- T012: CI/CD GitHub Actions + cobertura
- T013: docker-compose + README + smoke test
- 4 sprints frontend: a11y, design system Linear-inspired, bundle split, docs

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/architecture.md` | 3.2 Serviços (Orchestrator) | `componente-novo` | Package `app/services/pipeline/` criado com 6 módulos: `scout.py`, `worker.py`, `audit_stage.py`, `point_executor.py`, `writer.py`, `constants.py`; orquestrador fino mantém API pública via re-export |
| `_reversa_sdd/architecture.md` | 3.2 Serviços (Workers) | `componente-novo` | Package `app/services/workers/` criado com 7 módulos: `base.py`, `scout.py`, `historian.py`, `skeptic.py`, `pragmatist.py`, `futurist.py`, `writer.py` + factory `create_workers()` |
| `_reversa_sdd/architecture.md` | 3.2 Serviços (Orchestrator) | `regra-alterada` | `app/services/research.py` 591 → 161 LOC; lógica extraída verbatim, API pública preservada (17 símbolos re-exportados) |
| `_reversa_sdd/domain.md` | Regras R-01..R-07 | *(inalterado)* | Todas as 7 regras 🟢 preservadas semanticamente: verbatim citation (R-01), SSRF guard (R-02), error sanitization (R-03), auditor retry (R-04), lifespan recovery (R-05), evidence idempotency (R-06), semaphore concurrency (R-07) |
| `_reversa_sdd/architecture.md` | 3.3 Testes | `regra-alterada` | Testes monkeypatch atualizados: `app.services.research.complete` → `app.services.pipeline.scout.complete`; testes unitários + integração passam |
| `_reversa_sdd/architecture.md` | 3.4 Config/Settings | `regra-alterada` | Nova coluna `jina_base_url` em `AppSettings` + schema + runtime getter + frontend field (BUG-20261006-57LI) |
| `_reversa_sdd/architecture.md` | 3.2 Serviços (Audit) | `regra-alterada` | `_audit_point()` com try/except para LLM 503 → graceful degradation: ponto `blocked`, research continua (BUG-20261005-7H2K) |
| `_reversa_sdd/architecture.md` | 3.2 Serviços (PointExecutor) | `regra-alterada` | `_run_point()` com try/except isolado por ponto → falha não mata research inteira |

## Regras sob vigilância

`W001`–`W011` — ver `_reversa_forward/modularizacao-backend/regression-watch.md`

## Fontes

- `_reversa_forward/modularizacao-backend/legacy-impact.md`
- `_reversa_forward/modularizacao-backend/progress.jsonl`
- `_reversa_forward/modularizacao-backend/requirements.md`
- `_reversa_forward/modularizacao-backend/regression-watch.md`
- `_reversa_forward/modularizacao-backend/actions.md`
