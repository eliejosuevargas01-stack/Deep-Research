# language: pt
Funcionalidade: Histórico Local de Pesquisas
  Como usuário do Deep Research
  Quero que minhas pesquisas fiquem salvas no navegador com seus snapshots de preferências
  Para que eu possa consultar planos e dossiês anteriores sem reprocessamento, contaminação de estado ou planos forjados

  Cenário: Persistência e restauração de dossiê concluído a partir do histórico
    Dado que concluí uma pesquisa com tema "Impacto da IA no Setor Produtivo"
    Quando navego para a página de "Histórico"
    Então devo ver o aviso de armazenamento local no navegador
    E devo ver a pesquisa "Impacto da IA no Setor Produtivo" listada com status concluído
    Quando clico no botão "Abrir" da pesquisa listada
    Então o workspace deve carregar imediatamente o dossiê concluído sem requisições de reprocessamento

  Cenário: Abertura direta de registro histórico somente de redação sem plano
    Dado que possuo no histórico um registro histórico concluído apenas com dossiê do redator e sem plano
    Quando navego para a página de "Histórico"
    E clico no botão "Abrir" da pesquisa somente-redação
    Então o workspace deve carregar diretamente o relatório do dossiê
    E nenhum plano fictício ou barra lateral órfã deve ser fabricada
    E o texto do relatório deve permanecer exatamente idêntico ao registro salvo

  Cenário: Alternância entre registro com plano e registro somente de redação limpa metadados órfãos
    Dado que possuo no histórico um registro com plano formulado e um registro somente de redação
    Quando abro a pesquisa que possui plano formulado
    Então devo ver o plano e a barra lateral de contexto da pesquisa com plano
    Quando retorno ao histórico e clico no botão "Abrir" da pesquisa somente-redação
    Então o workspace deve exibir o relatório da pesquisa somente-redação
    E a barra lateral anterior não deve permanecer visível
    E nenhum plano fictício deve ser forjado para a pesquisa somente-redação

  Cenário: Preservação de snapshot de preferências no histórico local
    Dado que planejei e concluí uma pesquisa de 2 pontos com personas "historiador,cetico" para o tema "Fusão Nuclear Comercial"
    Quando navego para a página de "Histórico"
    Então devo ver a pesquisa "Fusão Nuclear Comercial" listada com status concluído
    Quando clico no botão "Abrir" da pesquisa listada
    Então o plano restaurado deve preservar o snapshot de 2 pontos analíticos

  Cenário: Projeção segura de histórico descartando raciocínio interno e envelopes
    Dado que uma resposta do backend contém campos de raciocínio privado e envelopes
    Quando a pesquisa é salva no histórico local
    Então o registro armazenado no navegador não deve conter chaves de raciocínio ou telemetria privada

  Cenário: Resiliência contra registros corrompidos no armazenamento local
    Dado que o localStorage contém dados corrompidos ou malformados
    Quando navego para a página de "Histórico"
    Então a página de histórico deve carregar normalmente sem quebras

  Cenário: Visualização fidedigna de contagem desconhecida em plano legado sem preferencias
    Dado que possuo um plano legado sem snapshot de preferencias salvo no histórico
    Quando navego para a página de "Histórico"
    E clico no botão "Abrir" da pesquisa legada
    Então o cabeçalho do plano deve exibir "Personas analíticas" sem adivinhar contagem de 4 personas
