# language: pt
Funcionalidade: Módulo de Briefing e Planejamento Inicial da Pesquisa

  Como operador ou pesquisador do Deep Research Engine
  Quero submeter um tema, gerar um rascunho estruturado com busca preliminar e revisar ou aprovar o briefing
  Para direcionar a investigação autônoma com pontos de pesquisa relevantes e robustez contra falhas de IA

  Cenário: Geração bem-sucedida de rascunho de briefing com busca e LLM
    Dado um tema válido de pesquisa "Avanços em Computação Quântica 2026"
    E serviços de busca SERP e LLM retornando respostas válidas com 5 pontos
    Quando uma requisição "POST /briefings" é enviada com o tema
    Então a resposta da API deve ter status HTTP 201
    E a resposta deve conter status de briefing "draft" e versão 2
    E o briefing deve conter entre 3 e 7 pontos de pesquisa estruturados

  Cenário: Falha de busca SERP retorna erro 503 amigável
    Dado um tema válido de pesquisa "Criptografia Pós-Quântica"
    E o provedor de busca SERP indisponível simulando falha de rede
    Quando uma requisição "POST /briefings" é enviada com o tema
    Então a resposta da API deve ter status HTTP 503
    E a resposta de erro do briefing deve conter "Busca SERP indisponível"

  Cenário: Falha de provedor de LLM retorna erro 503
    Dado um tema válido de pesquisa "Fusão Nuclear Comercial"
    E o provedor de LLM indisponível simulando esgotamento de quota ou timeout
    Quando uma requisição "POST /briefings" é enviada com o tema
    Então a resposta da API deve ter status HTTP 503
    E a resposta de erro do briefing deve conter "Geração de briefing indisponível"

  Cenário: Validação de tema inválido ou muito curto retorna erro 422
    Dado um tema de pesquisa inválido "AB"
    Quando uma requisição "POST /briefings" é enviada com o tema inválido
    Então a resposta da API deve ter status HTTP 422
    E a resposta deve conter detalhe "Tema deve conter entre 3 e 300 caracteres"

  Cenário: Revisão com feedback do operador auto-aprova e avança para investigação
    Dado um briefing em rascunho persistido com versão 2
    Quando uma requisição "PATCH /briefings/<id>" é enviada com nota "Focar em aplicações médicas"
    Então a resposta da API deve ter status HTTP 200
    E a resposta deve conter status de briefing "approved" e versão incrementada
    E a investigação deve ser agendada para execução em background

  Cenário: Bloqueio estrito de reabertura de briefing já aprovado
    Dado um briefing com status "approved" gravado no sistema
    Quando uma requisição "POST /briefings/<id>/reopen" é enviada
    Então a resposta da API deve ter status HTTP 409
    E a resposta de erro do briefing deve conter "Briefing aprovado não pode ser reaberto"

  Cenário: Bloqueio de segunda revisão de briefing
    Dado um briefing já revisado com versão superior a 2
    Quando uma requisição "PATCH /briefings/<id>" é enviada com nova nota
    Então a resposta da API deve ter status HTTP 409
    E a resposta de erro do briefing deve conter "Briefing já revisado; segunda revisão não permitida"

  Cenário: Consulta de briefing aprovado via endpoint dedicado
    Dado um briefing com status "approved" e data de aprovação registrada
    Quando uma requisição "GET /briefings/approved/<id>" é enviada
    Então a resposta da API deve ter status HTTP 200
    E o corpo da resposta deve conter o tema, pontos e o carimbo de data "approved_at"

  Cenário: Histórico de versões do briefing reflete transições imutáveis
    Dado um briefing que transitou de rascunho para aprovado
    Quando uma requisição "GET /briefings/<id>/versions" é enviada
    Então a resposta da API deve ter status HTTP 200
    E a lista de versões deve conter pelo menos 2 registros cronológicos
