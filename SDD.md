# SPEC — Especificação Técnica: Hermes Deep Research

---

## 1. Fluxo de Dados e Máquina de Estados

```mermaid
stateDiagram-v2
    [*] --> Ingestao: POST /research
    Ingestao --> Planner_Scoping: Gera research_id no Banco
    Planner_Scoping --> FanOut_Buscadores: Cria N pontos (1..10) + 12 perguntas/ponto

    state "Loop por Ponto (Paralelo 1..N)" as LoopPonto {
        FanOut_Buscadores --> Persistencia_Busca: 4 Personas (Historiador, Cético, Visionário, Futurista)
        Persistencia_Busca --> Hidratacao_Auditor: Salva R(k) no Banco + calcula URLs não usadas
        Hidratacao_Auditor --> Auditor_12Q: Injeta informacao_coletada_acumulada no 1º prompt
        Auditor_12Q --> Avaliacao_Planner: Retorna 12 booleans (true/false)
        Avaliacao_Planner --> FanOut_Buscadores: Avaliacao < veracidade_alvo e tentativa_atual < max_rodadas_auditoria
        Avaliacao_Planner --> Hidratacao_Redator: Avaliacao >= veracidade_alvo ou tentativa_atual == max_rodadas_auditoria
    }

    Hidratacao_Redator --> Redator_Final: Injeta contexto total + resultado_final_auditor
    Redator_Final --> Callback_Webhook: Escreve relatório + lacunas e envia POST
    Callback_Webhook --> [*]
```

---

## 2. Estratégia de Injeção no 1º Prompt (Banco + Hermes)

O **Hermes** governa o fluxo por meio de ferramentas de orquestração leve, enquanto o backend faz a leitura e gravação pesada no PostgreSQL:

1. **Quando o Hermes chama `spawn_buscadores(research_id, ponto_id, rodada)`:**
   - Se `rodada == 1`, o backend monta o 1º prompt para cada persona com `tema`, `ponto`, `subperguntas` e `hipoteses`.
   - Se `rodada > 1`, o backend consulta no banco quais perguntas receberam `false` no auditor da rodada anterior e reúne `urls_lidas` acumuladas daquele ponto, injetando os dois conjuntos no 1º prompt dos buscadores.
2. **Quando o Hermes chama `spawn_auditor(research_id, ponto_id, rodada)`:**
   - O backend executa um `SELECT` de `agent_executions` daquele ponto e rodada inicial até a atual, concatena `informacao_coletada` de todas as personas e rodadas e injeta no 1º prompt do auditor junto com `perguntas_auditoria`.
3. **Quando o Hermes chama `spawn_redator(research_id, ponto_id)`:**
   - O backend executa o mesmo acumulado por ponto e combina com `resultado_final_auditor` para injetar no 1º prompt do redator.

---

## 3. Convenção Canônica de Nomes e Contratos

Os nomes abaixo são os únicos nomes oficiais do sistema e devem ser usados em todos os payloads de entrada, saída e persistência:

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

> Qualquer documento, endpoint ou tabela que usar `veracidade`, `callback`, `max_tentativas`, `urls_lidas_mas_nao_usadas` em vez dos nomes acima deve ser tratado como documentação antiga e será normalizado antes da implementação.

---

## 4. Contratos JSON (Schemas de Entrada e Saída)

### 4.1. Payload inicial do usuário
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

### 4.2. Saída do planner (decomposição inicial)
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

### 4.3. Payload de entrada do subagente buscador
```json
{
  "research_id": "123ABC321",
  "ponto_id": 1,
  "rodada": 2,
  "persona": "historiador",
  "tema": "matriz energetica no Brasil.",
  "ponto_enunciado": "Quais são as matrizes energéticas do Brasil e sua participação atual",
  "subperguntas": [
    "Qual o percentual atual de renováveis vs não-renováveis?",
    "Como se divide a geração hidráulica, térmica, eólica e solar?",
    "Quais foram as atualizações oficiais mais recentes?"
  ],
  "hipoteses": [
    "Fontes renováveis representam mais de 45% da matriz energética total."
  ],
  "perguntas_auditoria_pendentes": {
    "4": "Os dados respeitam a janela de atualidade exigida (24H)?",
    "8": "Eventuais divergências numéricas entre fontes foram explicadas?"
  },
  "urls_lidas_ignoradas": [
    "https://url1.com.br",
    "https://url2.com"
  ],
  "max_queries": 3
}
```

### 4.4. Saída padronizada do subagente buscador
```json
{
  "research_id": "123ABC321",
  "ponto_id": 1,
  "rodada": 2,
  "persona": "historiador",
  "tema": "matriz energetica no Brasil.",
  "informacao_coletada": "Texto denso, detalhado e sem resumo prematuro contendo todos os fatos, números, citações e evidências extraídas das leituras...",
  "urls_usadas": [
    "https://www.epe.gov.br/pt/publicacoes-dados-abertos/publicacoes/balanco-energetico-nacional"
  ],
  "urls_lidas": [
    "https://www.epe.gov.br/pt/publicacoes-dados-abertos/publicacoes/balanco-energetico-nacional",
    "https://portal-irrelevante-exemplo.com.br/noticia-antiga"
  ]
}
```

> O backend calcula automaticamente `urls_lidas_nao_usadas = urls_lidas - urls_usadas` ao persistir no banco.

### 4.5. Entrada e saída do auditor

**Entrada injetada no 1º prompt do auditor:**
```json
{
  "research_id": "123ABC321",
  "ponto_id": 1,
  "persona": "auditor",
  "soul": "Você é o auditor. Seu objetivo é avaliar rigorosamente todas as informações coletadas em todas as rodadas e responder somente com true ou false para cada uma das 12 perguntas.",
  "tentativa_atual": 2,
  "max_rodadas_auditoria": 4,
  "perguntas_auditoria": {
    "1": "...",
    "12": "..."
  },
  "informacao_coletada_acumulada": [
    {
      "rodada": 1,
      "historiador": "Informação integral da rodada 1...",
      "cetico": "Informação integral da rodada 1...",
      "visionario": "Informação integral da rodada 1...",
      "futurista": "Informação integral da rodada 1..."
    },
    {
      "rodada": 2,
      "historiador": "Informação integral da rodada 2...",
      "cetico": "Informação integral da rodada 2...",
      "visionario": "Informação integral da rodada 2...",
      "futurista": "Informação integral da rodada 2..."
    }
  ]
}
```

**Saída estrita do auditor:**
```json
{
  "research_id": "123ABC321",
  "ponto_id": 1,
  "tentativa_atual": 2,
  "perguntas_respondidas": {
    "1": true,
    "2": true,
    "3": true,
    "4": true,
    "5": true,
    "6": true,
    "7": true,
    "8": false,
    "9": true,
    "10": true,
    "11": true,
    "12": true
  }
}
```

### 4.6. Decisão do planner
```json
{
  "research_id": "123ABC321",
  "tentativa_atual": 2,
  "tema": "matriz energetica no Brasil.",
  "avaliacao_pontos": [
    {
      "ponto_id": 1,
      "perguntas_true": 11,
      "total_perguntas": 12,
      "porcentagem_aprovacao": 91.67,
      "meta_veracidade_alvo": 90.0,
      "aprovado": true
    },
    {
      "ponto_id": 2,
      "perguntas_true": 8,
      "total_perguntas": 12,
      "porcentagem_aprovacao": 66.67,
      "meta_veracidade_alvo": 90.0,
      "aprovado": false
    }
  ]
}
```

### 4.7. Entrada e saída do redator

**Entrada injetada no 1º prompt do redator:**
```json
{
  "research_id": "123ABC321",
  "ponto_id": 1,
  "persona": "redator",
  "soul": "Você é o redator-chefe. Seu objetivo é redigir o relatório definitivo usando 100% da base informacional coletada em todas as rodadas, citando as urls_usadas e documentando explicitamente todas as lacunas remanescentes.",
  "ponto_enunciado": "Quais são as matrizes energéticas do Brasil e sua participação atual",
  "resultado_final_auditor": {
    "1": true,
    "2": true,
    "3": true,
    "4": true,
    "5": true,
    "6": true,
    "7": true,
    "8": false,
    "9": true,
    "10": true,
    "11": true,
    "12": true
  },
  "perguntas_auditoria": {
    "1": "...",
    "8": "Eventuais divergências numéricas entre fontes foram explicadas?",
    "12": "..."
  },
  "urls_usadas_acumuladas": [
    "https://www.epe.gov.br/pt/publicacoes-dados-abertos/publicacoes/balanco-energetico-nacional"
  ],
  "informacao_coletada_acumulada_integral": [
    {
      "rodada": 1,
      "historiador": "...",
      "cetico": "...",
      "visionario": "...",
      "futurista": "..."
    },
    {
      "rodada": 2,
      "historiador": "...",
      "cetico": "...",
      "visionario": "...",
      "futurista": "..."
    }
  ]
}
```

**Saída do redator:**
```json
{
  "research_id": "123ABC321",
  "ponto_id": 1,
  "relatorio_ponto": "## 1. Composição da Matriz Energética Brasileira\n\nTexto analítico completo e aprofundado...",
  "lacunas_identificadas": "Embora os dados de participação e capacidade instalada tenham sido confirmados, permaneceu uma lacuna quanto à reconciliação metodológica entre os números parciais de curto prazo do ONS e o consolidado anual da EPE (item 8 da auditoria).",
  "urls_citadas": [
    "https://www.epe.gov.br/pt/publicacoes-dados-abertos/publicacoes/balanco-energetico-nacional"
  ]
}
```

---

## 5. Schema do Banco de Dados (PostgreSQL)

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Registro Mestre da Pesquisa
CREATE TABLE research_runs (
    research_id VARCHAR(64) PRIMARY KEY,
    tema TEXT NOT NULL,
    profundidade INT NOT NULL CHECK (profundidade BETWEEN 1 AND 10),
    veracidade_alvo NUMERIC(5,2) NOT NULL,
    max_rodadas_auditoria INT NOT NULL,
    atualidade VARCHAR(32) NOT NULL,
    callback_url TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PROCESSING', -- PROCESSING, COMPLETED, FAILED
    plano_inicial JSONB,
    relatorio_final_consolidado TEXT,
    lacunas_finais_consolidadas JSONB,
    urls_usadas_globais JSONB DEFAULT '[]'::jsonb,
    urls_lidas_globais JSONB DEFAULT '[]'::jsonb,
    urls_nao_usadas_globais JSONB DEFAULT '[]'::jsonb,
    total_prompt_tokens BIGINT DEFAULT 0,
    total_completion_tokens BIGINT DEFAULT 0,
    total_reasoning_tokens BIGINT DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 2. Estado Individual de Cada Ponto (1..N)
CREATE TABLE research_points (
    point_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id VARCHAR(64) NOT NULL REFERENCES research_runs(research_id) ON DELETE CASCADE,
    ponto_id INT NOT NULL,
    enunciado TEXT NOT NULL,
    subperguntas JSONB NOT NULL,
    hipoteses JSONB NOT NULL,
    lacunas_iniciais JSONB NOT NULL,
    perguntas_auditoria JSONB NOT NULL, -- Objeto com chaves "1" a "12"
    ultimo_resultado_auditor JSONB,     -- Objeto booleano {"1": true, ..., "12": false}
    porcentagem_aprovacao NUMERIC(5,2) DEFAULT 0,
    rodada_atual INT NOT NULL DEFAULT 1,
    aprovado BOOLEAN NOT NULL DEFAULT FALSE,
    relatorio_ponto TEXT,
    lacunas_ponto TEXT,
    UNIQUE (research_id, ponto_id)
);

-- 3. Log Imutável de Execuções de Agentes (Telemetria + Histórico Sem Truncamento)
CREATE TABLE agent_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_id VARCHAR(64) NOT NULL REFERENCES research_runs(research_id) ON DELETE CASCADE,
    ponto_id INT,                        -- NULL apenas no Planner global ou consolidador final
    rodada INT NOT NULL DEFAULT 1,
    agent_role VARCHAR(32) NOT NULL,     -- 'planner', 'historiador', 'cetico', 'visionario', 'futurista', 'auditor', 'redator'
    input_prompt_payload JSONB NOT NULL, -- Tudo o que entrou no 1º prompt do agente
    raw_output_payload JSONB NOT NULL,   -- O JSON retornado pelo agente
    informacao_coletada TEXT,            -- Preenchido pelos 4 subagentes buscadores
    reasoning_trace TEXT,                -- Pensamento bruto (<think> / reasoning_content)
    tool_calls JSONB DEFAULT '[]'::jsonb,-- Histórico completo de chamadas de ferramentas e respostas
    urls_usadas JSONB DEFAULT '[]'::jsonb,
    urls_lidas JSONB DEFAULT '[]'::jsonb,
    urls_lidas_nao_usadas JSONB DEFAULT '[]'::jsonb,
    prompt_tokens INT NOT NULL DEFAULT 0,
    completion_tokens INT NOT NULL DEFAULT 0,
    reasoning_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_executions_lookup ON agent_executions (research_id, ponto_id, rodada, agent_role);
```

---

## 6. Query de Hidratação Sem Truncamento (Backend → 1º Prompt)

Para montar o 1º prompt do **Auditor** ou do **Redator** para um `ponto_id`, o backend executa:

```sql
SELECT
    rodada,
    jsonb_object_agg(agent_role, informacao_coletada) AS coletas_da_rodada,
    jsonb_agg(urls_usadas) AS urls_usadas_rodada,
    jsonb_agg(urls_lidas) AS urls_lidas_rodada
FROM agent_executions
WHERE research_id = $1
  AND ponto_id = $2
  AND agent_role IN ('historiador', 'cetico', 'visionario', 'futurista')
GROUP BY rodada
ORDER BY rodada ASC;
```

Essa query garante que `Rodada 1 + Rodada 2 + Rodada 3 + Rodada 4` entrem ordenadas e completas no prompt inicial do agente avaliador/redator em uma única operação de leitura.