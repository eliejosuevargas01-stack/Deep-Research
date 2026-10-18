# Roadmap — 001-modulo-briefing

> **Aviso de vigência documental:** Este Roadmap registra o plano técnico e arquitetural da Feature 001 (Módulo de Briefing). Conforme os requisitos vigentes da Feature 002 (`_reversa_forward/002-investigacao-personas/requirements.md:134-137,231`), fluxos sucessores foram ajustados: reabertura de aprovado retorna HTTP 409 e edição direta de lista foi substituída por revisão única via `PATCH /briefings/{research_id}` com `note`. A extinção de `/approve` de C8 permanece planejada e não implementada. Os contratos históricos e registros de planejamento são preservados com notas de vigência.

## Resumo da abordagem

Feature greenfield em `_reversa_forward/001-modulo-briefing`; especificações reversas foram descartadas e não são fonte de requisitos (requirements.md, linhas 12–21). Implementar somente backend de briefing: receber tema validado (3–300 chars), criar registro persistido, obter SERP com tool Jina, gerar 3–7 pontos de foco, visando habitualmente 5, via instrução carregada de arquivo em `prompts/`, permitir edição, aprovação e reabertura. Não executar investigação posterior nem produzir relatório.

## Princípios aplicados

- Privacidade e isolamento de prompts: segredos, conteúdo integral do prompt e raciocínio bruto não podem aparecer em respostas/logs públicos; tema e SERP são dados não confiáveis. Princípio legado `.reversa/principles.md` §II é tecnicamente compatível, mas princípios antigos não são fonte de requisitos sem confirmação do escopo atual. Aplicação registrada como recomendação de segurança, não como requisito novo.
- Rastreabilidade: registrar tema, resultados SERP, versão/identificador do prompt, edições e aprovação, em conformidade com NFR de rastreabilidade (requirements.md §6, tabela NFR, linha de Rastreabilidade), cuja confiança é inferida.
- Conflito explícito: princípio antigo de degradação graciosa/fallback para provedores alternativos (`.reversa/principles.md`:23–26) conflita com tool exclusiva SERP Jina (requirements.md:34, 52). Prevalece requisito atual: sem fallback de busca.
- Conflito de comportamento: legado permite Reader, ferramentas adicionais e fluxo de investigação (`app/tools/search_pipeline.py:63–184, 198–230`; `app/routers/research.py:135–167, 287–319`), mas requisito atual proíbe Reader/extração e pesquisa automática. Não reaproveitar esse fluxo como regra.

## Decisões técnicas

| Decisão | Proposta | Confiança |
|---|---|---|
| Fronteira | Criar módulo de domínio briefing separado dos serviços existentes; evitar acoplamento a fluxo de investigação | 🟢 escopo confirmado; estrutura proposta |
| Persistência | Entidade e ciclo próprios para briefing, sem `Research`/`ResearchPoint`/`ResearchStatus`; infraestrutura compartilhada DB/auth pode ser reutilizada | 🟢 decisão T015; entidade pura em T007; modelo DB/storage/migration permanecem em T011 |
| SERP | Adapter único que invoca `https://s.jina.ai/`; no máximo uma chamada em andamento; até 4 tentativas sequenciais por operação que falhar; sucesso encerra tentativas | 🟢 política de requisitos; Google exclusivo dispensado pelo usuário em 2026-10-11; parser tolerante e timeout 30s configurável |
| Retentativa LLM | Aplicação técnica de RF-10: até 4 tentativas totais, reutilizando SERP (classificação de erro e timeout no adendo T029–T031 abaixo) | 🟢 RF-10; concretização técnica, não decisão nova de produto |

`LLMAttemptError` vive em `app/briefing/service.py` com mensagem segura fixa. No serviço, somente `LLMAttemptError`, timeout por tentativa via `asyncio.timeout(llm_timeout_s)` configurado (finito positivo, default 30s), retorno não-string e parse/shape/count inválidos consomem tentativa; sem deadline global extra sobre operação/retries/Tx2 além desses timeouts por tentativa. O binding T029–T031 converte somente falhas externas reconhecidas pela matriz concreta LiteLLM/httpx/builtin descrita no adendo D5 e em `audit/t029-t031-planning-delta.md`: conexão e status 429/500/502/503/504 conhecidos, e timeout levantado dentro do SDK/transporte. Não classificar por substring/número no texto: `RuntimeError`/`TypeError` arbitrário (inclusive contendo `timeout`, `quota`, `429`, `503`) e erros desconhecidos propagam com identidade sem retry/FAILED; auth/config também propagam. Builtin `TimeoutError` arbitrário de callable injetado ao serviço propaga; builtin `TimeoutError` originado dentro do binding é falha externa; deadline `asyncio.timeout.expired()` do serviço consome tentativa. `CancelledError` propaga. `InvalidContent` levantado pelo callable é bug e propaga; `InvalidContent` da validação de saída parseada conta como saída inválida. Parser usa `json.loads`, exige lista de objetos com `title` e `description`, aceita JSON puro ou uma cerca `json` exata opcional, sem extração de fragmentos; mensagens de shape/count são fixas e seguras. Antes de prompt/SERP/LLM, validar `llm_attempts` (`int` não-`bool` 1..4) e `llm_timeout_s` (`int`/`float` não-`bool`, finito, maior que zero); inválido gera `ValueError` sem I/O. `sem conclusão` (RN-03) orienta instrução de saída, sem julgador semântico ou retry extra.
| Saída | Validar atomicamente 3–7 pontos com título/descrição na geração, edição salva e aprovação; instruir agente a visar 5 pontos e adaptar quando necessário | 🟢 requirements.md:36, 53 |
| Prompt | Carregar arquivo em pasta de prompts a cada geração; validar no serviço que o retorno do loader injetado é string não-vazia após strip, falhando com erro seguro antes de SERP/LLM em ausência, vazio, whitespace ou tipo inválido; sem texto equivalente embutido na lógica | 🟢 requirements.md:38, 114–116; A004 |
| Estado | máquina mínima `generating → draft → approved`, falha persistida sem briefing válido; reabertura `approved → draft` sem condição não aprovada | 🟢 *(Nota de vigência: Reabertura approved → draft supersedida por Feature 002:135,231 com bloqueio HTTP 409)* |
| API | Contratos HTTP backend para criar/consultar/editar/aprovar/reabrir; autenticação existente pode ser reutilizada após revisão de fronteira | 🟢 *(implementado em `app/briefing/router.py:141-345`)* |

## Delta arquitetural

Criar módulo `app/briefing/` (proposta) com domínio, schema/validação, orquestração de geração, adapter SERP Jina e carregador de prompt apontando para arquivo versionado em pasta de prompts. Integrar router FastAPI e sessão DB existentes sem invocar `schedule()`/`run_research()`.

Contexto existente verificado: `app/routers/research.py:135–167` cria `Research` e agenda scout; `app/services/research.py` contém lógica de pipeline; `app/tools/search_pipeline.py:137–184` mistura SerpAPI, Apify, Jina e fallback DuckDuckGo, e `:198–230` lê páginas; `app/prompts/scout.md` existe, mas instrui leitura e cerca de cinco pontos; `app/models/domain_models.py:31–57` combina Research e ResearchPoint; `app/schemas/__init__.py:13–67` aplica tema até 500 e exatamente cinco pontos. Não reutilizar comportamento incompatível sem isolamento e validação.

## Delta de dados

Ver `data-delta.md`. Proposta: entidade briefing com UUID, tema, estado, pontos JSON estruturados, resultados SERP mínimos necessários, identificador/hash de prompt, versão de conteúdo, falha segura, timestamps e metadados de aprovação/reabertura. Decisão final de tabela normalizada versus JSON deve manter histórico de edições consultável e integridade transacional.

## Delta de contratos

Ver `interfaces/briefing-http.md`. Contrato proposto para operações autenticadas de criar/obter/editar/aprovar/reabrir e consultar briefing aprovado. Rotas definitivas e esquema de autenticação requerem alinhamento com convenções do projeto; nenhum frontend incluído.

## Plano de migração

1. Delimitar módulo, estados e contratos; validar integração DB/HTTP existente.
2. Implementar esquema e persistência/migração sem alterar fluxo de pesquisa legado.
3. Implementar carregador de prompt e adapter SERP exclusivo; aplicar decisão de 2026-10-11: SERP Jina sem Google exclusivo, parser `title`/`url`/`description` com extras ignorados, timeout de cliente 30s configurável; verificar contrato em testes isolados.
4. Implementar geração com validação, persistência segura e retentativas independentes; preservar resultado SERP após erro LLM.
5. Integrar ciclo de edição, aprovação, leitura para consumidor futuro e reabertura, sem disparar investigação.
6. Verificar critérios funcionais e de segurança com dependências externas substituíveis; QA/auditoria em ações separadas.

## Risco e bloqueio de investigação

**Atualização, 2026-10-11:** usuário resolveu escolhas pendentes: aceita SERP Jina sem garantia de motor Google exclusivo, parser tolerante com três campos obrigatórios e timeout de cliente Jina/LLM 30s configurável por tentativa. Não houve chamada real. Investigação e limitação da evidência anteriores são preservadas abaixo como histórico.

**Bloqueio anterior (histórico):** documentação oficial Jina consultada (`https://docs.jina.ai/api/`, seção “5. Search API”; resultado oficial `https://api.jina.ai/docs`) descreve endpoint `https://s.jina.ai/`, método POST e saída configurável Markdown/HTML/JSON/texto/imagem, mas não comprova que resultados sejam especificamente do Google. A documentação diferencia `s.jina.ai` como search/SERP de `r.jina.ai` como Reader; não permite afirmar resposta exclusivamente composta por snippets. Portanto, não prometer backend Google nem pressupor snippets-only.

Ação específica antes da implementação da integração: obter confirmação documental oficial ou evidência verificável do endpoint Jina para mecanismo Google e estrutura/campos retornados; guardar fixture redigida e mapear parser sem chamar serviço pago nesta etapa. Se contrato não puder ser comprovado, solicitar decisão ao usuário sobre aceitabilidade do mecanismo Jina efetivamente documentado. Não trocar por API paralela nem Reader.

Riscos adicionais: edição manual deve preservar 3–7 pontos e versões consultáveis; não impor faixa diferente da aprovada; reabertura permanece permitida independentemente do avanço de outras etapas, pois restrição não foi aprovada; schema legado de cinco pontos e estados acoplados a pesquisa exigem isolamento. Reabertura e edição não podem iniciar execução de pesquisa. *(Nota de vigência: Reabertura de aprovado e edição manual direta de lista foram formalmente supersedidas na Feature 002:134-137, 231; extinção de /approve é futura em C8.)*

## Critério de pronto

RF-01–RF-10 atendidos; tema inválido bloqueado antes de chamadas externas; uma tool SERP Jina e sem Reader/outras tools; busca apenas repetida após falha, sequencial, máximo quatro tentativas totais por operação; sucesso SERP reutilizado se LLM falhar; prompt lido do arquivo em tempo de execução; rascunho válido com 3–7 pontos de foco e alvo habitual de 5; edição persistida e consultável mantendo 3–7; aprovação exige 3–7; aprovação recusa edição até reabrir; reabertura devolve a rascunho; acesso aprovado disponível sem iniciar pesquisa; erros seguros sem segredos; nenhum relatório/pesquisa executada. Bloqueio de Google/Jina resolvido com evidência ou decisão explícita antes de declarar critério Google atendido.

## Adendo T004/T005/T007 — contrato técnico local, 2026-10-11

Recorte mínimo consumível por T010/T011. Domínio puro stdlib em `app/briefing/domain.py`, sem DB/HTTP/rede/I-O; reutiliza `validate_theme`, `validate_points`, `assert_can_edit`, `transition`, `BriefingStatus`, `InvalidContent`, `InvalidTransition`. Entidade `Briefing` isolada de `Research`/`ResearchPoint`/`ResearchStatus`. Nenhuma operação dispara busca/agente/pesquisa. Sem endpoint regenerar, sem limite 1–10, sem investigação, sem trimming obrigatório de pontos além de não-vazio.

Símbolos propostos: `new_briefing(theme)`, `complete_briefing(briefing, points)`, `fail_briefing(briefing, error)`, `edit_briefing(briefing, points)`, `approve_briefing(briefing, approved_at)`, `reopen_briefing(briefing)`, `read_approved(briefing)`; dataclasses congeladas `Briefing`/`BriefingPoint` com `id` estável, `version` desde 1, `approved_at`, `error`; snapshot ou nova instância imutável. Detalhe em `data-delta.md`, seção "Contrato local puro T004/T005/T007".

| Critério | Símbolos | Teste executável proposto | Gate |
|---|---|---|---|
| Tema 3–300, strip, rejeição antes de I/O | `new_briefing` + `validate_theme` | fronteiras 2/3/300/301, strip, tipos inválidos → `InvalidContent`; teste puro não prova ordem de I/O do serviço | Local T004; spy no serviço real substituído por fake pertence a T010 |
| Count 3–7 geração/edição/aprovação | `complete_briefing`, `edit_briefing`, `approve_briefing` | 2/3/7/8 itens; 5 aceito como alvo, não limite | Local T005/T007 |
| Content title/description não vazios | `validate_points` | whitespace/ausente/tipo inválido rejeitado; sem trim obrigatório | Local T005/T007 |
| State generating/draft/failed/approved | `transition`, `assert_can_edit` + operações | gerar→draft/failed; draft→approved; approved→draft; failed terminal; só draft editável | Local T007 |
| Atomic snapshot | operações acima | edição/transição inválida preserva snapshot anterior | Local T005/T007 |
| Identity/version | `Briefing.id`/`version` | mesmo UUID; versão +1 por operação aceita, recusada não incrementa | Local T007 |
| Isolation | cópia/tupla/congelado | mutar entrada/snapshot não contamina anterior | Local T005/T007 |
| Read-approved | `read_approved` | approved retorna snapshot isolado; demais estados → `InvalidTransition` | Local T005/T007; consulta durável fica T011 |

T004 gate local = schema + `new_briefing`/`validate_theme`, sem spy de chamada externa em função pura. Prova integrada de rejeição antes de SERP/LLM pertence ao serviço real T010, com dependências substituídas; ação permanece aberta até esse gate. T005 gate local parcial; ação permanece aberta até integração durável "versão salva consultável" em T011. T007 gate domínio puro, sem afirmar DB. Storage durável/histórico/concorrência/idempotência ficam T011, não decididos aqui.

## Adendo T006/T010 — geração isolada e orquestração, 2026-10-11

Recorte mínimo consumível por T006 (testes) e T010 (serviço). Orquestração em `app/briefing/service.py` compondo peças entregues: `domain.py` (T007), `prompt_loader.py` (T008), `serp_client.py` (T009/T016), num único registro `Briefing` em memória. Sem DB, rotas HTTP, auth, migrations, rede real ou binding LLM real nesta dupla de ações.

### Fronteira e assinatura proposta

```python
async def generate_briefing(
    theme: str,
    *,
    serp_client,                         # obrigatório: JinaSerpClient ou fake com search(theme)
    llm_complete,                        # obrigatório: callable one-attempt async(system, user) -> str
    prompt_loader=load_briefing_prompt,   # default real entregue em T008; callable síncrono () -> str
    llm_attempts: int = 4,               # int não-bool 1..4 (teto TOTAL da geração: inicial + 3 retentativas)
    llm_timeout_s: float = 30.0,         # float/int não-bool finito positivo (timeout por tentativa)
) -> Briefing
```

- Sem default para `serp_client`/`llm_complete`: binding real e configuração de chave/modelo não aprovados; default inexistente esconderia I/O de rede. `prompt_loader` tem default real (T008).
- Validação na fronteira antes de qualquer I/O: `llm_attempts` fora de 1..4 ou `llm_timeout_s` não finito/positivo → `ValueError` (espelha T009/T016).
- Retorno: `Briefing` final (`DRAFT` ou `FAILED`), mesmo `id` do `new_briefing` inicial (RF-10, mesmo registro). Tema inválido lança `InvalidContent` sem registro criado.
- Sem clock, sem timestamps, sem metadados de execução novos: nenhum consumidor definido; `version` continua saindo só das operações de domínio.

### Contrato isolado de LLM (one-attempt)

```python
async def llm_complete(system: str, user: str) -> str
```

- Uma tentativa, assíncrona, sem retry/fallback/backoff internos. Timeout por tentativa é imposto pelo SERVIÇO via `asyncio.timeout(llm_timeout_s)` envolvendo a chamada; o binding não implementa relógio.
- Entrada mínima: `system` = instrução lida do arquivo de prompt; `user` = JSON estruturado contendo `{"tema": <str>, "resultados_serp": [...], "formato_saida": "Retorne exclusivamente uma lista JSON válida de objetos com 'title' e 'description', sem texto adicional."}` — instrução de saída explícita orienta o modelo a produzir o formato exigido pelo parser (A003), preservando a instrução de sistema do arquivo.
- Saída esperada: texto com lista JSON de pontos `[{"title": ..., "description": ...}, ...]`. Parse e validação ficam no serviço: extração opcional de cerca ```json, `json.loads` stdlib, lista exigida; `complete_briefing` valida 3–7 e título/descrição. Parse stdlib local em vez de `app.services.llm.parse_json` (módulo acoplado ao stack de providers/litellm): 🟢 proposta, mantém `app/briefing/` sem dependência de provider.
- Exceção própria `LLMAttemptError` definida em `app/briefing/service.py` (mensagem segura fixa, sem payload bruto) para falha externa de chamada do binding. Cada falha (`LLMAttemptError`, timeout imposto na fronteira, retorno não-string, parse/shape/count inválidos com mensagem segura fixa) consome 1 das 4 tentativas totais (A002). Erros de configuração/programação e exceções desconhecidas propagam imediatamente sem retentativa.
- `asyncio.CancelledError` propaga imediatamente: sem retentativa, sem `fail_briefing` (cancelamento não é falha externa).
- Captura limitada: só `LLMAttemptError`, `TimeoutError` imposto pela fronteira `asyncio.timeout` do serviço, e `InvalidContent`/erro de parse conhecidos levantados pelo próprio serviço ao validar a saída parseada. `InvalidContent` vindo de DENTRO do callable é bug/exceção desconhecida e propaga sem retry. Exceções desconhecidas do callable, bug do serviço e erros de configuração propagam sem virar FAILED/retry genérico. `PromptUnavailable`/`SerpSearchError` tratadas separadamente conforme ordem acima.
- PROIBIDO empilhar `app.services.llm.complete(role, system, user, db)` sob o loop de 4: o legado já carrega timeout=180, 5 tentativas internas, fallback de router e fallback gemini (`app/services/llm.py:255–369`); a composição multiplicaria tentativas (~20 por geração) e violaria RF-10 (teto de 4 totais).

### Ordem rigorosa de I/O e gates

1. `new_briefing(theme)` primeiro: tema inválido lança `InvalidContent` com ZERO chamadas a prompt/SERP/LLM — gate integrado pendente de T004, provado com fakes/spies em T006.
2. `prompt_loader()`: callable síncrono `() -> str`. Retorno não-string, vazio ou whitespace, bem como `PromptUnavailable`, é tratado como falha de configuração de prompt e leva o registro a `FAILED` via `fail_briefing` antes de qualquer SERP ou LLM (A004). String válida é preservada integralmente como system.
3. `serp_client.search(briefing.theme)` UMA vez por geração; as 4 tentativas da busca pertencem ao cliente (T009, internas). Serviço nunca re-chama `search` depois — sem retry duplo. `SerpSearchError` → `fail_briefing` seguro → `FAILED`; LLM jamais chamado.
4. Loop LLM 1..`llm_attempts` sequencial: sucesso → `complete_briefing(briefing, pontos)` → `DRAFT`. Falha → próxima tentativa REUTILIZANDO a mesma lista SERP em memória, sem nova busca. Esgotadas as 4 → `fail_briefing` seguro → `FAILED`, sem corpo bruto, credenciais ou conteúdo de prompt no erro.
5. Erros seguros fixos por modo de falha (prompt indisponível / busca indisponível / geração indisponível); nada dinâmico do provedor vaza (RF-08, NFR segurança).

### Concorrência e limites

Chamadas estritamente sequenciais dentro de cada invocação (awaits encadeados, sem `gather`); isso não impede sobreposição entre LLM de chamadas concorrentes. `JinaSerpClient` serializa somente suas próprias requisições de busca por instância via lock local (T009): invocações que compartilham a mesma instância serializam busca, mas não o restante do fluxo nem chamadas que usam instâncias distintas. Nenhum lock de serviço/global/cross-process é prometido ou introduzido nesta etapa (A005). Se for necessária serialização mais ampla, é decisão de T011; testes afirmam apenas as garantias acima.

### Fora de T006/T010 (permanece T011)

Persistência, models SQLAlchemy, migrations Alembic, rotas FastAPI, autenticação, histórico durável consultável, transações de banco, concorrência cross-process e binding LLM real. Serviço verde com fakes prova orquestração, NÃO geração runtime: aceite permanece parcial até o binding real existir e passar por QA/auditoria.

Ação exata que fornecerá o binding LLM real: sub-passo de T011 "ligar `llm_complete` real" — callable one-attempt sobre a infraestrutura de settings existente (`app/services/settings.py:273,289` define `runtime_settings`/`get_record` para resolver modelo/chave por role), reutilizando UMA role já existente em `app/schemas/__init__.py:5` `ROLES` escolhida e nomeada explicitamente na execução de T011 (candidata registrada `scout`; role `briefing` inexistente; não inventar credencial nem nova role implícita), timeout configurado por tentativa (default 30s, finito positivo) repassado ao provider e limitado pela fronteira asyncio.timeout do serviço, sem retries/fallback internos; se `complete` legado não puder ser reduzido a uma tentativa, o binding chama o provider diretamente reutilizando a mesma resolução de chave/modelo. Decisão técnica 🟢 proposta (configuração LLM/auth/storage não aprovadas), origem: infraestrutura existente de settings; limites: nenhuma credencial inventada, nenhuma chamada de rede nesta etapa; assinatura do serviço não muda. Entregáveis verificáveis deste sub-passo: (1) `llm_complete` real ligado em `generate_briefing` nas rotas/persistência de T011; (2) entradas de settings delimitadas no data delta (role/modelo/provider/timeout por tentativa, teto 4 total, sem retry aninhado); (3) gate de QA T012 exercitando o binding real: uma chamada externa ativa por tentativa, teto de 4 sem retry aninhado do provider, timeout acordado, erro seguro sem segredos/payload bruto. T011 não pode ser fechada com fakes no lugar do binding (A001); geração runtime declarada somente após QA/auditoria T012/T013.

### Adendo T029–T031 — contrato vigente do binding (consolidação A001/A002)

- Assinatura: `make_scout_complete(session_factory: async_sessionmaker[AsyncSession], default_timeout_s: float = 30.0) -> Callable[..., Awaitable[str]]`; callable `scout_complete(system: str, user: str, timeout_s: float | None = None)`. Preserva keywords/defaults T028; ownership de sessão isolada é a única mudança deliberada frente ao factory inicial. D5 antigo permanece como `[HISTÓRICO E SUBSTITUÍDO]` e não é prescrição vigente.
- Timeout: `default_timeout_s` validado na factory; override `timeout_s` validado antes de sessão/settings/transport/LLM (falha aborta com zero chamadas de fronteira). Int/float positivos finitos não-bool; overflow extremo vira `ValueError` fixo; `None` usa default; valores finitos >30s aceitos e repassados; nenhum teto novo.
- Runtime: role fixa `scout`; `runtime_settings(db)`/`get_record(db)`/`_provider(model)`/chave por provider mantém erros de configuração; preserva escolhas runtime sem fixar modelo histórico. `_classify_error` e `complete` legados não são alterados.
- Retries: `num_retries=0` **e** `max_retries=0` explícitos em cada chamada `acompletion`; uma invocação gera exatamente 1 request. LiteLLM 1.104.0/OpenAI fake 503 com 1 request é evidência do caminho verificado, não prova de todos providers/configurações globais.
- Classificação: conversão para `LLMAttemptError` somente para classes/estados concretos reconhecidos (LiteLLM + httpx + builtin `TimeoutError` interno do binding), conforme matriz em `audit/t029-t031-planning-delta.md` e D5 vigente. Proibição de conversão por palavra/número no texto; auth/config/programação e desconhecidos propagam com identidade. Builtin `TimeoutError` do SDK no binding é externo elegível; arbitrário de callable injetado no serviço propaga; deadline `asyncio.timeout.expired()` do serviço consome tentativa.
- Segurança: args, causa observável e traceback formatado sem sentinelas/segredos; não inferir ausência de `__context__` por `from None`.
- D3: sessão própria curta em `runtime_settings`/`get_record`, copia escalares, fecha antes de LLM; sem `commit`/`rollback` de sessão do chamador; primeira leitura com flush é revertida ao fechar, sem persistência silenciosa de defaults. Teste futuro SQLite real ainda não executado agora.

### Matriz de testes T006 (tests/test_briefing_generation.py)

Fakes: SERP (grava chamadas; lista canned ou `SerpSearchError(4)`), prompt_loader (str ou `PromptUnavailable`), LLM (script por tentativa: texto válido / texto inválido / exceção / `CancelledError` / sleep para timeout).

| # | Cenário | Expectativa | Gate |
|---|---|---|---|
| a | Happy path tema→SERP→LLM | `DRAFT` 3–7 pontos; SERP 1 chamada; LLM 1 chamada; mesmo `id`; `version` incrementada; fake registra payload e teste asserciona `user` contendo `formato_saida` com instrução de lista JSON e `system` idêntico ao retorno do loader (A003) | T006 local |
| b | Tema inválido (2/301/strip vazio) | `InvalidContent`; zero chamadas em SERP/prompt/LLM (spies) | Gate integrado T004 |
| c | SERP falha (4 tentativas internas) | LLM nunca chamado; `FAILED`; erro seguro; mesmo `id` | T006 local |
| d | LLM falha 2, acerta na 3ª | SERP exatamente 1 chamada total; LLM 3 chamadas; `DRAFT` final | T006 local (RF-10 reuso) |
| e | LLM falha 4/4 | SERP 1; LLM exatamente 4; `FAILED`; sem corpo bruto/segredo | T006 local |
| f | Prompt ausente/vazio/inválido (`PromptUnavailable`, `""`, whitespace, não-string) | `FAILED` antes de SERP/LLM; zero chamadas externas; string válida preservada como `system` | T006 local (RF-04; A004) |
| g | Parse inválido / 2 ou 8 pontos | conta como tentativa fracassada; retentativa reusa SERP; exaustão → `FAILED` | T006 local |
| h | `CancelledError` do LLM | propaga; LLM chamado exatamente 1 vez; sem retentativa | T006 local |
| i | Timeout por tentativa | `llm_timeout_s` curto + LLM lento → tentativa fracassada, conta no teto | T006 local |
| j | Config inválida (`llm_attempts` True/1.5/0/5/str, `llm_timeout_s` True/str/None/NaN/inf/0/-1) | `ValueError` antes de qualquer loader/SERP/LLM (spies zero) | T006 local (A002) |
| k | Retorno não-string (`None`, dict) | saída externa inválida por checagem explícita: consome tentativa; esgotamento → `FAILED`; sem `except TypeError` genérico | T006 local (A002) |
| l | Exceção desconhecida (`RuntimeError`) do callable | propaga imediatamente sem retry e sem `fail_briefing`; LLM chamado 1 vez | T006 local (A002) |
| m | JSON com cerca ```json / pontos 3/4/6/7 aceitos; 2/8 recusados | parser aceita cerca única opcional ou JSON puro, exige lista integral; recusa conta tentativa | T006 local (A003) |

Gates locais vs integrados: T006 verde com fakes = gate local de geração; T010 verde = gate de orquestração no mesmo registro; ambos permanecem `[ ]` até execução real. O gate integrado de T004 (rejeição antes de I/O no serviço real) só fecha T004 após execução real dos testes com spies + auditoria/QA posteriores (T012/T013) — planejamento por si só não fecha gate.

## Adendo T025/T026 — delta HTTP consumível, 2026-10-11

Adendo validado e **implementado em código** com suíte de testes (183 testes verdes, `audit/t012-t036-execution.md:58`). A prescrição HTTP canônica `/briefings` (D1, D3, D4) está entregue em `app/briefing/router.py` e integrada em `app/main.py` (`include_router(briefing_router)`), com schemas D4 (`BriefingResponse` incluindo `version/error/approved_at`, `BriefingVersionResponse`) em `app/briefing/schemas.py` (T035). Detalhe executável em `audit/t025-t026-planning-delta.md`.

Qualificam-se somente estes trechos conflitantes, sem reescrever histórico: `## Decisões técnicas | API` ("contrato público não especificado") passa a remeter ao prefixo canônico `/briefings`, POST síncrono via `orchestrate_persisted_briefing` e matriz de erros do delta; `## Delta de contratos` ("rotas definitivas e esquema de autenticação requerem alinhamento") passa a remeter à prescrição vigente em `interfaces/briefing-http.md` (reuse `require_admin`, CSRF em mutações, rollback somente da transação de leitura auth antes de operação externa; sem leitura de atributos ORM de `Principal` após rollback). Demais decisões, deltas e riscos permanecem vigentes. Timeout Jina/LLM: valor configurado único por tentativa, lido de `settings.SEARCH_TIMEOUT_SECONDS` (default 30s, finito positivo; `app/briefing/router.py:_resolve_briefing_timeout` repassa a Jina, binding e serviço), sem teto novo; HTTP não impõe deadline global extra sobre a operação externa completa — serviço e binding usam o mesmo valor configurado (`llm_timeout_s`/`default_timeout_s`, default 30.0), até 4 tentativas totais por operação com SERP reaproveitado. Histórico de versões: Tx1 persiste somente `BriefingRecord` corrente `generating` v1; append começa em v2 (`save_briefing_transition`); sem insert v1/migration. Configuração LLM: factory `make_scout_complete` valida apenas timeout; settings/modelo/chave resolvidos somente na invocação do callable após Tx1/SERP — `ProviderConfigurationError` não entra em retry, wrapper tenta emergência `FAILED` (best-effort) e repropaga, HTTP 500 genérico fixo; sem preflight pré-Tx1 e sem alterar T031. `ValueError` Jina capturado somente na construção/verificação pré-Tx1. Desconhecidos/cancelamento: sem retry, wrapper tenta emergência após Tx1 e repropaga, default HTTP 500 genérico. Upstream auth traduz por classes concretas (`litellm.exceptions.AuthenticationError`/`PermissionDeniedError`; `APIError.status_code`/`httpx.HTTPStatusError.response.status_code` inteiro não-bool 401/403) a 500 genérico. Body approve/reopen: omitido/`null`/`{}` no-op; `[]`/string/número/bool/extras 422 preservando snapshot+history.

[HISTÓRICO E SUBSTITUÍDO — fase pré-T035; schemas D4 já implementados em `app/briefing/schemas.py` e cobertos por `tests/test_briefing_schemas.py`; prescrição vigente no adendo T025/T026 acima.] Pré-requisito D4 antes do router: `BriefingResponse` atual não tem `version/error/approved_at` e `BriefingVersionResponse` inexiste; ambas exigidas por `audit/t011-integration-decomposition.md:57–77`. Parent deve inserir ação prévia de schemas + `tests/test_briefing_schemas.py` com dependência em T025/T026.
