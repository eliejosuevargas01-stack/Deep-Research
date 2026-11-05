# Hermes Deep Research

Pipeline assíncrono, auditável e modular de pesquisa profunda operado integralmente pelo **Hermes** (`hermes-agent`), sob o paradigma de **Estado Acumulativo sem Truncamento (Append-Only Context Hydration)**.

## Arquitetura do Sistema

O **Hermes** é o único motor de inteligência, busca web e delegação do sistema. O backend auxiliar **não faz chamadas diretas a APIs externas de LLM ou buscadores**: ele aciona unicamente o Hermes em um workspace isolado por pesquisa, gerencia a persistência no banco de dados, hidrata o 1º prompt de cada papel e sincroniza o `config.yaml` do perfil Hermes:

1. **Ingestão assíncrona:** o backend recebe os parâmetros da pesquisa (`tema`, `profundidade`, `veracidade_alvo`, `max_rodadas_auditoria`, `atualidade`, `callback_url`), cria o workspace exclusivo da execução e gera um `research_id`.
2. **Hermes Planner (com busca exploratória inicial):** o agente principal no Hermes realiza uma varredura exploratória simples na web (`web_search` e leitura livre de páginas com `web_extract`) apenas para coletar informação basal sobre o tema e decompô-lo em `N` pontos independentes (`N = profundidade`, de 1 a 10).
3. **Fan-out massivo de subagentes buscadores (até 40 simultâneos):** sem trava artificial de 3 pontos paralelos, todos os `N` pontos em aberto acionam simultaneamente as 4 personas de busca (`historiador`, `cetico`, `visionario`, `futurista`) via `delegate_task` no Hermes, chegando a **40 subagentes simultâneos** (`10 pontos × 4 personas`, com `max_concurrent_children: 40` no `config.yaml`).
4. **Hermes Auditor (12 perguntas booleanas):** recebe no 1º prompt 100% do contexto acumulado de todas as rodadas do ponto (`R1 + R2 + ... + Rk`) sem truncamento e responde as 12 perguntas estritamente com `true` ou `false`.
5. **Loop de retentativa determinístico:** calcula-se a taxa de aprovação frente a `veracidade_alvo`. Se reprovado e abaixo de `max_rodadas_auditoria`, dispara-se nova rodada de busca no Hermes injetando as perguntas `false` como foco e todas as `urls_lidas` anteriores como bloqueio (*blacklist*).
6. **Hermes Redator:** quando o ponto é aprovado ou atinge o limite de rodadas, o Redator recebe toda a informação acumulada de todas as rodadas e o resultado final do Auditor, produzindo o relatório analítico exaustivo e documentando explicitamente as lacunas remanescentes.
7. **Webhook callback:** o resultado consolidado de todos os pontos e a telemetria real somada das sessões do Hermes (agente principal + subagentes) são enviados por POST para `callback_url`.

---

## Configuração Dinâmica do Hermes (`config.yaml`) e Modelos por Subagente

Todas as configurações do Hermes — provedor OpenAI-compatible (`base_url`, `api_key`), limites de concorrência (`max_concurrent_children: 40`, `oneshot_max_children: 0`) e o **modelo específico de cada subagente** — são gerenciadas diretamente no arquivo `hermes_home/profiles/deep-research/config.yaml` através do endpoint de configurações (`GET /config` e `PUT /config`, ou `/api/v1/settings`):

- `planner` (Agente Principal / Planejador)
- `historiador` (Subagente Buscador 1)
- `cetico` (Subagente Buscador 2)
- `visionario` (Subagente Buscador 3)
- `futurista` (Subagente Buscador 4)
- `auditor` (Subagente Auditor de 12 Critérios)
- `redator` (Subagente Redator do Dossiê)

O roteamento de modelos no Hermes utiliza `delegation.backend: por_papel` (plugin `delegation_por_papel`), garantindo que cada subagente delegado execute com o modelo configurado para o seu papel.

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
- `perguntas_respondidas`
- `resultado_final_auditor`

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
├── hermes_home/
│   ├── profiles/deep-research/
│   │   ├── config.yaml         # provedor, modelos por subagente e max_concurrent_children: 40
│   │   ├── SOUL.template.md    # contratos operacionais; deploy materializa como SOUL.md
│   └── plugins/delegation/por_papel/
│       ├── __init__.py         # roteador de modelo por papel em cada delegate_task
│       └── plugin.yaml
├── src/
│   ├── main.py                 # entrypoint ASGI
│   ├── api.py                  # POST /research, GET /research/{id}, GET/PUT /config, GET /health
│   ├── config.py               # config de execução (pipeline, binário e perfil do Hermes)
│   ├── settings.py             # leitura/escrita do config.yaml do perfil Hermes
│   ├── contracts.py            # contratos canônicos + validação (12 perguntas, mínimos, URLs)
│   ├── hydrator.py             # monta o 1º prompt de cada papel a partir do banco
│   ├── planner.py              # taxa de veracidade e decisão de fluxo
│   ├── orchestrator.py         # lotes de tarefas por rodada; zero chamadas de API diretas
│   ├── hermes_runner.py        # aciona `hermes -p deep-research` com cwd no workspace
│   ├── telemetria.py           # tokens/modelo por subagente lidos do state.db
│   ├── engine.py               # contrato AgentCall/Tarefa + extração de JSON
│   ├── webhook.py              # callback final
│   ├── prompts/                # planner.md, buscador.md, auditor.md, redator.md
│   └── db/
│       ├── schema.sql          # DDL canônico PostgreSQL (SDD §6)
│       ├── sqlite_manager.py   # schema local com as mesmas tabelas
│       └── repository.py       # persistência, hidratação e consolidação
├── tests/                      # suíte de testes de contrato, configuração Hermes e pipeline
└── data/                       # runtime: deep_research.db e workspaces isolados por pesquisa
```

---

## Critérios de Auditoria (12 Perguntas)

Os 12 critérios abaixo orientam a formulação das 12 perguntas binárias (`"1"` a `"12"`) de cada ponto e compõem a métrica final do auditor (`quantidade de respostas true / 12`):

1. `clareza_tematica` — abordagem objetiva do eixo e aderência às subperguntas do plano.
2. `corroboracao_canonica` — suporte em fontes primárias verificáveis; URL sozinha não é prova.
3. `atualidade` — marcos e dados vigentes para a janela de `atualidade` exigida; marco antigo não é estado atual.
4. `ausencia_contradicoes` — coerência interna entre os dados coletados pelas 4 personas.
5. `embasamento_factual` — ancoragem empírica; ausência de evidência ≠ falsidade.
6. `aderencia_escopo` — atém-se ao tema, ao enunciado e às subperguntas do ponto.
7. `profundidade_analitica` — complexidade adequada e incertezas delimitadas.
8. `precisao_dados` — exatidão numérica, métricas, datas, unidades e identificadores.
9. `neutralidade` — fatos separados de hipóteses; equilíbrio analítico.
10. `densidade_evidencias` — proporção consistente entre afirmações e `urls_usadas`.
11. `declaracao_incertezas` — lacunas remanescentes expressas e delimitadas.
12. `solidez_logica` — conclusões decorrem diretamente das evidências apresentadas.
