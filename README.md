# Deep Research

Pipeline modular de pesquisa profunda na internet. Recebe um tema, produz um plano de investigação estruturado, coleta evidência web com personas analíticas, audita cada ponto contra 12 critérios de qualidade e redige um dossiê final em Markdown com fontes canônicas rastreáveis.

A interface web (React + TypeScript) é servida pelo próprio backend FastAPI em origem única, sem runtime Node em produção.

O problema que resolve: research manual leva dias, as fontes não são auditadas e o relatório perde rastreabilidade. O Deep Research automatiza o ciclo com pontos aprovados/reprovados individualmente, evidência rastreável e dossiê final — meta de ciclo completo abaixo de 10 minutos. Público: analistas de research, redatores e integradores de API.

- **Versão:** 0.1.0
- **Idioma da interface e dos relatórios:** português
- **Estado:** Checkpoint 1 (fluxo completo síncrono) e streaming SSE implementados
- **Especificações:** [`_reversa_sdd/`](_reversa_sdd/) (PRD, SDD, adendos e rastreabilidade)

---

## 1. O que o sistema entrega

| Capacidade | Resultado |
| :--- | :--- |
| Planejamento | N eixos investigativos com pergunta principal, subperguntas, hipóteses, consultas iniciais, riscos de viés, evidência de refutação e critério de conclusão |
| Coleta | Evidência integral lida em páginas reais (não snippets) por 4 personas: historiador, visionário, cético e futurista |
| Auditoria | Vetor tipado de 12 critérios por ponto, com limiar configurável de 10, 11 ou 12 aprovações |
| Redação | Dossiê em Markdown com citações `[Fonte](URL)`, fontes verificadas e avaliação de qualidade do próprio artigo |
| Rastreabilidade | IDs de fonte (`src_*`) e trechos (`chk_*`), hashes SHA-256, offsets, contabilidade de fontes consultadas/utilizadas/não utilizadas |
| Entrega | Resposta HTTP síncrona ou pipeline autônomo com callback webhook assinado (HMAC-SHA256) |
| Observabilidade | Progresso por SSE, status por ponto, envelopes de cada chamada LLM persistidos em `generation_attempts` |

---

## 2. Como funciona

```
POST /api/v1/plan     → plano + N pontos persistidos (não executa busca)
POST /api/v1/search   → leitura web por persona, evidência e proveniência por ponto
POST /api/v1/audit    → 12 critérios por ponto, aprovação/reprovação e tarefas de correção
POST /api/v1/writer   → dossiê final, avaliação do artigo, fontes e webhook opcional
```

Com `async_execute: true`, o `POST /plan` retorna `202` e o `PipelineRunner` executa as quatro etapas em background, com retentativas automáticas:

1. busca e auditoria por ponto, até **4 tentativas de busca** e **3 de auditoria**;
2. redação bloqueada se algum ponto não for aprovado;
3. dossiê aprovado, publicação atômica e despacho do webhook.

```
Navegador (React SPA)
   │  fetch /api/v1/*            ▲ SSE /api/v1/pipeline/{id}/stream
   ▼                             │
FastAPI (app/main.py) ───────────┘
   │
   ├── Jina s.jina.ai  → descoberta (SERP, apenas metadados)
   ├── Jina r.jina.ai  → leitura integral das páginas em Markdown
   ├── LLM OpenAI-compatible /chat/completions (modelo leve e forte)
   └── SQLite WAL: pesquisa, pontos, conteudo_coletado, credenciais,
                   generation_attempts
```

Detalhamento técnico: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 3. Stack

| Camada | Tecnologia |
| :--- | :--- |
| Backend | Python ≥ 3.11 (ambiente atual em 3.14), FastAPI, Uvicorn, Pydantic v2 + pydantic-settings |
| Persistência | SQLAlchemy 2.0 assíncrono + aiosqlite, SQLite em modo WAL |
| Integrações | httpx, tenacity; Jina Search/Reader; qualquer provedor compatível com OpenAI Chat Completions |
| Segurança | Fernet (AES-128-CBC + HMAC-SHA256) para credenciais; HMAC-SHA256 para sessão e webhook |
| Frontend | React 18, TypeScript 5.7, Vite 6, CSS puro tokenizado, GSAP, react-markdown + remark-gfm |
| Testes | pytest + pytest-asyncio; Cucumber + Playwright para o frontend |
| Empacotamento | `pyproject.toml`; Dockerfile multi-stage (Node build → Python runtime); docker compose |

---

## 4. Início rápido (local)

### Pré-requisitos

- Python 3.11 ou superior
- Node.js 20 ou superior (apenas para compilar o frontend)
- Chaves de acesso a um provedor LLM compatível com OpenAI e à Jina

### Passos

```bash
cd Deep-Research

# 1. Ambiente Python
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

# 2. Configuração
cp .env.example .env
# edite .env: CREDENTIALS_MASTER_KEY, OPENAI_API_KEY, JINA_API_KEY, N_PONTOS, PERSONAS_CONFIG...

# 3. Frontend (gera frontend/dist)
cd frontend
npm ci
npm run build
cd ..

# 4. Servidor integrado
python scripts/run_app.py --port 8010
```

Acesse `http://127.0.0.1:8010`. O `run_app.py` compila o frontend automaticamente se `frontend/dist/index.html` não existir; use `--build` para forçar nova compilação.

### Desenvolvimento com hot reload

```bash
# terminal 1 — API
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# terminal 2 — Vite (proxy para 8010)
cd frontend && npm run dev     # http://127.0.0.1:3000
```

### Docker

```bash
docker compose up --build      # http://127.0.0.1:8085
```

O compose usa `network_mode: host` (Linux) para preservar o loopback real e permitir sessão local automática. Para macOS/Windows, use o modo local com `scripts/run_app.py`.

Guia operacional completo: [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

---

## 5. Configuração mínima

| Variável | Obrigatória | Função |
| :--- | :---: | :--- |
| `DATABASE_URL` | sim | `sqlite+aiosqlite:///./data/deep_research.db` |
| `CREDENTIALS_MASTER_KEY` | sim | Chave Fernet que cifra a tabela `credenciais`; somente via ambiente |
| `OPENAI_API_KEY` | sim | Credencial do provedor LLM |
| `JINA_API_KEY` | sim | Credencial Jina Search/Reader |
| `N_PONTOS` | sim* | Número de eixos investigativos |
| `PERSONAS_CONFIG` | sim* | Lista das 7 personas do pipeline |
| `WEBHOOK_HMAC_SECRET` | não | Segredo de assinatura do callback; sem ele não há entrega por webhook |
| `CALLBACK_WEBHOOK_URL` | não | URL padrão de callback |
| `API_SECRET_KEY` | não | Ativa autenticação por `X-API-Key`/`Bearer` nas rotas `/api/v1/*` |

\* Também podem ser definidas pelo painel de configurações, que grava na tabela cifrada `credenciais`.

**Precedência de credenciais:** banco cifrado → variáveis de ambiente → erro explícito. Exceção: `CREDENTIALS_MASTER_KEY` existe apenas no ambiente; `API_SECRET_KEY` é lida primeiro do ambiente e depois do banco.

Referência completa (timeouts, orçamentos, recência, modelos): [`docs/OPERATIONS.md`](docs/OPERATIONS.md#2-variáveis-de-ambiente).

---

## 6. API

Todas as rotas de negócio vivem sob `/api/v1`. Referência completa com payloads e erros: [`docs/API.md`](docs/API.md).

| Método | Rota | Função |
| :--- | :--- | :--- |
| `POST` | `/api/v1/plan` | Cria plano e pontos (`201`; `202` com `async_execute: true`) |
| `GET` | `/api/v1/plan/{id_pesquisa}/stream` | SSE do raciocínio do planejador |
| `POST` | `/api/v1/search` | Executa a coleta por personas |
| `POST` | `/api/v1/audit` | Audita os pontos coletados |
| `POST` | `/api/v1/writer` | Redige, avalia e publica o dossiê |
| `GET` | `/api/v1/pipeline/{id_pesquisa}/status` | Status consolidado do pipeline |
| `GET` | `/api/v1/pipeline/{id_pesquisa}/sources` | Contabilidade de fontes (somente leitura) |
| `GET` | `/api/v1/pipeline/{id_pesquisa}/stream` | SSE de progresso, raciocínios e dossiê |
| `POST` | `/api/v1/admin/credentials` | Cria/atualiza credencial cifrada |
| `GET` | `/api/v1/admin/credentials` | Lista metadados mascarados e origem ativa |

Rotas públicas fora do prefixo: `GET /health`, `GET /app/session`, `GET /docs` (Swagger), `GET /openapi.json`, e a SPA em `/`.

### Autenticação

1. **Navegador local:** `GET /app/session` emite cookie `dr_local_session` (`HttpOnly`, `SameSite=Strict`, TTL 24 h) quando o cliente é loopback, o `Host` é local e `Origin`/`Referer` coincidem. Requisições mutantes exigem mesma origem (CSRF).
2. **Integração:** `X-API-Key` ou `Authorization: Bearer <chave>` quando `API_SECRET_KEY` está configurada. Endpoints SSE aceitam `?token=` ou `?api_key=` porque `EventSource` não envia cabeçalhos.
3. **Modo aberto:** sem `API_SECRET_KEY` e sem cookie válido, as rotas `/api/v1/*` ficam liberadas. Isso é um modo de desenvolvimento, não uma configuração de produção.

---

## 7. Estrutura do repositório

```
Deep-Research/
├── app/
│   ├── main.py                 FastAPI, lifespan, /health, sessão, SPA e assets
│   ├── config.py               Pydantic Settings (sem fallbacks hardcoded)
│   ├── api/v1/endpoints/       plan, search, audit, writer, pipeline, admin
│   ├── core/                   planner, searcher, auditor, writer, pipeline_runner,
│   │                           personas, temporal, plan_validator, security, streaming
│   ├── db/                     modelos ORM, sessão WAL, init/migrações, repositórios
│   ├── schemas/                contratos Pydantic de entrada e saída
│   ├── services/               credenciais, cripto, contabilidade de fontes, webhook
│   ├── tools/                  clientes LLM e Jina, tipos e erros
│   └── ui_session.py           sessão local assinada e checagem mesma origem
├── frontend/
│   ├── src/components/         Composer, PlanView, ExecutionView, ReportView, Settings...
│   ├── src/hooks/              usePipelineStream (SSE)
│   ├── src/services/           cliente HTTP e histórico local
│   ├── features/               testes Cucumber/Gherkin
│   └── dist/                   bundle servido pelo FastAPI
├── tests/                      unit/ e integration/ (pytest)
├── docs/                       arquitetura, API, operações e evidências de frontend
├── scripts/                    run_app.py, run_local.py, shim Jina local
├── _reversa_sdd/               PRD, SDD, adendos, personas e rastreabilidade
├── _reversa_forward/           requisitos por feature
├── data/                       banco SQLite (não versionado)
├── Dockerfile                  build multi-stage
└── docker-compose.yml          execução em 127.0.0.1:8085
```

---

## 8. Testes

```bash
# Backend — 509 testes coletados
.venv/bin/python -m pytest

# Um módulo específico
.venv/bin/python -m pytest tests/unit/test_writer_acceptance.py -q

# Frontend — typecheck + build de produção
cd frontend && npm run build

# E2E Cucumber/Playwright (requer app em execução)
cd frontend && npm run test:e2e
```

O E2E usa `BASE_URL` (padrão `http://localhost:8011`). O script `run_test.sh` sobe a aplicação na porta 8111 com `.env.test`.

---

## 9. Documentação

| Documento | Conteúdo |
| :--- | :--- |
| [`docs/html/index.html`](docs/html/index.html) | Versão HTML navegável — busca, tema claro/escuro e sumário por página |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Componentes, fluxo por etapa, modelo de dados, concorrência, SSE, segurança |
| [`docs/API.md`](docs/API.md) | Contratos HTTP, payloads, códigos de erro, eventos SSE e webhook |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Variáveis de ambiente, execução, banco, testes, diagnóstico e segurança operacional |
| [`frontend/README.md`](frontend/README.md) | Visão do frontend e comandos |
| [`docs/frontend/`](docs/frontend/) | Auditorias, evidências visuais e relatórios de remediação |
| [`PRODUCT.md`](PRODUCT.md) | Plataforma, propósito, restrições e princípios de produto |
| [`DESIGN.md`](DESIGN.md) | Sistema visual e decisões de design |
| [`_reversa_sdd/prd.md`](_reversa_sdd/prd.md) | PRD vigente (requisitos, métricas, invariantes) |
| [`_reversa_sdd/sdd/`](_reversa_sdd/sdd/) | SDD por endpoint e adendos de confiabilidade |
| [`docs/security_audit_findings.md`](docs/security_audit_findings.md) | Auditoria de segurança e itens de remediação |

A versão HTML é gerada a partir destes arquivos por `scripts/build_docs_html.py`; instruções em [`docs/html/README.md`](docs/html/README.md).

---

## 10. Limitações conhecidas

- **SQLite único:** o banco é um arquivo local com WAL; não há suporte a múltiplas instâncias concorrentes.
- **SSE em memória:** o `PipelineEventHub` é por processo. Com múltiplos workers, eventos não são compartilhados; o snapshot inicial do banco cobre o estado persistido, não o histórico de deltas.
- **Sem rate limiting:** não há middleware de limite por IP/chave.
- **Sem paginação ou listagem de pesquisas:** o histórico da interface é local ao navegador (`localStorage`).
- **Sem deleção:** não existem endpoints para remover pesquisas ou credenciais.
- **Autenticação opcional:** sem `API_SECRET_KEY`, a API fica aberta (modo desenvolvimento).
- **Entrada de tema:** o backend aceita tema com 5 ou mais caracteres e sem teto; o compositor da interface limita a 500 caracteres.
- **Webhook sem fila durável:** são 1 tentativa + 3 retries em processo; falha definitiva fica registrada em `pesquisa.webhook_status`, sem reentrega posterior.
