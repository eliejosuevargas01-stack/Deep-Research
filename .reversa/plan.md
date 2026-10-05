# Plano Reversa — Deep Research Engine

> Modo autônomo. Checkpoint após cada agente.

## Fase 1 — Exploração Geral ✅
- [X] **Scout** → `_reversa_sdd/surface.json` (61 arquivos, Python dominante, sugerida organização por feature)

## Fase 2 — Extração Específica (arquitetura, domínio, código)
- [ ] **app/core + app/db + app/models + app/schemas** → spec módulo fundação (config, security, DB engine, domain models, Pydantic schemas)
- [ ] **app/routers + app/main** → spec módulo API ingress (auth, settings, research, SSE, lifespan recovery)
- [ ] **app/services** → spec módulo pipeline cognitivo (research.py orquestrador 591 LOC, llm.py gateway, audit.py, crypto.py, settings.py, webhook.py)
- [ ] **app/tools + app/prompts** → spec módulo integrações externas (search_pipeline, outbound SSRF, personas.json)
- [ ] **frontend/src** → spec módulo frontend (main.tsx monolítico, api.ts SSE client, types.ts, routes.ts)
- [ ] **tests + alembic** → spec módulo qualidade e migrações (test_backend 2226 LOC, e2e, postgres fixtures, migrations 0001-0003)
- [ ] **Architect** → `_reversa_sdd/architecture.md` (consolida análise dos módulos, C4, contratos)
- [ ] **Data Master** → `_reversa_sdd/domain.md` (ERD, 8 entidades, restrições)
- [ ] **Inspector** → `_reversa_sdd/code-analysis.md` (débito técnico, métricas)
- [ ] **Detective** → `_reversa_sdd/business-knowledge.md` (conhecimento implícito, logs)
- [ ] **Quality (doc_level completo)** → C4 context/container, ERD, ADRs, OpenAPI, matrizes de rastreabilidade

## Fase 3 — Verificação de Regressão
- [ ] `step-04-regression-check.md` → comparar extração nova vs `_reversa_sdd/` existente, apontar divergências
