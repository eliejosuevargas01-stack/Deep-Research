# Legacy Impact — Feature 004: Módulo de Redação de Relatório Final e Entrega via Webhook

- **Feature:** `004-modulo-redator-webhook`
- **Data de Fechamento:** 2026-10-19
- **Política de Edição do Legado:** `allowLegacyEdits: true`, `allowedPaths: ["*"]`
- **Status Geral:** Concluído e verificado em ambiente real

## 1. Mapeamento de Arquivos Afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `app/services/pipeline/writer.py` | Pipeline de Redação | `regra-alterada` | HIGH | Fixação definitiva do status `ResearchStatus.DONE.value` mesmo com ressalvas (`AUDIT_CAVEAT`), guardrails rigorosos de citação e extensão mínima. |
| `app/models/domain_models.py` | Modelo de Domínio | `regra-alterada` | MEDIUM | Relacionamento da entidade `Report` com `Research` e `ResearchPoint`. |
| `app/services/webhook.py` | Notificações Externas | `regra-alterada` | HIGH | Proteção anti-SSRF com `PinnedResolver`, formatação do payload de entrega e resiliência a falhas HTTP 5xx do webhook. |
| `app/routers/research.py` | Routers de Pesquisa | `regra-alterada` | HIGH | Restauração formal do endpoint `@router.post("/research/{research_id}/briefing/approve")` para atendimento à interface web. |
| `app/core/config.py` | Configurações Globais | `regra-alterada` | MEDIUM | Adição do campo `TRUSTED_ROUTER_HOSTS` para liberação controlada de hosts internos do Docker. |
| `app/services/settings.py` | Segurança de Configurações | `regra-alterada` | HIGH | Validação anti-SSRF de URLs com whitelist explícita de hosts Docker internos. |
| `app/services/search.py` | Mecanismo de Busca | `regra-alterada` | HIGH | Fallback para Jina sem autenticação e DuckDuckGo em erro 401/402; eliminação de ReDoS no scraping com `_SafeHTMLTextExtractor`. |
| `app/tools/search_pipeline.py` | Pipeline de Scraping | `regra-alterada` | HIGH | Implementação de `_SafeHTMLTextExtractor` baseado em `HTMLParser` prevenindo travamento de CPU (CWE-1333). |
| `app/db/database.py` | Conexão com Banco | `regra-alterada` | HIGH | Aumento do pool de conexões SQLAlchemy (`pool_size=25`, `max_overflow=25`) para suporte ao fan-out de workers concorrentes. |
| `tests/test_backend.py` | Suíte de Testes | `regra-alterada` | MEDIUM | Atualização de asserções de `/briefing/approve` de 404 para 200/409 e alinhamento de locks em `run_research`. |
| `tests/test_e2e_criteria.py` | Critérios de Aceitação | `regra-alterada` | MEDIUM | Alinhamento do fluxo ponta a ponta com o contrato atualizado de aprovação. |

## 2. Riscos e Resoluções

| Risco Anterior | Resolução Comprovada | Evidência |
|---|---|---|
| ReDoS travando CPU em scraping de HTML externo | Substituição de regex catastrófica por parser de tags `HTMLParser` com limite seguro | Monitoramento de CPU no Docker: 95% -> 1.7% |
| Quota Jina esgotada (402) derrubando investigação | Fallback automático para consultas não autenticadas e DuckDuckGo | Probe de produção gerando 120 evidências reais |
| Pool PostgreSQL esgotado por workers paralelos | Reconfiguração de `pool_size=25` e `max_overflow=25` no engine assíncrono | Sucesso em fan-out simultâneo de 5 tópicos x 4 personas |
| SSRF bloqueando comunicação entre contêineres Coolify | Parametrização via `TRUSTED_ROUTER_HOSTS` e whitelist de hostnames de rede interna | Comunicação validada com `9router-pkiyejd1hbkakf216ckm0hu4:20128` |
| Falha do webhook externo abortando a pesquisa | Isolamento de exceção de webhook preservando status `DONE` da pesquisa | Evento `callback_failed` anotado sem prejuízo do relatório |
