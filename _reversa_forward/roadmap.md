# Roadmap — Deep Research Engine Backend Modularization

> Gerado pelo ciclo Reversa Forward  
> Data: 2026-10-05  
> Milestone: Modularização Backend v1.0

## Visão Geral

Evoluir o pipeline cognitivo monolítico (`app/services/research.py`, 591 LOC) para uma arquitetura de agentes desacoplados e testáveis, mantendo compatibilidade completa com a API, modelo de dados e eventos SSE existentes.

## Fases e Milestones

### Fase 1: Preparação e Infraestrutura de Bases (Semana 1)
- Migrar `app/tools/search_pipeline.py` → `app/services/search.py` (REQ-01)
- Criar estrutura `app/services/workers/` com `__init__.py` e `base.py` (REQ-01, REQ-06)
- Definir interfaces `BaseWorker`, `WorkerResult`, `AuditVerdict` (REQ-01)
- Configurar ambiente de testes local (`venv`, `pytest`, `pytest-asyncio`, `pytest-cov`) (REQ-03, REQ-06)

### Fase 2: Modularização do Pipeline (Semana 2–3)
- Extrair `BaseWorker` (lógica comum de busca/extracção de evidências/persistência) (REQ-01, REQ-02)
- Criar `ScoutWorker` (`app/services/workers/scout.py`) (REQ-01)
- Criar 4 personas: `HistorianWorker`, `SkepticWorker`, `PragmatistWorker`, `FuturistWorker` (REQ-01)
- Criar `AuditorAgent` (`app/services/audit_agent.py`) (REQ-01)
- Criar `WriterAgent` (`app/services/workers/writer.py`) (REQ-01)
- Refatorar `app/services/research.py` para orquestrar via injeção de dependência (REQ-02, REQ-04)

### Fase 3: Testes e Validação (Semana 4)
- Testes unitários para cada worker (mocks LLM + Search) (REQ-03)
- Teste de integração E2E completo (REQ-04)
- Relatório de cobertura >= 80% (REQ-05)

### Fase 4: CI/CD e Qualidade (Semana 5)
- Configurar GitHub Actions: lint (ruff), type-check (mypy), testes, cobertura (REQ-06)
- Smoke test `docker-compose up` local (REQ-07)

## Prioridades de Risco

| Prioridade | Item | Risco | Mitigação |
|:----------:|------|-------|-----------|
| 🔴 Alto | Refactoring do orquestrador (`run_point` loop) | Quebra do recovery `lifespan` | Preservar API pública + teste `lifespan_recovery` |
| 🟡 Médio | Injeção de dependência de model/name por persona | Divergência entre settings JSON e worker | Validar via fixture de teste |
| 🟢 Baixo | SearchPipeline migration | Break import em `tools/` | Deprecar gradualmente, manter alias |

## Definição de Pronto (p/ Fase 2)
- Todos workers + agents extraídos com testes unitários
- `app/services/research.py` < 200 LOC (orquestração fina)
- Zero breaking changes na API pública
- `pytest tests/unit/ tests/integration/ -x --tb=short` verde
- Cobertura >= 80% em módulos novos
