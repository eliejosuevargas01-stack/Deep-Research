# language: pt
Funcionalidade: Módulo de Autenticação e Controle de Acesso

  Como administrador ou cliente da API do Deep Research Engine
  Quero autenticar via cookie de sessão seguro ou credenciais de API
  Para acessar os endpoints protegidos com segurança e sem vazamento de segredos

  Cenário: Login com credenciais válidas de administrador
    Dado que o sistema possui a senha de administrador configurada
    Quando uma requisição "POST /api/auth/login" é enviada com a senha correta
    Então a resposta da API deve ter status HTTP 200
    E o corpo da resposta deve indicar "authenticated": true e role "admin"
    E a resposta deve conter "authenticated": true e um token "csrf_token"
    E o cookie "dr_session" deve ser configurado na resposta
    E o cookie "dr_session" deve ser definido como httpOnly com "Path=/" e "SameSite=lax"
    E a sessão de administrador correspondente deve ser persistida no banco de dados
    E a resposta não deve conter a senha do administrador nem o segredo da API

  Cenário: Login rejeitado com credenciais inválidas
    Dado que o sistema possui a senha de administrador configurada
    Quando uma requisição "POST /api/auth/login" é enviada com senha incorreta
    Então a resposta da API deve ter status HTTP 401
    E a resposta deve conter detalhe "Invalid credentials"
    E nenhum cookie "dr_session" deve ser configurado
    E nenhuma sessão de administrador deve ser persistida no banco de dados

  Cenário: Acesso autenticado a endpoint protegido via Bearer token
    Dado que a API possui o segredo "API_AUTH_SECRET" configurado
    Quando uma requisição "GET /api/auth/me" é enviada com cabeçalho "Authorization: Bearer <API_AUTH_SECRET>"
    Então a resposta da API deve ter status HTTP 200
    E o corpo da resposta deve indicar "authenticated": true e role "admin"

  Cenário: Acesso autenticado a endpoint protegido via X-API-Key
    Dado que a API possui o segredo "API_AUTH_SECRET" configurado
    Quando uma requisição "GET /api/auth/me" é enviada com cabeçalho "X-API-Key: <API_AUTH_SECRET>"
    Então a resposta da API deve ter status HTTP 200
    E o corpo da resposta deve indicar "authenticated": true e role "admin"

  Cenário: Acesso rejeitado a endpoint protegido sem credenciais
    Dado que o usuário não fornece nenhuma credencial de autenticação
    Quando uma requisição "GET /api/auth/me" é enviada sem cabeçalhos ou cookies
    Então a resposta da API deve ter status HTTP 401
    E a resposta deve conter detalhe "Authentication required"

  Cenário: Rejeição de credenciais ambíguas ou múltiplas simultâneas
    Dado que o usuário envia simultaneamente Bearer token e X-API-Key
    Quando uma requisição "GET /api/auth/me" é enviada com ambas as credenciais
    Então a resposta da API deve ter status HTTP 400
    E a resposta deve conter detalhe "Ambiguous authentication: multiple credential types supplied"

  Cenário: Rejeição de cabeçalho de tenant proibido
    Dado que o usuário envia o cabeçalho proibido "x-tenant-id"
    Quando uma requisição "GET /api/auth/me" é enviada com o cabeçalho "x-tenant-id"
    Então a resposta da API deve ter status HTTP 400
    E a resposta deve conter detalhe "Client tenant headers are prohibited"

  Cenário: Rejeição de mutação com cookie de sessão sem token CSRF válido
    Dado que o usuário possui uma sessão ativa via cookie "dr_session"
    Quando uma requisição de mutação "POST /api/auth/logout" é enviada sem cabeçalho "X-CSRF-Token"
    Então a resposta da API deve ter status HTTP 403
    E a resposta deve conter detalhe "CSRF validation failed"

  Cenário: Logout com cookie de sessão e CSRF válido
    Dado que o usuário possui uma sessão ativa via cookie "dr_session" com token CSRF válido
    Quando uma requisição de mutação "POST /api/auth/logout" é enviada com o cabeçalho "X-CSRF-Token"
    Então a resposta da API deve ter status HTTP 204
    E o cookie "dr_session" deve ser removido na resposta

  Cenário: Rotas de autenticação não vaziam segredos do sistema
    Dado que o sistema possui a senha de administrador e o segredo "API_AUTH_SECRET" configurados
    Quando o login é realizado e as rotas "/api/auth/me" e "/api/auth/csrf" são consultadas em sequência
    Então a resposta do login não deve conter a senha do administrador nem o segredo da API
    E a resposta de "/api/auth/me" não deve conter a senha do administrador nem o segredo da API
    E a resposta de "/api/auth/csrf" não deve conter a senha do administrador nem o segredo da API
