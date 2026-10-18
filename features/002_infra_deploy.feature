# language: pt
Funcionalidade: Validação de Build, Deploy, Migrações e Infraestrutura

  Como engenheiro de plataforma e confiabilidade
  Quero garantir que os serviços executem migrações no startup, validem dependências e relatem saúde real
  Para assegurar deploy consistente, idempotência de banco e resiliência a falhas

  Cenário: Migrações executadas pelo serviço no startup sem contêineres efêmeros
    Dado a configuração de deploy em "docker-compose.yml" e "Dockerfile"
    Quando inspecionado o comando de inicialização do serviço backend
    Então o serviço deve executar "alembic upgrade head" antes de iniciar o servidor uvicorn
    E a infraestrutura não deve conter serviços efêmeros dedicados apenas a migrações
    E o backend deve depender da condição "service_healthy" do banco de dados

  Cenário: Idempotência das migrações Alembic
    Dado um banco de dados com migrações aplicadas até a revisão head
    Quando o comando de migração "alembic upgrade head" é executado novamente
    Então a execução deve concluir com sucesso sem erros
    E nenhuma alteração conflitante deve ser detectada no esquema

  Cenário: Criação e integridade das tabelas do domínio
    Dado o esquema de banco de dados inicializado
    Quando as tabelas do sistema são inspecionadas
    Então as tabelas "research", "research_points", "evidences", "agent_event_logs", "reports", "audit_trails", "admin_sessions", "app_settings" devem existir

  Cenário: Verificação de saúde da aplicação via endpoint GET /health
    Dado que a aplicação backend está ativa e conectada ao banco de dados
    Quando uma requisição "GET /health" é enviada
    Então a resposta da API deve ter status HTTP 200
    E a resposta deve conter status "healthy" e database "connected"

  Cenário: Endpoint GET /health falha com HTTP 503 quando o banco está inacessível
    Dado que a conexão com o banco de dados falha
    Quando uma requisição "GET /health" é enviada
    Então a resposta da API deve ter status HTTP 503
    E a resposta de saúde deve conter erro "Database unavailable"

  Cenário: Persistência de dados entre ciclos de vida
    Dado um registro de pesquisa gravado no banco de dados
    Quando uma nova sessão do banco é aberta simulando reinício da aplicação
    Então o registro de pesquisa deve permanecer íntegro e consultável

  Cenário: Recuperação no startup de investigações interrompidas
    Dado uma pesquisa em status "SCRAPER" com ponto em "SCRAPER_IN_PROGRESS" gravada no banco
    Quando o ciclo de lifespan da aplicação é inicializado
    Então a rotina de recuperação deve agendar a retomada da investigação em background
