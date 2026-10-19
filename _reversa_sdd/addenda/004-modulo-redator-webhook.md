# Adendo de Convergência: Módulo de Redação de Relatório Final e Entrega via Webhook

> Identificador da feature: `004-modulo-redator-webhook`  
> Data: `2026-10-19`  
> Cenário: `forward` (ancorado em PRD, SDD, pipeline assíncrono e validação E2E em produção)

## Vigência

Vigente desde 2026-10-19.

## Resumo da entrega

O módulo de redação e entrega conclui o pipeline do Deep Research Engine:
- 🟢 CONFIRMADO — Síntese de relatório Markdown acadêmico com no mínimo 200 palavras e correspondência estrita de títulos de tópicos investigados [`app/services/pipeline/writer.py:24-74`].
- 🟢 CONFIRMADO — Guardrails de citação factual: exigência de links inline `[texto](url)` para todas as asserções e restrição rigorosa ao conjunto de URLs coletadas (`linked_urls.issubset(known_urls)`) [`app/services/pipeline/writer.py:45-68`].
- 🟢 CONFIRMADO — Tolerância analítica a ressalvas: presença de tópicos em `AUDIT_CAVEAT` permite conclusão satisfatória com publicação do relatório em status `DONE` [`app/services/pipeline/writer.py:73`].
- 🟢 CONFIRMADO — Despacho de notificação assíncrona Webhook contendo metadados completos da pesquisa e relatório com proteção anti-SSRF via `PinnedResolver` [`app/services/webhook.py:20-85`, `app/tools/outbound.py:12-45`].
- 🟢 CONFIRMADO — Resiliência operacional: falhas externas de entrega no webhook não alteram o status da pesquisa para FAILED nem indisponibilizam o relatório na API [`app/services/webhook.py:65-80`].
- 🟢 CONFIRMADO — Restauração formal do endpoint `POST /api/research/{research_id}/briefing/approve` atendendo ao contrato de interação da interface web [`app/routers/research.py:100-140`].
- 🟢 CONFIRMADO — Comunicação de contêineres Docker via `TRUSTED_ROUTER_HOSTS` mantendo proteção SSRF para hosts externos [`app/core/config.py:48`, `app/services/settings.py:178-185`].
- 🟢 CONFIRMADO — Fallback resiliente contra cotas esgotadas de provedores de busca e leitura para Jina livre e DuckDuckGo [`app/services/search.py:280-320`, `app/tools/search_pipeline.py:200-240`].
- 🟢 CONFIRMADO — Prevenção de vulnerabilidade de ReDoS no scraping web através de `_SafeHTMLTextExtractor` baseado em `HTMLParser` [`app/services/search.py:25-50`].
- 🟢 CONFIRMADO — Total de 12 ações atômicas (T051 a T062) concluídas com 138 testes automatizados aprovados (exit 0) e execução comprovada em produção com pesquisa real [`_reversa_forward/004-modulo-redator-webhook/actions.md`, `progress.jsonl`].

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta | Nível e Evidência |
|---|---|---|---|---|
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Módulo de síntese factual (`app/services/pipeline/writer.py`) e persistência relacional da entidade `Report`. | 🟢 CONFIRMADO [`app/services/pipeline/writer.py:24-74`, `app/models/domain_models.py`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Despacho de webhook de callback com proteção anti-SSRF e evento de auditoria. | 🟢 CONFIRMADO [`app/services/webhook.py:20-85`] |
| `_reversa_sdd/sdd/briefing.md` | §6 Ciclo de Vida | regra-alterada | Restauração de `POST /api/research/{id}/briefing/approve` para compatibilidade com o frontend (HTTP 200 / 409). | 🟢 CONFIRMADO [`app/routers/research.py:100-140`, `tests/test_backend.py`] |
| `contracts.md` | Endpoints | contrato-alterado | Endpoint `/briefing/approve` documentado como ativo com idempotência; `/api/reports/{id}` expõe relatório com métricas de citação. | 🟢 CONFIRMADO [`contracts.md`, `app/routers/research.py`] |
| `app/core/config.py` | Configuração | delta-de-contrato-externo | Adição de `TRUSTED_ROUTER_HOSTS` para liberação controlada de hostnames de contêineres internos. | 🟢 CONFIRMADO [`app/core/config.py:48`] |
| `app/services/search.py` | Mecanismo de Busca | regra-alterada | Substituição de regex por `_SafeHTMLTextExtractor` (HTMLParser stdlib) e fallbacks contra HTTP 401/402. | 🟢 CONFIRMADO [`app/services/search.py:25-50,300-340`] |

## Regras sob vigilância

Os watch items abaixo garantem a estabilidade das entregas:
- 🟢 CONFIRMADO — `W001` a `W009` em `_reversa_forward/004-modulo-redator-webhook/regression-watch.md`.

## Fontes

- `_reversa_forward/004-modulo-redator-webhook/requirements.md`
- `_reversa_forward/004-modulo-redator-webhook/roadmap.md`
- `_reversa_forward/004-modulo-redator-webhook/actions.md`
- `_reversa_forward/004-modulo-redator-webhook/legacy-impact.md`
- `_reversa_forward/004-modulo-redator-webhook/regression-watch.md`
- `_reversa_forward/004-modulo-redator-webhook/progress.jsonl`
- `docs/E2E_VERIFICATION_REPORT.md`
