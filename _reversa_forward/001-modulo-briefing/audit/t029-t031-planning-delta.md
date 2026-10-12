# T029–T031 — delta de planejamento do binding LiteLLM

**Estado:** delta documental consolidado após cross-check; auditor decide PASS. Escopo exclusivo: contrato do binding interno, D3/D5 e detalhe de boundary na interface HTTP canônica. Não altera arquitetura do módulo, endpoints, helper legado ou decisões já aprovadas fora dos conflitos descritos.

## Resolução do cross-check

| ID | Resultado documental | Contrato consolidado |
|---|---|---|
| A001 HIGH | Resolvido documentalmente; auditor decide PASS | Factory `make_scout_complete(session_factory, default_timeout_s=30.0)` e callable `scout_complete(system, user, timeout_s=None)` preservam keywords/defaults T028; default validado na factory; override validado antes de sessão/settings/transport/LLM; int/float não-bool, positivo finito; extremos com `OverflowError` viram `ValueError` fixo; `None` usa default; valores >30s aceitos, sem teto novo. |
| A002 MEDIUM | Resolvido documentalmente; auditor decide PASS | Matriz concreta LiteLLM/httpx/builtin reconhecidas; 429/500/502/503/504 e timeout do provider elegíveis; auth/config/programação e desconhecidos propagam por identidade. Sem classificar `RuntimeError`/`TypeError` arbitrário por palavras/números na mensagem. Fronteiras de timeout e segurança de exceção explícitas. |
| A003 LOW | Nota retarget histórica preservada; sem finding ativo | Actions já aponta `interfaces/briefing-http.md`; nota histórica abaixo registra retarget concluído pelo parent. |

A resolução é documental, não fecha actions nem prova runtime.

## Contratos técnicos consolidados

### F-CONTRACT-01 — T029

Uma chamada de `make_scout_complete` resulta em exatamente uma tentativa HTTP pelo SDK. Passar explicitamente `num_retries=0` **e** `max_retries=0` nos kwargs de `litellm.acompletion`; são controles distintos e nenhum isoladamente demonstra que o outro está desabilitado. Evidência em LiteLLM 1.104.0 no caminho OpenAI fake 503 com 1 request comprova o caminho do SDK verificado, mas NÃO prova todos providers nem configurações globais. Testar `acompletion` real com transporte fake sem rede, provocando falha e contando requests (1); verificar ausência de repetição/fallback. Preservar seleções runtime de role (`scout`) e provider/modelo sem fixar modelo histórico.

### F-ERROR-01 — T030

Definir matriz concreta por tipo de classes elegíveis para `LLMAttemptError` (mensagem segura fixa `Geração de briefing indisponível`, sem payload bruto, argumentos da causa ou causa observável expostos):
- LiteLLM (`litellm.exceptions` conforme 1.104.0, onde exporta `Timeout`): `APIConnectionError`, `Timeout`, `InternalServerError` (500), `RateLimitError` (429), `ServiceUnavailableError` (503), e `APIError` quando status numérico reconhecido é 429, 500, 502, 503 ou 504.
- Transporte (`httpx` 0.28.1): `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, e `HTTPStatusError` quando status numérico reconhecido é 429, 500, 502, 503 ou 504.
- Builtin `TimeoutError`/`asyncio.TimeoutError` levantado pelo SDK ou transporte dentro do binding durante a chamada é falha externa de LLM elegível para conversão em `LLMAttemptError`.
- Delimitação estrita de fronteiras: builtin `TimeoutError` arbitrário levantado por outro callable injetado no serviço (fora da fronteira do binding) é tratado como exceção desconhecida e propaga sem retry ou fail genérico, conforme roadmap; deadline `asyncio.timeout` expirado na camada de serviço consome a tentativa no loop de geração.
- Propagação estrita por identidade sem conversão para `LLMAttemptError`: erros de autenticação (`AuthenticationError`, 401, 403), configuração (`ProviderConfigurationError`, chaves ausentes, modelos ausentes), e erros de programação desconhecidos (`RuntimeError`, `TypeError`, bugs internos).
- Proibição explícita: É expressamente proibido converter `RuntimeError` ou `TypeError` arbitrário em `LLMAttemptError` apenas por conter no texto palavras como "timeout", "quota" ou números como 429 ou 503. Exceções desconhecidas do callable continuam o contrato padrão do roadmap (propagam com identidade).
- Segurança de exceção: `args`, mensagem, causa observável e traceback formatado não contêm sentinelas/chaves/segredos. O uso de `from None` suprime o contexto na exibição padrão (`__suppress_context__=True`), mas não se deve afirmar ausência física do atributo `__context__` apenas por causa de `from None`. O teste de segurança verifica campos visíveis, mensagem e formatação de traceback.

### F-CONSISTENCY-01 — T031

Substituir D5 antigo por assinatura canônica preservando compatibilidade com T028 e callers:
- `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s: float = 30.0) -> Callable[..., Awaitable[str]]`, gerando `scout_complete(system: str, user: str, timeout_s: float | None = None) -> str`.
- Única alteração deliberada é o ownership do banco passar para a factory; keywords e defaults de T028 permanecem preservados; sessão caller-owned não é aceita.
- `default_timeout_s` é validado na fábrica; `timeout_s` por chamada é validado rigorosamente antes de abrir sessão, carregar settings, validar transporte ou chamar LLM (abort precoce com zero chamadas de fronteira). Ambos aceitam int/float positivos finitos (não-bool), tratam overflow extremo convertendo `OverflowError` em `ValueError` fixo com a mensagem esperada, e aceitam valores finitos > 30.0s (None significa usar default; sem impor teto de 30s).
- Sessão de DB: a invocação abre sessão própria curta via `session_factory()`, lê `runtime_settings(db)` e `get_record(db)`, copia os valores escalares imutáveis e fecha a sessão em `async with` antes de validar transporte ou chamar `litellm.acompletion`. Nenhuma sessão ou transação de banco permanece aberta durante o I/O de rede. Não chamar `commit()` nem `rollback()` em sessão do chamador.
- D3 e primeira leitura: se `get_record(db)` materializar `AppSettings` via flush sem commit, o fechamento da sessão isolada reverte a inserção sem persistência silenciosa de defaults. Os valores lidos servem à chamada atual. A verificação futura com SQLite real e helpers reais confirmará que nenhuma linha espúria é persistida.

## Matriz mínima de verificação antes do coding

| ID / etapa | Critério RED (prova que falha antes da implementação/correção) | Critério GREEN (prova que passa; gate continua aberto até executar) |
|---|---|---|
| T029 — retries SDK | Transporte fake devolve 503; usar `litellm.acompletion` real e contar requests. Falha se kwargs não contêm ambos os zeros ou request count >1. | `num_retries=0`, `max_retries=0`; exatamente 1 HTTP request, sem retry/fallback. Evidência LiteLLM 1.104.0 / OpenAI fake 503 vale somente para caminho verificado, não todos providers/configurações globais. |
| T030 — erros reconhecidos | Injetar um a um: LiteLLM `APIConnectionError`, `Timeout`, `InternalServerError`, `RateLimitError`, `ServiceUnavailableError`, `APIError` statuses 429/500/502/503/504; httpx connect/connect-timeout/read/write/pool e `HTTPStatusError` statuses 429/500/502/503/504; builtin `TimeoutError` levantado dentro do binding. Falha se caso reconhecido propagar cru ou se classe/status não elegível for convertido. | Cada elegível vira exatamente `LLMAttemptError` com mensagem fixa. `args`, causa observável e traceback formatado não contêm sentinelas/segredos/tokens; não inferir ausência de `__context__` por `from None`. Casos com request fake mantêm count 1. |
| T030 — propagação / fronteiras | Injetar auth 401/403, `ProviderConfigurationError`, ausência de chave/modelo, `BadRequestError`, status não reconhecido, `RuntimeError` e `TypeError` arbitrários contendo `timeout`, `quota`, `429`, `503`; injetar também `TimeoutError` de callable arbitrário no serviço e deadline controlado. | Auth/config/programação e callable desconhecido propagam o mesmo objeto, sem retry ou fail genérico; palavras/números não alteram classe. `TimeoutError` arbitrário do callable propaga; somente builtin `TimeoutError` dentro do binding é externo elegível; `asyncio.timeout.expired()` do serviço consome tentativa. |
| T031 — assinatura e timeout | Testar assinatura por keywords/defaults de T028; factory inválida em RED; para override inválido usar spies em factory/settings/record/transport/LLM e exigir zero chamadas. | Assinatura canônica; default validado na factory. Override `None` usa default; int/float positivos finitos não-bool, inclusive >30s, aceitos e repassados. Bool/string/NaN/±inf/zero/negativo e extremos com `OverflowError` geram `ValueError` fixo antes de abrir sessão ou qualquer I/O. Nenhum teto novo de 30s. |
| T031 — ownership e primeira leitura | SQLite real + helpers reais; transporte observa estado da sessão/transação; sem commit/rollback no chamador. `get_record` cria `AppSettings` via flush sem commit. | Sessão própria fecha antes do transporte; não há DB transaction durante rede; caller-owned não finalizada. Valores/defaults da primeira leitura atendem chamada corrente; close reverte criação transitória e deixa zero linha persistida silenciosamente. Gate é futuro, não afirmação de execução presente. |

## Arquivos documentais e retarget

- D3/D5 atualizados em `audit/t011-integration-decomposition.md`.
- Detalhes registrados em `interfaces/briefing-http.md`.
- Nota histórica de retarget: `actions.md` já aponta para `interfaces/briefing-http.md` canônico corrigido pelo parent.
- Nenhum arquivo de produção ou teste alterado até a aprovação da auditoria.
