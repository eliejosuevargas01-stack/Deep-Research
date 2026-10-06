# NOTAS PARA AJUSTES

> Melhorias identificadas em uso — aguardando triagem.

## 0. P0 — ServiceUnavailableError 503 (bug em produção) 🔥

**Registado como BUG-20261005-7H2K** — ver `_reversa_bugs/research-pipeline/bugs/BUG-20261005-7H2K-audit-blocked-503/`.

**Causa raiz** (confirmada em código + logs):
1. Auditor na round 4 → LiteLLM 503 → retry exaure 5 tentativas → raise
2. `_audit_point` (`audit_stage.py:74`) não apanha exceção
3. Propaga para `run_research` (`research.py:141`) que marca research inteiro como `failed`
4. `sanitize_error` esconde detalhes — frontend só vê mensagem genérica

**Fix mínimo recomendado**:
- Envolver `complete()` em `_audit_point` com try/except LiteLLM → fallback a `approved=False` + missing_research vazio (vai a blocked pelo max_attempts, research continua)
- Em `run_research`, quando um ponto falha com exceção, marca aquele ponto como `failed` e continua outros; não aborta research global
- Surface melhor erro no frontend (mostrar `point_id` que falhou, não só mensagem genérica)

**Evidência (print 20261006_1)**: app em `research.dominuslabs.online` falha após ~20min de execução. Timeline mostra:
- 80 evidências coletadas
- "Audit attempt 4: blocked" (repetido)
- `ServiceUnavailableError (status=503): research execution failed`
- Banner "A pesquisa foi interrompida" com botões Retomar / Verificar Configurações / Nova Pesquisa

**Hipóteses**:
- LLM gateway (Render router / OpenAI) retorna 503 por rate-limit ou overload → não há retry com backoff exponencial
- Auditor bloqueado 4x sugere loop de retry interno que esgota tentativas e estoura 503
- Possível pool exhaustion no FastAPI (conexões abertas durante pipeline longo)

**Ação**:
1. Instrumentar logs estruturados no pipeline (`app/services/research.py` / workers) — registrar cada 503 com payload/contexto
2. Adicionar retry com backoff + jitter nas chamadas LLM (`httpx`/`openai`) — máx 5 tentativas, backoff 2^n + jitter
3. Circuit breaker: após N falhas consecutivas no mesmo provider, trocar para fallback
4. Aumentar timeout do proxy/Cloudflare (research pode levar >20min)
5. Verificar pool do SQLAlchemy (`pool_size`, `max_overflow`) sob SSE longo

**Skill relevante**: `rate-limit-debugging`, `workflow-orchestrator-resilience`, `fastapi-sqlalchemy-production`

---



## 1. Scout raso (backend)

**Problema**: Scout não retorna "vamos pesquisar estes N pontos" (lista de subquestões para aprofundar). Retorna resposta superficial já respondendo as 5 perguntas.

**Evidência (print 20261005_5)**: Card "Descobertas por Pergunta" resume cada research question em 1 frase genérica ("A system struggles between speed and access...", "Scalability challenges include: high computational costs...") sem listar sub-temas/tópicos que deveriam guiar pesquisa profunda. Faltam seção "Pontos a aprofundar" por pergunta.

**Ação**: Revisar prompt/lógica do Scout em `app/services/workers/` para separar 2 etapas:
- Pesquisa inicial rasa (breadth) — ok
- Extrair e listar N subuntos/temas para pesquisa profunda
- Não responder ainda; apenas definir o plano de pesquisa

## 2. Formato de saída no frontend

**Problema**: UI usa "caixas" para cada fonte/citação, engessado. Gemini/ChatGPT Deep Research usam formato narrativo/artigo com citações inline (superscript links + referências no fim), mais legível.

**Evidência (print 20261005_6)**: Secção de fontes usa cards grandes (~6 caixas lado a lado) com domínio, título, snippet e botão "Verificar fonte". Comparação mental com Gemini/ChatGPT: texto corrido com citações inline superscript (`[1]`, `[2]`) + secção "Referências" no fim, sem caixas pesadas.

**Ação**: Redesenhar o relatório final no frontend:
- Texto corrido estilo artigo
- Citações inline como marcadores clicáveis [1], [2]...
- Secção de referências no final
- Menos caixas, mais fluxo de leitura

## 3. Campo para proxy Jina AI no frontend

**Problema**: Não há campo no frontend para configurar o Cloudflare Worker/proxy do Jina AI.

**Evidência (prints 20261005_4 e 20261005_7)**: Settings mostra um único card "Chave OpenAI" com input de senha. Sem secções para: base URL LLM, provedor de busca, nem URL de proxy/worker Jina. Apenas tema (dark) vem do sistema.

**Ação**: Adicionar em Settings (frontend + backend):
- Campo `jina_proxy_url` / `web_proxy_url`
- Persistir em AppSettings (tabela `app_settings`)
- Expor no router `/settings` (PUT/GET) com validação URL
- `search_pipeline.py` deve usar proxy quando configurado
