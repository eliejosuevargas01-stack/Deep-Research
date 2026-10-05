# Arquitetura do Sistema: Deep Research Engine

> Gerado por Reversa SDD Engine  
> Data: 2026-10-04  
> Projeto: Deep Research Engine

## 1. Visão Geral e Topologia

O Deep Research Engine é uma plataforma de pesquisa profunda distribuída e multiagente com pipeline cognitivo desacoplado em 4 fases e frontend em tempo real.

```
                                  HTTPS Request
                                        │
                                        ▼
    ┌────────────────────────────────────────────────────────────────────────┐
    │  Traefik / Nginx Ingress Reverse Proxy (Port 80/443)                   │
    └───────────────────┬────────────────────────────────┬───────────────────┘
                        │ /                              │ /api/*
                        ▼                                ▼
    ┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
    │ Frontend (React 19 + Vite + Nginx)   │  │ Backend (FastAPI + Python 3.12/14)   │
    │ - Tailwind CSS Dark Tokens (Linear)  │  │ - Session Auth (HttpOnly Cookie JWT) │
    │ - SSE Realtime Consumer              │  │ - Connection-pinned SSRF Guard       │
    │ - Briefing Human-in-the-Loop Editor  │  │ - Async Multi-Agent Pipeline         │
    └──────────────────────────────────────┘  └──────────────────┬───────────────────┘
                                                                 │
                   ┌─────────────────────────────────────────────┼────────────────────────────────────────────┐
                   ▼                                             ▼                                            ▼
    ┌─────────────────────────────┐               ┌─────────────────────────────┐              ┌─────────────────────────────┐
    │ Pipeline Cognitivo          │               │ Camada de Busca e Extração  │              │ Camada de Dados (PostgreSQL)│
    │ 1. Scout Agent (LLM)        │               │ - Connection-pinned SSRF    │              │ - Async SQLAlchemy          │
    │ 2. Human Review (1x)        │──────────────►│ - Jina / SerpAPI / Apify    │─────────────►│ - Modelos com versioning    │
    │ 3. WorkerPool (20 Max Cap)  │               │ - Jina Reader Scraper       │              │ - Configs Criptografadas    │
    │ 4. Auditor de Citações      │               │ - Webhook Callback Client   │              │ - Alembic Migrations        │
    │ 5. Redator Markdown         │               └─────────────────────────────┘              └─────────────────────────────┘
    └─────────────────────────────┘
```

## 2. Componentes Principais

| Componente | Caminho | Responsabilidade | Contratos Principais |
|---|---|---|---|
| **Auth & Security** | `app/core/security.py` | Emissão de cookies JWT HttpOnly, hash de `jti`, validação de API Key `X-API-Key`, proteção CSRF. | Single-admin, sem exposição de segredos ao JS. |
| **Ingresso API** | `app/routers/` | Endpoints de autenticação (`auth.py`), pesquisas (`research.py`) e configurações (`settings.py`). | Validação Pydantic estrita, SSE Streaming com retomada via `Last-Event-ID`. |
| **Pipeline & Agentes** | `app/services/research.py` | Orquestração de Scout, Workers (4 personas), Auditor de citações e Redator. | Concorrência máxima de 20 workers (`asyncio.Semaphore(20)`), até 3 retries por ponto. |
| **LLM Gateway** | `app/services/llm.py` | Interface unificada via LiteLLM SDK com guardrails de saída para canários e segredos. | Sem chamadas HTTP diretas por provedor, suporte a OpenAI-compatible com `base_url`. |
| **Ferramentas de Busca** | `app/tools/search_pipeline.py` | Busca e leitura de páginas com fallback Jina/SerpAPI/Apify e extração de trechos limpos. | Verificação de domínio único, 3 a 5 fontes legíveis para o Scout. |
| **SSRF Guard** | `app/tools/outbound.py` | Validação de URLs públicas e bloqueio de redes privadas (RFC1918, loopback, link-local, AWS metadata). | Proteção a nível de socket antes da conexão TCP. |
| **Criptografia** | `app/services/crypto.py` | Criptografia simétrica AES-256-GCM para chaves de provedores no PostgreSQL. | Chave mestra em `APP_ENCRYPTION_KEY`. |
| **Frontend UI** | `frontend/src/` | Interface React 19 em modo escuro estilo Linear com stream SSE, editor de briefing e configurações. | Sessão via cookie transparente, proteção contra reordenamento inválido de DAG. |

## 3. Fluxo de Vida de uma Pesquisa

1. **Ingresso (`POST /api/research`)**: Recebe `theme` e `callback_url` opcional para backend. Cria registro em estado `scouting`.
2. **Scout & Briefing**: O Scout faz busca preliminar (3 a 5 sites distintos) e gera 5 pontos de pesquisa em JSON com dependências e paralelismo. Transiciona para `pending_approval`.
3. **Revisão Humana Única**:
   - Se aprovado (`POST /api/research/{id}/briefing/approve`): grava pontos e inicia execução paralela.
   - Se editado (`POST /api/research/{id}/briefing/edit`): Scout refaz rascunho com o feedback e aprova automaticamente.
4. **Execução Paralela de Workers**: Orquestrador despacha até 20 workers simultâneos (4 personas por ponto: *Historiador*, *Cético*, *Pragmático*, *Visionário*). Cada persona busca até 3 queries e extrai citações exatas.
5. **Auditoria por Ponto**: O Auditor checa se afirmações têm citações exatas do texto coletado e detecta contradições. Se aprovado, avança. Se reprovado, gera até 3 retries com instruções específicas de busca. Se falhar 4x, marca ponto como `blocked` e inclui ressalvas.
6. **Redação Final**: O Redator compila o relatório final em Markdown com links para todas as fontes e alertas para pontos bloqueados.
7. **Callback & Stream**: O relatório é persistido, disponibilizado no endpoint `/api/reports/{id}` e enviado via Webhook com retry seguro. O stream SSE emite eventos seguros em tempo real.
