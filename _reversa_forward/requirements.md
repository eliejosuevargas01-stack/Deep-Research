# Requirements — Deep Research Engine Backend Modularization

> Documento gerado pelo ciclo Reversa Forward (Guiado)  
> Data: 2026-10-05  
> Status: **Rascunho validado** — aguardando Quality Audit

## 1. Objetivo Principal
Modularizar o pipeline cognitivo monolítico em `app/services/research.py` (591 loc) em uma arquitetura de agentes desacoplados, testáveis e extensíveis, mantendo **compatibilidade total** com a API, banco de dados e contrato de eventos SSE existentes.

## 2. Escopo da Primeira Fase (MVP Modularização Backend)

### 2.1 Estrutura de Módulos Alvo
```
app/services/
├── __init__.py
├── research.py              # Orquestrador fino (mantém API pública + lifespan recovery)
├── workers/
│   ├── __init__.py
│   ├── base.py              # BaseWorker (ABC): LLM client, search pipeline, evidence storage, heartbeat
│   ├── scout.py             # ScoutWorker: busca preliminar + geração de briefing (5 pontos)
│   ├── historian.py         # HistorianWorker: persona contextual + busca factual
│   ├── skeptic.py           # SkepticWorker: persona crítico + busca contraditória
│   ├── pragmatist.py        # PragmatistWorker: persona pragmático + busca aplicável
│   ├── futurist.py          # FuturistWorker: persona visionário + busca tendências
│   └── writer.py            # WriterAgent: síntese final Markdown com citações canônicas
├── audit_agent.py           # AuditorAgent: validação determinística + cognitiva + retry logic
├── llm.py                   # (existente) Gateway LiteLLM + guardrails
├── audit.py                 # (existente) Funções utilitárias de auditoria determinística
├── crypto.py                # (existente)
├── settings.py              # (existente)
├── webhook.py               # (existente)
└── search_pipeline.py       # (movido para app/tools/ ou mantido)
```

### 2.2 Contratos de Interface (ABC)

#### `BaseWorker` (abstração comum)
```python
class BaseWorker(ABC):
    def __init__(self, db: AsyncSession, settings: Settings, llm: LLMGateway, search: SearchPipeline):
        ...
    
    @abstractmethod
    async def execute(self, point: ResearchPoint, context: dict) -> WorkerResult:
        """Executa trabalho da persona e retorna evidências coletadas."""
        ...
    
    async def _search_and_extract(self, queries: list[str], point_id: UUID) -> list[Evidence]:
        """Busca multi-provedor + extração Jina Reader com deduplicação de domínio."""
        ...
    
    async def _store_evidence(self, evidence_list: list[Evidence]) -> None:
        """Persiste evidências com optimistic locking."""
        ...
```

#### `WorkerResult` (DTO padronizado)
```python
@dataclass
class WorkerResult:
    point_id: UUID
    persona: str
    evidences: list[Evidence]
    metrics: dict  # {queries_executed, sources_found, duration_ms, tokens_used}
    errors: list[str]  # vazio se sucesso
```

### 2.3 Fluxo do Orquestrador (`research.py` refinado)
1. `schedule(research_id)` → carrega pontos `ready` (DAG de dependências)
2. Para cada lote paralelo: cria tasks `worker.execute(point, context)` com `Semaphore(20)`
3. Coleta `WorkerResult`, persiste evidências, avança status do ponto
4. Chama `AuditorAgent.audit(point, evidences)` → retorna `AuditVerdict`
5. Se `APPROVED`: avança; se `RETRY` (até 3x): reexecuta worker com instruções; se `BLOCKED`: marca ponto e continua
6. Ao final: chama `WriterAgent.synthesize(research, all_evidences, audit_findings)` → persiste `Report`

### 2.4 Critérios de Aceite Técnicos

| ID | Critério | Verificação |
|---|---|---|
| **REQ-01** | `BaseWorker` + 4 personas + `WriterAgent` + `AuditorAgent` existem como arquivos separados em `app/services/workers/` e `app/services/audit_agent.py` | `ls app/services/workers/` |
| **REQ-02** | Orquestrador `research.py` importa e usa as classes concretas sem duplicar lógica de LLM/search/evidence | Code review |
| **REQ-03** | Testes unitários para cada worker (mock LLM + Search) rodam em < 30s total | `pytest tests/unit/workers/ -x --tb=short` |
| **REQ-04** | Teste de integração E2E completo: POST → SSE → briefing → workers → audit → report → webhook | `pytest tests/integration/test_full_pipeline.py -x` |
| **REQ-05** | Cobertura de código >= 80% (backend) | `pytest --cov=app --cov-report=term-missing` |
| **REQ-06** | Pipeline CI/CD GitHub Actions: lint (ruff), type-check (mypy), testes unit+integ, build docker | `.github/workflows/ci.yml` executando com sucesso |
| **REQ-07** | `docker-compose up` sobe stack completa (PostgreSQL + Backend + Frontend) com Swagger em `/docs` e SSE demo funcional | Smoke test manual |

### 2.5 Restrições e Não-Funcionais
- **Zero breaking changes** na API pública (`/api/research`, `/api/reports`, `/api/events`, `/api/auth`, `/api/settings`)
- **Migração de banco** apenas se necessário (Alembic versionado)
- **Backwards compatibility** do `lifespan` recovery (scouting, revising, in_progress)
- **Performance**: concorrência máxima mantida em 20 workers (Semaphore global)
- **Observabilidade**: logging estruturado (JSON) em cada worker + auditor + writer com `research_id`, `point_id`, `persona`

## 3. Requisitos Fora do Escopo (Futuro)
- Frontend componentização (`DataPanel.tsx` → componentes)
- Observabilidade avançada (Prometheus, OpenTelemetry, Grafana dashboards)
- Rate limiting por tenant / API key
- Multi-tenancy real (hoje single-admin)

---

## 4. Perguntas de Lacuna (Gap Analysis) — Para Quality Audit

1. **Contrato de `SearchPipeline`**: Hoje em `app/tools/search_pipeline.py`. Deve mover para `app/services/search.py` ou manter em `tools/`?
2. **Configuração de modelos por persona**: Hoje em `AppSettings.models` (JSON). Workers precisam de `model_name` injetado ou ler direto do settings?
3. **Prompt templates**: Estão em `app/prompts/`. Cada worker carrega seu template ou centraliza em `BaseWorker`?
4. **Métricas de custo/tokens**: Adicionar campos em `WorkerResult.metrics` para `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`?