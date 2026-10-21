# Adendo de Convergência: Convergência do Pipeline, Workers Jina, Barreira de Personas, Teto de Auditoria e Briefing Síncrono

> Identificador da feature: `005-convergencia-pipeline`  
> Data: `2026-10-21`  
> Cenário: `forward` (ancorado em PRD, SDD briefing, addenda 001–004 e diretrizes de convergência)

## Vigência

Vigente desde 2026-10-21.

## Resumo da entrega

A feature `005-convergencia-pipeline` estabelece a convergência definitiva do ciclo cognitivo e a robustez operacional do Deep Research Engine:
- 🟢 CONFIRMADO — Coleta integral de 10 páginas por pesquisa via Jina Search Tool (`num=10`), parser HTML defensivo via `_JinaHTMLCleaner` (stdlib `HTMLParser`) sem vulnerabilidades de ReDoS e validação de URLs via SSRF guard [`app/services/search.py`, `app/investigation/tools.py`].
- 🟢 CONFIRMADO — Orçamento de 1 a 3 queries por persona/ponto/rodada, primeira busca mandatória antes da entrega da análise final e validação rigorosa de citações exatas verbatim no texto fonte [`app/investigation/schemas.py`, `app/investigation/worker.py`].
- 🟢 CONFIRMADO — Persistência relacional de rodadas e barreira de merge: novas colunas `investigation_round` e `round`, tabela `investigation_merges` (migração Alembic `0008`) e persistência atômica das 4 análises válidas por ponto antes do acionamento do auditor [`alembic/versions/0008_...`, `app/models/domain_models.py`, `app/investigation/storage.py`].
- 🟢 CONFIRMADO — Auditoria factual sem truncamento (remoção do corte de 60k), vinculada estritamente ao snapshot committed de merge e com teto máximo de 4 tentativas (`MAX_AUDIT_ATTEMPTS=4`); 4ª reprovação gera `AUDIT_CAVEAT` (`is_caveat=True`) e encaminha ao Writer sem loop infinito [`app/audit/service.py`, `app/audit/domain.py`].
- 🟢 CONFIRMADO — Isolamento estrito de falhas de infraestrutura: erros de persona em tempo de execução gravam status `FAILED`, mas preservam `attempt_count=0` do ponto (tentativas consumidas exclusivamente por reprovação factual do auditor) [`app/investigation/storage.py`].
- 🟢 CONFIRMADO — Writer flexível com guardrails anti-alucinação: aceitação de seções enxutas com notas explícitas de limitação de evidência (`_LIMITATION_PATTERNS`) e propostas conceituais (`_is_nonfactual_proposal`) sem piso de 200 palavras e com proibição absoluta de URLs inventadas inline [`app/services/pipeline/writer.py`].
- 🟢 CONFIRMADO — Orquestração por lotes topológicos (`ready_point_batches`) respeitando dependências entre pontos e paralelismo seguro de 4 personas por ponto sem semáforos globais [`app/investigation/service.py`].
- 🟢 CONFIRMADO — Transição atômica CAS para o status `WRITE` e fechamento explícito da sessão SQLAlchemy antes de acionar a LLM do Writer, prevenindo retenção de locks transacionais de banco durante processamento de rede [`app/investigation/service.py`].
- 🟢 CONFIRMADO — Briefing HTTP estritamente síncrono e de decisão única: POST `/briefings` retorna 201 gerado e persistido, PATCH `/briefings/{id}` revisa e autoaprova com 200, POST `/briefings/{id}/investigate` inicia investigação exclusiva em background com 202, rejeitando chamadas redundantes com 409 Conflict e sem rotas alternativas de aprovação [`app/briefing/router.py`, `app/briefing/service.py`].
- 🟢 CONFIRMADO — Adaptador `run_research` em `app/services/research.py` delegando para `InvestigationService`, preservando retrocompatibilidade, eventos SSE e contratos legados de consulta GET `/api/reports/{id}` e `/retry-callback` idempotente sem duplicação de relatório [`app/services/research.py`, `app/routers/research.py`].
- 🟢 CONFIRMADO — Total de 31 ações atômicas (T001 a T031) concluídas com 172 testes e 162 subtestes automatizados aprovados (100% GREEN, RC: 0), validação do ciclo de migração em PostgreSQL 16 efêmero via Docker e preservação de 100% da integridade dos 4 arquivos protegidos do repositório.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta | Nível e Evidência |
|---|---|---|---|---|
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Coleta de 10 páginas integrais via Jina (`num=10`), parser HTML stdlib e SSRF guard. | 🟢 CONFIRMADO [`app/investigation/tools.py`, `tests/investigation/test_jina_tool.py`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-nova | Orçamento de 1–3 queries por persona, busca mandatória no 1º turno e citação verbatim. | 🟢 CONFIRMADO [`app/investigation/worker.py`, `tests/investigation/test_persona_worker.py`] |
| `_reversa_sdd/prd.md` | §5 Dados | delta-de-dados | Tabela `investigation_merges`, colunas de rodada `investigation_round` e `round` (migração 0008). | 🟢 CONFIRMADO [`alembic/versions/0008_...`, `tests/investigation/test_round_migration.py`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-alterada | Barreira de 4 personas para merge; erro técnico não consome cota de tentativa de auditoria. | 🟢 CONFIRMADO [`app/investigation/storage.py`, `tests/investigation/test_round_storage.py`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-alterada | Auditoria por merge committed sem corte de 60k; teto de 4 tentativas (`AUDIT_CAVEAT`). | 🟢 CONFIRMADO [`app/audit/service.py`, `tests/audit/test_audit_round_merge.py`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | regra-alterada | Writer flexível com guardrail de notas de limitação e proposta didática sem URLs fictícias. | 🟢 CONFIRMADO [`app/services/pipeline/writer.py`, `tests/unit/test_pipeline_writer_convergence.py`] |
| `_reversa_sdd/sdd/briefing.md` | §3 Interfaces | regra-alterada | Briefing síncrono e decisão única (POST 201, PATCH 200, investigate 202, 409 em duplicidade). | 🟢 CONFIRMADO [`app/briefing/router.py`, `tests/test_briefing_*.py`] |
| `_reversa_sdd/prd.md` | §4 Arquitetura | componente-novo | Orquestrador topológico (`ready_point_batches`) e adaptador `run_research` -> `InvestigationService`. | 🟢 CONFIRMADO [`app/services/research.py`, `app/investigation/service.py`, `tests/integration/`] |

## Regras sob vigilância

Os watch items abaixo garantem a estabilidade permanente das entregas:
- 🟢 CONFIRMADO — `W001` a `W009` em `_reversa_forward/005-convergencia-pipeline/regression-watch.md`.

## Fontes

- `_reversa_forward/005-convergencia-pipeline/requirements.md`
- `_reversa_forward/005-convergencia-pipeline/roadmap.md`
- `_reversa_forward/005-convergencia-pipeline/actions.md`
- `_reversa_forward/005-convergencia-pipeline/legacy-impact.md`
- `_reversa_forward/005-convergencia-pipeline/regression-watch.md`
- `_reversa_forward/005-convergencia-pipeline/progress.jsonl`
- `_reversa_forward/005-convergencia-pipeline/interfaces/pipeline-http.md`
- `_reversa_forward/005-convergencia-pipeline/audit/code-collection-data.md`
- `_reversa_forward/005-convergencia-pipeline/audit/qa-collection-data.md`
- `_reversa_forward/005-convergencia-pipeline/audit/code-lifecycle-writer.md`
- `_reversa_forward/005-convergencia-pipeline/audit/qa-lifecycle-writer.md`
- `_reversa_forward/005-convergencia-pipeline/audit/code-http-integration.md`
- `_reversa_forward/005-convergencia-pipeline/audit/qa-http-integration.md`
