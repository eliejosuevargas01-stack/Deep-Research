# Deep Research Engine - Goal

## Problem Statement

Construir um motor de pesquisa profunda (Deep Research) autônomo e distribuído, multiagente, que execute um pipeline de 4 fases (Briefing → Paralelismo → Auditoria → Redação) para coletar informações de alta fidelidade da web de forma verificável, com checagem cruzada, controle de alucinações e rastreabilidade total de fontes.

## Definition of Done

1. **API REST/FastAPI:**
   * Endpoint `/api/research` para submissão de novas pesquisas (com validação de tema e headers de autenticação `Bearer <API_AUTH_SECRET>`).
   * Endpoint `/api/reports/{id}` para consulta a relatórios gerados.
   * Middleware de segurança que rejeita payloads inválidos com HTTP 400/401/422 (abortando a execução).

2. **Engine de Execução (Async Workers):**
   * Implementado agente de *Briefing & Scout* (1 LLM Top-Tier) que gera rascunho de 5 pontos e respeita fluxo *Human-in-the-Loop*.
   * Orquestrador que dispara 4 "worker personas" em paralelo por ponto (até 20 workers simultâneos em 5 pontos independentes).
   * Subfluxo unificado de *Search-Read-Clean* (SerpAPI/Apify/Jina Scraper → Jina Reader → Limpeza & Fusão de 5-10 páginas).
   * Mecanismo de *Optimistic Locking* no DB para prevenir *race conditions* no armazenamento de evidências.

3. **Agente Auditor (Juiz):**
   * Lógica sem tools que valida contradições, alucinações, verifica citações de fontes.
   * Loop de 3 tentativas por ponto. Após 3 falhas, ativa *blocker* e encaminha para redação com ressalvas.

4. **Agente Redator (Final):**
   * Síntese sem tools, consumindo estritamente o roteiro/outline do Auditor.
   * Gera relatório final em Markdown com links e citações de fontes reais.
   * Dispara callback assíncrono HTTP POST para a URL origional registrada no payload de entrada.

5. **Persistência:**
   * Modelos SQLAlchemy (PostgreSQL) para: Pesquisas, Pontos, Workers, Evidências, Relatórios e Aprovação.

## Operator/Tenant UX

* Um chamador externo faz um único `POST /api/research` com:
  - `tema` (string, obrigatório)
  - `callback_url` (URL para notificação final)
  - `auth_key` / Bearer Token
* A aprovação do rascunho ocorre via:
  - Webhook interno simulando Human-in-the-Loop, OU
  - Endpoint `/api/briefing/approve/{id}` (admin).
* O usuário final consulta o relatório em `/api/reports/{id}` — sempre markdown estruturado e links verificáveis.

## What Exists & Will Be Reused

| Componente Atual | Função | Como Adapta |
|------------------|--------|-------------|
| `.env.example` | Gestão de secrets (API Keys, DB, Auth) | Carregado via Pydantic `pydantic-settings` e injetado no `Settings` singleton |
| `requirements.txt` | FastAPI, Uvicorn, SQLAlchemy, Asyncpg, LiteLLM | Será complementado com `httpx`, `asyncio` e `pyppeteer` para scraping |
| `_reversa_docs/` | Arquitetura 3D visual | Referência para a camada de visão do sistema |

## Out of Scope

* Interface administrativa web (UI Dashboard React).
* Execução real de agents LLM (é um orquestrador de prompts/strings para futuro uso).
* Publicação ou CI/CD em nuvem (mantido local via Uvicorn).

## Constraints

* Multi-tenant por design: isolamento implícito por `research_id`.
* Segurança: validação de autenticação antes de qualquer processamento de CPU/LLM.
* Não armazenar credenciais em texto claro no DB — apenas referências e hash.

## Key Decisions

* **Orquestrador Async:** Usar `asyncio` nativo do Python para paralelismo de workers sem Celery/Temporal (menor overhead).
* **Store de Evidências:** PostgreSQL JSONB para armazenamento flexível de respostas e metadados de fontes.
* **LLM Provider:** LiteLLM configurado via `.env`, permitindo troca sem código.
