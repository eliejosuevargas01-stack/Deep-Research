# PRD — Hermes Deep Research Pipeline

**Versão:** 1.1  
**Status:** Aprovado para Implementação  
**Core Engine:** Hermes  

---

## 1. Objetivo do Produto

Construir um pipeline automatizado e auditável de pesquisa profunda capaz de investigar qualquer tema em múltiplos níveis de profundidade (1 a 10 pontos simultâneos), utilizando múltiplas perspectivas cognitivas (Historiador, Cético, Visionário e Futurista), validação rigorosa por checklist booleano (Auditor de 12 perguntas) e síntese exaustiva (Redator) sem perda ou truncamento de contexto entre rodadas.

---

## 2. Parâmetros de Entrada do Usuário

O sistema é acionado via requisição assíncrona contendo:

- `tema` (`string`, obrigatório): assunto central da pesquisa.
- `profundidade` (`int`, 1 a 10): quantidade de pontos estruturais em que o tema será decomposto.
- `veracidade_alvo` (`int` ou `float`, 0 a 100): percentual mínimo de respostas `true` exigidas para aprovação de um ponto.
- `max_rodadas_auditoria` (`int`, 1 a 10, padrão 4): máximo de ciclos de busca + auditoria permitidos por ponto.
- `atualidade` (`string`): janela temporal prioritária para os dados, como `24H`, `7D`, `1Y` e `ALL`.
- `callback_url` (`string`, URL): endpoint webhook que receberá o payload final quando a pesquisa terminar.

> Convenção canônica: os campos do payload de entrada e dos contratos internos devem usar os nomes acima, sem variações.

---

## 3. Contratos Canônicos de Entrada e Saída

### 3.1. Entrada do usuário

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

### 3.2. Saída do planner

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

## 4. Requisitos Funcionais (RF)

### RF01 — Decomposição Inicial pelo Planner
O planner deve gerar um plano contendo exatamente `N` pontos, sendo `N = profundidade`. Cada ponto deve conter:

- `ponto_id`
- `enunciado`
- `subperguntas` (mínimo 3)
- `hipoteses` (mínimo 3)
- `lacunas_iniciais` (mínimo 3)
- `perguntas_auditoria` (12 chaves, de `1` a `12`)

### RF02 — Coleta Paralela Multi-Persona por Ponto
Para cada ponto em aberto, o sistema deve instanciar simultaneamente 4 subagentes (`historiador`, `cetico`, `visionario`, `futurista`), cada um limitado a `max_queries: 3` por rodada.

### RF03 — Acúmulo Integral de Contexto (Zero Truncamento)
Toda informação coletada em uma rodada deve ser salva integralmente no banco de dados. Quando houver retentativas (rodada 2, 3, 4), as informações anteriores nunca devem ser descartadas ou resumidas.

- O auditor da rodada `K` recebe `informacao_coletada_acumulada = R1 + R2 + ... + RK`.
- O redator recebe `informacao_coletada_acumulada_integral = R1 + R2 + ... + RN`.

### RF04 — Auditoria Booleana de 12 Perguntas
O subagente auditor deve retornar um objeto JSON com mapeamento do índice da pergunta para `true` ou `false`.

### RF05 — Cálculo de Veracidade e Loop de Retentativa
O planner avalia o retorno do auditor por ponto:

$$
\text{taxa\_aprovacao} = \left( \frac{\text{quantidade de respostas true}}{12} \right) \times 100
$$

- Se `taxa_aprovacao >= veracidade_alvo`, o ponto é aprovado.
- Se `taxa_aprovacao < veracidade_alvo` e `tentativa_atual < max_rodadas_auditoria`, o ponto entra em nova rodada.
- Se `tentativa_atual == max_rodadas_auditoria`, o processo é encerrado para aquele ponto e ele segue para o redator.

### RF06 — Direcionamento Inteligente nas Retentativas
A partir da rodada 2, o primeiro prompt dos subagentes buscadores deve incluir:

1. a lista de perguntas com resposta `false` da rodada anterior;
2. a lista acumulada de `urls_lidas` daquele ponto para evitar releitura.

### RF07 — Redação Final e Documentação de Lacunas
O redator é o único responsável por escrever as lacunas textuais finais e o relatório analítico completo, com citações para `urls_usadas`.

### RF08 — Notificação via Webhook Callback
Ao finalizar a redação de todos os pontos, o sistema atualiza o registro principal para `COMPLETED` e dispara um POST HTTP para `callback_url` com o relatório consolidado, lacunas, URLs e métricas de execução.

---

## 5. Requisitos Não-Funcionais (RNF)

- **RNF01 — Persistência e Telemetria Total:** cada chamada ao Hermes gera um registro imutável com payload de entrada, resposta bruta, reasoning, tool calls, tokens e latency.
- **RNF02 — Passagem por Referência no Orquestrador:** textos longos ficam no banco e são injetados no 1º prompt do auditor e redator.
- **RNF03 — Isolamento de Falhas por Ponto:** falha de um subagente não derruba os demais.

---

## 6. Métricas de Sucesso

1. Integridade de contexto: 100% dos bytes da rodada acumulada presentes no prompt do auditor e do redator.
2. Eficiência de re-busca: 0% de URLs repetidas em `urls_lidas` durante retentativas.
3. Cobertura de telemetria: 100% das chamadas registradas com contagem de tokens e reasoning.