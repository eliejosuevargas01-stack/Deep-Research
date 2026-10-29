# language: pt
Funcionalidade: Controle de Auditoria e Tratamento de Falhas
  Como sistema de alta confiabilidade
  Quero garantir que nenhum relatório seja redigido sem prévia aprovação na auditoria
  Para apresentar diagnósticos claros, rotulagem temporal fidedigna e recuperação específica em caso de falhas

  Cenário: Bloqueio estrito da redação quando a auditoria reprova os pontos
    Dado que planejei uma pesquisa para o tema "Investigação com Dados Fracos"
    Quando a auditoria retorna parecer reprovado com 10 de 12 critérios
    E clico no botão "Iniciar pesquisa"
    Então a etapa de auditoria deve indicar reprovação dos pontos
    E o endpoint do redator nunca deve ser chamado
    E devo ver a notificação de bloqueio da investigação na auditoria
    E devo ter a opção de formular um novo tema

  Cenário: Rotulagem temporal honesta do ciclo 1 durante nova busca no ciclo 2
    Dado que planejei uma pesquisa para o tema "Investigação Iterativa Multi-Ciclo"
    Quando a primeira auditoria reprova e o sistema avança para nova busca no ciclo 2
    Então o cabeçalho da auditoria deve indicar "Auditoria do ciclo 1 — revisão em andamento no ciclo 2"
    E devo ver o banner contextual explicando que a nova busca busca enriquecer evidências
    E devo ver a lista estruturada de critérios reprovados com lacunas e correções
    E o registro técnico completo deve estar acessível sob o bloco colapsável

  Cenário: Tratamento de erro 500 do servidor durante o planejamento
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando submeto um tema que gera erro interno no servidor
    Então devo ver um banner de alerta exibindo a mensagem descritiva do erro
    E a interface não deve quebrar ou expor segredos

  Cenário: Captura de tela da falha na auditoria em dispositivo móvel
    Dado que acesso a aplicação no dispositivo "mobile"
    E a auditoria retorna parecer reprovado com 10 de 12 critérios
    Quando submeto o tema "Investigação Mobile com Falha"
    E clico no botão "Iniciar pesquisa"
    Então devo ver a notificação de bloqueio da investigação na auditoria

  Cenário: Tratamento de erro 422 com objeto de detalhe estruturado
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando submeto um tema que retorna objeto 422 com mensagem e pergunta de esclarecimento
    Então o banner de erro deve exibir a mensagem e a pergunta de esclarecimento extraídas

  Cenário: Redator retornando 200 com status incompleto ou dossiê vazio não é considerado sucesso
    Dado que planejei uma pesquisa para o tema "Investigação Incompleta"
    Quando o redator retorna resposta 200 com status "incompleto" e sem texto
    E clico no botão "Iniciar pesquisa"
    Então o sistema não deve marcar a pesquisa como concluída
    E devo ver a indicação de falha com o diagnóstico retornado

  Cenário: Recuperação e retentativa sensível ao estágio após falha de timeout
    Dado que a busca web retorna falha por tempo limite
    Quando clico no botão "Iniciar pesquisa"
    Então devo ver a indicação de tempo limite excedido
    E devo ver a opção de tentar busca e auditoria novamente

  Cenário: Retentativa sensível ao estágio após busca com sucesso e erro HTTP 504 na auditoria
    Dado que a busca web tem sucesso mas a primeira auditoria falha com erro 504
    Quando clico no botão "Iniciar pesquisa"
    Então devo ver a indicação de falha na execução
    E devo ver a opção de "Tentar auditoria novamente"
    Quando clico no botão de retentativa
    Então a etapa de auditoria deve ser executada sem repetir a busca web
    E o redator deve ser chamado somente após a aprovação da auditoria

  Cenário: Retentativa específica do redator após auditoria aprovada
    Dado que a auditoria aprovou os pontos mas o redator falha com erro 500
    Quando clico no botão "Iniciar pesquisa"
    Então devo ver a indicação de falha no redator
    E devo ver a opção de "Tentar redigir dossiê novamente"
    Quando clico no botão de retentativa
    Então apenas o endpoint do redator deve ser chamado novamente

  Cenário: Prevenção de concorrência por duplo clique na execução
    Dado que planejei uma pesquisa para o tema "Investigação com Concorrência"
    Quando clico duas vezes rapidamente no botão "Iniciar pesquisa"
    Então apenas uma requisição inicial de busca deve ser enviada

  Cenário: Navegação entre rotas durante pipeline sem efeito colateral e com preservação de resultado
    Dado que planejei uma pesquisa para o tema "Investigação com Navegação Paralela"
    Quando clico no botão "Iniciar pesquisa"
    E navego para a página de "Configurações" através do menu
    Então o badge superior deve indicar a sessão integrada ativa
    Quando retorno para a página de "Pesquisa" através do menu
    E após aprovação na auditoria o redator deve consolidar o dossiê
    Então devo ver o relatório do dossiê com status concluído
