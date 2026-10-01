# Alma do Projeto: Deep Research Engine

Plataforma autônoma e distribuída de pesquisa profunda multiagente (Deep Research), projetada com pipeline desacoplado em 4 fases sequenciais e execução concorrente de até 20 pesquisadores virtuais especializados.

## Visão Geral da Arquitetura
1. **API Ingress & Safety:** FastAPI + Middleware de Autenticação + Validadores Pydantic + Guardrails.
2. **Phase 1 - Scout & Briefing:** Agente Top-Tier LLM + Web Search + File Reader para definição do roadmap de 5 pontos (Human-in-the-Loop).
3. **Phase 2 - Parallel Research Execution:** Orquestrador de Concorrência gerindo 4 Personas por ponto (Historiador, Cético, Pragmático, Visionário) com Subfluxo Jina Scraper/Apify/SerpAPI + Jina Reader.
4. **Phase 3 - Audit & Quality Gate:** Auditor sem tools executando rigor de fatos, controle de alucinações, construção de outline e controle de até 3 tentativas (Blocker).
5. **Phase 4 - Editorial Synthesis & Dispatch:** Redator sem tools gerando o relatório final Markdown com citações canônicas + Callback Webhook de entrega.
