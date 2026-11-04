# Hermes Deep Research Pipeline

Motor modular e assíncrono de pesquisa profunda (*Deep Research*) baseado no **Hermes** como núcleo agêntico de planejamento, busca, auditoria e redação.

O sistema opera sob o paradigma de **Estado Acumulativo sem Truncamento (Append-Only Context)** e **Injeção no 1º Prompt via Banco de Dados**, garantindo rastreabilidade total de URLs, raciocínio (*reasoning*), chamadas de ferramentas (*tool calls*) e consumo de tokens.

---

## Visão Geral da Arquitetura

O **Hermes** atua como o cérebro central em todas as pontas do fluxo, enquanto o backend auxiliar gerencia a persistência no banco de dados e a hidratação dos prompts iniciais de cada subagente para evitar estouro de janela de contexto no agente orquestrador pai:

1. **Ingestão assíncrona:** o backend recebe os parâmetros da pesquisa (`tema`, `profundidade`, `veracidade_alvo`, `max_rodadas_auditoria`, `atualidade`, `callback_url`) e gera um `research_id`.
2. **Planner:** realiza busca exploratória inicial e decompoe o tema em `N` pontos, onde `N = profundidade`.
3. **Fan-out de buscadores:** cada ponto é pesquisado em paralelo por 4 personas (`historiador`, `cetico`, `visionario`, `futurista`).
4. **Auditor:** recebe no 1º prompt o contexto acumulado de todas as rodadas do ponto e responde as 12 perguntas com `true` ou `false`.
5. **Loop de retentativa:** o planner calcula a taxa de aprovação e, se necessário, dispara nova rodada com foco nas perguntas com `false` e URLs já lidas como bloqueio.
6. **Redator:** quando o ponto é aprovado ou o limite é atingido, produz o relatório final e documenta as lacunas remanescentes.
7. **Webhook callback:** o resultado consolidado e a telemetria agregada são enviados por POST para `callback_url`.

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
- `perguntas_respondidas`
- `resultado_final_auditor`

> Regra: nomes de contrato em JSON e campos de banco devem usar o mesmo vocabulário para evitar inconsistência entre backend, planner, auditor e redator.

---

## Personas de Busca

| Subagente | Persona | Papel na Coleta |
| :--- | :--- | :--- |
| **Subagente 1** | `historiador` | Contexto histórico, fundamentos e esclarecimento das subperguntas. |
| **Subagente 2** | `cetico` | Validação cruzada, fontes primárias e detecção de viés. |
| **Subagente 3** | `visionario` | Padrões, tendências emergentes e desdobramentos estratégicos. |
| **Subagente 4** | `futurista` | Cenários prospectivos, riscos futuros e impactos sistêmicos. |

---

## Rastreamento de URLs

Cada execução de subagente classifica as fontes consultadas em três categorias:

- `urls_usadas`: URLs de onde a informação relevante foi extraída para compor a resposta.
- `urls_lidas`: todas as URLs abertas ou visitadas durante a execução.
- `urls_lidas_nao_usadas`: calculada automaticamente como `urls_lidas - urls_usadas`.

Esse campo de diferença é usado para auditoria de eficiência e bloqueio de releitura nas rodadas subsequentes.

---

## Contratos canônicos de Entrada e Saída

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

### Saída do planner (decomposição inicial)

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
      "perguntas_auditoria": {
        "1": "As fontes primárias oficiais (EPE, ANEEL ou ONS) foram citadas?",
        "2": "Há distinção clara entre matriz energética e matriz elétrica?",
        "3": "Os percentuais de participação de cada fonte somam valores consistentes?",
        "4": "Os dados respeitam a janela de atualidade exigida (24H)?",
        "5": "A capacidade instalada em GW foi informada?",
        "6": "Há dados específicos sobre biomassa e derivados de cana?",
        "7": "Há dados sobre combustíveis fósseis (petróleo, gás e carvão)?",
        "8": "Eventuais divergências numéricas entre fontes foram explicadas?",
        "9": "As tendências de expansão de curto/médio prazo foram mapeadas?",
        "10": "Os riscos operacionais e de infraestrutura foram levantados?",
        "11": "Há contextualização histórica da evolução dessa matriz?",
        "12": "As projeções de longo prazo estão ancoradas em planos decenais ou dados reais?"
      }
    }
  ]
}
```

---

## Estrutura da Implementação

```text
hermes-deep-research/
├── README.md / PRD.md / SDD.md
├── config/
│   └── hermes_config.yaml      # engine (OpenAI-compat), concorrência, caminho do banco
├── src/
│   ├── main.py                 # entrypoint ASGI
│   ├── api.py                  # POST /research, GET /research/{id}, GET /health
│   ├── contracts.py            # contratos canônicos + validação (12 perguntas, mínimos)
│   ├── hydrator.py             # monta o 1º prompt de cada papel a partir do banco
│   ├── planner.py              # taxa de veracidade e decisão de fluxo
│   ├── orchestrator.py         # máquina de estados (planner → personas → auditor → redator)
│   ├── engine.py               # chamada ao núcleo agêntico + extração estrita de JSON
│   ├── webhook.py              # callback final
│   ├── prompts/                # planner.md, buscador.md, auditor.md, redator.md
│   └── db/
│       ├── schema.sql          # DDL canônico PostgreSQL (SDD §5)
│       ├── sqlite_manager.py   # schema local com as mesmas tabelas
│       └── repository.py       # persistência, hidratação e consolidação
├── tests/                      # 25 testes com engine determinístico (sem LLM)
└── data/                       # runtime: deep_research.db (ignorado pelo git)
```

---

## Execução local

```bash
uv sync

cp .env.example .env          # preencha LLM_API_KEY e DR_ENGINE_MODEL

cd src && uvicorn main:app --host 0.0.0.0 --port 8000 --env-file ../.env
```

Variáveis lidas do `.env` (ou do ambiente): `LLM_BASE_URL`, `LLM_API_KEY`,
`DR_ENGINE_MODEL`/`LLM_MODEL`, `DR_DB_PATH`, `DR_CONFIG`.

```bash
curl -s -X POST http://localhost:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"tema":"matriz energetica no Brasil","profundidade":2,"veracidade_alvo":90,"max_rodadas_auditoria":4,"atualidade":"24H","callback_url":"https://webhook.example/cb"}'

curl -s http://localhost:8000/research/<research_id>
```

O runtime local usa SQLite (`data/deep_research.db`); o DDL de produção em PostgreSQL está em
`src/db/schema.sql`. Testes: `uv run pytest -q` (nenhuma chamada de LLM real).

---

## Critérios de auditoria

Os 12 critérios abaixo compõem a métrica final do auditor. O cálculo usa a quantidade de respostas `true` sobre 12 perguntas.

- clareza_tematica
- corroboracao_canonica
- atualidade
- ausencia_contradicoes
- embasamento_factual
- aderencia_escopo
- profundidade_analitica
- precisao_dados
- neutralidade
- densidade_evidencias
- declaracao_incertezas
- solidez_logica
