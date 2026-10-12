# T003 — Evidências públicas do contrato Jina Search

Data da verificação: 2026-10-10. Escopo: somente fontes públicas. Nenhuma chamada à API Jina, credencial ou `.env` usada. Código `jina-ai/reader` verificado no pin público `1574bfd380d249c86c82db4dace0d9c8fe17e2b1` (main em 2026-05-22).

## Vereditos

| Afirmação | Veredito | Motivo |
|---|---|---|
| 1. Endpoint, método e autenticação | **COMPROVADO** | Meta-prompt oficial especifica `https://s.jina.ai/`, `POST`, bearer token, `Content-Type` e `Accept`. |
| 2. Mecanismo é Google | **NÃO COMPROVADO** | Tutorial da Elastic menciona Google mas também "outro mecanismo". Código OSS aceita `google` e `bing` como provider/engine; não prova qual backend o endpoint público usa por padrão. |
| 3. `no-content` exclui conteúdo de páginas do retorno | **COMPROVADO, com escopo restrito** | Meta-prompt Search API declara a opção; tutorial Elastic declara modo search-only sem tentar obter a página; código `SearcherHost` desvia o fetching de páginas quando `respondWith` contém `no-content`. Não prova ausência de qualquer acesso auxiliar na rede do SaaS. |
| 4. Campos JSON da resposta SERP | **COMPROVADO parcialmente** | Exemplo oficial Search comprova `code`, `status`, `data[]` com `title`, `description`, `url`, `content`, `usage.tokens` — mas COM conteúdo de página, sem `no-content`. Forma exata sob `no-content` não tem exemplo oficial; `publishedTime` não aparece nas fontes consultadas. |
| 5. Limites e timeouts | **COMPROVADO parcialmente / NÃO COMPROVADO para timeout** | Meta-prompt comprova `s.jina.ai: 100 RPM, 1000 RPM premium`. `X-Timeout` existe na seção Search ("maximum time (in seconds) to wait for the webpage to load") sem default/SLA comprovado. `reasonableDelayMs` (15 s em `serp.ts`, 25 s em `searcher.ts`) é atraso interno do OSS, não timeout público. 4 tentativas é regra interna RF-10, não contrato Jina. |

## Trechos literais verificáveis

### 1. Endpoint, método, auth, JSON e opções Search

Fonte: [Meta-prompt oficial, v11.txt, seção "4. Search API"](https://github.com/jina-ai/meta-prompt/blob/main/v11.txt) (bruto: https://raw.githubusercontent.com/jina-ai/meta-prompt/main/v11.txt).

> Endpoint: https://s.jina.ai/
> Purpose: search the web for information and return results in a format optimized for downstream tasks like LLMs and other applications. Use https://eu.s.jina.ai/ to reside all infrastructure and data processing operations entirely within EU jurisdiction.
> Method: POST
> Authorization: HTTPBearer
> - **Authorization**: Bearer $JINA_API_KEY
> - **Content-Type**: application/json
> - **Accept**: application/json

> Request body schema: {"application/json":{"q":{"type":"string","required":true},"gl":{"type":"string","required":false,"description":"The country to use for the search. It's a two-letter country code."},"location":{"type":"string","required":false,"description":"From where you want the search query to originate. It is recommended to specify location at the city level in order to simulate a real user’s search."},"hl":{"type":"string","required":false,"description":"The language to use for the search. It's a two-letter language code."},"num":{"type":"number","required":false,"description":"Sets maximum results returned. Using num may cause latency and exclude specialized result types. Omit unless you specifically need more results per page."},"page":{"type":"number","required":false,"description":"The result offset. It skips the given number of results. It's used for pagination."} }}

> **Note: all API's require authorization using the bearer token (get it from https://jina.ai/?sui=apikey)!**

### 2. Mecanismo de busca

Fonte: [Elastic Search Labs — Jina Reader, "Search with s.jina.ai"](https://www.elastic.co/search-labs/tutorials/jina-tutorial/jina-reader) (texto renderizado da página).

> Reader – via the https://s.jina.ai API – performs web search: You give it a query, and it processes the results from a search engine. The service it provides is to standardize SERPs (Search Engine Results Page): the page of results you get when you search on Google or another search engine.

> The Reader API will perform your search on Google and process the result into a structured Markdown page that includes, for the top 10 matches, the page title, URL, and the description/summary provided by the underlying search engine.

Limite: o tutorial descreve uso com Google, mas a primeira frase admite "a search engine" / "Google or another search engine" — não estabelece Google como mecanismo invariável do endpoint público.

Código OSS no pin acima — [`src/api/serp.ts`](https://github.com/jina-ai/reader/blob/1574bfd380d249c86c82db4dace0d9c8fe17e2b1/src/api/serp.ts), linhas 126-129:

> @Param('provider', { type: new Set(['google', 'bing']) })
> @Param('engine', { type: new Set(['google', 'bing']) })
> searchEngine?: 'google' | 'bing',

[`src/services/serp/google.ts`](https://github.com/jina-ai/reader/blob/1574bfd380d249c86c82db4dace0d9c8fe17e2b1/src/services/serp/google.ts), linhas 33-35:

> export class GoogleSERP extends AsyncService {
>     logger = this.globalLogger.child({ service: this.constructor.name });
>     googleDomain = process.env.OVERRIDE_GOOGLE_DOMAIN || 'www.google.com';

Isso prova implementação Google disponível no OSS, não configuração do SaaS público.

### 3. Sem conteúdo de páginas

Fonte: [Meta-prompt oficial, v11.txt, seção Search API](https://github.com/jina-ai/meta-prompt/blob/main/v11.txt).

> - **X-Respond-With** (optional): Use `no-content` to exclude page content from the response

Fonte: [Elastic Search Labs — Jina Reader](https://www.elastic.co/search-labs/tutorials/jina-tutorial/jina-reader) (texto renderizado).

> You can do search-only, without attempting to retrieve the underlying page, by adding the header X-Respond-With: no-content.

Exemplo curl do tutorial (valores literais, chave mascarada no original como `<YOUR_API_KEY>`):

```
curl "https://s.jina.ai/Elastic+Jina" -H "Authorization: Bearer <YOUR_API_KEY>" -H "X-Respond-With: no-content"
```

Código público versionado — [`src/api/searcher.ts`](https://github.com/jina-ai/reader/blob/1574bfd380d249c86c82db4dace0d9c8fe17e2b1/src/api/searcher.ts):

Linha 129:

> const crawlWithoutContent = crawlerOptions.respondWith.includes('no-content');

Linhas 286-289 e 298 (ramo que encerra o fluxo com os resultados SERP, sem chamar `fetchSearchResults`):

> if (crawlWithoutContent || count === 0) {
>     ...
>     it = toAsyncGenerator(results);

Linhas 778-781 (ramo de cache):

> if (cacheUsed && crawlerOptions.respondWith?.includes('no-content')) {
>     yield results;
>     return;
> }

Nota: `crawler-options.ts` do OSS não lista `no-content` no enum `CONTENT_FORMAT` nem na descrição OpenAPI de `X-Respond-With`; o suporte a `no-content` existe no `SearcherHost` (Search), não como formato de crawl do Reader. Limite: o ramo executado no SaaS não pode ser inspecionado aqui.

### 4. JSON e formato de resultado

Fonte: [Meta-prompt oficial, v11.txt, seção Search API](https://github.com/jina-ai/meta-prompt/blob/main/v11.txt).

> Example response: {"code":200,"status":20000,"data":[{"title":"Jina AI - Your Search Foundation, Supercharged.","description":"Our frontier models form the search foundation for high-quality enterprise search...","url":"https://jina.ai/","content":"Jina AI - Your Search Foundation, Supercharged...","usage":{"tokens":10475}},{"title":"Jina AI CEO, Founder, Key Executive Team, Board of Directors & Employees","description":"An open-source vector search engine that supports structured filtering...","url":"https://www.cbinsights.com/company/jina-ai/people","content":"Jina AI Management Team...","usage":{"tokens":8472}}]}

Este é exemplo publicado pela documentação, mas NÃO é fixture da resposta `no-content`: contém `content`. Não inferir presença/ausência de campos sob `no-content`. `publishedTime` não aparece no schema nem no exemplo extraídos.

### 5. Rate limits e timeout

Fonte: [Meta-prompt oficial, v11.txt, parte de limites](https://github.com/jina-ai/meta-prompt/blob/main/v11.txt).

> 5. Finally, Jina AI API endpoints rate limits:
> ...
> Reader APIs:
>  - r.jina.ai: 500 RPM, 5k RPM premium
>  - s.jina.ai: 100 RPM, 1000 RPM premium

Fonte Search API do mesmo arquivo:

> - **X-Timeout** (optional): Specifies the maximum time (in seconds) to wait for the webpage to load

Código OSS — [`src/api/serp.ts:51`](https://github.com/jina-ai/reader/blob/1574bfd380d249c86c82db4dace0d9c8fe17e2b1/src/api/serp.ts):

> reasonableDelayMs = 15_000;

[`src/api/searcher.ts:57,198`](https://github.com/jina-ai/reader/blob/1574bfd380d249c86c82db4dace0d9c8fe17e2b1/src/api/searcher.ts):

> reasonableDelayMs = 25_000;
> const timeoutMs = crawlOpts.timeoutMs || this.reasonableDelayMs;

São atrasos internos distintos do OSS, não timeout/SLA da API pública. `X-Timeout` documentado refere-se a carregamento de webpage, não a timeout total da pesquisa.

## Consequência para RF-02 / RF-10

RF-02 exige Google especificamente e ausência de leitura de páginas; "Google" continua sem prova suficiente diante da evidência de múltiplos providers. `no-content` tem documentação direta e ramo de código SERP, mas a resposta JSON snippets-only não tem exemplo oficial. RF-10 (4 tentativas sequenciais) é política interna da aplicação; fontes Jina não impõem esse retry.

Bloqueio T003: não congelar parser como `{title,url,description,publishedTime}` nem afirmar Google invariável. Decisão necessária do usuário: aceitar SERP Jina sem garantia de Google exclusivo, ou exigir Google comprovado (outro provider ou validação operacional); aceitar contrato mínimo `no-content` baseado só nos campos comprovados, ou exigir prova oficial da forma exata do JSON.
