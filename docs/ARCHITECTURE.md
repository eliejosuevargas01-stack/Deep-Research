# Arquitetura — Deep Research

Documento técnico do pipeline, do modelo de dados e das decisões de engenharia. Complementa o [`README.md`](../README.md) e o contrato HTTP em [`API.md`](API.md).

---

## 1. Visão geral

O sistema é um monólito modular FastAPI com quatro estágios de domínio e um orquestrador opcional:

```
┌──────────────────────────────────────────────────────────────────────┐
│ app/main.py                                                          │
│  lifespan → init_db()   /health   /app/session   SPA + /assets       │
│  include_router(/api/v1) com verify_api_key                          │
└───────────────┬──────────────────────────────────────────────────────┘
                │
   ┌────────────┼─────────────┬──────────────┬──────────────┐
   ▼            ▼             ▼              ▼              ▼
 plan.py     search.py     audit.py      writer.py     pipeline.py
   │            │             │              │              │
 Planner     Searcher      Auditor        Writer      status/sources/SSE
   │            │             │              │
   └────────────┴──────┬──────┴──────────────┘
                       ▼
        ResearchRepository / CredentialsRepository
                       │
             SQLite WAL (5 tabelas)

Integrações externas:
  Jina s.jina.ai  → descoberta (SERP)
  Jina r.jina.ai  → leitura integral em Markdown
  LLM /chat/completions → modelo leve (coleta) e forte (plano, auditoria, redação)
  Webhook HTTPS → entrega assinada do dossiê
```

Cada endpoint também funciona isoladamente: o estado compartilhado é o banco, não a memória do processo. Isso permite chamadas externas em sequência (`plan → search → audit → writer`) sem usar o `PipelineRunner`.

---

## 2. Camadas e responsabilidades

| Módulo | Responsabilidade |
| :--- | :--- |
| `app/main.py` | Aplicação, lifespan, DDL no boot, `/health`, sessão local, entrega da SPA e assets, handlers globais de erro |
| `app/config.py` | `Settings` via Pydantic; sem defaults hardcoded para parâmetros obrigatórios; `.env` ignorado sob pytest |
| `app/api/v1/router.py` | Agrega os seis routers sob `/api/v1` com `verify_api_key` |
| `app/api/v1/endpoints/` | Tradução HTTP ↔ domínio, mapeamento de exceções para status codes, criação de clientes LLM/Jina |
| `app/core/planner.py` | Descoberta de SERP, geração do plano, validação semântica, persistência atômica |
| `app/core/searcher.py` | Protocolo de ações das personas, leitura web, proveniência, seleção de contexto, reserva/finalização atômica |
| `app/core/auditor.py` | Vetor de 12 critérios, decisão determinística, passes de evidência, tarefas de correção |
| `app/core/writer.py` | Prontidão, redação, avaliação do artigo, cache idempotente, publicação e webhook |
| `app/core/pipeline_runner.py` | Execução autônoma, retentativas, status do pipeline, `PipelineEventHub` |
| `app/core/personas.py` | Personas canônicas de busca, papéis internos e snapshot por pesquisa |
| `app/core/temporal.py` | Data de referência, políticas de recência, consultas ancoradas, ranking por frescor |
| `app/core/plan_validator.py` | Validação estrutural determinística do plano e duplicatas literais |
| `app/core/reading_coordinator.py` | Deduplicação in-flight e cache compartilhado de leituras |
| `app/core/security.py` | `X-API-Key`/`Bearer` ou cookie de sessão, com checagem CSRF |
| `app/core/stream_context.py` | Contexto por tarefa que publica deltas no hub SSE |
| `app/db/` | Modelos ORM, engine WAL, migrações aditivas idempotentes, repositórios |
| `app/services/` | Resolução de credenciais, criptografia Fernet, contabilidade de fontes, webhook |
| `app/tools/` | Cliente LLM (streaming, envelopes, custo), cliente Jina, erros tipados |
| `app/ui_session.py` | Elegibilidade de sessão local, token HMAC, cookie e validação de mesma origem |
| `frontend/` | SPA React consumida em origem única; histórico local; SSE |

---

## 3. Fluxo por etapa

### 3.1 Planejamento — `POST /api/v1/plan`

1. Resolve credenciais e parâmetros (banco cifrado → ambiente).
2. Consulta a SERP via `s.jina.ai` **apenas para metadados** (título, URL, descrição, data); o corpo das páginas não é baixado nesta etapa.
3. Chama o modelo forte (`LLM_MODEL_STRONG`, com fallback para o leve) pedindo exatamente `N_PONTOS` eixos estruturados.
4. Valida o contrato com `plan_validator` (tipos estritos, quantidade exata, duplicatas literais) e com uma avaliação semântica via LLM (escopo, público, recência, sobreposição entre eixos).
5. Persiste, em uma única transação, a `pesquisa`, os `pontos` e os envelopes de telemetria em `generation_attempts`.
6. Grava o snapshot de preferências em `pesquisa.metadados_planejamento`: `n_pontos`, `personas`, `recencia`, data de referência.

Contratos de erro relevantes:

- tema ambíguo → `422` com `tipo: ambiguidade_bloqueante` e pergunta de esclarecimento;
- plano fora do contrato → `422` com `tipo: PlanContractError`;
- falha do provedor → `502`; falha Jina → `502`/`504`.

Com `async_execute: true`, a resposta é `202` e o `PipelineRunner` é agendado em `BackgroundTasks`.

### 3.2 Busca — `POST /api/v1/search`

- Personas de busca permitidas: `historiador`, `visionario`, `cetico`, `futurista`. O conjunto efetivo vem de, nesta ordem: payload, snapshot da pesquisa, configuração resolvida.
- Cada persona opera em protocolo JSON de ações (buscar, ler, concluir), sem tool calls nativos. A SERP serve para descoberta; snippet não conta como página lida.
- A leitura integral usa `r.jina.ai`. O `ReadingCoordinator` mantém **uma tarefa in-flight por URL**, cache compartilhado de leituras bem-sucedidas e refcount de consumidores, de modo que o cancelamento de um ponto não interrompe a leitura usada por outro.
- Proveniência: cada fonte recebe `src_*`, cada trecho `chk_*`, com hash SHA-256 e offsets no corpo. IDs inventados pelo modelo, metatexto, resposta truncada (`finish_reason != stop`) e vazamento de raciocínio são rejeitados.
- Antes de I/O, a rodada é reservada atomicamente no banco com `lease_token`; a finalização grava coleta, estado do ponto e envelopes em conjunto, e invalida dossiê anterior.
- Limites operacionais: `SEARCH_POINT_TIMEOUT_SECONDS` (480 s), `SEARCH_READER_TIMEOUT_SECONDS` (45 s), `SEARCH_MAX_URLS_PER_TURN` (4), `JINA_HTTP_TIMEOUT_SECONDS` (45 s).
- O resumo HTTP remove `reasoning` de cada persona; o SSE autenticado publica o raciocínio operacional em tempo real.
- Falha de coleta não é mascarada: `falha_coleta`, `diagnostico`, `total_falhas_coleta` e o estado real do ponto são propagados.

### 3.3 Auditoria — `POST /api/v1/audit`

- Avalia cada ponto contra **12 critérios canônicos** (`app/schemas/audit.py`), com vetor tipado e justificativa obrigatória.
- Limiar configurável: 10, 11 ou 12 critérios aprovados; padrão **11** (91,67%). A pontuação é calculada no backend, não pelo modelo.
- Evidência é dividida em passes com orçamento de 320 000 caracteres (`AUDIT_EVIDENCE_BUDGET_CHARS`); o JSON de decisão tem teto de 1 200 000 caracteres (`AUDIT_JSON_BUDGET_CHARS`).
- Decisão com deadline de 600 s por ponto (`AUDIT_POINT_TIMEOUT_SECONDS`), 300 s por passe de evidência e lease de 1 800 s (`AUDIT_POINT_LEASE_SECONDS`).
- Cortes/repetições idênticas podem reutilizar cache puro, sem nova chamada LLM.
- Critérios reprovados geram `tarefas` direcionadas para a próxima rodada de busca.
- `pronto_para_writer` só é `true` quando todos os pontos da pesquisa estão aprovados e com coleta atual.

### 3.4 Redação — `POST /api/v1/writer`

- **Gate de prontidão:** exige todos os pontos aprovados, plano estruturado, coleta atual e auditoria válida/aplicada. Sem isso, a redação é bloqueada.
- O modelo forte redige quatro seções em Markdown, com citações `[Fonte](URL)` e fontes apenas do conjunto lido com sucesso. Blocos de código, cercas abertas, URLs inventadas e término irregular são rejeitados.
- O artigo pronto é avaliado separadamente por outro passe forte, com os mesmos 12 critérios e corte 11/12.
- Teto: **2 rascunhos e 2 avaliações**, deadline total de **600 s**.
- Reserva/lease/fence atômicos por `UPDATE` condicional e `rowcount`; somente um processo publica.
- Publicação atômica acontece **antes** do webhook; `status = concluido` só para artigo aprovado. Falha preserva diagnósticos e não publica rascunho como final.
- `artifact_hash` identifica o artefato publicado. Reexecuções com o mesmo hash e avaliação válida usam cache de idempotência (0 chamadas LLM, sem novo webhook).
- `reasoning` não é devolvido na API nem no webhook. A entrega é uma atualização condicional exclusiva dos campos de webhook.

### 3.5 Orquestração autônoma — `PipelineRunner`

```
planejado → buscando → auditando → (aprovado?) → redigindo → concluido
                  ↑          │
                  └── reprovado: nova rodada (até 4 buscas / 3 auditorias)
                             │
                             └── bloqueado / reprovado / parcial / falha
```

- Status persistidos em `pesquisa.status_pipeline`: `planejado`, `buscando`, `auditando`, `redigindo`, `concluido`, `bloqueado`, `reprovado`, `parcial`, `falha`.
- O runner não faz retry triplo externo; mapeia `LLMCallError` para `502`, timeouts para `504` e conflitos de posse para `409`.
- `execution_mode`: `parallel` (padrão) processa os N pontos concorrentemente; `sequential` processa em ordem de `ponto_n`. Valor inválido é rejeitado com `422`, sem fallback silencioso.

---

## 4. Modelo de dados

SQLite com `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` e `busy_timeout=30000`. O schema é criado no boot (`Base.metadata.create_all`) e recebe migrações aditivas idempotentes.

### `pesquisa`

| Campo | Tipo | Observação |
| :--- | :--- | :--- |
| `id_pesquisa` | `String(36)` PK | UUID |
| `tema` | `Text` | Pedido original |
| `criado_em`, `concluido_em` | `String(30)` | ISO UTC normalizado |
| `status_pipeline` | `String(30)` | default `planejado` |
| `erro_pipeline` | `Text` | Diagnóstico terminal |
| `plano_estruturado` | `Text` (JSON) | `PlanoInvestigacao` integral |
| `metadados_planejamento` | `Text` (JSON) | Preferências, modelos, recência |
| `dossier_final` | `Text` | Markdown publicado |
| `reasoning_dossier` | `Text` | Interno, não exposto na API |
| `metadados_redacao` | `Text` (JSON) | Avaliação e artefato |
| `webhook_status`, `webhook_resposta` | `Text` | `entregue` / `falha_definitiva` / `pendente` |

### `pontos`

Chave primária `ponto_id`; FK `id_pesquisa` com `ON DELETE CASCADE`. Campos: `ponto_n`, `ponto`, `status`, `pontos_fracos`, `reasoning_planejamento`, `reasoning_auditoria`, `tentativas`, `tentativas_auditoria`, `lease_token`, `eixo_estruturado`. Restrição única `(id_pesquisa, ponto_n)` e índice `(id_pesquisa, status)`.

### `conteudo_coletado`

Chave `id`; FKs para `pesquisa` e `pontos`. Campos: `rodada`, `tema`, `ponto`, `conteudo_coletado`, `reasoning_coleta`, `urls_lidas`, `urls_fonte`, `metadados_coleta`. Restrição única `(id_pesquisa, ponto_id, rodada)` — cada rodada de coleta é preservada, não sobrescrita.

### `credenciais`

`chave` única, `valor_cifrado` (Fernet), `base_url`, `tipo` (`llm`, `jina`, `webhook`, `parametro`), `descricao`, `atualizado_em`. O valor nunca é devolvido em claro pela listagem: apenas metadados mascarados e `origem_ativa` (`banco_cifrado` ou `ambiente`).

### `generation_attempts`

Envelope imutável por chamada LLM: etapa (`plan`, `search`, `audit`, `write`), persona, modelo solicitado/usado, hash e versão do prompt, mensagens, conteúdo, reasoning, `finish_reason`, `usage`, custo estimado, latência, tentativas, erros e tool calls. É a base de auditoria de custo e de reprodutibilidade.

---

## 5. Concorrência, posse e idempotência

- **Reserva atômica:** cada estágio reserva o ponto/rodada com `UPDATE` condicional e confere `rowcount`; não existe leitura-depois-escrita sem fence.
- **Leases:** `pontos.lease_token` identifica o dono temporário da execução. Reservas expiradas podem ser retomadas; dono divergente recebe conflito (`409`).
- **Fences de publicação:** a redação só publica se o `artifact_hash` e o estado de auditoria ainda corresponderem ao que foi reservado.
- **Cache de idempotência:** reexecução de redação com artefato íntegro e avaliação ≥ 11 não chama LLM nem reenvia webhook.
- **Leituras compartilhadas:** `ReadingCoordinator` elimina duplicação de download entre personas/pontos e protege contra envenenamento por falha.
- **Retentativas:** busca até 4 rodadas; auditoria até 3; redação até 2 rascunhos e 2 avaliações. Os tetos são verificados no banco, não apenas em memória.

---

## 6. Streaming SSE

`PipelineEventHub` é um singleton em memória:

- mantém até **100 eventos** por pesquisa e **50 pesquisas** no histórico recente;
- cada assinante recebe uma `asyncio.Queue` isolada;
- `publish` é seguro entre threads;
- sem assinantes, os eventos continuam no histórico por pesquisa.

O endpoint `GET /api/v1/pipeline/{id_pesquisa}/stream`:

1. valida autenticação pela dependência do router (API key/Bearer ou cookie);
2. envia um **snapshot do banco**: `pipeline.status`, `point.status`, `audit.result`, `search.progress`, `writer.progress`, `report.final` quando existirem;
3. transmite eventos ao vivo do hub;
4. agrupa deltas consecutivos do mesmo agente/estágio em um único frame (até 400 deltas);
5. envia `: keep-alive` a cada 15 s;
6. encerra em status terminal, desconexão, `snapshot_only=true` ou `max_events`.

Reconexão não reproduz o histórico de eventos; o snapshot do banco reconstrói o estado persistido. `GET /api/v1/plan/{id}/stream` existe para acompanhar o raciocínio do planejador **enquanto** o `POST /plan` ainda está em andamento — o cliente precisa informar `id_pesquisa` no próprio `POST`.

Eventos publicados:

| Evento | Origem | Conteúdo principal |
| :--- | :--- | :--- |
| `pipeline.status` | runner / snapshot | `status_pipeline`, timestamps |
| `point.status` | runner / snapshot | ponto, status, tentativas |
| `stage.start` / `stage.end` | `pipeline_runner` (auditoria e redação) | estágio, agente, ponto |
| `agent.delta` | cliente LLM | `kind` (`reasoning`/`content`), texto incremental |
| `search.progress` | searcher / snapshot | persona, queries, URLs lidas, falha |
| `audit.result` | auditor / snapshot | status, pontuação, critérios, pontos fracos |
| `writer.progress` | writer / snapshot | status, reasoning, tamanho |
| `report.final` | writer / snapshot | dossiê final e conclusão |
| `pipeline.error` | runner | erro terminal |

---

## 7. Segurança

### Autenticação e sessão

- `verify_api_key` aceita `X-API-Key`, `Bearer`, ou `token`/`api_key` na query para `GET`/`HEAD` (necessário para `EventSource`).
- Sem chave externa, aceita cookie `dr_local_session` assinado com HMAC-SHA256.
- O cookie só é emitido para cliente **loopback real**, `Host` local e `Origin`/`Referer` coincidentes (`is_local_eligible`). Requisições mutantes com cookie exigem mesma origem (`verify_same_origin_csrf`).
- TTL da sessão: 24 h. Chave de assinatura: `API_SECRET_KEY` → `WEBHOOK_HMAC_SECRET` → `CREDENTIALS_MASTER_KEY` → segredo efêmero do processo.
- **Modo aberto:** sem `API_SECRET_KEY` configurada, requisições sem credencial passam. Isso deve ser fechado em produção.

### Credenciais

- Fernet (`AES-128-CBC` + `HMAC-SHA256`) na coluna `credenciais.valor_cifrado`.
- Precedência: banco cifrado → ambiente → `ValueError` explícito.
- `CREDENTIALS_MASTER_KEY` existe somente no ambiente (bootstrap).
- A listagem administrativa mascara valores: URLs permanecem visíveis; segredos mostram `[REDACTED]` ou `abcd****wxyz`.
- Nenhuma credencial é gravada em `localStorage`/`sessionStorage` pelo frontend.

### Webhook

- Corpo JSON cru assinado com HMAC-SHA256 no header `X-Signature: sha256=<hex>`.
- Headers adicionais: `X-Event-Type`, `X-Research-Id`.
- Política 1 + 3 retries com backoff exponencial; apenas `2xx` confirma `entregue`; `4xx` é rejeição definitiva; `429`/`5xx` são retentados.
- Falha definitiva fica em `pesquisa.webhook_status`, sem descartar o dossiê.

### Redação de segredos

`redact_sensitive_string` remove chaves de mensagens de erro antes de devolvê-las ao cliente. O handler global de exceções devolve `Erro interno do servidor.` sem stack trace.

---

## 8. Política temporal e recência

`app/core/temporal.py` centraliza a decisão temporal para planner, search, audit e writer:

- data de referência calculada em tempo de execução no fuso `America/Sao_Paulo` (configurável por `RESEARCH_REFERENCE_TIMEZONE`);
- `RESEARCH_REFERENCE_DATE` (YYYY-MM-DD) fixa a data para testes/reprodutibilidade;
- modos: `auto`, `recente` (365 dias), `24h`, `7d`, `30d`, `12m`, `historico`;
- `auto` usa o estado mais recente quando o tema não fixa recorte histórico;
- consultas são ancoradas no ano corrente e a SERP é ordenada por frescor quando aplicável;
- o bloco temporal é injetado nos prompts para impedir que o limite de conhecimento do modelo seja tratado como limite dos fatos.

---

## 9. Contabilidade de fontes

`SourceAccountingService` produz `FontesResumo` a partir de `conteudo_coletado.metadados_coleta` e do dossiê:

- **consultadas:** todas as URLs efetivamente lidas com sucesso;
- **utilizadas:** URLs citadas no dossiê final;
- **não utilizadas:** consultadas que não entraram no relatório;
- `observacao`, `status` (`completo`, `parcial`, `indisponivel`) e `artifact_hash` quando houver artefato publicado.

O endpoint é estritamente somente leitura: não chama LLM, não lê a web e não altera o banco.

---

## 10. Frontend

- React 18 + TypeScript, Vite, CSS tokenizado; sem framework de componentes ou biblioteca de estado.
- Rotas de interface: `research`, `history`, `settings`, `docs`. A navegação usa caminhos no browser; o backend serve `index.html` como fallback (SPA).
- `src/services/api.ts` centraliza `fetch` same-origin para `/app/session`, `/health` e `/api/v1/*`; erros são normalizados por `parseApiError`.
- `src/hooks/usePipelineStream.ts` abre `EventSource` em `/api/v1/pipeline/{id}/stream` com `withCredentials` e trata todos os eventos do catálogo SSE.
- Histórico: `localStorage` sob `deep_research_local_history_v1`, apenas com dados públicos (sem reasoning interno). Pesquisa ativa e tema também são persistidos localmente.
- A chave `API_SECRET_KEY` nunca é embutida no bundle: o navegador usa o cookie de sessão emitido pelo servidor.
- Em produção o FastAPI serve `frontend/dist` (`/assets/*` e fallback SPA); em desenvolvimento o Vite roda em `:3000` com proxy para `:8010`.

---

## 11. Decisões e trade-offs

| Decisão | Motivo | Custo |
| :--- | :--- | :--- |
| SQLite + WAL | Operação simples, zero infraestrutura, transações confiáveis para um nó | Não escala horizontalmente; escritas serializadas |
| Monólito modular | Quatro endpoints independentes com estado no banco | Acoplamento ao processo para SSE e caches |
| Hub SSE em memória | Latência baixa e implementação direta | Sem replay entre reinícios e sem fan-out entre workers |
| Sem fila durável | MVP sem broker | Webhook e pipeline assíncrono dependem do processo vivo |
| Credenciais no banco cifrado | Configuração dinâmica pela interface | Exige `CREDENTIALS_MASTER_KEY` estável; perda da chave inviabiliza a decifra |
| Sem framework de UI | Controle visual e bundle direto | Componentes e estilos mantidos manualmente |
| Protocolo JSON de ações | Inspeção e validação estritas do comportamento do modelo | Mais tokens de prompt e parsing rigoroso |

Pontos de extensão naturais: substituir SQLite por PostgreSQL (SQLAlchemy já abstrai), trocar o hub por Redis/Postgres `LISTEN/NOTIFY`, adicionar fila para webhook, middleware de rate limit e paginação/consulta de histórico no servidor.

---

## 12. Referências

- [`../README.md`](../README.md) — visão geral e início rápido
- [`API.md`](API.md) — contratos HTTP
- [`OPERATIONS.md`](OPERATIONS.md) — operação e diagnóstico
- [`../_reversa_sdd/prd.md`](../_reversa_sdd/prd.md) — PRD e invariantes
- [`../_reversa_sdd/sdd/`](../_reversa_sdd/sdd/) — SDD por endpoint e adendos v2..v8
- [`security_audit_findings.md`](security_audit_findings.md) — auditoria de segurança
