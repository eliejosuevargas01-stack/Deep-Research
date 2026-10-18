# language: pt
Funcionalidade: Entrega de Relatório via Callback Webhook e API para Frontend

  Como sistema consumidor ou usuário do Deep Research Engine
  Quero receber notificações de conclusão via webhook seguro e consultar o relatório via API
  Para integrar resultados externamente com proteção anti-SSRF e consistência de dados

  Cenário: Entrega bem-sucedida de webhook para endpoint público válido
    Dado uma pesquisa concluída em status "DONE" com relatório gerado e callback_url pública
    Quando o serviço de despacho de webhook é executado
    Então a requisição POST deve ser entregue com sucesso com status 200
    E um registro de auditoria na etapa "callback" com status entregue deve ser persistido
    E um evento de sistema "callback_delivered" deve ser emitido

  Cenário: Bloqueio estrito de entrega para URLs privadas ou internas via proteção anti-SSRF
    Dado uma pesquisa concluída configurada com callback_url apontando para "http://127.0.0.1:8080/hook"
    Quando o serviço de despacho de webhook tenta validar e conectar ao destino
    Então o envio para a URL privada deve falhar com violação de segurança SSRF
    E o registro de auditoria deve indicar que o webhook não foi entregue

  Cenário: Resiliência contra falha de entrega sem alterar status da pesquisa
    Dado uma pesquisa concluída em status "DONE" cujo endpoint de webhook externo retorna erro 500
    Quando o serviço de despacho de webhook processa o erro
    Então o status da pesquisa deve permanecer como "DONE"
    E o relatório gerado deve permanecer integralmente disponível para consulta

  Cenário: Validação do payload de entrega do webhook
    Dado uma pesquisa concluída com relatório markdown estruturado
    Quando o payload de entrega do webhook é gerado
    Então o payload deve conter "research_id", "report_id", "theme", "content_markdown" e "generated_at"

  Cenário: Consistência entre relatório entregue e consulta de API pelo frontend
    Dado uma pesquisa concluída com relatório gravado no banco de dados
    Quando o cliente do frontend envia uma requisição "GET /api/research/<id>"
    Então a resposta da API deve ter status HTTP 200
    E os dados retornados devem ser consistentes com o relatório gerado
