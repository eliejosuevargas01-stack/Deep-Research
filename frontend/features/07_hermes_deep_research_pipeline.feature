# language: pt
Funcionalidade: Pipeline Modular de Pesquisa Profunda com Hermes (Deep Research)
  Como um sistema consumidor do motor de pesquisa profunda
  Quero submeter um tema com parâmetros rigorosos de profundidade, veracidade, atualidade e modelos por subagente no Hermes
  Para que o Hermes execute toda a varredura web, delegação de até 40 subagentes simultâneos, auditoria e redação sem chamadas externas fora do Hermes e sem truncamento de contexto

  Contexto:
    Dado que o núcleo agêntico "Hermes" está operacional com o perfil "deep-research" e conectado ao banco de dados
    E que o arquivo "config.yaml" do perfil Hermes está configurado com "delegation.backend: por_papel" e "max_concurrent_children: 40"
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
    Então o backend deve criar um workspace isolado exclusivo para a pesquisa "123ABC321" sem acesso a pesquisas anteriores
    E deve persistir o registro mestre na tabela "research_runs" com o research_id "123ABC321" e status "PROCESSING"
    E o backend não deve realizar nenhuma chamada HTTP direta a APIs externas de LLM ou busca fora do Hermes

  Cenário: 01. Varredura exploratória inicial na web e decomposição do tema pelo Hermes Planner em N pontos
    Dado que a pesquisa "123ABC321" possui profundidade configurada para 10
    Quando o backend aciona unicamente o Hermes no papel "planner" para iniciar a pesquisa
    Então o Planner no Hermes deve realizar uma busca exploratória simples na web abrindo as páginas necessárias apenas para coletar contexto basal sobre o tema
    E deve gerar e salvar no banco um plano contendo exatamente 10 pontos independentes (de 1 a 10)
    E cada ponto deve conter obrigatoriamente:
      | campo               | regra de validação                                         |
      | subperguntas        | lista com no mínimo 3 subperguntas exploratórias           |
      | hipoteses           | lista com no mínimo 3 hipóteses iniciais                   |
      | lacunas_iniciais    | lista com no mínimo 3 lacunas mapeadas                     |
      | perguntas_auditoria | objeto contendo exatamente 12 perguntas numeradas de 1 a 12 |

  Cenário: 02. Disparo paralelo (Fan-Out) de até 40 subagentes buscadores simultâneos no Hermes na Rodada 1
    Dado que os 10 pontos da pesquisa "123ABC321" foram criados pelo Planner
    E que não existe limite artificial de 3 pontos paralelos no sistema
    Quando o Hermes inicia a Rodada 1 de coleta para todos os 10 pontos em paralelo
    Então o Hermes deve instanciar simultaneamente 4 subagentes por ponto totalizando 40 execuções paralelas ("max_concurrent_children: 40")
    E cada ponto deve ser pesquisado pelas 4 personas distintas recebendo no 1º prompt o tema, a atualidade "24H", o enunciado, as subperguntas, as hipóteses e as lacunas iniciais:
      | subagente | persona     | limite_queries |
      | 1         | historiador | 3              |
      | 2         | cetico      | 3              |
      | 3         | visionario  | 3              |
      | 4         | futurista   | 3              |
    E o contexto do Hermes Orquestrador pai deve receber apenas o recibo leve de conclusão por referência de ID

  Cenário: 03. Classificação de URLs e cálculo automático de URLs lidas mas não usadas
    Dado que o subagente "historiador" no Hermes finalizou a coleta do "ponto_1" na Rodada 1
    E retornou as seguintes listas de URLs válidas no seu payload de saída:
      | tipo        | urls                                                                          |
      | urls_lidas  | ["https://epe.gov.br/ben", "https://ons.org.br/dados", "https://blog-antigo.com"] |
      | urls_usadas | ["https://epe.gov.br/ben", "https://ons.org.br/dados"]                        |
    Quando o backend persiste a execução na tabela "agent_executions"
    Então o campo "urls_lidas_nao_usadas" deve ser preenchido automaticamente com:
      """json
      ["https://blog-antigo.com"]
      """

  Cenário: 04. Persistência obrigatória de telemetria real de todas as sessões do Hermes (Agente Principal e Subagentes)
    Dado que qualquer agente do ecossistema Hermes ("planner", "historiador", "cetico", "visionario", "futurista", "auditor" ou "redator") executa uma tarefa
    Quando a execução do agente ou subagente no Hermes é concluída
    Então um registro imutável deve ser salvo na tabela "agent_executions" com os dados reais extraídos da sessão do Hermes contendo:
      | coluna               | descrição                                                               |
      | model_used           | modelo efetivamente usado pelo papel segundo o config.yaml do Hermes    |
      | input_prompt_payload | JSON integral injetado no 1º prompt do agente                           |
      | raw_output_payload   | JSON bruto retornado pelo agente                                        |
      | reasoning_trace      | cadeia de raciocínio registrada sem cortes                              |
      | tool_calls           | array com todas as queries buscadas e páginas abertas no Hermes         |
      | prompt_tokens        | total exato de tokens de entrada da sessão daquele agente/subagente     |
      | completion_tokens    | total exato de tokens de saída da sessão daquele agente/subagente       |
      | reasoning_tokens     | total exato de tokens gastos em raciocínio                              |
      | total_tokens         | soma total de tokens da chamada                                         |
      | latency_ms           | tempo total de execução em milissegundos                                |

  Cenário: 05. Auditoria booleana de 12 perguntas com injeção no 1º prompt sem truncamento
    Dado que os 4 subagentes ("historiador", "cetico", "visionario", "futurista") finalizaram a Rodada 1 do "ponto_1"
    Quando o Hermes aciona o subagente "auditor" para o "ponto_1"
    Então o backend deve buscar no banco 100% da "informacao_coletada" dos 4 subagentes e injetá-la diretamente no 1º prompt do Auditor junto com a atualidade "24H" sem qualquer resumo ou truncamento
    E o Auditor deve avaliar o conteúdo frente às 12 perguntas do ponto retornando exclusivamente valores booleanos ("true" ou "false") de "1" a "12"
    E o Auditor não deve redigir textos descritivos de lacunas

  Esquema do Cenário: 06. Cálculo de veracidade e decisão de fluxo (Quality Gate)
    Dado que a meta de veracidade da pesquisa "123ABC321" é de 90%
    E que o limite máximo de rodadas de auditoria é 4
    Quando o Auditor do "ponto_1" na tentativa <rodada_atual> retorna <qtd_true> respostas "true" dentre as 12 perguntas
    Então o sistema deve calcular a aprovação em <porcentagem>%
    E definir o status "aprovado" do ponto como <status_aprovado>
    E executar a próxima ação no Hermes como "<proxima_acao>"

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
    Quando o Hermes dispara os 4 subagentes buscadores para a Rodada 2 do "ponto_1"
    Então o backend deve injetar logo no 1º prompt dos 4 subagentes o enunciado das perguntas "4", "8" e "10" em "perguntas_auditoria_pendentes" como foco prioritário da rodada
    E deve injetar a lista das 9 URLs já visitadas em "urls_lidas_ignoradas" para impedir releituras

  Cenário: 08. Acúmulo integral de todas as rodadas (R1 + R2 + R3 + R4) na reavaliação do Auditor
    Dado que o "ponto_1" precisou avançar até a Rodada 3 de coleta
    Quando o Auditor no Hermes é acionado para avaliar a tentativa 3 do "ponto_1"
    Então o 1º prompt do Auditor deve conter obrigatoriamente a soma integral sem truncamento de:
      | bloco_historico | conteúdo incluído                                                            |
      | Rodada 1        | textos completos de historiador, cetico, visionario e futurista da Rodada 1 |
      | Rodada 2        | textos completos de historiador, cetico, visionario e futurista da Rodada 2 |
      | Rodada 3        | textos completos de historiador, cetico, visionario e futurista da Rodada 3 |
    E nenhuma informação coletada em rodadas reprovadas anteriormente pode ser descartada

  Cenário: 09. Síntese pelo Redator com contexto acumulado total e escrita das lacunas
    Dado que o "ponto_1" encerrou a fase de auditoria na Rodada 3 com 11 perguntas "true" e a pergunta "8" como "false"
    Quando o Hermes aciona o subagente "redator" para o "ponto_1"
    Então o backend deve injetar no 1º prompt do Redator 100% das informações coletadas nas Rodadas 1, 2 e 3 sem truncamento
    E deve injetar o vetor booleano final do Auditor indicando que a pergunta "8" permaneceu "false"
    E o Redator deve produzir o texto analítico completo citando apenas URLs presentes em "urls_usadas_acumuladas"
    E o Redator deve redigir explicitamente a seção de "lacunas_identificadas" detalhando o que faltou na pergunta "8"

  Cenário: 10. Consolidação dos 10 pontos e disparo do Webhook de Callback
    Dado que todos os 10 pontos da pesquisa "123ABC321" finalizaram a etapa do Redator no Hermes
    Quando o serviço consolida os relatórios, as lacunas escritas pelo Redator e soma a telemetria global real do Hermes no banco
    Então o status da pesquisa na tabela "research_runs" deve ser atualizado para "COMPLETED"
    E o sistema deve enviar uma requisição HTTP POST para "https://webhook.callback.com" contendo:
      | chave_payload         | origem dos dados                                                                              |
      | research_id           | "123ABC321"                                                                                   |
      | relatorio_final       | concatenação estruturada dos relatórios dos 10 pontos                                         |
      | lacunas_finais        | consolidação de todas as lacunas redigidas pelo Redator em cada ponto                         |
      | urls_usadas           | união deduplicada de todas as URLs efetivamente citadas                                       |
      | urls_lidas            | união deduplicada de todas as URLs abertas durante a pesquisa                                 |
      | urls_lidas_nao_usadas | diferença exata entre "urls_lidas" e "urls_usadas"                                            |
      | metricas_tokens       | soma total real de prompt_tokens, completion_tokens e reasoning_tokens (pai + subagentes)     |

  Cenário: 11. Configuração dinâmica do config.yaml do Hermes e modelos por subagente via endpoint
    Dado que o administrador envia uma requisição PUT para o endpoint de configuração "/config" (ou "/api/v1/settings") com:
      """json
      {
        "base_url": "http://9router:20128/v1",
        "api_key": "sk-hermes-key",
        "default_model": "deepseek/deepseek-v3.2",
        "max_concurrent_children": 40,
        "modelos_por_papel": {
          "planner": "deepseek/deepseek-v3.2",
          "historiador": "gemini/gemini-3.5-flash-lite",
          "cetico": "deepseek/deepseek-v3.2",
          "visionario": "gemini/gemini-3.5-flash-lite",
          "futurista": "gemini/gemini-3.5-flash-lite",
          "auditor": "ocg/deepseek-v4.1-flash",
          "redator": "ocg/deepseek-v4.1-flash"
        }
      }
      """
    Quando o backend aplica as configurações
    Então o arquivo "config.yaml" do perfil Hermes deve ser atualizado com "delegation.backend: por_papel" e "max_concurrent_children: 40"
    E cada subagente delegado pelo Hermes durante a pesquisa deve ser executado utilizando exatamente o modelo atribuído ao seu papel
