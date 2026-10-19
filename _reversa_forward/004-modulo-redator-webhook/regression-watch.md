# Regression Watch — Feature 004: Módulo de Redação de Relatório Final e Entrega via Webhook

- **Feature:** `004-modulo-redator-webhook`
- **Data de Fechamento:** 2026-10-19
- **Base de comparação:** Commit `f1c1cf0`
- **Status:** Todos os itens de vigilância ativos e comprovados em testes e produção.

## 1. Itens de Vigilância Ativos

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Status |
|---|---|---|---|---|
| W001 | `app/services/pipeline/writer.py` | Relatório gerado exige extensão mínima de 200 palavras e correspondência de tópicos | behave: `features/005_auditoria_relatorio.feature` | 🟢 APROVADO |
| W002 | `app/services/pipeline/writer.py` | Citações factual devem usar links markdown e pertencer às evidências persistidas | behave: `features/005_auditoria_relatorio.feature` | 🟢 APROVADO |
| W003 | `app/services/pipeline/writer.py` | Presença de pontos em `AUDIT_CAVEAT` não marca a pesquisa como `FAILED` | behave / prod: verificação de status `DONE` em relatório final | 🟢 APROVADO |
| W004 | `app/services/webhook.py` | Endereços IP privados são rejeitados com erro de segurança SSRF | behave: `features/006_entrega_webhook.feature` | 🟢 APROVADO |
| W005 | `app/services/webhook.py` | Falhas HTTP 500 do webhook não alteram o status `DONE` da pesquisa | behave: `features/006_entrega_webhook.feature` | 🟢 APROVADO |
| W006 | `app/routers/research.py` | `POST /api/research/{id}/briefing/approve` retorna 200 na primeira chamada e 409 em replay | pytest: `tests/test_backend.py` e `tests/test_e2e_criteria.py` | 🟢 APROVADO |
| W007 | `app/services/search.py` | Extração de HTML não sofre de ReDoS e limita tamanho do payload em buffer | unit test / prod: raspagem estável com consumo de CPU normalizado | 🟢 APROVADO |
| W008 | `app/services/settings.py` | URLs de proxy LLM contendo nomes de contêiner autorizados em `TRUSTED_ROUTER_HOSTS` são aceitas | unit test / prod: atualização de runtime settings com sucesso | 🟢 APROVADO |
| W009 | `app/services/research.py` | Idempotência em `run_research` previne execuções concorrentes com lock atômico | pytest: `test_full_pipeline_with_controlled_sources_and_models` | 🟢 APROVADO |
