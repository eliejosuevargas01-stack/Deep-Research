# language: pt
Funcionalidade: Orquestração e Execução dos Workers de Investigação

  Como motor de pesquisa autônoma
  Quero distribuir pontos de investigação entre 4 personas com execução paralela, limites de busca e auditoria
  Para consolidar evidências ricas com integridade, anti-duplicação e resiliência a falhas

  Cenário: Distribuição de ponto de pesquisa para as 4 personas em paralelo
    Dado uma pesquisa ativa com um ponto em estado "SCRAPER"
    Quando o serviço de investigação é executado para a pesquisa
    Então tarefas para as personas "historian", "skeptic", "pragmatist" e "futurist" devem ser disparadas
    E os resultados devem ser persistidos individualmente na tabela de resultados de steps

  Cenário: Respeito ao teto estrito de 3 buscas por worker
    Dado um worker de persona executando uma investigação de ponto
    Quando o modelo LLM tenta solicitar mais de 3 chamadas de busca
    Então o worker deve barrar buscas adicionais e exigir a entrega final dos dados coletados

  Cenário: Autocorreção de resposta em formato JSON inválido
    Dado um modelo que retorna inicialmente um texto fora do padrão JSON
    Quando o worker detecta a resposta malformada
    Então uma mensagem de correção deve ser enviada ao modelo solicitando o formato estrito
    E a entrega bem-sucedida deve ser validada após a correção

  Cenário: Sanitização de segredos e prevenção de vazamento em logs de erro
    Dado um erro simulado contendo "Bearer secret_token_123" e "api_key=my_super_secret"
    Quando a rotina de sanitização de erros do worker é invocada
    Então o texto de erro resultante não deve conter nenhum segredo em texto puro
    E os valores sensíveis devem ser substituídos por máscara de proteção

  Cenário: Consolidação dos resultados do ponto e transição para AUDIT_PENDING
    Dado um ponto de pesquisa cujas 4 personas concluíram a coleta com sucesso
    Quando a consolidação dos resultados do ponto é concluída
    Então o status do ponto de pesquisa deve transitar para "AUDIT_PENDING"

  Cenário: Re-pesquisa reativa com exclusão de URLs duplicadas
    Dado um ponto de pesquisa reprovado com veredito "SCRAPER_RETRY" e lista de URLs já lidas
    Quando a re-pesquisa do ponto é agendada
    Então o prompt das personas deve conter o filtro anti-duplicação com as URLs excluídas
    E o contador de tentativas do ponto deve ser incrementado

  Cenário: Resiliência a falha parcial sem abortar outras personas
    Dado um ponto onde uma das personas falha por erro de rede ou provedor
    Quando o ciclo de investigação do ponto é executado
    Então o erro da persona falha deve ser persistido como falha sem derrubar as outras personas
