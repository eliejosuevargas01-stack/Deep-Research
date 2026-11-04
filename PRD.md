# PRD — Hermes Deep Research Pipeline

**Versão:** 1.2  
**Status:** Aprovado para Implementação  
**Core Engine:** Hermes (`hermes-agent` com perfil `deep-research` e delegação `por_papel`)  

---

## 1. Objetivo do Produto

Construir um pipeline automatizado, isolado e auditável de pesquisa profunda onde o **Hermes** é o único motor de execução agêntica, pesquisa web e delegação de subagentes. O sistema investiga qualquer tema em múltiplos níveis de profundidade (1 a 10 pontos simultâneos), utilizando varredura exploratória inicial pelo Planner, coleta paralela em 4 perspectivas cognitivas (`historiador`, `cetico`, `visionario` e `futurista` — até **40 subagentes simultâneos** por rodada), validação rigorosa por checklist booleano (`auditor` de 12 perguntas) e síntese exaustiva (`redator`) sem perda ou truncamento de contexto entre rodadas.

### Princípios Arquiteturais Inegociáveis

1. **Zero Chamadas Diretas a APIs Externas pelo Backend:** O backend auxiliar **não** faz chamadas HTTP diretas a provedores de LLM (`/chat/completions`) nem a serviços externos de busca. O backend chama **unicamente o Hermes** e acompanha sua execução, persistindo os artefatos, o histórico e a telemetria no banco de dados.
2. **Hermes Faz Todo o Trabalho Pesado:** Toda busca na web (`web_search`), abertura e extração de páginas (`web_extract`), raciocínio, orquestração e delegação de subagentes (`delegate_task`) ocorrem integralmente dentro do runtime do Hermes.
3. **Sem Limite Artificial de 3 Pontos Paralelos (`max_concurrent_children: 40`):** Todos os `N` pontos do plano (`1..10`) rodam em paralelo sem trava de 3 pontos. Na fase de busca, o Hermes pode despachar até **40 subagentes simultâneos** (`10 pontos × 4 personas`) por rodada, com `max_concurrent_children: 40` e `oneshot_max_children: 0` no `config.yaml` do perfil Hermes.
4. **Configuração Total do Hermes via Endpoint (`config.yaml`):** Todas as configurações do perfil Hermes — credenciais do provedor (`base_url`, `api_key`), limites de delegação e a escolha do **modelo específico de cada subagente** (`planner`, `historiador`, `cetico`, `visionario`, `futurista`, `auditor`, `redator`) — são lidas e modificadas diretamente no `config.yaml` do Hermes por meio do endpoint de configurações do sistema (`GET /config` e `PUT /config` / `/api/v1/settings`).
5. **Isolamento Estrito por Pesquisa:** Cada pesquisa executa em seu próprio workspace exclusivo. O Hermes tem acesso permitido unicamente aos arquivos e ao contexto da pesquisa em andamento, sem jamais ler ou reutilizar relatórios de execuções anteriores.

---

## 2. Parâmetros de Entrada do Usuário

O sistema é acionado via requisição assíncrona contendo:

- `tema` (`string`, obrigatório): assunto central da pesquisa.
- `profundidade` (`int`, 1 a 10): quantidade de pontos estruturais em que o tema será decomposto e investigado simultaneamente.
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

### 3.2. Saída do planner (após varredura exploratória inicial no Hermes)

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

### RF01 — Varredura Exploratória Inicial e Decomposição pelo Planner no Hermes
Ao iniciar a pesquisa, o agente principal **Planner** no Hermes realiza uma **busca exploratória inicial na web** (`web_search` e abertura livre das páginas necessárias via `web_extract`) com a finalidade exclusiva de levantar contexto real e atualizado sobre o tema antes de estruturar o plano. Em seguida, gera um plano contendo exatamente `N` pontos (`N = profundidade`, de 1 a 10), onde cada ponto contém obrigatoriamente:

- `ponto_id` (sequencial de `1` a `N`)
- `enunciado`
- `subperguntas` (mínimo 3)
- `hipoteses` (mínimo 3)
- `lacunas_iniciais` (mínimo 3)
- `perguntas_auditoria` (12 chaves, de `"1"` a `"12"`)

### RF02 — Fan-Out Paralelo Multi-Persona no Hermes (Até 40 Subagentes Simultâneos)
Não há limite de 3 pontos paralelos. Para todos os `N` pontos em aberto (`1..10`), o Hermes instancia simultaneamente os 4 subagentes buscadores (`historiador`, `cetico`, `visionario`, `futurista`), alcançando até **40 subagentes simultâneos** por rodada (`max_concurrent_children: 40`), cada um realizando até `max_queries: 3` buscas na rodada e abrindo as páginas relevantes para extrair evidências densas.

### RF03 — Acúmulo Integral de Contexto (Zero Truncamento)
Toda informação coletada em uma rodada é salva integralmente no banco de dados. Quando houver retentativas (rodada 2, 3, 4), as informações anteriores nunca são descartadas ou resumidas:

- O subagente `auditor` da rodada `K` recebe no seu 1º prompt `informacao_coletada_acumulada = R1 + R2 + ... + RK`, além de `atualidade` e `perguntas_auditoria`.
- O subagente `redator` recebe no seu 1º prompt `informacao_coletada_acumulada_integral = R1 + R2 + ... + RN`, `urls_usadas_acumuladas` e `resultado_final_auditor`.

### RF04 — Auditoria Booleana de 12 Perguntas
O subagente `auditor` no Hermes avalia o material acumulado frente às 12 perguntas do ponto e à janela de `atualidade`, retornando estritamente um objeto JSON com o mapeamento das chaves `"1"` a `"12"` para `true` ou `false`.

### RF05 — Cálculo de Veracidade e Loop de Retentativa
O sistema avalia o retorno do auditor por ponto:

$$
\text{taxa\_aprovacao} = \left( \frac{\text{quantidade de respostas true}}{12} \right) \times 100
$$

- Se `taxa_aprovacao >= veracidade_alvo`, o ponto é aprovado e segue para o `redator`.
- Se `taxa_aprovacao < veracidade_alvo` e `tentativa_atual < max_rodadas_auditoria`, o ponto entra em nova rodada de busca no Hermes.
- Se `tentativa_atual == max_rodadas_auditoria`, as buscas são encerradas para aquele ponto e ele segue para o `redator` com o registro das perguntas que permaneceram `false`.

### RF06 — Direcionamento Inteligente nas Retentativas
Na Rodada 1, o 1º prompt de cada subagente buscador recebe `tema`, `atualidade`, `ponto_enunciado`, `subperguntas`, `hipoteses` e `lacunas_iniciais`. A partir da Rodada 2, recebe também:

1. `perguntas_auditoria_pendentes`: dicionário contendo apenas as perguntas que receberam `false` na rodada anterior como alvo prioritário;
2. `urls_lidas_ignoradas`: lista acumulada de todas as `urls_lidas` daquele ponto nas rodadas anteriores para bloquear releituras.

### RF07 — Redação Final e Documentação de Lacunas
O subagente `redator` no Hermes é o único responsável por escrever o relatório analítico completo do ponto (`relatorio_ponto`) e as lacunas textuais finais (`lacunas_identificadas`), citando exclusivamente URLs presentes em `urls_usadas_acumuladas`.

### RF08 — Notificação via Webhook Callback
Ao finalizar a redação de todos os `N` pontos, o sistema consolida os relatórios na ordem `1..N`, calcula as listas globais deduplicadas de URLs (`urls_usadas`, `urls_lidas`, `urls_lidas_nao_usadas`), soma a telemetria real de tokens de todas as sessões do Hermes (agente principal + subagentes), atualiza o registro principal para `COMPLETED` e dispara um POST HTTP para `callback_url`.

### RF09 — Gestão Dinâmica do `config.yaml` do Hermes e Modelos por Subagente via API
O sistema deve fornecer um endpoint de configuração (`GET /config` e `PUT /config`, com alias `/api/v1/settings`) que lê e atualiza diretamente o arquivo `config.yaml` do perfil Hermes (`hermes_home/profiles/deep-research/config.yaml`), permitindo configurar em tempo de execução:

- Credenciais e endpoint do provedor no Hermes (`model.base_url`, `model.api_key`, `model.default`);
- Modelo individual de cada papel/subagente via `delegation.backend: por_papel` (`planner`, `historiador`, `cetico`, `visionario`, `futurista`, `auditor`, `redator`);
- Parâmetros de concorrência de delegação do Hermes (`max_concurrent_children: 40`, `max_spawn_depth: 2`, `oneshot_max_children: 0`).

---

## 5. Requisitos Não-Funcionais (RNF)

- **RNF01 — Telemetria Real do Hermes (Pai + Subagentes):** cada execução do agente principal e dos subagentes delegados no Hermes tem seu consumo real de tokens (`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `total_tokens`), `reasoning_trace`, `tool_calls` e `latency_ms` extraídos das sessões/logs do Hermes (`state.db` / workspace da pesquisa) e persistidos de forma imutável na tabela `agent_executions`.
- **RNF02 — Passagem por Referência e Hidratação pelo Banco:** textos longos ficam no banco de dados e são injetados diretamente no 1º prompt de cada subagente do Hermes sem sobrecarregar o contexto do orquestrador pai.
- **RNF03 — Isolamento de Falhas e de Workspace:** a falha de uma persona não derruba as demais do mesmo ponto, e o processo Hermes de uma pesquisa é estritamente confinado ao diretório da pesquisa atual.

---

## 6. Métricas de Sucesso

1. **Integridade de contexto:** 100% dos bytes coletados nas rodadas `1..K` presentes no 1º prompt do auditor e do redator.
2. **Escala real de delegação:** capacidade de executar até 40 subagentes buscadores simultâneos (`10 pontos × 4 personas`) no Hermes sem fila artificial de 3 pontos.
3. **Eficiência de re-busca:** 0% de URLs repetidas em `urls_lidas` durante retentativas.
4. **Fidelidade de configuração e telemetria:** 100% dos subagentes rodando com o modelo configurado para o seu papel no `config.yaml` do Hermes e 100% dos tokens reais (agente principal + subagentes) contabilizados no banco.
