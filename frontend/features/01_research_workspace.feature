# language: pt
Funcionalidade: Workspace de Investigação e Planejamento Analítico
  Como um pesquisador ou analista
  Quero formular temas de pesquisa, configurar preferências e revisar o plano estruturado
  Para obter um dossiê analítico aprofundado com fontes canônicas verificadas e exportação fidedigna

  Cenário: Visualização do estado inicial vazio com sugestões
    Dado que acesso a aplicação no dispositivo "desktop"
    Então devo ver o título "Workspace de Investigação Analítica"
    E devo ver a lista de sugestões de temas investigativos
    E o botão de submissão do compositor deve estar desabilitado

  Cenário: Validação de tamanho do tema no compositor com texto de ajuda
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando digito "abc" no compositor
    Então o contador de caracteres deve indicar comprimento inválido
    E devo ver a mensagem de ajuda indicando o limite de 5 a 500 caracteres
    E o botão de submissão deve permanecer desabilitado
    Quando digito "O futuro da matriz de energia limpa no Brasil até 2035" no compositor
    Então o botão de submissão deve ficar habilitado

  Cenário: Seleção de sugestão com botão semântico e foco no editor
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando clico na sugestão de tema "O futuro da matriz energética no Brasil"
    Então o compositor deve conter o texto "O futuro da matriz energética no Brasil"
    E o foco do navegador deve estar no campo do compositor

  Cenário: Comportamento do teclado no compositor com Shift+Enter e Enter
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando digito "Primeira linha" no compositor
    E pressiono a combinação Shift+Enter no compositor
    Então o valor do compositor deve conter quebra de linha
    E nenhuma requisição de plano deve ter sido disparada
    Quando digito "Segunda linha com tema investigativo profundo" no compositor
    E pressiono Enter no compositor
    Então a requisição de plano deve ser disparada exatamente uma vez

  Cenário: Dimensionamento responsivo e limite de rolagem do compositor
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando preencho um tema multilinha de 3 linhas no compositor
    Então a altura do compositor deve expandir sem cortar o texto visível
    Quando altero o viewport para 375px de largura
    Então a caixa de entrada deve manter o texto sem transbordamento horizontal
    Quando altero o viewport de volta para desktop
    Então o compositor deve manter o texto moldado com auto-redimensionamento sem corte
    Quando preencho um tema longo com mais de 300 caracteres
    Então a altura da área de texto deve ser limitada a no máximo 120px com rolagem vertical ativa

  Cenário: Configuração de preferências com botão expansível sem clipping de viewport
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando clico no botão de preferências de pesquisa
    Então o painel de preferências deve estar visível
    E o topo do painel de preferências não deve estar cortado fora da viewport
    Quando seleciono 3 pontos analíticos nas preferências
    E desmarco a persona "futurista"
    E fecho o painel de preferências com a tecla Escape
    Então o foco deve retornar para o botão de preferências
    E o chip de preferências deve indicar "3 pontos • 3 personas"

  Cenário: Planejamento de investigação com snapshot de preferências
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando clico no botão de preferências de pesquisa
    E seleciono 2 pontos analíticos nas preferências
    E desmarco a persona "futurista"
    E fecho o painel de preferências
    Quando preencho o tema "Transição Energética Global" no compositor
    E clico no botão de planejar investigação
    Então devo ver o cartão do plano "Plano pronto para revisão"
    E devo ver a lista vertical dos pontos investigativos com divulgação progressiva
    E o plano deve exibir o chip com 2 pontos analíticos
    E o plano deve exibir o chip de personas com 3 personas ativas e títulos configurados
    E a única ação de continuidade visível deve ser o botão "Iniciar pesquisa"

  Cenário: Prevenção de concorrência por duplo clique no planejamento
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando preencho o tema "Investigação com Concorrência no Planejamento" no compositor
    E clico duas vezes rapidamente no botão de planejar investigação
    Então apenas uma requisição de criação de plano deve ser enviada

  Cenário: Visibilidade e acionabilidade do botão Iniciar pesquisa no viewport 1280x577 sem rolagem
    Dado que acesso a aplicação no dispositivo de resolução 1280x577
    Quando preencho o tema "Mobilidade urbana sustentável e veículos elétricos" no compositor
    E clico no botão de planejar investigação
    Então devo ver o cartão do plano "Plano pronto para revisão"
    E o botão "Iniciar pesquisa" deve estar localizado acima da dobra na viewport inicial
    E o botão "Iniciar pesquisa" deve ser clicável diretamente nas coordenadas do elemento sem rolagem prévia

  Cenário: Divulgação progressiva dos eixos e proteção contra descarte acidental do plano
    Dado que planejei uma pesquisa para o tema "Transição Energética Global"
    Então devo ver os pontos analíticos inicialmente recolhidos
    Quando clico no botão para expandir os detalhes de todos os pontos
    Então devo ver as subperguntas e hipóteses detalhadas de todos os pontos
    Quando clico no botão "Novo tema" do banner do plano
    Então devo ver o diálogo de confirmação "Descartar plano formulado?"
    E o foco do teclado deve estar contido no diálogo de confirmação
    Quando pressiono Escape no diálogo de confirmação
    Então o diálogo de confirmação deve fechar e o plano atual deve permanecer visível

  Cenário: Limpeza do compositor pós-plano e ação de editar tema
    Dado que acesso a aplicação no dispositivo "desktop"
    Quando preencho o tema "Transição Energética Global" no compositor
    E clico no botão de planejar investigação
    Então o campo do compositor deve ficar limpo
    Quando clico no botão "Editar tema" do plano
    Então o compositor deve conter o texto "Transição Energética Global"
    E o foco do navegador deve estar no campo do compositor

  Cenário: Execução síncrona do fluxo completo com fontes verificadas
    Dado que planejei uma pesquisa para o tema "Transição Energética Global"
    Quando clico no botão "Iniciar pesquisa"
    Então o sistema deve transicionar pelo estágio de busca com personas analíticas
    E o sistema deve transicionar pela auditoria de qualidade com 12 critérios
    E após aprovação na auditoria o redator deve consolidar o dossiê
    E devo ver o relatório do dossiê com status concluído
    E devo ver o painel "Fontes da Investigação"
    E os botões de copiar markdown e baixar arquivo devem estar disponíveis

  Cenário: Verificação de cópia no clipboard e download real de Markdown idêntico ao dossiê
    Dado que concluí a pesquisa para o tema "Transição Energética Global"
    Quando clico no botão "Baixar .md"
    Então o download do arquivo Markdown deve ser concluído com sucesso
    E o conteúdo do arquivo baixado em UTF-8 deve ser idêntico ao texto do dossiê retornado pelo redator
    E o hash SHA-256 do arquivo baixado deve coincidir exatamente com o artefato publicado
    Quando clico no botão "Copiar Markdown"
    Então o texto na área de transferência do contexto de teste deve coincidir exatamente com o dossiê
    E devo ver o feedback visual temporário "Copiado!"

  Cenário: Responsividade em dispositivo móvel 375px
    Dado que acesso a aplicação no dispositivo "mobile"
    Então o layout deve adaptar-se à largura móvel sem rolagem horizontal
    E as sugestões de temas devem ser exibidas em coluna única
    E o compositor deve permanecer acessível na parte inferior

  Cenário: Responsividade da barra de navegação em largura intermediária de 837px sem estouro
    Dado que acesso a aplicação no dispositivo de largura 837px
    Então a barra de navegação superior não deve ter elementos cortados ou transbordando
    E o layout da página não deve possuir rolagem horizontal

  Cenário: Responsividade da barra de navegação em largura de 916px sem sobreposição
    Dado que acesso a aplicação no dispositivo de largura 916px
    Então a barra de navegação superior não deve ter elementos cortados ou transbordando
    E o layout da página não deve possuir rolagem horizontal

  Cenário: Comportamento de animação com preferência de movimento reduzido e contraste de tipografia
    Dado que acesso a aplicação no dispositivo "desktop" com preferência de movimento reduzido
    Quando clico no botão de preferências de pesquisa
    Então o painel de preferências deve ficar visível imediatamente sem transição prolongada
    E o conteúdo interativo deve permanecer completamente legível e acessível
    E as fontes tipográficas da aplicação devem estar efetivamente carregadas no documento
    E o contraste medido dos textos principais contra o fundo deve atender aos requisitos de legibilidade
