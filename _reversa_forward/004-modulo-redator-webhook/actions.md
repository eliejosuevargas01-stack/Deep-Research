# Ações: Módulo de Redação de Relatório Final e Entrega via Webhook

> Identificador: `004-modulo-redator-webhook`  
> Data: `2026-10-19`  
> Requirements: `_reversa_forward/004-modulo-redator-webhook/requirements.md`  
> Roadmap: `_reversa_forward/004-modulo-redator-webhook/roadmap.md`

---

## Tabela de Ações Atômicas

| ID | Ação | Sprint | Responsável | Arquivos Permitidos | Status | Check |
|---|---|---|---|---|---|---|
| **T051** | Implementar `validate_report_quality` e `_write_report` em `app/services/pipeline/writer.py` com checagem de 200 palavras mínimas, títulos exatos e citações `[texto](url)` obrigatórias. | C13 | Worker | `app/services/pipeline/writer.py` | 🟢 CONFIRMADO | [X] |
| **T052** | Implementar validação estrita de subconjunto de URLs citadas (`linked_urls.issubset(known_urls)`) rejeitando relatórios que citem fontes não coletadas pelas personas. | C13 | Worker | `app/services/pipeline/writer.py` | 🟢 CONFIRMADO | [X] |
| **T053** | Implementar persistência do modelo relacional `Report` com `citation_metrics` e `audit_findings` em banco de dados e garantir status final `DONE` na pesquisa. | C13 | Worker | `app/services/pipeline/writer.py`, `app/models/domain_models.py` | 🟢 CONFIRMADO | [X] |
| **T054** | Implementar serviço assíncrono de callback webhook em `app/services/webhook.py` com formatação do payload JSON contendo `research_id`, `report_id`, `theme`, `content_markdown` e `generated_at`. | C14 | Worker | `app/services/webhook.py` | 🟢 CONFIRMADO | [X] |
| **T055** | Aplicar guardrails anti-SSRF em `app/tools/outbound.py` com `PinnedResolver` bloqueando loopback, RFC 1918 e link-local antes da conexão TCP. | C14 | Worker | `app/tools/outbound.py`, `app/services/webhook.py` | 🟢 CONFIRMADO | [X] |
| **T056** | Garantir resiliência na entrega de webhook: requisições com resposta HTTP 500 ou erro de rede não abortam o status da pesquisa, registrando evento em `agent_event_logs` e `audit_trails`. | C14 | Worker | `app/services/webhook.py`, `app/services/research.py` | 🟢 CONFIRMADO | [X] |
| **T057** | Restaurar endpoint formal `POST /api/research/{research_id}/briefing/approve` no backend retornando HTTP 200 na aprovação inicial e 409 em tentativas repetidas para atender a interface web. | C15 | Worker | `app/routers/research.py` | 🟢 CONFIRMADO | [X] |
| **T058** | Adicionar suporte a `TRUSTED_ROUTER_HOSTS` em `app/core/config.py` e `app/services/settings.py` para permitir comunicação segura entre contêineres Docker com o 9router. | C15 | Worker | `app/core/config.py`, `app/services/settings.py`, `docker-compose.yml` | 🟢 CONFIRMADO | [X] |
| **T059** | Implementar fallbacks para busca e leitura web em caso de erros de quota Jina (HTTP 401/402) com chave vazia e fallback DuckDuckGo. | C15 | Worker | `app/services/search.py`, `app/tools/search_pipeline.py`, `app/investigation/tools.py`, `app/briefing/serp_client.py` | 🟢 CONFIRMADO | [X] |
| **T060** | Eliminar vulnerabilidade de ReDoS em extração de texto HTML de scraping substituindo expressões regulares catastróficas por `_SafeHTMLTextExtractor` baseado em `HTMLParser` stdlib. | C15 | Worker | `app/services/search.py`, `app/tools/search_pipeline.py` | 🟢 CONFIRMADO | [X] |
| **T061** | Implementar suítes de testes BDD Cucumber / Behave cobrindo síntese de relatório (`features/005_auditoria_relatorio.feature`) e entrega de webhook (`features/006_entrega_webhook.feature`). | C15 | Worker | `features/005_auditoria_relatorio.feature`, `features/steps/auditoria_relatorio_steps.py`, `features/006_entrega_webhook.feature`, `features/steps/entrega_webhook_steps.py` | 🟢 CONFIRMADO | [X] |
| **T062** | Validar execução de pesquisa ponta a ponta em ambiente de produção Coolify com relatório gerado, métricas de citação verificadas e persistência comprovada em banco PostgreSQL real. | C15 | Worker | `tests/e2e_production_probe.py` | 🟢 CONFIRMADO | [X] |
