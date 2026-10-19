# Requisitos: Módulo de Redação de Relatório Final e Entrega via Webhook

> Identificador da feature: `004-modulo-redator-webhook`  
> Data: `2026-10-19`  
> Cenário: `forward` (ancorado em GOAL.md, plan.md, workflow.md e validações E2E)  
> Status: 🟢 CONFIRMADO (100% deliberado, implementado e testado)

---

## 1. Visão Geral e Objetivo

O Módulo de Redação de Relatório Final e Entrega via Webhook é o estágio de síntese e distribuição do Deep Research Engine. Atua após a conclusão e aprovação dos pontos de investigação na auditoria (`ResearchStatus.WRITE`), consolidando todo o material investigado em um relatório Markdown denso, acadêmico, rigorosamente citado (*verbatim citations*) e notificando sistemas externos de forma segura via Webhook com proteção anti-SSRF.

---

## 2. Princípios Reversa Aplicados

| Princípio | Aplicação na Feature 004 |
|---|---|
| **I. Rastreabilidade Factual Estrita (Verbatim Citation)** | Cada frase e bullet point de conteúdo factual deve conter link inline `[texto](url)` referenciando exclusivamente URLs coletadas pelas personas. O uso de URLs externas desconhecidas resulta em bloqueio imediato com `RuntimeError`. |
| **II. Defesa de Privacidade e Isolamento de Prompts** | Prompts de geração e cadeias de pensamento do Redator não são persistidos nem expostos no relatório. Apenas o Markdown final sanitizado e as métricas de citação são gravados em banco. |
| **III. Resiliência por Degradação Graciosa e Limites Rígidos** | Falhas na entrega do Webhook (erros 500 do destinatário, timeouts) não regridem o status da pesquisa para `FAILED`. O relatório é preservado integralmente com status `DONE` e a falha de entrega é registrada em `audit_trails`. |
| **IV. Segurança Anti-SSRF em Comunicações Externas** | Disparos para URLs privadas (RFC 1918, loopback, link-local) são estritamente bloqueados em nível de transporte antes do handshake de rede através de `PinnedResolver`. |

---

## 3. Requisitos Funcionais

### RF-401: Síntese de Relatório Markdown pelo WriterAgent
- Disparo automático após transição de todos os pontos para estados conclusivos (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`).
- O relatório deve conter extensão mínima de 200 palavras (alvo padrão ≥ 400 palavras).
- Títulos de seção de nível 2 (`##`) devem corresponder exatamente aos títulos de cada ponto investigado.
- Pontos que atingiram o teto de tentativas em `AUDIT_CAVEAT` devem conter ressalvas e limitações explícitas de evidência.

### RF-402: Guardrails Rígidos de Citação Factual
- O redator deve linkar pelo menos uma URL de evidência.
- Todas as URLs citadas no Markdown devem pertencer estritamente ao conjunto de evidências persistidas (`linked_urls.issubset(known_urls)`).
- Todo conteúdo em prosa factual, itens de lista ou linhas de tabela com dados substantivos requer link markdown `[texto](url)`.

### RF-403: Persistência de Relatório e Transição de Status
- O relatório gerado é persistido na entidade relacional `Report` com chaves estrangeiras vinculadas à pesquisa.
- A pesquisa deve ter seu status atualizado atômica e irreversivelmente para `ResearchStatus.DONE`.
- Métricas estruturadas de citação (`evidence_records` e `source_urls_cited`) e os achados da auditoria por ponto são armazenados em JSON.

### RF-404: Notificação de Entrega via Webhook Seguro
- Se a pesquisa contiver `callback_url`, efetuar requisição HTTP POST contendo `research_id`, `report_id`, `theme`, `content_markdown` e `generated_at`.
- Validação estrita anti-SSRF com resolução DNS segura contra endereços IP privados ou internos.
- Tratamento resiliente de erros: status HTTP 5xx ou falha de conexão no receptor externo mantém a pesquisa como `DONE` e anota evento `callback_failed` em `agent_event_logs` e `audit_trails`.

### RF-405: Alinhamento de Contratos de API e Infraestrutura
- Disponibilização do endpoint de aprovação `POST /api/research/{research_id}/briefing/approve` retornando HTTP 200 na aprovação inicial e HTTP 409 em tentativas subsequentes.
- Suporte a hostnames de roteamento interno via `TRUSTED_ROUTER_HOSTS` em `app/core/config.py` e `app/services/settings.py`.
- Fallbacks resilientes contra falhas de provedores de busca (401/402 de chaves expiradas para Jina/DuckDuckGo).
- Extrator de texto HTML seguro (`_SafeHTMLTextExtractor`) baseado em `HTMLParser` para prevenção de vulnerabilidade de ReDoS (CWE-1333).
