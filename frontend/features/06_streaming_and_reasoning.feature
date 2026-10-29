# language: pt
Funcionalidade: Streaming em Tempo Real e Feed de Raciocínio dos Agentes
  Como um pesquisador analítico acompanhando a investigação
  Quero visualizar a deliberação dos agentes e personas em tempo real com indicador de pulso, filtros e expansão
  Para auditar a profundidade metodológica e acompanhar a fundamentação contínua da pesquisa

  Cenário: Conexão SSE e ativação do indicador pulsante em tempo real
    Dado que acesso a aplicação no dispositivo "desktop"
    E planejo uma pesquisa para o tema "Impacto da Inteligência Artificial na Matriz Energética"
    Quando o canal de streaming SSE é iniciado para a pesquisa ativa
    Então devo ver o indicador pulsante em tempo real ativo com a classe pulse-violet
    E o indicador pulsante deve indicar atividade dos agentes em tempo real
    E uma captura de tela do indicador pulsante ativo deve ser salva no diretório de evidências

  Cenário: Streaming de raciocínios das personas de busca e parecer do auditor em cards expansíveis
    Dado que a conexão de streaming está ativa para a pesquisa em andamento
    Quando o pipeline transmite raciocínios de busca e parecer da auditoria
    Então devo ver os cartões de raciocínio renderizados no feed
    E cada cartão deve exibir o crachá do agente e o título da deliberação
    E devo conseguir recolher e expandir o conteúdo de um cartão de raciocínio ao clicar no cabeçalho
    E uma captura de tela dos cartões de raciocínio expansíveis deve ser salva no diretório de evidências

  Cenário: Filtro dos cartões de raciocínio por agente/persona através dos chips interativos
    Dado que o feed de raciocínio possui deliberações de busca e auditoria registradas
    Quando seleciono o chip de filtro de "Personas de Busca"
    Então apenas os cartões das personas de busca devem estar visíveis no feed
    Quando seleciono o chip de filtro de "Auditor"
    Então apenas os pareceres do auditor analítico devem estar visíveis no feed
    Quando seleciono o chip de filtro "Todos"
    Então todos os cartões de raciocínio devem voltar a ficar visíveis
    E os contadores dos chips devem corresponder ao total de deliberações por agente
    E uma captura de tela do filtro por chips deve ser salva no diretório de evidências

  Cenário: Interação com controles de rolagem e cópia do raciocínio para o clipboard
    Dado que o feed de raciocínio possui deliberações analíticas detalhadas
    Quando clico no botão de auto-rolagem do feed
    Então o botão de auto-rolagem deve indicar o estado pausado
    Quando clico novamente no botão de auto-rolagem do feed
    Então o botão de auto-rolagem deve retornar ao estado ativo
    Quando clico no botão de copiar o raciocínio de um cartão
    Então o texto da deliberação analítica deve ser gravado na área de transferência
    E o botão de cópia deve exibir a confirmação visual
    E uma captura de tela dos controles de rolagem e cópia deve ser salva no diretório de evidências

  Cenário: Conclusão do streaming com entrega do dossiê final e preservação do feed de reasoning
    Dado que a conexão de streaming está ativa com deliberações analíticas registradas
    Quando o pipeline transmite o relatório final concluído com o dossiê completo
    Então devo ver o relatório do dossiê analítico entregue com sucesso
    E o feed de raciocínio com todos os cartões anteriores deve permanecer preservado e acessível
    E o indicador pulsante deve transicionar para o estado ocioso
    E uma captura de tela da conclusão do streaming com dossiê e feed preservado deve ser salva no diretório de evidências

  Cenário: Tratamento de erro terminal do pipeline com encerramento seguro da conexão SSE
    Dado que a conexão de streaming está ativa para a pesquisa em andamento
    Quando o pipeline transmite um evento de erro fatal no stream
    Então devo ver o banner de alerta exibindo a mensagem descritiva do erro terminal
    E o indicador pulsante deve estar em estado ocioso
    E as opções de reinício e recuperação devem estar acessíveis
    E uma captura de tela do tratamento de erro terminal deve ser salva no diretório de evidências
