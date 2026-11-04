# Hermes Deep Research Pipeline

Motor modular e assíncrono de pesquisa profunda (*Deep Research*) baseado no **Hermes** como núcleo agêntico de planejamento, busca, auditoria e redação.

O sistema opera sob o paradigma de **Estado Acumulativo sem Truncamento (Append-Only Context)** e **Injeção no 1º Prompt via Banco de Dados**, garantindo rastreabilidade total de URLs, raciocínio (*reasoning*), chamadas de ferramentas (*tool calls*) e consumo de tokens.

---

## Visão Geral da Arquitetura

O **Hermes** atua como o cérebro central em todas as pontas do fluxo, enquanto o backend auxiliar gerencia a persistência no banco de dados e a hidratação dos prompts iniciais de cada subagente para evitar estouro de janela de contexto no agente orquestrador pai:

1. **Ingestão Assíncrona:** O backend recebe os parâmetros da pesquisa (`tema`, `profundidade`, `veracidade`, `rondas de auditoria maxima`, `atualidade`, `callback`) e gera um `research_id`.
2. **Hermes Planner:** Realiza uma busca exploratória inicial e decompõe o tema em $N$ pontos (onde $N = \text{profundidade}$, de 1 a 10). Para cada ponto, define `subperguntas`, `hipoteses` e `lacunas`'.
3. **Fan-Out de Subagentes Buscadores:** Cada ponto é pesquisado em paralelo por **4 personas distintas** (`historiador`, `cetico`, `visionario`, `futurista`), totalizando até 40 execuções simultâneas por rodada (e até 160 execuções em 4 rodadas).
4. **Hermes Auditor (Quality Gate):** Recebe no seu 1º prompt **100% da informação acumulada** de todas as rodadas daquele ponto (`R1 + R2 + ... + Rn`) sem truncamento e avalia as **12 perguntas na sua** estritamente com `true` ou `false`.
5. **Loop de Retentativa Determinístico:** O Planner calcula a taxa de aprovação das 12 perguntas frente à meta de `veracidade`. Pontos reprovados voltam para os 4 buscadores na rodada seguinte, recebendo as perguntas `false` como foco e as URLs já lidas como *blacklist*.
6. **Hermes Redator:** Quando o ponto é aprovado (ou atinge o limite de rodadas), o Redator recebe **toda a informação acumulada de todas as rodadas** e o vetor booleano final do Auditor, redigindo o relatório definitivo e documentando explicitamente as **lacunas** que permaneceram abertas.
7. **Webhook Callback:** O resultado consolidado e a telemetria agregada são enviados via POST para a URL de `callback`.

---

## Personas de Busca

| Subagente | Persona | Papel na Coleta |
| :--- | :--- | :--- |
| **Subagente 1** | `historiador` | Aluno curioso focado em contexto histórico, fundamentos, dados basais e esclarecimento exaustivo das subperguntas. |
| **Subagente 2** | `cetico` | Crítico focado em validação cruzada de evidências, verificação de fontes primárias, detecção de vieses e separação entre fato e especulação. |
| **Subagente 3** | `visionario` | Analista focado em conexão de padrões, movimentos de mercado, tendências emergentes e desdobramentos estratégicos. |
| **Subagente 4** | `futurista` | Estrategista de longo prazo focado em cenários prospectivos, impactos sistêmicos, riscos futuros e oportunidades disruptivas. |

---

## Rastreamento de URLs

Cada execução de subagente classifica as fontes consultadas em três categorias:
* **`urls_usadas`**: URLs de onde a informação relevante foi efetivamente extraída para compor a resposta.
* **`urls_lidas`**: Todas as URLs abertas/visitadas durante a execução.
* **`urls_lidas_mas_nao_usadas`**: Calculada automaticamente pelo sistema (`urls_lidas - urls_usadas`), servindo para auditoria de eficiência e bloqueio de releitura nas rodadas subsequentes.

---

## Estrutura Sugerida do Repositório

```text
hermes-deep-research/
├── README.md
├── docs/
│   ├── PRD.md
│   └── SPEC.md
├── src/
│   ├── api/
│   │   └── routes.ts              # Endpoint POST /research e disparo de Webhook
│   ├── orchestrator/
│   │   ├── hermes_client.ts       # Wrapper da API do Hermes (captura reasoning/tokens/tools)
│   │   ├── planner_service.ts     # Loop principal e controle de estado por ponto
│   │   └── prompt_hydrator.ts     # Monta o 1º prompt a partir do banco (R1..Rn sem truncar)
│   ├── prompts/
│   │   ├── planner.md
│   │   ├── subagents.md
│   │   ├── auditor.md
│   │   └── redator.md
│   └── db/
│       ├── schema.sql             # Tabelas PostgreSQL (JSONB)
│       └── repository.ts          # Persistência de execuções e agregação de contexto
└── data/
    └── researches/                # Espelho opcional em JSON por execução para debug local
```
Os 12 critérios (nota = quantos estão APROVADO, 0 a 12).

    clareza_tematica — abordagem objetiva do eixo e aderência às subperguntas do plano.
    corroboracao_canonica — suporte em fontes primárias verificáveis; URL sozinha não é prova.
    atualidade — marcos e dados vigentes para o recorte; marco antigo não é estado atual.
    ausencia_contradicoes — coerência interna entre os dados das personas.
    embasamento_factual — ancoragem empírica; ausência de evidência ≠ falsidade.
    aderencia_escopo — atém-se ao pedido, ao formato e ao público do plano.
    profundidade_analitica — complexidade adequada, incertezas delimitadas.
    precisao_dados — exatidão numérica, métricas, datas e identificadores.
    neutralidade — fatos separados de hipóteses; equilíbrio analítico.
    densidade_evidencias — proporção entre afirmações e URLs efetivamente usadas.
    declaracao_incertezas — lacunas remanescentes expressas e delimitadas.
    solidez_logica — conclusões decorrem das evidências apresentadas.
