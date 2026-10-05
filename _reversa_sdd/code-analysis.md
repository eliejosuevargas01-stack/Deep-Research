# Análise de Código e Qualidade: Deep Research Engine

> Gerado por Reversa SDD Engine  
> Data: 2026-10-04  
> Projeto: Deep Research Engine

## 1. Estrutura de Módulos e Dependências

```
app/
├── core/
│   ├── config.py             # Pydantic Settings (.env, limites de queries, semáforos)
│   └── security.py           # Autenticação JWT Cookie + X-API-Key + CSRF
├── db/
│   └── database.py           # Engine assíncrona SQLAlchemy (asyncpg / aiosqlite)
├── models/
│   └── domain_models.py      # Declarative Base com 8 tabelas de domínio
├── schemas/
│   └── __init__.py           # Schemas Pydantic com validação rigorosa
├── routers/
│   ├── auth.py               # Rotas /api/auth/login, /api/auth/logout, /api/auth/me
│   ├── settings.py           # Rotas /api/settings (GET, PUT, credenciais e modelos)
│   └── research.py           # Rotas /api/research, briefing edit/approve, events SSE, reports
├── services/
│   ├── crypto.py             # AES-256-GCM com chave mestra
│   ├── settings.py           # Gestão de credenciais com hot-reload e mascaramento
│   ├── llm.py                # LiteLLM SDK gateway, guardrails de saída, fallback
│   ├── audit.py              # Auditoria determinística e cognitiva de citações
│   ├── research.py           # Orquestração Scout, Workers, Auditor, Writer e recovery
│   └── webhook.py            # Despacho assíncrono com retry seguro e proteção SSRF
└── tools/
    ├── outbound.py           # Validador SSRF com socket-level IP pinning
    └── search_pipeline.py    # Pipeline Jina Search/Reader, SerpAPI, Apify com fallbacks
```

## 2. Padrões de Segurança e Confiabilidade Implementados

1. **Guardrail de Privacidade e Canários (`app/services/llm.py:apply_output_guardrail`)**:
   - Bloqueio de senhas, chaves de API, variáveis de ambiente e prompts de sistema no texto gerado antes de alcançar o usuário ou banco.
2. **SSRF Defense-in-Depth (`app/tools/outbound.py`)**:
   - Resolução de DNS com validação contra CIDRs privadas (RFC1918, loopback, link-local, AWS metadata).
   - Bloqueio de redirecionamentos inseguros.
3. **Controle de Concorrência e Isolamento (`app/services/research.py:WORK_LIMIT`)**:
   - `asyncio.Semaphore(20)` garante que nenhuma pesquisa exceda 20 workers simultâneos.
   - Resolução de lotes DAG (`ready_point_batches`) para execução simultânea de pontos paralelos e despacho progressivo de pontos sequenciais.
4. **Ciclo de Auditoria de 4 Tentativas (`app/services/research.py:remaining_attempts`)**:
   - Execução inicial + 3 retries (total de 4 execuções por ponto).
   - Na quarta reprovação, ativa o modo `BLOCKED` e anexa ressalvas ao invés de quebrar a pipeline.
5. **Validação de Citação Exata Verbatim (`app/services/audit.py:deterministic_citation_audit`)**:
   - Validação se cada `claim` possui um `exact_quote` que é substring real do conteúdo raspado da fonte.
   - O Redator é obrigado a citar as fontes em formato de link Markdown em cada frase afirmativa factual.

## 3. Avaliação de Débito Técnico e Oportunidades de Melhoria

| Área | Situação Atual | Oportunidade / Melhoria |
|---|---|---|
| **Test Runner** | Testes completos em `tests/` (`test_backend.py`, `test_e2e_criteria.py`), mas ambiente local requer virtualenv dedicado para execução direta de `pytest`. | Configurar venv padronizado ou rodar via container docker de testes. |
| **Frontend Bundle** | React 19 em arquivo consolidado `main.tsx` (95KB). | Modularizar componentes de UI em arquivos dedicados (`components/chat/`, `components/report/`, etc.). |
| **Recovery de Tarefas** | `lifespan` do FastAPI reinicia pesquisas pendentes na subida do backend. | Implementar heartbeat periódico no banco para detecção de nós mortos em caso de cluster multi-réplica. |
