# Hermes Deep Research

Pipeline assíncrono, auditável e modular de pesquisa profunda operado integralmente pelo **Hermes** (`hermes-agent`), sob o paradigma de **Estado Acumulativo (DB Integral + Prompt Compactado sem Perda Factual)**.

**Versão:** 1.3 (2026-11-07) · PRD.md / SDD.md são a especificação vigente.

## Arquitetura (`api` + `engine` isolado)

| Serviço | Imagem/build | Porta | Papel |
|---|---|---|---|
| `api` | `Dockerfile.api` (python:3.12-slim) | **8000 pública** | backend: valida, hidrata prompts do banco, despacha ao engine, persiste, SSE, webhook |
| `engine` | `engine/Dockerfile` (`FROM nousresearch/hermes-agent:latest`) | **8100 interna** (expose, sem publish) | Hermes isolado: `USER hermes`, `POST /run`, `GET/PUT /config`, `GET /health` |

- O **Hermes** é o único motor de inteligência, busca web e delegação. O backend **não faz chamadas diretas a LLMs/buscadores**: aciona o engine via `DR_ENGINE_URL=http://engine:8100` em workspace isolado por pesquisa (`/workspaces/{research_id}`).
- Fluxo: **Ingestão** (`POST /research` → `research_id` + workspace) → **Planner** (varredura exploratória + N pontos; backend injeta as 12 perguntas estáticas em cada ponto) → **Fan-out** (N×4 personas, até 40 simultâneos) → **Auditor** (12 booleanos, contexto acumulado compactado) → **Loop** (pendentes + blacklist de URLs) → **Redator** (relatório + lacunas, só URLs acumuladas) → **Webhook** (dossiê + `avaliacao_pontos` + tokens).
- Telemetria real: `state.db` do Hermes montado `:ro` (`DR_HERMES_STATE_DB`) + fallback `usage.json` na linha `orquestrador` (tokens do delegador, nunca inventados).

## Env obrigatórias

```bash
cp .env.example .env   # edite com valores reais; .env é ignorado pelo git
```

| Variável | Serviço | Uso |
|---|---|---|
| `LLM_BASE_URL` | engine | endpoint OpenAI-compatível |
| `LLM_API_KEY` | engine | segredo → `.env` 600 dentro do container; nunca no YAML/API/git |
| `LLM_MODEL` | engine | default = planner (forte). Ex.: `ocg/deepseek-v4.1-flash` |
| `API_KEY` | api | chave da API pública (compose exige definida); sem ela o backend fica aberto (só dev) |
| `ENGINE_TOKEN` | ambos | `X-Engine-Token` entre api e engine |

Placeholders nos exemplos: `https://SEU-ROTEADOR/v1`, `***`. **Nunca commitar chave real.**

## Modelos por papel (defaults)

Forte (`ocg/deepseek-v4.1-flash`): `planner`, `auditor`, `redator`. Leve (`gemini/gemini-3.5-flash-lite`): `historiador`, `cetico`, `visionario`, `futurista`. Overrides: `LLM_MODEL_<PAPEL>` (ex.: `LLM_MODEL_AUDITOR`); `LLM_MODEL` só afeta o planner. `PUT /config` altera modelos/limites; credencial no payload → **422**.

## SSE / resume

`GET /research/{id}/eventos` (alias `/events`): snapshot (run completo) quando `desde=0`, replay `id > base` via `Last-Event-ID` ou `?desde=`, heartbeat `: ping` ~15s, at-least-once com **dedupe do cliente por `id`**. Reload/troca de página restaura do `id 0` sem perda. SSE aceita `?api_key=`.

## API key

Pública: `X-API-Key` ou `Bearer` (SSE: `?api_key=`); `GET /health` sempre aberto; erro → `401`. Interna: `X-Engine-Token` (engine, tudo exceto `/health`).

## Comandos (compose)

```bash
docker compose config        # valida interpolação (exige API_KEY definida)
docker compose up --build -d # sobe api (8000) + engine (8100 interna)
docker compose logs -f api engine
curl localhost:8000/health
curl -H "X-API-Key: $API_KEY" localhost:8000/config
```

## Testes

- Backend: `.venv/bin/python -m pytest tests -q` → **78 passed** (pipeline, contratos, settings, webhook, eventos/SSE, evidências, garantias, lacunas, repositório, engine, API key).
- Frontend: `npm test --prefix frontend` → **51 passed** (14 arquivos: `apiV12`, `ssePesquisa`, `usePesquisaAoVivo`, views, validação).

---

## Convenção de Nomes Canônica

Os nomes abaixo são os valores oficiais do sistema e devem ser usados em toda a implementação, testes e documentação:

- `research_id`
- `tema`
- `profundidade`
- `veracidade_alvo`
- `max_rodadas_auditoria`
- `atualidade`
- `callback_url`
- `ponto_id`
- `enunciado`
- `subperguntas`
- `hipoteses`
- `lacunas_iniciais`
- `perguntas_auditoria`
- `tentativa_atual`
- `urls_usadas`
- `urls_lidas`
- `urls_lidas_nao_usadas`
- `informacao_coletada`
- `informacao_coletada_acumulada`
- `informacao_coletada_acumulada_integral`
- `compactacao`
- `perguntas_respondidas`
- `perguntas_nao_concluidas`
- `resultado_final_auditor`
- `avaliacao_pontos`

> Regra: nomes de contrato em JSON e campos de banco devem usar o mesmo vocabulário para evitar inconsistência entre backend, planner, buscadores, auditor e redator.

---

## Personas de Busca

| Subagente | Persona | Papel na Coleta |
| :--- | :--- | :--- |
| **Subagente 1** | `historiador` | Contexto histórico, fundamentos, marcos canônicos e esclarecimento das subperguntas. |
| **Subagente 2** | `cetico` | Validação cruzada, fontes primárias, contradições numéricas e detecção de viés. |
| **Subagente 3** | `visionario` | Padrões, estado da arte, tendências emergentes e desdobramentos estratégicos. |
| **Subagente 4** | `futurista` | Cenários prospectivos datados, riscos futuros e impactos sistêmicos. |

---

## Rastreamento de URLs

Cada execução de subagente buscador no Hermes classifica as fontes consultadas em três categorias:

- `urls_usadas`: URLs de onde a informação relevante foi efetivamente extraída para compor a resposta.
- `urls_lidas`: todas as URLs abertas ou visitadas durante a execução (`web_extract`).
- `urls_lidas_nao_usadas`: calculada automaticamente pelo backend como `urls_lidas - urls_usadas`.

Esse campo de diferença é usado para auditoria de eficiência e bloqueio de releitura nas rodadas subsequentes.

---

## Contratos Canônicos de Entrada e Saída

### Payload inicial do usuário

```json
{
  "tema": "matriz energetica no Brasil.",
  "profundidade": 10,
  "veracidade_alvo": 90,
  "max_rodadas_auditoria": 4,
  "atualidade": "24H",
  "callback_url": "https://webhook.callback.com"
}
```

### Saída do planner (após busca exploratória inicial)

O planner gera `ponto_id`, `enunciado`, `subperguntas`, `hipoteses` e `lacunas_iniciais`.
O backend injeta `perguntas_auditoria` (as 12 estáticas abaixo) em cada ponto antes de persistir.

```json
{
  "research_id": "123ABC321",
  "tema": "matriz energetica no Brasil.",
  "profundidade": 10,
  "veracidade_alvo": 90,
  "max_rodadas_auditoria": 4,
  "atualidade": "24H",
  "callback_url": "https://webhook.callback.com",
  "pontos": [
    {
      "ponto_id": 1,
      "enunciado": "Quais são as matrizes energéticas do Brasil e sua participação atual",
      "subperguntas": [
        "Qual o percentual atual de renováveis vs não-renováveis?",
        "Como se divide a geração hidráulica, térmica, eólica e solar?",
        "Quais foram as atualizações oficiais mais recentes?"
      ],
      "hipoteses": [
        "Fontes renováveis representam mais de 45% da matriz energética total.",
        "A geração solar distribuída cresceu acima da média histórica no último ciclo.",
        "Gargalos de transmissão limitam o escoamento no Nordeste."
      ],
      "lacunas_iniciais": [
        "Dados consolidados das últimas 24 horas do ONS.",
        "Impacto exato do curtailment eólico recente.",
        "Diferença metodológica entre dados da EPE e da ANEEL."
      ],
      "perguntas_auditoria": "(injetada pelo backend — ver § Critérios de Auditoria; idêntica em todos os pontos)"
    }
  ]
}
```

> Boletim oficial `avaliacao_pontos` (por ponto: `perguntas_true/12`, `%`, `meta`, `aprovado`) compõe o dossiê (`## Avaliação de veracidade`), o webhook e o `GET /research/{id}`. Detalhes: SDD §5.7.

---

## Estrutura da Implementação

```text
hermes-deep-research/
├── README.md / PRD.md / SDD.md   # especificação v1.3
├── engine/
│   ├── Dockerfile                # FROM nousresearch/hermes-agent:latest, USER hermes, expose 8100
│   ├── entrypoint.sh             # renderiza config.yaml do env (provider env, sem segredo)
│   └── service.py                # GET /health, GET/PUT /config, POST /run (X-Engine-Token)
├── hermes_home/
│   ├── profiles/deep-research/   # semente de perfil (SOUL, plugin); segredo nunca commitado
│   └── plugins/delegation/por_papel/
├── src/
│   ├── main.py                   # entrypoint ASGI
│   ├── api.py                    # POST /research, GET /research/{id}, GET/PUT /config, SSE /eventos, GET /health
│   ├── config.py                 # config de execução (pipeline, binário e perfil do Hermes)
│   ├── settings.py               # provider só env; PUT com credencial → 422; repassa ao engine
│   ├── contracts.py              # contratos canônicos + validação (12 estáticas, mínimos, URLs)
│   ├── evidencias.py             # compactação determinística (DB intacto, prompt sem perda factual)
│   ├── hydrator.py               # monta o 1º prompt de cada papel a partir do banco
│   ├── planner.py                # taxa de veracidade, decisão de fluxo, avaliacao_pontos
│   ├── orchestrator.py           # lotes por rodada; resiliência por ponto; eventos SSE
│   ├── hermes_runner.py          # despacha ao engine; telemetria state.db :ro + fallback usage.json
│   ├── telemetria.py             # tokens/modelo por subagente lidos do state.db
│   ├── engine.py                 # contrato AgentCall/Tarefa + extração de JSON
│   ├── webhook.py                # callback final (5 tentativas 1s/2s/4s/8s)
│   ├── prompts/                  # planner.md, buscador.md, auditor.md, redator.md
│   └── db/
│       ├── schema.sql            # DDL canônico PostgreSQL (SDD §6, 4 tabelas incl. research_events)
│       ├── sqlite_manager.py     # schema local paritário
│       └── repository.py         # persistência, hidratação (2 SELECTs), consolidação, eventos
├── frontend/src/v12/             # fluxo ativo: AppV12, ResearchViews, SettingsV12, usePesquisaAoVivo, ssePesquisa
├── frontend/src/services/apiV12.ts  # POST/GET /research, GET/PUT /config, X-API-Key (?api_key no SSE)
├── tests/                        # suíte backend (78 testes)
└── data/                         # runtime: deep_research.db e workspaces isolados por pesquisa
```

---

## Documentação Reversa (as-built)

A documentação reversa do backend como implementado — contratos, fluxos, banco, telemetria, divergências vs PRD/SDD e rastreabilidade RF01-RF12/RNF01-RNF03 e D-01..D-12 — está em [`_reversa_sdd/`](_reversa_sdd/README.md). Provas executáveis em `_reversa_sdd/verification/` (pytest, smoke HTTP, inventário SQLite, e2e do runner).

---

## Critérios de Auditoria (12 Perguntas ESTÁTICAS)

As 12 perguntas abaixo são ESTÁTICAS e universais: idênticas em todos os pontos.
O planner NÃO as cria; o backend injeta `PERGUNTAS_AUDITORIA_ESTATICAS` em cada ponto
em `_planejar` antes de persistir. O auditor responde cada uma com `true`/`false`;
a métrica é `quantidade de respostas true / 12`:

1. `clareza_tematica` — "O material coletado aborda de forma clara e objetiva o eixo do ponto e responde às suas subperguntas? (sim/não)"
2. `corroboracao_canonica` — "As afirmações centrais estão sustentadas por fontes primárias verificáveis, e não apenas por URLs citadas sem verificação? (sim/não)"
3. `atualidade` — "Os marcos e dados apresentados estão atualizados dentro da janela de atualidade exigida? (sim/não)"
4. `ausencia_contradicoes` — "Não há contradições internas relevantes entre as informações coletadas pelas 4 personas? (sim/não)"
5. `embasamento_factual` — "As conclusões têm ancoragem empírica no material, sem tratar ausência de evidência como falsidade nem como prova? (sim/não)"
6. `aderencia_escopo` — "O material atém-se ao tema, ao enunciado e ao escopo do ponto, sem desvios relevantes? (sim/não)"
7. `profundidade_analitica` — "A análise tem profundidade adequada e delimita as incertezas em vez de apenas descrever fatos? (sim/não)"
8. `precisao_dados` — "Números, datas, unidades, métricas e identificadores estão precisos e consistentes entre as fontes? (sim/não)"
9. `neutralidade` — "Fatos observados estão separados de hipóteses e interpretações, com neutralidade analítica? (sim/não)"
10. `densidade_evidencias` — "A densidade de evidências é proporcional às afirmações, com respaldo em urls_usadas? (sim/não)"
11. `declaracao_incertezas` — "As incertezas e lacunas remanescentes estão declaradas e delimitadas explicitamente? (sim/não)"
12. `solidez_logica` — "As conclusões decorrem logicamente das evidências apresentadas, sem saltos lógicos? (sim/não)"
