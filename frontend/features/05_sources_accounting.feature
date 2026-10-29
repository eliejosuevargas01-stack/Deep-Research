# language: pt
Funcionalidade: Separação Contábil e Rastreabilidade de Fontes da Investigação
  Como usuário do Deep Research
  Quero visualizar a contabilidade distinta entre fontes consultadas, utilizadas e consultadas mas não citadas
  Para verificar a proveniência real do dossiê analítico sem métricas enganosas ou dados alheios de versões anteriores

  Cenário: Visualização da contabilidade tripartite de fontes com evidências completas
    Dado que inicializo o contexto da aplicação para validação de fontes
    E que uma pesquisa é executada com sucesso gerando dossiê real com fontes no backend
    Quando visualizo o relatório final publicado
    Então devo ver o painel "Fontes da Investigação"
    E o rótulo enganoso anterior "Fontes Bibliográficas Verificadas" não deve estar visível
    E devo ver a separação compacta com contadores exatos para consultadas, utilizadas e não citadas
    E devo ver a explicação de que fontes não citadas representam contexto investigativo e não fontes rejeitadas
    Quando abro explicitamente o grupo de fontes utilizadas no dossiê
    Então devo ver os links seguros e títulos públicos correspondentes às fontes utilizadas
    E os grupos de fontes não citadas e de todas as fontes consultadas devem estar acessíveis de forma expansível

  Cenário: Exibição fidedigna de relatório legado sem evidências brutas de leitura
    Dado que inicializo o contexto da aplicação para validação de fontes
    E que visualizo um relatório legado cuja contabilidade bruta de leituras é indisponível
    Quando o painel de fontes é exibido
    Então os contadores de fontes consultadas e de não citadas devem exibir "—" e nunca o número zero inventado
    E devo ver o indicativo de status "Legado / Indisponível"
    E devo ver a notificação honesta informando que evidências brutas não foram registradas
    Quando abro explicitamente o grupo de fontes utilizadas no dossiê
    Então as citações conhecidas extraídas do texto publicado devem permanecer visíveis no grupo de utilizadas

  Cenário: Rejeição estrita e aviso de divergência de hash de artefato publicado
    Dado que inicializo o contexto da aplicação para validação de fontes
    E que a resposta do endpoint de fontes retorna um hash de artefato divergente do texto publicado atual
    Quando o relatório final é renderizado
    Então o sistema deve rejeitar a exibição das listas e contadores de fontes pertencentes à outra versão
    E devo ver o aviso conciso "As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado."
    E o texto original do relatório, a cópia e o download do Markdown devem permanecer totalmente preservados e intactos
    E o histórico local não deve persistir o resumo divergente

  Cenário: Rejeição de vinculação de fontes quando o registro histórico contém apenas resumo sem texto integral
    Dado que possuo um registro histórico que contém apenas resumo textual sem o texto integral publicado
    Quando o relatório é renderizado no workspace
    Então o sistema deve rejeitar a vinculação de resumo de fontes do artigo completo
    E devo ver o aviso informando que o registro contém apenas resumo
    E o texto do resumo e os botões de ação devem permanecer preservados

  Cenário: Rejeição de resumo defasado ao alternar para outro relatório com mesmo identificador mas corpo modificado
    Dado que inicializo o contexto da aplicação para validação de fontes
    E que possuo um relatório exibido com resumo de fontes validado
    Quando o corpo do relatório é atualizado com novo texto sob o mesmo identificador
    Então o sistema deve invalidar o resumo anterior e não deve reter os dados da versão antiga

  Cenário: Tratamento de falha de rede na consulta de fontes com opção de nova tentativa
    Dado que inicializo o contexto da aplicação para validação de fontes
    E que a requisição ao endpoint de fontes falha com erro de comunicação
    Quando visualizo o relatório final publicado
    Então o texto integral do dossiê não deve ser ocultado
    E devo ver um banner de alerta informando a falha de comunicação
    E devo ver o botão "Tentar novamente" para repetir exclusivamente a consulta de fontes
    Quando clico no botão "Tentar novamente" da consulta de fontes
    Então uma nova requisição GET deve ser enviada para fontes sem nenhum disparo de POST no pipeline
    E os botões de copiar e baixar o Markdown devem permanecer totalmente operacionais

  Cenário: Replay live somente-leitura de relatório publicado com hidratação real de fontes
    Dado que a variável de ambiente SOURCE_LIVE_REPLAY_PATH está configurada com o arquivo de replay do relatório publicado
    Quando inicializo o contexto isolado de teste apontando para o servidor live
    E carrego o registro histórico no navegador isolado e abro a pesquisa
    Então o sistema deve autenticar a sessão e consultar as fontes via GET sem nenhum disparo de POST
    E a contabilidade de fontes deve registrar exatamente 11 consultadas, 9 utilizadas e 2 não citadas
    E devo conseguir expandir o grupo de 2 fontes não citadas e o grupo de todas as 11 fontes consultadas
    E o hash do dossiê exibido deve coincidir exatamente com o artefato publicado do arquivo de replay
    E uma captura de tela da seção de fontes deve ser salva no diretório de evidências
