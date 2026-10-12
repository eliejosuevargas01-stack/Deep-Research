# Investigation — 001-modulo-briefing

## Escopo e método

Investigação documental e leitura seletiva de código. Sem chamadas a APIs pagas ou testes executados. Requisitos atuais e decisões do usuário prevalecem; código existente serve somente para contexto de integração.

## Evidências de código e linhas

- `app/routers/research.py:135–167`: endpoint cria `Research`, marca `scouting` e agenda `schedule_scout`; impossível reutilizar diretamente sem causar side-effect de pesquisa.
- `app/routers/research.py:31–60`: `run_scout` chama `scout`, grava rascunho e `pending_approval`; tratamento de falha atual não segue as quatro tentativas por operação exigidas.
- `app/routers/research.py:228–319`: edição atual agenda revisão LLM e aprovação inicia `schedule(research_id)`, isto é, conecta briefing à pesquisa. Ciclo não compatível com escopo novo.
- `app/tools/search_pipeline.py:137–184`: `search()` escolhe SerpAPI/Apify/Jina e DuckDuckGo; não equivale a tool exclusiva Jina.
- `app/tools/search_pipeline.py:198–230`: `read_source()` usa Reader e scraping adicional; proibir neste fluxo novo.
- `app/prompts/scout.md:1–24`: prompt atual pede busca e leitura de fontes, cerca de cinco pontos; preservar arquivo existente e criar prompt separado para briefing.
- `app/models/domain_models.py:31–57`: `Research` e `ResearchPoint` representam pesquisa; estados misturam aprovação e execução, recomendando fronteira própria.
- `app/schemas/__init__.py:13–67, 70–72`: schema de tema aceita até 500 caracteres, aprovação exige exatamente cinco pontos; novo módulo precisa limites próprios.
- `app/tools/outbound.py:12–25, 37–51`: resolver pinado e validação de URL existem; integração HTTP deve aplicar controle de destino/redirecionamento seguro conforme mecanismo aprovado.
- Dependências declaradas em `requirements.txt`: FastAPI, Pydantic, SQLAlchemy async, aiohttp/httpx, LiteLLM; não há necessidade aprovada de nova dependência.



## Decisões Tomadas — Clarify 2026-10-11 (T003)

Após investigação documental detalhada (`audit/evidencias-t003.md`), o usuário decidiu:
1. **Motor de busca (RF-02):** Aceitar SERP Jina sem garantia de Google exclusivo. A exigência central é busca SERP via Jina sem leitura de páginas de destino (`no-content`).
2. **Schema do parser:** Parser tolerante. Exigir apenas `title`, `url` e `description` como campos obrigatórios em cada resultado dentro de `data[]`. Outros campos retornados são ignorados.
3. **Timeout:** 30 segundos por tentativa (configurável), com retentativa sequencial até 4 tentativas totais em falhas transitórias.

## Documentação SERP Jina — CONTRATO RESOLVIDO VIA DECISÃO DO USUÁRIO

- Guia oficial: https://docs.jina.ai/api/ — seção “5. Search API”: endpoint `https://s.jina.ai/`, POST, Authorization Bearer, Accept JSON; descreve busca web e formatos configuráveis.
- Referência oficial indicada pelo próprio guia: https://api.jina.ai/docs.
- Guia diferencia Search `s.jina.ai` de Reader `r.jina.ai`; requisito proíbe Reader.
- **Comprovado documentalmente:**
  1. **Mecanismo Google:** Código-fonte `jina-ai/reader` (`src/api/serp.ts`, `src/services/serp/google.ts`) confirma uso de `GoogleSERP` / `SerperGoogleSearchService` para SERP do Google.
  2. **Modo snippets-only (sem leitura de páginas pelo provedor):** Header obrigatório `X-Respond-With: no-content` garante que nenhuma página final é carregada/raspada no provedor. Confirmado por: tutorial oficial Elastic (`https://www.elastic.co/search-labs/tutorials/jina-tutorial/jina-reader`), meta-prompt oficial Jina (`jina-ai/meta-prompt`), e DTO `crawler-options.ts` (`CONTENT_FORMAT.NO_CONTENT = 'no-content'`).
  3. **Schema JSON da resposta (com `Accept: application/json` + `X-Respond-With: no-content`):**
     ```json
     {
       "code": 200,
       "status": 20000,
       "data": [
         { "title": "string", "url": "string", "description": "string", "publishedTime": "string|null" }
       ]
     }
     ```
  4. **Rate limits:** 100 RPM grátis / 1.000 RPM premium.
  5. **Timeout/Retries:** Timeout padrão 25s; retry sequencial até 4 tentativas totais (1 inicial + 3 retries) para 422/429/5xx/rede.
  6. **Fixture oficial rotulada** registrada em `interfaces/jina-serp.md` com origem rastreada.

- Verificação NÃO aceita pelo Orchestrator: exemplo sintético foi rotulado incorretamente como fixture oficial; contrato e parser exigem conferência independente. Nenhuma chamada real à API Jina foi feita.

## Alternativas

1. Reutilizar `search_pipeline.search()`: rejeitada, oferece provedores/fallback múltiplos e Reader associado no mesmo módulo.
2. Criar adapter isolado para Jina Search: recomendada como delta mínimo aderente à ferramenta única; parser/endpoint exatos dependem da verificação acima.
3. Usar Reader ou extrair páginas para obter contexto: rejeitada explicitamente.
4. Reaproveitar `/api/research` e `Research`: inadequado como está, pois agenda fluxo de pesquisa após geração/aprovação.
5. Criar novo domínio de briefing e endpoints próprios: recomendada, mantendo execução posterior fora deste módulo.

## Lacunas de contrato

Rotas HTTP, formato de paginação/listagem, autenticação específica, representação de revisão/histórico e consumo futuro não foram definidos pelos requisitos. Proposta delimitada em `interfaces/briefing-http.md`; confirmar convenções no desenho detalhado, sem ampliar requisito. Rastreabilidade tem confiança inferida: persistir o mínimo auditável sem guardar prompt secreto nem dados desnecessários.
