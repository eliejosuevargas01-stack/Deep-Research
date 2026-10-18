# Relatório de Validação E2E e Especificação Comportamental do Sistema

> **Deep Research Engine** — Motor Autônomo e Distribuído de Pesquisa Profunda  
> **Data:** Outubro de 2026  
> **Status:** 100% Validado (138 testes executados / 0 falhas)  
> **Frameworks:** Behave (Cucumber/Gherkin), Pytest, Node Test Runner

---

## 1. Visão Geral da Arquitetura

O **Deep Research Engine** é um sistema distribuído de pesquisa factual profunda composto por:
1. **Frontend (SPA):** Desenvolvido em React 19 + TypeScript + Vite + Tailwind CSS + TanStack Router. Fornece interface interativa tipo chat para submissão de temas, edição/aprovação de rascunhos de briefing, visualização de progresso via SSE (Server-Sent Events) e leitura de relatórios com citações verbatim.
2. **Backend API (FastAPI):** Serviço assíncrono em Python 3.12 estruturado em camadas (routers, services, models, schemas, tools e prompts). Opera com migrações automáticas via Alembic no startup.
3. **Persistência Relacional:** PostgreSQL 16 (produção/deploy) e SQLite aiosqlite in-memory (testes isolados e aceitação).
4. **Pipeline Multiagente em 4 Etapas:**
   - **Briefing (ScoutWorker):** Formula busca SERP preliminar e gera de 3 a 7 pontos de investigação em rascunho.
   - **Investigação Paralela (PersonaWorkers):** 4 personas (`historian`, `skeptic`, `pragmatist`, `futurist`) investigam cada ponto em paralelo, com teto de 3 buscas e 10 turnos de ferramentas por persona.
   - **Auditoria Factual (AuditService):** Avalia evidências coletadas, pontua qualidade (0 a 12), detecta contradições e emite vereditos (`AUDIT_APPROVED`, `AUDIT_CAVEAT`, `SCRAPER_RETRY`).
   - **Síntese de Relatório (WriterAgent):** Consolida pontos aprovados em relatório Markdown extenso (mínimo 200 palavras) fundamentado estritamente em citações verbatim com links inline `[texto](url)` validadas contra as evidências coletadas.
   - **Entrega (Webhook Callback):** Notificação HTTP POST com assinatura HMAC e proteção estrita anti-SSRF para URLs públicas.

---

## 2. Endpoints e Contratos de API Verificados

### 2.1 Autenticação e Sessão
- `POST /api/auth/login`: Autentica com senha administrativa (`ADMIN_PASSWORD`). Retorna cookie `dr_session` (HttpOnly, Path=/, SameSite=lax) e corpo JSON com `authenticated: true` e `csrf_token`.
- `GET /api/auth/me`: Retorna `{"authenticated": true, "role": "admin"}` se autenticado via cookie de sessão, `Authorization: Bearer <API_AUTH_SECRET>` ou `X-API-Key: <API_AUTH_SECRET>`. Credenciais múltiplas ou ambíguas retornam HTTP 400.
- `GET /api/auth/csrf`: Rotaciona e retorna novo token CSRF para a sessão ativa.
- `POST /api/auth/logout`: Invalida a sessão no banco de dados e remove o cookie `dr_session`. Exige cabeçalho `X-CSRF-Token` (HTTP 403 em caso de ausência).

### 2.2 Infraestrutura e Saúde
- `GET /health`: Checa integridade da aplicação e conectividade real com o banco de dados. Retorna `{"status": "healthy", "database": "connected", "version": "1.0.0"}` com HTTP 200. Retorna HTTP 503 com `{"detail": "Database unavailable"}` se a conexão falhar.

### 2.3 Briefing
- `POST /briefings`: Cria e orquestra rascunho de briefing.
  - **Payload:** `{"theme": "string entre 3 e 300 caracteres"}`
  - **Status 201:** `{"id": UUID, "theme": str, "status": "draft", "version": 2, "points": [...]}`
  - **Erros Tratados:**
    - HTTP 422: Tema inválido ou menos de 3 caracteres (`{"detail": "Tema deve conter entre 3 e 300 caracteres"}`)
    - HTTP 503: Provedor SERP indisponível (`{"detail": "Busca SERP indisponível"}`)
    - HTTP 503: Provedor de LLM indisponível (`{"detail": "Geração de briefing indisponível"}`)
- `PATCH /briefings/{id}`: Submete feedback textual do operador (`{"note": "..."}`), auto-aprova diretamente e despacha a investigação em background. Retorna HTTP 200 com `status: "approved"` e versão incrementada. Retorna HTTP 409 se já revisado (versão > 2).
- `POST /briefings/{id}/reopen`: Bloqueado estritamente com HTTP 409 (`{"detail": "Briefing aprovado não pode ser reaberto"}`) se o briefing já foi aprovado.
- `GET /briefings/approved/{id}`: Retorna o briefing aprovado com `approved_at`, tema e pontos. Retorna HTTP 409 se não estiver aprovado.
- `GET /briefings/{id}/versions`: Retorna histórico imutável das transições de versão.

### 2.4 Investigação e Workers
- Orquestração fan-out: Cada ponto de pesquisa é dividido entre as personas `historian`, `skeptic`, `pragmatist` e `futurist`.
- Limites operacionais:
  - Teto de 3 chamadas à ferramenta de busca por persona.
  - Até 3 ciclos de autocorreção em caso de resposta fora do formato JSON estrito (`{"result": "...", "used_urls": [...]}`).
  - Máscara automática de segredos (`Bearer ***`, `api_key=***`, `sk-***`) em logs de erro.
  - Persistência dos resultados parciais em `research_step_results`.

### 2.5 Auditoria e Relatório
- Critérios de Auditoria: Pontuação de 0 a 12.
  - Score ≥ 10: `AUDIT_APPROVED`
  - Tentativa 1 a 3 com score < 10: `SCRAPER_RETRY` com lista concreta de `missing_research` e filtro anti-duplicação de URLs já lidas.
  - 4ª tentativa reprovada: Conversão automática e forçada para `AUDIT_CAVEAT`, liberando a pesquisa sem bloqueios fatais.
- Guardrails do Redator (`WriterAgent`):
  - Extensão mínima de 200 palavras.
  - Inclusão exata de cabeçalhos correspondentes a cada ponto de pesquisa.
  - Citações obrigatórias no formato `[texto](url)` originadas estritamente das evidências coletadas (`linked_urls.issubset(known_urls)`).
  - Bloqueio com `RuntimeError` se citar URLs não coletadas ou publicar conteúdo factual sem citação.
  - Persistência na tabela `reports` e transição da pesquisa para `DONE`.

### 2.6 Entrega e Webhook Callback
- Notificação HTTP POST contendo:
  ```json
  {
    "research_id": "UUID",
    "report_id": "UUID",
    "theme": "string",
    "content_markdown": "# Relatório ...",
    "generated_at": "ISO-8601"
  }
  ```
- Proteção anti-SSRF: Validação estrita de resolução de DNS proibindo IPs privados (RFC 1918, loopback, link-local).
- Resiliência: Falhas de rede ou HTTP 500 do receptor externo não cancelam nem alteram o status da pesquisa para FAILED; a falha é registrada em `audit_trails` e o relatório permanece disponível via API.

---

## 3. Cobertura da Suíte de Testes BDD (Gherkin/Behave)

| Feature | Arquivo | Cenários | Steps | Status |
|---------|---------|----------|-------|--------|
| **1. Autenticação** | `features/001_autenticacao.feature` | 10 | 44 | ✅ 100% Pass |
| **2. Infra & Deploy** | `features/002_infra_deploy.feature` | 7 | 26 | ✅ 100% Pass |
| **3. Auditoria Reversa** | `features/003_auditoria.feature` | 8 | 38 | ✅ 100% Pass |
| **3. Briefing** | `features/003_briefing.feature` | 9 | 41 | ✅ 100% Pass |
| **4. Workers** | `features/004_workers.feature` | 7 | 25 | ✅ 100% Pass |
| **5. Auditoria & Relatório** | `features/005_auditoria_relatorio.feature` | 5 | 20 | ✅ 100% Pass |
| **6. Entrega & Webhook** | `features/006_entrega_webhook.feature` | 5 | 20 | ✅ 100% Pass |
| **Total BDD** | **7 Features** | **51 Cenários** | **214 Steps** | **✅ 100% Pass** |

---

## 4. Testes Unitários e Frontend

- **Backend Pytest (`tests/test_backend.py` + `tests/test_e2e_criteria.py`):** 59 testes aprovados (100%).
- **Frontend Test Runner (`frontend/tests/frontend.test.mjs`):** 28 testes aprovados (100%).
- **Total Geral de Testes:** 138 testes automatizados aprovados sem erros.
