# T011 — decomposição da integração (decisões técnicas fechadas)

## Escopo
Somente HTTP, persistência durável e binding LiteLLM one-attempt. Sem pipeline de pesquisa, Reader, frontend ou migração real. Plano executável sem ambiguidades.

## D1 — Identidade e ciclo de vida na geração
Decisão: a rota / serviço persiste com o ID gerado pelo domínio puro. A rota NÃO pré-aloca ID.
- `app/briefing/domain.py:94 new_briefing(theme)` mantém assinatura `(theme: str) -> Briefing`, gerando `uuid4()` interno com status `GENERATING` e versão 1.
- No endpoint `POST /briefings`:
  1. Validação de tema via schema Pydantic (`422` antes de qualquer I/O).
  2. Chamada de `new_briefing(theme)`.
  3. `INSERT INTO briefings` gravando `id`, `theme`, `status='generating'`, `version=1` em transação curta com `commit` imediato.
  4. Execução de prompt, SERP e LLM inteiramente fora da transação de banco.
  5. Atualização final via CAS (`WHERE id=:id AND version=1`) para `draft` (sucesso) ou `failed` (erro).
- Prevenção de colisão: chave primária em `briefings.id` aliada a UUID4 stdlib garante unicidade. Tentativa de colisão resulta em erro de constraint na transação curta de inserção, nunca recriação ou sobrescrita silenciosa.

## D2 — Histórico e versionamento (RF-05 / RF-09)
Decisão: modelo snapshot append-only com tabela dedicada `briefing_versions` e endpoint de consulta explícito.
- Endpoints:
  - `GET /briefings/{id}`: retorna o snapshot corrente do briefing (`BriefingResponse`, incluindo campo `version`).
  - `GET /briefings/{id}/versions`: retorna lista ordenada ascendente (`version ASC`) do histórico; responde `404` caso o briefing pai não exista. Sem histórico embutido no payload do GET principal.
- Tabelas de dados:
  - `briefings`:
    - `id UUID PRIMARY KEY`
    - `theme VARCHAR(300) NOT NULL`
    - `status VARCHAR(20) NOT NULL`
    - `version INTEGER NOT NULL`
    - `points_json JSON NOT NULL DEFAULT '[]'`
    - `error TEXT NULL`
    - `approved_at TIMESTAMPTZ NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `briefing_versions`:
    - `id UUID PRIMARY KEY`
    - `briefing_id UUID NOT NULL REFERENCES briefings(id) ON DELETE CASCADE`
    - `version INTEGER NOT NULL`
    - `status VARCHAR(20) NOT NULL`
    - `points_json JSON NOT NULL`
    - `error TEXT NULL`
    - `approved_at TIMESTAMPTZ NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - Restrições: `UNIQUE(briefing_id, version)`, `INDEX(briefing_id, version ASC)`.
- Ciclo de escrita: cada mutação de estado bem-sucedida (`complete`, `fail`, `edit`, `approve`, `reopen`) incrementa `version` no domínio e grava, em transação atômica única, a atualização de `briefings` e um novo registro em `briefing_versions`.
- Conteúdo de `points_json`: armazena exclusivamente os pontos validados serializados (`[{"title": "...", "description": "..."}]`). Nunca armazena saída bruta de LLM, segredos ou prompts internos.

## D3 — Persistência transacional e tratamento de órfãos
Decisão: duas transações atômicas curtas e proteção por `try...finally` na rota/serviço, sem filas em background ou jobs pesados de cleanup.
- Transação 1 (reserva): insere o registro com status `generating` (versão 1) e efetua commit imediato, liberando a conexão com o pool.
- Execução externa: busca SERP e chamadas LiteLLM ocorrem inteiramente fora de transação ativa.
- Transação 2 (conclusão): `UPDATE briefings SET status=:st, version=:new_v, points_json=:pts, error=:err, updated_at=now() WHERE id=:id AND version=:old_v` acompanhado do `INSERT INTO briefing_versions`. Se `rowcount != 1`, houve conflito de versão (CAS falhou) -> `ROLLBACK` e resposta `409 Conflict`.
- Política de órfãos e falhas:
  - Bloco `try...except...finally` na camada de serviço/rota engloba o ciclo externo.
  - Em falha de provedor externo esgotada (SERP ou LLM), atualiza o registro existente para `failed` via CAS e retorna `503 Service Unavailable`.
  - Em cancelamento de requisição (`asyncio.CancelledError`) ou exceção não tratada: bloco de captura tenta uma transação curta de emergência para atualizar status para `failed` com mensagem genérica, antes de propagar.
  - Em falha catastrófica de infraestrutura (crash do container antes da Tx2): o registro permanece visível em `generating`. Não há job de recuperação em background nem transição automática silenciosa. O operador ou usuário identifica o estado estagnado e reexecuta a operação via novo `POST /briefings`.

## D4 — Schemas de API
Decisão: enriquecer os schemas de resposta em `app/briefing/schemas.py` mantendo compatibilidade retroativa estrita e `extra = "forbid"`.
- `BriefingResponse`:
  - `id: UUID`
  - `theme: str`
  - `status: BriefingStatus`
  - `points: list[BriefingPoint] = Field(default_factory=list)`
  - `version: int = Field(default=1, ge=1)`
  - `error: str | None = None`
  - `approved_at: datetime | None = None`
  - Mantém o `@model_validator` exigindo validação de pontos (3 a 7) para status `draft` e `approved`.
- Novo schema `BriefingVersionResponse`:
  - `version: int = Field(ge=1)`
  - `status: BriefingStatus`
  - `points: list[BriefingPoint] = Field(default_factory=list)`
  - `error: str | None = None`
  - `approved_at: datetime | None = None`
  - `created_at: datetime`
  - `model_config = {"extra": "forbid"}`
- `GET /briefings/{id}/versions` responde `list[BriefingVersionResponse]`.
- Schemas de requisição (`BriefingCreateRequest`, `BriefingEditPointsRequest`, `BriefingApproveRequest`, `BriefingReopenRequest`) e `ApprovedBriefingResponse` permanecem inalterados.

## D5 — Trace estático LiteLLM/Settings (HISTÓRICO E SUBSTITUÍDO)

**HISTÓRICO E SUBSTITUÍDO PELO ADENDO T029–T031 ABAIXO.** O conteúdo original desta seção, inclusive a assinatura `make_scout_complete(db: AsyncSession, timeout_s: float = 30.0)`, snippet de chamada e descrição de classificação, fica preservado somente para proveniência; não é contrato vigente e não deve coexistir como prescrição implementável. Para contrato único, seguir exclusivamente D5 revisado nas linhas seguintes.

<details>
<summary>Conteúdo histórico substituído — não implementar</summary>

Decisão histórica: fábrica de invocação por requisição injetando sessão de banco, role `scout`, uma chamada direta sem retry interno.
- Credenciais/modelo eram lidos por `runtime_settings(db)`; modelo via `models.get("scout")`, com fallbacks do runtime. Provedor por `_provider(model)`; chave via `keys.get(provider)`; `api_base` por settings/registro.
- Assinatura histórica: `make_scout_complete(db: AsyncSession, timeout_s: float = 30.0) -> Callable[[str, str], Awaitable[str]]`.
- Snippet histórico chamava `litellm.acompletion` sem o contrato de timeout T028 completo, ownership da sessão isolada e dupla desativação de retries.
- Classificação histórica descrita genericamente como conversão de falhas de rede/provedor, sem matriz concreta completa.

</details>


## Adendo T029–T031 — binding LLM (contrato único vigente)

Este adendo substitui os trechos incompatíveis de D3 e D5; D5 antigo acima é histórico e não vigente. Resolução documental para o cross-check: auditor decide PASS.

### D3 — fronteira entre transação e I/O externo

Reserva e conclusão continuam transações curtas conforme acima. A operação externa não recebe nem mantém sessão/transação do chamador: o binding recebe `session_factory` (fábrica compatível com `async_sessionmaker[AsyncSession]`) e abre uma sessão própria apenas para ler settings, chave, modelo e `api_base`. Resolve e copia os valores escalares necessários; fecha a sessão em `async with` antes de chamar `litellm.acompletion`. A chamada de rede ocorre sem sessão DB aberta pelo binding. Binding não chama `commit()` nem `rollback()` sobre sessão do chamador.

Se `get_record(db)` criar `AppSettings` e somente fizer `flush`, a primeira leitura na sessão isolada vê o objeto criado dentro dessa unidade de trabalho, mas fechar a sessão sem `commit` reverte sua inserção; isso não persiste inicialização como efeito colateral. O comportamento esperado é usar os defaults/valores resolvidos para a chamada corrente e descartar a criação transitória. Persistir defaults exigiria decisão explícita e transação própria separada, fora deste delta; não alterar `get_record` legado nem introduzir commit implícito. Verificar esse caso em teste com SQLite/settings reais.

### D5 — assinatura e sequência (contrato único vigente)

- Assinatura: `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s: float = 30.0) -> Callable[..., Awaitable[str]]`. Retorna `scout_complete(system: str, user: str, timeout_s: float | None = None) -> str`. Única mudança deliberada é ownership do DB para a factory; keywords e defaults existentes em T028 preservados; sessão caller-owned não é aceita.
- Timeout: `default_timeout_s` validado na fábrica; `timeout_s` por chamada validado antes de abrir sessão, settings, transporte ou LLM (falha aborta com zero I/O). Ambos rejeitam `bool`, não-números, NaN, infinitos, zero, negativos e extremos que estouram `float()` (OverflowError convertido em ValueError fixo); aceitam int/float finitos positivos, inclusive > 30.0s; `None` no override significa usar o default. Não é novo teto: default 30.0s não impõe máximo.
- Role/modelo runtime: role fixa `scout`, resolução por `runtime_settings(db)` + `_provider(model)` + `keys.get(provider)` + `get_record(db)` para `api_base`, com mesmos erros de configuração do runtime. Preserva escolhas runtime sem fixar modelo histórico específico.
- Na invocação: abrir sessão própria da fábrica em `async with`; `runtime_settings(db)` e `get_record(db)`; copiar valores escalares imutáveis; fechar sessão ao sair do bloco; validar transporte; invocar `litellm.acompletion`. Nenhuma sessão/transação de DB permanece aberta durante o I/O de rede.
- Desativação de retry: `num_retries=0` **e** `max_retries=0` explícitos nos kwargs de `acompletion`. LiteLLM 1.104.0 honra ambos no caminho OpenAI auditado; uma invocação do callable produz exatamente 1 requisição HTTP, sem retry interno ou fallback de modelo. Evidência OpenAI com resposta fake 503 (1 request) NÃO generaliza para todos providers/configurações globais.
- Matriz de classificação — conversão para `LLMAttemptError` (mensagem segura fixa `Geração de briefing indisponível`, sem causa bruta observável) por classe/tipo concreto, não por substring de mensagem ou número contido no texto de `RuntimeError`/`TypeError` arbitrário:
  - LiteLLM (`litellm.exceptions` conforme 1.104.0, onde exporta `Timeout`): `APIConnectionError`, `Timeout`, `InternalServerError` (HTTP 500), `RateLimitError` (HTTP 429), `ServiceUnavailableError` (HTTP 503), e `APIError` quando reconhece status 429/500/502/503/504 por atributo `status_code`/`response.status_code`.
  - Transporte (`httpx` 0.28.1): `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `HTTPStatusError` com status reconhecido 429/500/502/503/504.
  - Builtin `TimeoutError`/`asyncio.TimeoutError` levantado pelo SDK/transporte dentro do binding durante a chamada = falha externa elegível.
  - Delimitação: `TimeoutError` arbitrário levantado por outro callable injetado no serviço (fora do binding) propaga como exceção desconhecida conforme roadmap (sem retry/FAILED genérico); deadline `asyncio.timeout` expirado no serviço consome a tentativa no loop, conforme fronteira do serviço.
- Propagação com identidade, sem retry nem conversão em `LLMAttemptError`: `AuthenticationError`/401/403, `PermissionDeniedError`, `ProviderConfigurationError`, chave/modelo ausentes, `BadRequestError` e erros de programação desconhecidos (`RuntimeError`, `TypeError`, bugs internos). É proibido converter `RuntimeError`/`TypeError` arbitrário apenas por conter palavras como "timeout"/"quota" ou números como 429/503 no texto; desconhecidos do callable continuam sob o contrato padrão do roadmap.
- Símbolos: implementação e testes consultam somente leitura `app/briefing/llm_binding.py` e `tests/test_briefing_llm_binding.py`; `_classify_error` e `complete` legados em `app/services/llm.py` não são alterados por este delta.
- Segurança de exceção: `args`, causa observável e traceback formatado não contêm segredos/tokens/sentinelas; `from None` suprime contexto de exibição (`__suppress_context__=True`) mas não se alega ausência de `__context__` apenas por isso. Exceções elegíveis usam mensagem fixa sem causa crua observável.
- Prova com transporte mock: `acompletion` real sobre transporte fake, falha injetada, contagem de requests (1), verificação de ausência de fallback/retry; teste de causa/campos da exceção contra sentinelas. Não é prova multi-provider.
