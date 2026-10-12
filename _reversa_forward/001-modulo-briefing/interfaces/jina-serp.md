# Interface: Jina SERP (Search API)

> Identificador: `interfaces/jina-serp.md`
> Status: Contrato proposto aceito pelo usuário em 2026-10-11: SERP via Jina sem garantia de Google exclusivo; parser tolerante e timeout de cliente definidos. Fontes não comprovam schema exato sob `no-content`; integração real ainda não testada.
> Data: `2026-10-10`

---

## 1. Visão geral e escopo do contrato

Este documento especifica o contrato HTTP e comportamento do provedor externo **Jina Search API** (`s.jina.ai`) para uso exclusivo do módulo de briefing como tool de busca SERP, distinguindo o que é estritamente comprovado de propostas técnicas pendentes de validação.

### Requisito crítico de execução (snippets-only)
- Por padrão, `s.jina.ai` realiza a busca web e visita/lê páginas de destino aplicando a tecnologia do `r.jina.ai` (Reader) no provedor.
- Para proibir a leitura/scraping de páginas de destino e obter modo search-only, as fontes públicas documentam o cabeçalho:
  ```http
  X-Respond-With: no-content
  ```
- **Evidências do cabeçalho:**
  - Meta-prompt oficial Jina AI (`v11.txt`, seção "4. Search API"): `- **X-Respond-With** (optional): Use `no-content` to exclude page content from the response`.
  - Tutorial Elastic Search Labs: *"You can do search-only, without attempting to retrieve the underlying page, by adding the header `X-Respond-With: no-content`."*
  - Código-fonte de referência (`jina-ai/reader`, `src/api/searcher.ts:129,286-289,778`): `crawlerOptions.respondWith.includes('no-content')` desvia o pipeline e encerra o fluxo sem invocar `fetchSearchResults`.
- **Limitação da evidência:** O código OSS e a documentação comprovam o desvio de scraping de páginas de destino no payload, mas não constituem garantia auditável de que o serviço SaaS não realize acessos auxiliares em sua própria rede.

---

## 2. Especificação do contrato HTTP

### Endpoint e Método
- **URL Base:** `https://s.jina.ai/` (COMPROVADO: meta-prompt oficial v11.txt, seção "4. Search API": `Endpoint: https://s.jina.ai/`).
- **Espelho UE:** `https://eu.s.jina.ai/` (COMPROVADO: meta-prompt oficial v11.txt, seção Search).
- **Método HTTP:** `POST` (COMPROVADO: meta-prompt, `Method: POST`). Tutorial da Elastic também demonstra GET opcional com query no path (`https://s.jina.ai/your+query`).

### Cabeçalhos da requisição
| Cabeçalho | Valor / Tipo | Status | Descrição |
|-----------|--------------|--------|-----------|
| `Authorization` | `Bearer $JINA_API_KEY` | COMPROVADO | Autenticação bearer (meta-prompt Search API). |
| `Content-Type` | `application/json` | COMPROVADO | Formato do body POST (meta-prompt Search API). |
| `Accept` | `application/json` | COMPROVADO | Solicita resposta JSON (meta-prompt Search API). |
| `X-Respond-With` | `no-content` | COMPROVADO como opção da API | Exclui conteúdo da página da resposta; header exigido internamente pelo módulo. |
| `X-Timeout` | Integer (segundos) | COMPROVADO como opcional | Meta-prompt Search API: `Specifies the maximum time (in seconds) to wait for the webpage to load`; valor padrão/SLA não comprovados. |
| `X-Site` | domínio | COMPROVADO como opcional | Limita busca ao domínio especificado (meta-prompt Search API). |

### Schema do Corpo da Requisição (COMPROVADO)
Fonte: meta-prompt oficial `v11.txt`, seção "4. Search API". Trecho literal:

```
Request body schema: {"application/json":{"q":{"type":"string","required":true},"gl":{"type":"string","required":false,"description":"The country to use for the search. It's a two-letter country code."},"location":{"type":"string","required":false,"description":"From where you want the search query to originate. It is recommended to specify location at the city level in order to simulate a real user’s search."},"hl":{"type":"string","required":false,"description":"The language to use for the search. It's a two-letter language code."},"num":{"type":"number","required":false,"description":"Sets maximum results returned. Using num may cause latency and exclude specialized result types. Omit unless you specifically need more results per page."},"page":{"type":"number","required":false,"description":"The result offset. It skips the given number of results. It's used for pagination."} }}
```

Campos: `q` obrigatório; `gl`, `location`, `hl`, `num`, `page` opcionais.

---

## 3. Resposta e Estrutura JSON

### Exemplo oficial da Search API (COMPROVADO, resposta com conteúdo de página)
Fonte: meta-prompt oficial `v11.txt`, seção "4. Search API". Trecho literal:

```
Example response: {"code":200,"status":20000,"data":[{"title":"Jina AI - Your Search Foundation, Supercharged.","description":"Our frontier models form the search foundation for high-quality enterprise search...","url":"https://jina.ai/","content":"Jina AI - Your Search Foundation, Supercharged...","usage":{"tokens":10475}},{"title":"Jina AI CEO, Founder, Key Executive Team, Board of Directors & Employees","description":"An open-source vector search engine that supports structured filtering...","url":"https://www.cbinsights.com/company/jina-ai/people","content":"Jina AI Management Team...","usage":{"tokens":8472}}]}
```

### Schema de resposta com `X-Respond-With: no-content` (não comprovado como resposta real)

**Decisão do usuário, 2026-10-11:** parser tolerante exige somente `title`, `url` e `description` em cada item de `data[]`; campos adicionais são ignorados. Não exigir `publishedTime` ou conteúdo de página. Decisão de cliente não comprova schema do provedor.
> Aviso: exemplo oficial contém `content` e não demonstra a forma exata sob `no-content`. Fixture abaixo é **proposta técnica**, NÃO comprovada; parser não deve exigir campos além dos comprovados.

```json
{
  "code": 200,
  "status": 20000,
  "data": [
    {
      "title": "string",
      "url": "string",
      "description": "string (snippet)",
      "publishedTime": "string | null — campo NÃO comprovado; usar somente como opcional/tolerante"
    }
  ]
}
```

---

## 4. Exemplo de requisição, sem valor de evidência de resposta

> Resposta abaixo é exemplo sintético criado pelo worker, NÃO fixture oficial, NÃO resposta real e NÃO evidência do contrato. Mantido somente para ilustrar o uso dos campos comprovados.

### Exemplo de Requisição `curl`
```bash
curl -X POST "https://s.jina.ai/" \
  -H "Authorization: Bearer $JINA_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-Respond-With: no-content" \
  -d '{
    "q": "inteligencia artificial no Brasil",
    "gl": "br",
    "hl": "pt",
    "num": 5
  }'
```

### Exemplo de resposta JSON sintética (não obtida da API)
```json
{
  "code": 200,
  "status": 20000,
  "data": [
    {
      "title": "Inteligência Artificial no Brasil: panorama e diretrizes",
      "url": "https://www.exemplo.gov.br/ia-brasil",
      "description": "Panorama atual do desenvolvimento e regulamentação da inteligência artificial no Brasil...",
      "publishedTime": "2026-01-15T10:00:00Z"
    },
    {
      "title": "Estratégia Brasileira de Inteligência Artificial",
      "url": "https://www.exemplo.org/ebia",
      "description": "Documento traz os eixos estratégicos para fomento e uso ético de IA em território nacional...",
      "publishedTime": "2025-11-20T14:30:00Z"
    }
  ]
}
```

---

## 5. Mecanismo de Busca, Rate Limits, Timeouts e Retentativas

### Mecanismo de Busca
- Status: **NÃO COMPROVADO** como Google exclusivo.
- Tutorial Elastic (trecho literal): *"Reader – via the https://s.jina.ai API – performs web search: You give it a query, and it processes the results from a search engine."* O tutorial também descreve uma integração usando Google, mas não estabelece Google como mecanismo invariável do endpoint público.
- Código de referência `jina-ai/reader`, `src/api/serp.ts` (pin `1574bfd…`): parâmetros `@Param('provider', { type: new Set(['google', 'bing']) })` e `@Param('engine', { type: new Set(['google', 'bing']) })` — prova que o OSS suporta google e bing, não qual backend o SaaS usa.
- `src/services/serp/google.ts` declara `export class GoogleSERP` com `googleDomain = process.env.OVERRIDE_GOOGLE_DOMAIN || 'www.google.com'` — prova implementação Google disponível, não configuração do serviço público.

### Limites de Taxa (Rate Limits — COMPROVADO)
Fonte: meta-prompt oficial `v11.txt`, trecho literal:
```
 - s.jina.ai: 100 RPM, 1000 RPM premium
```

### Timeout e Retentativas
- **Timeout HTTP público:** NÃO COMPROVADO como valor fixo. Código de referência `src/api/serp.ts:51` define `reasonableDelayMs = 15_000`; `src/api/searcher.ts:57` define `reasonableDelayMs = 25_000` e `src/api/searcher.ts:198` usa `const timeoutMs = crawlOpts.timeoutMs || this.reasonableDelayMs;`. São atrasos internos distintos no OSS, não timeout/SLA garantido da API pública. **Decisão do usuário, 2026-10-11:** timeout de cliente para Jina e LLM de 30 segundos por tentativa, configurável. Limite de até 4 tentativas totais continua vigente; valor não deriva de SLA público.
- **Política de retentativa (4 tentativas):** exigência interna RF-10 da aplicação, NÃO recurso da API Jina. Retentativas Jina para 429/erros de rede são decisão de cliente.
- Em sucesso SERP seguido de falha do LLM/agente, reutilizar o resultado já obtido sem nova chamada externa (exigência RF-10).

---

## 6. Evidências e Fontes Oficiais Registradas

1. **Documentação Oficial Jina API:**
   - URL: `https://docs.jina.ai/api` (Seção "5. Search API", `s.jina.ai`, método `POST`, `Accept: application/json`).
2. **Dashboard de Referência Jina AI:**
   - URL: `https://jina.ai/en-US/api-dashboard/` (Especificação de `s.jina.ai` e parâmetro `Accept: application/json`).
3. **Tutorial de Integração Jina Reader (Elasticsearch Labs):**
   - URL: `https://www.elastic.co/search-labs/tutorials/jina-tutorial/jina-reader`
   - Trecho comprovatório:
     > *"You can do search-only, without attempting to retrieve the underlying page, by adding the header `X-Respond-With: no-content`."*
4. **Repositório do Provedor (`jina-ai/reader`):**
   - URL: `https://github.com/jina-ai/reader/blob/main/README.md`
   - URL: `https://github.com/jina-ai/reader/blob/main/src/dto/crawler-options.ts`
   - URL: `https://github.com/jina-ai/reader/blob/main/src/api/serp.ts`
   - URL: `https://github.com/jina-ai/reader/blob/main/src/services/serp/google.ts`

---

## 7. Adendo de implementação local T009 (2026-10-11; não altera evidências acima)

- `app/briefing/serp_client.py`: `JinaSerpClient(api_key, timeout=30, http_client=None)`; `async search(theme) -> list[dict]` devolve exclusivamente `title`, `url`, `description`.
- Endpoint HTTPS fixo `https://s.jina.ai/`, `POST` com JSON `{"q": <tema normalizado>}` e cabeçalhos `Authorization: Bearer [REDACTED]`, `Accept: application/json`, `Content-Type: application/json`, `X-Respond-With: no-content`; redirects desativados por chamada. Nenhuma URL SERP é visitada.
- Tema passa por `validate_theme` (strip e 3–300) antes de I/O; chave validada como token ASCII imprimível (caracteres em 33–126) antes de I/O, rejeitando vazia, espaços, controles (NUL/TAB/DEL/CR/LF) e não-ASCII; timeout finito e positivo. Erro público tem mensagem fixa e número real de tentativas; exceções subjacentes só em chaining interno, sem log.
- Até quatro tentativas totais sequenciais por operação; sucesso encerra imediatamente. HTTP não-2xx, falha de transporte/timeout, JSON/shape inválido e ausência de resultados utilizáveis tentam novamente. Cancelamento propaga. Parser descarta itens inválidos individualmente, mantendo válidos; lista final vazia falha. URL exige esquema HTTP(S) e host, sem fetch/DNS.
- Timeout `asyncio.timeout` é teto wall-clock por tentativa (30s padrão); não é SLA do provedor. Sem backoff obrigatório nesta fase (intervalo não decidido — limitação registrada).
- Lock `asyncio` serializa chamadas somente na mesma instância; não é coordenação cross-process. Cliente injetado permanece sob propriedade do caller; cliente criado internamente fecha após tentativa. Compartilhamento com T011 ainda pendente.
- Testes em `tests/test_briefing_serp_client.py` usam `httpx.MockTransport` e fixtures SINTÉTICAS; nenhuma chamada real ao provedor foi feita.
