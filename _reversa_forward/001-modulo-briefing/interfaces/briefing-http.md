# Interface HTTP — briefing backend

## Prescrição vigente (T025/T026, consolidada 2026-10-11)

Esta seção é o contrato vigente para as ações T025/T026, consolidando decisões do delta `audit/t025-t026-planning-delta.md`. Sem alias, sem duplicação com `/api/*` do legado, sem frontend. Autenticação reutiliza `require_admin` (cookie CSRF em mutações, Bearer/X-API-key também aceitos conforme `app/core/security.py`); nenhum mecanismo novo.

### Rotas canônicas

| Método e rota | Request | Resposta sucesso | Regras |
|---|---|---|---|
| `POST /briefings` | `BriefingCreateRequest` (`theme`) | `201` + `BriefingResponse` | Validação Pydantic 422 antes de settings-runtime/SERP/LLM ou criação/mutação de briefing; autenticação pode consultar DB via `get_db`. Execução síncrona única via `orchestrate_persisted_briefing` (Tx1 → prompt → SERP → LLM ≤4 → CAS Tx2); sem scheduler/background |
| `GET /briefings/{id}` | — | `200` + `BriefingResponse` | Snapshot corrente; 404 se ausente |
| `PATCH /briefings/{id}` | `BriefingEditPointsRequest` (`points`) | `200` + `BriefingResponse` | Somente `draft`; versão +1 e histórico append; aprovado/estado incompatível 409; CAS 409 |
| `POST /briefings/{id}/approve` | omitido, `null` ou `{}` | `200` + `BriefingResponse` | Somente `draft`; `[]`, string, número, bool ou objeto com extra → 422; aprova com `approved_at`, versão +1 |
| `POST /briefings/{id}/reopen` | omitido, `null` ou `{}` | `200` + `BriefingResponse` | Somente `approved`; demais bodies → 422; versão +1, `approved_at` null |
| `GET /briefings/approved/{id}` | — | `200` + `ApprovedBriefingResponse` | Read-only; SELECT DB permitido; nenhum I/O externo/SERP/LLM/pesquisa; existente não aprovado 409; ausente 404 |
| `GET /briefings/{id}/versions` | — | `200` + `list[BriefingVersionResponse]` | Somente snapshots pós-transição (v2+); corrente `generating` v1 não listado; ordenada `version ASC`; pai inexistente 404 (não lista vazia); sem `briefing_id` no payload |

Corpo `approve/reopen` omitido, JSON `null` explícito ou objeto vazio `{}` são no-op; qualquer outro tipo JSON ou campo extra gera 422 (`extra="forbid"`). Requisição rejeitada (422/404/409) não altera DB nem histórico.

### Matriz de erros HTTP

| Situação | Status | Detalhe público |
|---|---|---|
| Tema/pontos fora das regras (Pydantic/`InvalidContent`) | 422 | mensagens do schema/validação, sem dados dinâmicos de provedor |
| Briefing inexistente (get/get current/patch/approve/reopen/approved/versions) | 404 | fixo |
| Estado incompatível, transição inválida (`InvalidTransition`), conflito CAS (`BriefingVersionConflictError`) | 409 | fixo |
| Prompt indisponível após Tx1 (`PromptUnavailable` → FAILED persistido) | 500 | fixo `Prompt de briefing indisponível` |
| SERP esgotada (`SerpSearchError`) ou LLM esgotado (`LLMAttemptError` ×4 → FAILED persistido) | 503 | fixo `Busca SERP indisponível` / `Geração de briefing indisponível` |
| Erro de configuração do binding (`ProviderConfigurationError`, descoberto na invocação do callable após Tx1/SERP; sem retry) | 500 | genérico fixo, sem mensagem original; wrapper tenta emergência FAILED e repropaga |
| Chave Jina inválida (`ValueError` somente na construção/verificação do `JinaSerpClient`, pré-Tx1 após tema válido/auth) | 500 | genérico fixo, sem briefing criado |
| Autorização upstream: `litellm.exceptions.AuthenticationError`/`PermissionDeniedError` diretas; `litellm.exceptions.APIError` com `status_code`, ou `httpx.HTTPStatusError` com `response.status_code`, inteiro não-bool 401/403 | 500 | genérico fixo; credenciais do provedor não são credenciais locais do operador |
| Auth ausente/inválida, CSRF inválido/ausente, credenciais ambíguas, header tenant proibido | 401/403/400 | conforme `require_admin` existente |

Erros desconhecidos propagam com identidade, sem retry/`LLMAttemptError`; após Tx1, wrapper tenta emergência `FAILED` com `Processamento abortado ou cancelado` e repropaga a mesma exceção. É best-effort: crash ou falha DB pode impedir persistência; não prometer `FAILED` garantido. Cancelamento (`CancelledError`) repropaga e não vira resposta normal. HTTP aplica default 500 genérico. `ProviderConfigurationError` pós-Tx1/SERP segue o mesmo caminho; `ValueError` só é capturado ao construir/verificar `JinaSerpClient`, não no handler inteiro. Tradução tipada upstream limita-se às classes/status concretos da matriz; não inferir classe de auth por atributo/string em exceção arbitrária. Sem `except Exception` broad que mascara programação/retry. Falha entre Tx1 e Tx2 pode deixar `generating` visível. HTTP público nunca expõe strings dinâmicas de erro, chaves, prompt integral, raciocínio bruto, payload de provedor ou traceback.

### Fronteira de transação e runtime (por operação)

- Cada rota recebe `db: AsyncSession = Depends(get_db)` e `principal: Principal = Depends(require_admin)`; `require_admin` usa a mesma instância request de `get_db`, portanto auth e CSRF concluem antes do corpo da rota. Em seguida, rota chama `db.rollback()` somente se `db.in_transaction()`, antes de qualquer query de domínio/operação externa. Rollback pode expirar/destacar ORM `Principal`; feature não lê atributos dele depois disso, usando apenas fato de autorização concluída. Não commitar, não finalizar sessão do chamador do binding, nem alterar `app/core/security.py`; sessão request permanece sob propriedade/ciclo de vida da camada HTTP.
- Factory `make_scout_complete` valida apenas timeout; settings/modelo/chave são resolvidos na invocação do callable, após Tx1 e SERP. `ProviderConfigurationError` então descoberto não entra em retry: wrapper tenta emergência `FAILED` e repropaga, HTTP retorna 500 genérico fixo. `JinaSerpClient`: `ValueError` somente na construção/verificação, pré-Tx1 após tema válido/auth, 500 genérico sem briefing. Instanciado por operação; lock por instância, sem promessa cross-process. `make_scout_complete(AsyncSessionLocal, default_timeout_s=30.0)` por request; serviço recebe mesmo timeout finito positivo configurado por tentativa, default 30s; sem singleton secreto em import.
- Sem retry externo/nested: retries SERP são internos ao client (≤4), retries LLM são o loop do serviço (≤4); binding é one-attempt. Uma chamada ativa POR OPERAÇÃO conforme vigente; sem scheduler, background task, fila ou pesquisa legada.

### Testes HTTP obrigatórios (tests/test_briefing_api.py)

ASGITransport + SQLite isolado, app importada sem executar lifespan legado; overrides somente de DB/session factory e dependências de I/O — nunca remover auth. `require_admin` real para 401 (sem credencial), 403 (cookie mutation sem CSRF/CSRF inválido), sucesso cookie+bearer+API-key. Cobrir a tabela de rotas acima com versão/histórico verificados e a matriz de erros; cada contrato precisa critério→símbolo→teste real executado.

## Status da prescrição

**IMPLEMENTADA em código** — API canônica `/briefings` (D1, D3, D4) entregue em `app/briefing/router.py` e integrada em `app/main.py` (`include_router(briefing_router)`). Schemas D4 (`BriefingResponse` com `version/error/approved_at`, `BriefingVersionResponse`) em `app/briefing/schemas.py` (T035). Suíte: 183 testes verdes (`audit/t012-t036-execution.md:58`). Gates independentes (auditoria/QA/runtime) seguem fora deste documento.

O bloco abaixo é o texto original desta interface, preservado como histórico/proposta anterior. Onde conflitar com a prescrição vigente acima, prevalece a prescrição vigente (prefixo `/briefings` sem alias, bodies approve/reopen, códigos por falha, `BriefingResponse` com `version/error/approved_at` e `BriefingVersionResponse` conforme D4).

| Operação | Finalidade | Regras |
|---|---|---|
| `POST /briefings` | Criar briefing e iniciar geração | Validar tema normalizado 3–300 antes de chamadas externas; registrar geração; iniciar SERP/agente de forma isolada |
| `GET /briefings/{id}` | Obter briefing e rascunho/estado | Expor versão atual, estado e erro seguro quando houver |
| `PATCH /briefings/{id}` | Editar rascunho | Permitir somente em rascunho; salvar versão consultável com 3–7 pontos; rejeitar quantidade fora do intervalo sem alterar versão anterior; recusar quando aprovado |
| `POST /briefings/{id}/approve` | Aprovar briefing válido | Exigir 3–7 pontos válidos; recusar edição posterior até reabrir |
| `POST /briefings/{id}/reopen` | Reabrir aprovado | Retornar a rascunho para nova edição |
| `GET /briefings/approved/{id}` ou consulta com escopo equivalente | Fornecer conteúdo aprovado | Somente aprovado; operação read-only; sem iniciar pesquisa |

As rotas acima são proposta técnica. Confirmar prefixo, pluralização, autenticação e formato de erro com convenções do backend antes da implementação.

## Representação

O nome canônico do campo de estado é `status`, conforme os schemas do módulo; seus valores são `generating`, `draft`, `failed` e `approved`. Rotas, autenticação, metadados e demais detalhes abaixo continuam proposta técnica, não API integralmente implementada ou congelada.

**Exemplo histórico de metadados — não implementado nem contrato vigente.** `prompt`, `search`, `updated_at` e qualquer proveniência/hash abaixo são sugestão não planejada nesta rodada; não persistir nem retornar nesta API. Campos D4 vigentes constam na prescrição acima.

```json
{
  "id": "uuid",
  "theme": "string",
  "status": "generating|draft|failed|approved",
  "points": [
    {"title": "string", "description": "string"}
  ],
  "prompt": {"file": "prompts/briefing.md", "version": "hash-or-version"},
  "search": {"query": "tema", "attempts": 1, "status": "ok|failed"},
  "version": 1,
  "error": null,
  "approved_at": null,
  "updated_at": "timestamp"
}
```

## Erros

- `422`: tema inválido, conteúdo de briefing inválido ou quantidade fora de 3–7 na geração, edição ou aprovação; tratamento do prompt segue política de configuração.
- `404`: briefing inexistente.
- `409`: conflito de estado, transição inválida ou edição em briefing já aprovado.
- `500`: falha de configuração ou ausência do arquivo de prompt antes de chamar agente (sem expor segredos).
- `503`: falha externa após quatro tentativas sequenciais.
- Mensagens não incluem segredos, chaves, prompt integral, raciocínio bruto ou detalhes internos sensíveis.

## Comportamento externo

- Busca: apenas SERP Jina, uma chamada ativa, repetição apenas em falha, quatro tentativas máximas por operação.
- Agente: chamada após prompt válido e SERP disponível; até quatro tentativas reaproveitando SERP; falha sem gravar briefing válido.
- Tempo limite Jina/LLM de 30s configurável por tentativa (decisão registrada em roadmap.md); idempotência de criação não decidida, sem inventar semântica nesta etapa.
- Nenhum webhook, SSE, Reader, scraping ou API paralela faz parte desta interface.


## Delta contratual interno do binding LLM — T029–T031 (consolidado)

Este delta documenta o contrato interno usado pela geração HTTP; não altera a forma de request/response HTTP. Assinatura: `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s: float = 30.0)` retorna `scout_complete(system: str, user: str, timeout_s: float | None = None)`. `default_timeout_s` é validado na factory; o override `timeout_s` é validado antes de abrir sessão, carregar settings, validar transporte ou chamar LLM (falha aborta com zero chamadas de fronteira; overflow extremo de `float()` vira `ValueError` fixo). `None` usa o default; int/float positivos finitos não-bool, inclusive valores >30s, são aceitos e repassados ao LiteLLM; sem teto novo. Abre sessão isolada curta do factory para ler e copiar configurações escalares, fechando-a antes do I/O LiteLLM, sem manter transações abertas e sem finalizar sessão do chamador. Implementação e testes consultam leitura de `app/briefing/llm_binding.py` e `tests/test_briefing_llm_binding.py`; helper legado `app/services/llm.py` (`_classify_error`/`complete`) não é alterado.
Erros de configuração continuam propagando diretamente como HTTP 500 (`ProviderConfigurationError`); erros de autorização upstream (401, 403) propagam com identidade no binding e, na fronteira HTTP, traduzem para 500 genérico fixo — não são credenciais locais do operador e não vazam corpo bruto. Somente falhas externas reconhecidas por tipo concreto produzem `LLMAttemptError` seguro com mensagem fixa `Geração de briefing indisponível` (args/causa observável/traceback sem segredos/sentinelas): LiteLLM `APIConnectionError`, `Timeout`, `InternalServerError` (500), `RateLimitError` (429), `ServiceUnavailableError` (503), e `APIError` com status 429/500/502/503/504; transporte `httpx` conexão/timeouts/`HTTPStatusError` com status reconhecido 429/500/502/503/504; e builtin `TimeoutError` levantado pelo SDK dentro do binding. É proibido converter `RuntimeError`/`TypeError` arbitrário por conter palavras como "timeout"/"quota" ou números como 429/503; desconhecidos e erros de programação propagam com identidade. Builtin `TimeoutError` arbitrário de outro callable injetado no serviço propaga; deadline `asyncio.timeout.expired()` do serviço consome tentativa; `from None` não autoriza afirmar ausência de `__context__`. Por chamada, passar explicitamente `num_retries=0` e `max_retries=0`, garantindo exatamente uma requisição HTTP por tentativa no caminho verificado (evidência LiteLLM 1.104.0/OpenAI fake 503 request 1 não prova todos providers/configurações globais).
