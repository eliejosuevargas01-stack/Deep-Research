# language: pt
Funcionalidade: Módulo de Auditoria Factual e Julgamento de Evidências

  Como editor-chefe acadêmico e auditor independente do sistema Deep Research
  Quero avaliar as evidências coletadas pelas quatro personas para cada ponto de pesquisa
  Para garantir rigor factual, citações verificáveis e direcionamento concreto de lacunas

  Cenário: Aprovação direta de ponto com score maior ou igual a 10 de 12
    Dado um ponto de pesquisa com evidências coletadas pelas 4 personas
    Quando o Agente Auditor avalia o ponto e atribui score 11 de 12 sem contradições
    Então o ponto de pesquisa deve transitar para o status "AUDIT_APPROVED"
    E o veredito estruturado deve ser registrado em audit_trails

  Cenário: Reprovação de ponto com solicitação de retry e missing research concreto
    Dado um ponto de pesquisa na tentativa 1 com evidências incompletas
    Quando o Agente Auditor avalia o ponto e atribui score 7 de 12
    Então o ponto de pesquisa deve transitar para o status "SCRAPER_RETRY"
    E o veredito deve conter instruções concretas de "missing_research"
    E o contador de tentativas do ponto deve ser incrementado para 2

  Cenário: Re-execução em retry respeitando filtro anti-duplicação de URLs
    Dado um ponto de pesquisa em status "SCRAPER_RETRY" que já leu "https://source1.com" e "https://source2.com"
    Quando as 4 personas executam a re-pesquisa com as instruções de missing research
    Então as consultas de busca devem descartar as URLs "https://source1.com" e "https://source2.com"
    E apenas novas URLs devem ser lidas e agregadas ao histórico

  Cenário: Ponto reprovado na quarta tentativa transita para AUDIT_CAVEAT sem travar a pesquisa
    Dado um ponto de pesquisa na tentativa 4 com score 8 de 12
    Quando o Agente Auditor conclui a avaliação
    Então o ponto não deve ser marcado como bloqueado fatal
    E o ponto deve transitar para o status "AUDIT_CAVEAT"
    E as limitações não resolvidas devem ser registradas no veredito

  Cenário: Falha de rede ou indisponibilidade de LLM no Auditor não queima tentativa do ponto
    Dado um ponto de pesquisa na tentativa 1 aguardando auditoria
    Quando o serviço de IA do Auditor falha com erro 503 por 4 vezes consecutivas
    Então o sistema deve registrar a tentativa como "AUDIT_INCONCLUSIVE"
    E o contador de tentativas do ponto de pesquisa deve permanecer em 1

  Cenário: Disparo automático da auditoria imediatamente após a conclusão dos 4 workers do ponto
    Dado uma pesquisa com 3 pontos sendo investigados em paralelo
    Quando os 4 workers do ponto 1 concluem sua coleta antes dos demais pontos
    Então a auditoria do ponto 1 deve ser iniciada imediatamente em background
    E sem aguardar a conclusão dos pontos 2 e 3

  Cenário: Disparo manual da auditoria via endpoint da API
    Dado uma pesquisa autenticada com ponto em status "AUDIT_PENDING"
    Quando uma requisição "POST /api/audit/{research_id}/points/{point_id}/run" é recebida
    Então a resposta da API deve ser HTTP 200 ou 202
    E a auditoria do ponto especificado deve ser executada

  Cenário: Transição da pesquisa para WRITE quando 100% dos pontos concluem a auditoria
    Dado uma pesquisa com todos os pontos nos estados "AUDIT_APPROVED" ou "AUDIT_CAVEAT"
    Quando o último ponto é processado pelo ciclo de auditoria
    Então o status da pesquisa deve transitar de "AUDIT" para "WRITE"
    E a pesquisa deve estar liberada para o Agente Redator
