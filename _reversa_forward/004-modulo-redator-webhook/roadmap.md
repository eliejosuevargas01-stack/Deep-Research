# Roadmap: Módulo de Redação de Relatório Final e Entrega via Webhook

> Identificador: `004-modulo-redator-webhook`  
> Data: `2026-10-19`  
> Requirements: `_reversa_forward/004-modulo-redator-webhook/requirements.md`

---

## 1. Fases e Sprints de Implementação

### Sprint C13 — Motor de Síntese e Guardrails do Redator
- Validação estrutural do relatório (`validate_report_quality`): extensão mínima, correspondência exata de títulos e tópicos.
- Verificação determinística de subconjunto de URLs citadas (`linked_urls.issubset(known_urls)`).
- Parser de conteúdo factual com exigência de citações `[texto](url)` em prosa substantiva.
- Persistência na entidade `Report` e transição definitiva da pesquisa para `ResearchStatus.DONE`.

### Sprint C14 — Despacho de Webhook Seguro e Proteção Anti-SSRF
- Pipeline de callback assíncrono em `app/services/webhook.py`.
- Resolução e bloqueio pré-conexão de IPs privados via `PinnedResolver` e `validate_public_url`.
- Registro de auditoria em `audit_trails` e emissão de eventos em `agent_event_logs`.
- Tolerância a falhas externas de webhook preservando integridade da pesquisa e disponibilidade do relatório na API.

### Sprint C15 — Resiliência de Infraestrutura e Validação E2E BDD
- Restauração formal do endpoint `POST /api/research/{research_id}/briefing/approve` exigido pelo frontend web.
- Suporte a hosts de proxy autorizados via variável `TRUSTED_ROUTER_HOSTS`.
- Fallbacks de busca contra cotas esgotadas (HTTP 402/401 Jina para endpoints abertos e DuckDuckGo).
- Substituição de regex de scraping vulnerável a ReDoS por parser de tags estrito da biblioteca padrão.
- Suíte completa de BDD em Behave (`features/005_auditoria_relatorio.feature` e `features/006_entrega_webhook.feature`).
