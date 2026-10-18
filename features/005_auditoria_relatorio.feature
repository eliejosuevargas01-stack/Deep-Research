# language: pt
Funcionalidade: Auditoria de Pontos e Síntese do Relatório Final com Citações

  Como sistema de pesquisa confiável
  Quero auditar o material coletado pelas personas e exigir síntese estritamente fundamentada em evidências
  Para garantir relatórios com citações verbatim, rastreabilidade e prevenção de alucinações

  Cenário: Auditoria de ponto com veredito aprovado
    Dado um ponto de pesquisa com evidências coletadas pelas personas
    Quando o serviço de auditoria avalia o material contra critérios de completude e veracidade
    Então o ponto deve receber o veredito "AUDIT_APPROVED"
    E a auditoria do ponto deve ser registrada no banco

  Cenário: Tratamento de inconsistência com limite de retries e conversão em caveat
    Dado um ponto de pesquisa que atinge a quarta tentativa de auditoria reprovada
    Quando o avaliador processa o novo veredito "SCRAPER_RETRY"
    Então o sistema deve forçar a conversão do veredito para "AUDIT_CAVEAT"
    E o ponto deve ser liberado para a fase de redação com ressalvas explícitas

  Cenário: Síntese de relatório final fundamentado em evidências e links verbatim
    Dado uma pesquisa com pontos auditados e evidências registradas no banco
    E o agente redator gerando texto de relatório com citações válidas para cada ponto
    Quando o estágio de escrita do relatório é executado
    Então o relatório final deve ser persistido na tabela "reports"
    E o status da pesquisa deve ser atualizado para "DONE"
    E as métricas de citação devem registrar o total de fontes citadas

  Cenário: Bloqueio estrito de relatório com URLs desconhecidas ou não coletadas
    Dado um redator que tenta incluir uma URL externa não presente nas evidências
    Quando a validação de integridade de citações é executada
    Então o sistema deve rejeitar o relatório com erro de URLs não coletadas

  Cenário: Bloqueio de relatório incompleto ou com cabeçalhos de tópicos ausentes
    Dado um texto de relatório com menos de 200 palavras ou sem cabeçalhos dos pontos
    Quando a validação de qualidade estrutural do relatório é invocada
    Então a publicação do relatório deve ser recusada com erro de qualidade
