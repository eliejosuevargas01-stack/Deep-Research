# language: pt
Funcionalidade: Configurações, Sessão Integrada e Parâmetros Cifrados
  Como administrador do Deep Research
  Quero gerenciar credenciais dos provedores de IA e parâmetros operacionais
  Para garantir segurança de operação sem exigir chave manual do cliente e com precedência clara conforme Adendo 002

  Cenário: Sessão integrada automática e verificação de comunicação com o backend
    Dado que navego para a página de "Configurações"
    Então o badge superior deve indicar a sessão integrada ativa
    Quando clico em "Testar Conexão com API"
    Então devo ver o status de conexão confirmando comunicação ativa

  Cenário: Validação acessível de campos com foco automático no primeiro controle inválido
    Dado que navego para a página de "Configurações"
    Quando preencho a URL do LLM com "invalid-url-sem-protocolo"
    E preencho o número de pontos com "99.5"
    E submeto o formulário de credenciais
    Então o campo de URL do LLM deve possuir atributo aria-invalid "true"
    E o campo de URL do LLM deve apontar para mensagem de erro via aria-describedby
    E o foco ativo do navegador deve ser transferido automaticamente para o campo de URL do LLM
    E nenhuma requisição de gravação deve ser enviada

  Cenário: Diferenciação clara entre banco sem parâmetros e erro de requisição
    Dado que o backend retorna erro na consulta de parâmetros
    Quando navego para a página de "Configurações"
    Então devo ver um alerta descritivo de falha ao consultar parâmetros
    E devo ver a opção de tentar novamente a consulta

  Cenário: Proteção contra perda involuntária de rascunho de configurações
    Dado que navego para a página de "Configurações"
    Quando preencho a URL do LLM com "https://api.openai.com/v1"
    Então devo ver o alerta de rascunho não salvo no formulário

  Cenário: Visualização de precedência do Adendo 002 com banco cifrado prioritário e valores mascarados
    Dado que o banco isolado contém parâmetros de ambiente e de banco
    E que navego para a página de "Configurações"
    Então devo ver a explicação da regra de precedência RN-10 com prioridade do banco cifrado sobre o ambiente
    E devo ver a tabela de parâmetros cadastrados
    E a coluna de origem ativa deve distinguir entre "Banco Cifrado" e "Ambiente (.env)"
    E nenhum segredo real deve ser exibido em texto legível

  Cenário: Proteção client-side contra vazamento de segredo HMAC desmascarado
    Dado que o backend retorna o segredo WEBHOOK_HMAC_SECRET em texto claro
    Quando navego para a página de "Configurações"
    Então o valor exibido na tabela para WEBHOOK_HMAC_SECRET deve estar mascarado pelo cliente

  Cenário: Rejeição de números decimais e negativos no campo de pontos
    Dado que navego para a página de "Configurações"
    Quando preencho o número de pontos com "3.5"
    E submeto o formulário de credenciais
    Então devo ver a mensagem de validação exigindo inteiro positivo sem decimais

  Cenário: Preservação de rascunho em memória através de navegação interna por hash
    Dado que navego para a página de "Configurações"
    Quando preencho a URL do LLM com "https://api.openai.com/v1"
    E navego para a página de "Pesquisa" através do menu
    E retorno para a página de "Configurações"
    Então o campo de URL do LLM deve preservar o valor "https://api.openai.com/v1"
    E nenhum segredo deve ser salvo em armazenamento local do navegador
    Quando clico no botão de descartar rascunho
    Então o campo de URL do LLM deve ficar vazio
