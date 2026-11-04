# language: pt
Funcionalidade: Pipeline Modular de Pesquisa Profunda com Hermes (Deep Research)
  Como um sistema consumidor do motor de pesquisa profunda
  Quero submeter um tema com parâmetros rigorosos de profundidade, veracidade e atualidade
  Para receber via webhook um relatório exaustivo, auditado e com rastreabilidade total de fontes e tokens sem truncamento de contexto

  Contexto:
    Dado que o núcleo agêntico "Hermes" está operacional e conectado ao banco de dados PostgreSQL
    E que uma nova requisição de pesquisa é recebida com o seguinte payload:
      """json
      {
        "tema": "matriz energetica no Brasil.",
        "profundidade": 10,
        "veracidade_alvo": 90,
        "max_rodadas_auditoria": 4,
        "atualidade": "24H",
        "callback_url": "https://webhook.callback.com"
      }
      """
    Então o backend deve persistir o registro mestre na tabela "research_runs" com o research_id "123ABC321" e status "PROCESSING"

  Cenário: 01. Decomposição inicial do tema pelo Hermes Planner em N pontos
    Dado que a pesquisa "123ABC321" possui profundidade configurada para 10
    Quando o serviço aciona o "hermes_planner_profile" para realizar a busca exploratória inicial
    Então o Planner deve gerar e salvar no banco um plano contendo exatamente 10 pontos independentes
    E cada ponto deve conter obrigatoriamente:
      | campo               | regra de validação                                         |
      | subperguntas        | lista com no mínimo 3 subperguntas exploratórias           |
      | hipoteses           | lista com no mínimo 3 hipóteses iniciais                   |
      | lacunas_iniciais    | lista com no mínimo 3 lacunas mapeadas                     |
      | perguntas_auditoria | objeto contendo exatamente 12 perguntas numeradas de 1 a 12 |

  Cenário: 02. Disparo paralelo (Fan-Out) dos subagentes buscadores na Rodada 1
    Dado que os 10 pontos da pesquisa "123ABC321" foram criados pelo Planner
    Quando o Planner inicia a Rodada 1 de coleta para todos os 10 pontos em paralelo
    Então o sistema deve instanciar simultaneamente 4 subagentes por ponto totalizando 40 execuções paralelas
    E cada ponto deve ser pesquisado pelas 4 personas distintas:
      | subagente | persona     | limite_queries |
      | 1         | historiador | 3              |
      | 2         | cetico      | 3              |
      | 3         | visionario  | 3              |
      | 4         | futurista   | 3              |
    E o contexto do Hermes Orquestrador pai deve receber apenas o recibo leve de conclusão por referência de ID

  Cenário: 03. Classificação de URLs e cálculo automático de URLs lidas mas não usadas
    Dado que o subagente "historiador" finalizou a coleta do "ponto_1" na Rodada 1
    E retornou as seguintes listas de URLs no seu payload de saída:
      | tipo       | urls                                                                          |
      | urls_lidas  | ["https://epe.gov.br/ben", "https://ons.org.br/dados", "https://blog-antigo.com"] |
      | urls_usadas | ["https://epe.gov.br/ben", "https://ons.org.br/dados"]                        |
    Quando o backend persiste a execução na tabela "agent_executions"
    Então o campo "urls_lidas_nao_usadas" deve ser preenchido automaticamente com:
      """json
      ["https://blog-antigo.com"]
      """

  Cenário: 04. Persistência obrigatória de telemetria completa em cada chamada de agente
    Dado que qualquer agente do ecossistema Hermes ("planner", "historiador", "cetico", "visionario", "futurista", "auditor" ou "redator") executa uma tarefa
    Quando a resposta da API do Hermes retorna ao sistema auxiliar
    Então um registro imutável deve ser salvo na tabela "agent_executions" contendo:
      | coluna               | descrição                                               |
      | input_prompt_payload | JSON integral injetado no 1º prompt do agente           |
      | raw_output_payload   | JSON bruto retornado pelo agente                        |
      | reasoning_trace      | cadeia de raciocínio registrada sem cortes              |
      | tool_calls           | array com todas as queries buscadas e retornos das tools |
      | prompt_tokens        | total exato de tokens de entrada                        |
      | completion_tokens    | total exato de tokens de saída                          |
      | reasoning_tokens     | total exato de tokens gastos em raciocínio              |
      | total_tokens         | soma total de tokens da chamada                         |
      | latency_ms           | tempo total de execução em milissegundos                |

  Cenário: 05. Auditoria booleana de 12 perguntas com injeção no 1º prompt sem truncamento
    Dado que os 4 subagentes ("historiador", "cetico", "visionario", "futurista") finalizaram a Rodada 1 do "ponto_1"
    Quando o Hermes Planner aciona o subagente "auditor" para o "ponto_1"
    Então o sistema auxiliar deve buscar no banco 100% da "informacao_coletada" dos 4 subagentes e injetá-la diretamente no 1º prompt do Auditor sem qualquer resumo ou truncamento
    E o Auditor deve avaliar o conteúdo frente às 12 perguntas do ponto retornando exclusivamente valores booleanos ("true" ou "false") de "1" a "12"
    E o Auditor não deve redigir textos descritivos de lacunas

  Esquema do Cenário: 06. Cálculo de veracidade pelo Planner e decisão de fluxo (Quality Gate)
    Dado que a meta de veracidade da pesquisa "123ABC321" é de 90%
    E que o limite máximo de rodadas de auditoria é 4
    Quando o Auditor do "ponto_1" na tentativa <rodada_atual> retorna <qtd_true> respostas "true" dentre as 12 perguntas
    Então o Planner deve calcular a aprovação em <porcentagem>%
    E definir o status "aprovado" do ponto como <status_aprovado>
    E executar a próxima ação como "<proxima_acao>"

    Exemplos:
      | rodada_atual | qtd_true | porcentagem | status_aprovado | proxima_acao                                 |
      | 1            | 8        | 66.67       | false           | chamar_subagentes_buscadores_rodada_seguinte |
      | 2            | 10       | 83.33       | false           | chamar_subagentes_buscadores_rodada_seguinte |
      | 2            | 11       | 91.67       | true            | chamar_subagente_redator                     |
      | 3            | 12       | 100.00      | true            | chamar_subagente_redator                     |
      | 4            | 9        | 75.00       | false           | encerrar_buscas_por_limite_e_chamar_redator  |

  Cenário: 07. Retentativa de busca com injeção das perguntas reprovadas e blacklist de URLs
    Dado que o "ponto_1" foi reprovado na Rodada 1 com as perguntas "4", "8" e "10" marcadas como "false" pelo Auditor
    E que na Rodada 1 foram lidas 9 URLs no total pelos 4 subagentes
    Quando o Planner dispara os 4 subagentes buscadores para a Rodada 2 do "ponto_1"
    Então o sistema auxiliar deve injetar logo no 1º prompt dos 4 subagentes o enunciado das perguntas "4", "8" e "10" como foco prioritário da rodada
    E deve injetar a lista das 9 URLs já visitadas em "urls_lidas_ignoradas" para impedir releituras

  Cenário: 08. Acúmulo integral de todas as rodadas (R1 + R2 + R3 + R4) na reavaliação do Auditor
    Dado que o "ponto_1" precisou avançar até a Rodada 3 de coleta
    Quando o Auditor é acionado para avaliar a tentativa 3 do "ponto_1"
    Então o 1º prompt do Auditor deve conter obrigatoriamente a soma integral sem truncamento de:
      | bloco_historico | conteúdo incluído                                                            |
      | Rodada 1        | textos completos de historiador, cetico, visionario e futurista da Rodada 1 |
      | Rodada 2        | textos completos de historiador, cetico, visionario e futurista da Rodada 2 |
      | Rodada 3        | textos completos de historiador, cetico, visionario e futurista da Rodada 3 |
    E nenhuma informação coletada em rodadas reprovadas anteriormente pode ser descartada

  Cenário: 09. Síntese pelo Redator com contexto acumulado total e escrita das lacunas
    Dado que o "ponto_1" encerrou a fase de auditoria na Rodada 3 com 11 perguntas "true" e a pergunta "8" como "false"
    Quando o Planner aciona o subagente "redator" para o "ponto_1"
    Então o sistema auxiliar deve injetar no 1º prompt do Redator 100% das informações coletadas nas Rodadas 1, 2 e 3 sem truncamento
    E deve injetar o vetor booleano final do Auditor indicando que a pergunta "8" permaneceu "false"
    E o Redator deve produzir o texto analítico completo citando apenas as "urls_usadas"
    E o Redator deve redigir explicitamente a seção de "lacunas_identificadas" detalhando o que faltou na pergunta "8"

  Cenário: 10. Consolidação dos 10 pontos e disparo do Webhook de Callback
    Dado que todos os 10 pontos da pesquisa "123ABC321" finalizaram a etapa do Redator
    Quando o serviço consolida os relatórios, as lacunas escritas pelo Redator e soma a telemetria global do banco
    Então o status da pesquisa na tabela "research_runs" deve ser atualizado para "COMPLETED"
    E o sistema deve enviar uma requisição HTTP POST para "https://webhook.callback.com" contendo:
      | chave_payload            | origem dos dados                                                         |
      | research_id              | "123ABC321"                                                              |
      | relatorio_final           | concatenação estruturada dos relatórios dos 10 pontos                    |
      | lacunas_finais            | consolidação de todas as lacunas redigidas pelo Redator em cada ponto     |
      | urls_usadas               | união deduplicada de todas as URLs efetivamente citadas                   |
      | urls_lidas                | união deduplicada de todas as URLs abertas durante a pesquisa             |
      | urls_lidas_nao_usadas     | diferença exata entre "urls_lidas" e "urls_usadas"                        |
      | metricas_tokens           | soma total de prompt_tokens, completion_tokens e reasoning_tokens do run |