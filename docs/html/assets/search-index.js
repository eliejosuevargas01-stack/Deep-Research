window.DOCS_SEARCH_INDEX = [
{
"page": "index",
"pageLabel": "Visão geral",
"id": "",
"title": "Introdução",
"text": "Pipeline modular de pesquisa profunda na internet. Recebe um tema, produz um plano de investigação estruturado, coleta evidência web com personas analíticas, audita cada ponto contra 12 critérios de qualidade e redige um"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "1-o-que-o-sistema-entrega",
"title": "1. O que o sistema entrega",
"text": "Capacidade Resultado Planejamento N eixos investigativos com pergunta principal, subperguntas, hipóteses, consultas iniciais, riscos de viés, evidência de refutação e critério de conclusão Coleta Evidência integral lida…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "2-como-funciona",
"title": "2. Como funciona",
"text": "POST /api/v1/plan → plano + N pontos persistidos (não executa busca) POST /api/v1/search → leitura web por persona, evidência e proveniência por ponto POST /api/v1/audit → 12 critérios por ponto, aprovação/reprovação e…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "3-stack",
"title": "3. Stack",
"text": "Camada Tecnologia Backend Python ≥ 3.11 (ambiente atual em 3.14), FastAPI, Uvicorn, Pydantic v2 + pydantic-settings Persistência SQLAlchemy 2.0 assíncrono + aiosqlite, SQLite em modo WAL Integrações httpx, tenacity;…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "4-início-rápido-local",
"title": "4. Início rápido (local)",
"text": ""
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "5-configuração-mínima",
"title": "5. Configuração mínima",
"text": "Variável Obrigatória Função DATABASE_URL sim sqlite+aiosqlite:///./data/deep_research.db CREDENTIALS_MASTER_KEY sim Chave Fernet que cifra a tabela credenciais ; somente via ambiente OPENAI_API_KEY sim Credencial do…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "6-api",
"title": "6. API",
"text": "Todas as rotas de negócio vivem sob /api/v1 . Referência completa com payloads e erros: docs/API.md . Método Rota Função POST /api/v1/plan Cria plano e pontos ( 201 ; 202 com async_execute: true ) GET…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "7-estrutura-do-repositório",
"title": "7. Estrutura do repositório",
"text": "Deep-Research/ ├── app/ │ ├── main.py FastAPI, lifespan, /health, sessão, SPA e assets │ ├── config.py Pydantic Settings (sem fallbacks hardcoded) │ ├── api/v1/endpoints/ plan, search, audit, writer, pipeline, admin │…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "8-testes",
"title": "8. Testes",
"text": "# Backend — 509 testes coletados .venv/bin/python -m pytest # Um módulo específico .venv/bin/python -m pytest tests/unit/test_writer_acceptance.py -q # Frontend — typecheck + build de produção cd frontend && npm run…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "9-documentação",
"title": "9. Documentação",
"text": "Documento Conteúdo docs/html/index.html Versão HTML navegável — busca, tema claro/escuro e sumário por página docs/ARCHITECTURE.md Componentes, fluxo por etapa, modelo de dados, concorrência, SSE, segurança docs/API.md…"
},
{
"page": "index",
"pageLabel": "Visão geral",
"id": "10-limitações-conhecidas",
"title": "10. Limitações conhecidas",
"text": "SQLite único: o banco é um arquivo local com WAL; não há suporte a múltiplas instâncias concorrentes. SSE em memória: o PipelineEventHub é por processo. Com múltiplos workers, eventos não são compartilhados; o snapshot…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "",
"title": "Introdução",
"text": "Documento técnico do pipeline, do modelo de dados e das decisões de engenharia. Complementa o README.md e o contrato HTTP em API.md ."
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "1-visão-geral",
"title": "1. Visão geral",
"text": "O sistema é um monólito modular FastAPI com quatro estágios de domínio e um orquestrador opcional: ┌──────────────────────────────────────────────────────────────────────┐ │ app/main.py │ │ lifespan → init_db() /health…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "2-camadas-e-responsabilidades",
"title": "2. Camadas e responsabilidades",
"text": "Módulo Responsabilidade app/main.py Aplicação, lifespan, DDL no boot, /health , sessão local, entrega da SPA e assets, handlers globais de erro app/config.py Settings via Pydantic; sem defaults hardcoded para parâmetros…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "3-fluxo-por-etapa",
"title": "3. Fluxo por etapa",
"text": ""
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "4-modelo-de-dados",
"title": "4. Modelo de dados",
"text": "SQLite com journal_mode=WAL , synchronous=NORMAL , foreign_keys=ON e busy_timeout=30000 . O schema é criado no boot ( Base.metadata.create_all ) e recebe migrações aditivas idempotentes."
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "5-concorrência-posse-e-idempotência",
"title": "5. Concorrência, posse e idempotência",
"text": "Reserva atômica: cada estágio reserva o ponto/rodada com UPDATE condicional e confere rowcount ; não existe leitura-depois-escrita sem fence. Leases: pontos.lease_token identifica o dono temporário da execução. Reservas…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "6-streaming-sse",
"title": "6. Streaming SSE",
"text": "PipelineEventHub é um singleton em memória: mantém até 100 eventos por pesquisa e 50 pesquisas no histórico recente; cada assinante recebe uma asyncio.Queue isolada; publish é seguro entre threads; sem assinantes, os…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "7-segurança",
"title": "7. Segurança",
"text": ""
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "8-política-temporal-e-recência",
"title": "8. Política temporal e recência",
"text": "app/core/temporal.py centraliza a decisão temporal para planner, search, audit e writer: data de referência calculada em tempo de execução no fuso America/Sao_Paulo (configurável por RESEARCH_REFERENCE_TIMEZONE );…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "9-contabilidade-de-fontes",
"title": "9. Contabilidade de fontes",
"text": "SourceAccountingService produz FontesResumo a partir de conteudo_coletado.metadados_coleta e do dossiê: consultadas: todas as URLs efetivamente lidas com sucesso; utilizadas: URLs citadas no dossiê final; não…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "10-frontend",
"title": "10. Frontend",
"text": "React 18 + TypeScript, Vite, CSS tokenizado; sem framework de componentes ou biblioteca de estado. Rotas de interface: research , history , settings , docs . A navegação usa caminhos no browser; o backend serve…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "11-decisões-e-trade-offs",
"title": "11. Decisões e trade-offs",
"text": "Decisão Motivo Custo SQLite + WAL Operação simples, zero infraestrutura, transações confiáveis para um nó Não escala horizontalmente; escritas serializadas Monólito modular Quatro endpoints independentes com estado no…"
},
{
"page": "arquitetura",
"pageLabel": "Arquitetura",
"id": "12-referências",
"title": "12. Referências",
"text": "../README.md — visão geral e início rápido API.md — contratos HTTP OPERATIONS.md — operação e diagnóstico ../_reversa_sdd/prd.md — PRD e invariantes ../_reversa_sdd/sdd/ — SDD por endpoint e adendos v2..v8…"
},
{
"page": "api",
"pageLabel": "API",
"id": "",
"title": "Introdução",
"text": "Contrato HTTP da versão 0.1.0 . Base local: http://127.0.0.1:8010 . Em Docker Compose: http://127.0.0.1:8085 . Swagger: GET /docs OpenAPI: GET /openapi.json Prefixo de negócio: /api/v1"
},
{
"page": "api",
"pageLabel": "API",
"id": "1-convenções",
"title": "1. Convenções",
"text": ""
},
{
"page": "api",
"pageLabel": "API",
"id": "2-post-apiv1plan",
"title": "2. POST /api/v1/plan",
"text": "Cria o plano de investigação e persiste a pesquisa. Não executa busca."
},
{
"page": "api",
"pageLabel": "API",
"id": "3-get-apiv1planid-pesquisastream",
"title": "3. GET /api/v1/plan/{id_pesquisa}/stream",
"text": "SSE com o raciocínio do planejador durante o POST /plan . O id_pesquisa deve ser conhecido pelo cliente antecipadamente (enviado no corpo do POST ). Content-Type: text/event-stream Eventos: agent.delta ( kind: reasoning…"
},
{
"page": "api",
"pageLabel": "API",
"id": "4-post-apiv1search",
"title": "4. POST /api/v1/search",
"text": "Executa a coleta web por personas nos pontos pendentes."
},
{
"page": "api",
"pageLabel": "API",
"id": "5-post-apiv1audit",
"title": "5. POST /api/v1/audit",
"text": "Audita os pontos coletados contra os 12 critérios."
},
{
"page": "api",
"pageLabel": "API",
"id": "6-post-apiv1writer",
"title": "6. POST /api/v1/writer",
"text": "Redige, avalia e publica o dossiê final; dispara o webhook quando configurado."
},
{
"page": "api",
"pageLabel": "API",
"id": "7-get-apiv1pipelineid-pesquisastatus",
"title": "7. GET /api/v1/pipeline/{id_pesquisa}/status",
"text": "{ \"id_pesquisa\": \"3f6c2b1a-...\", \"tema\": \"...\", \"status_pipeline\": \"redigindo\", \"erro_pipeline\": null, \"criado_em\": \"2026-10-28T20:15:03.123456Z\", \"concluido_em\": null, \"webhook_status\": \"pendente\", \"total_pontos\": 4,…"
},
{
"page": "api",
"pageLabel": "API",
"id": "8-get-apiv1pipelineid-pesquisasources",
"title": "8. GET /api/v1/pipeline/{id_pesquisa}/sources",
"text": "Somente leitura. Retorna FontesResumo : Campo Descrição status Disponibilidade da contabilidade total_consultadas / total_utilizadas / total_nao_utilizadas Contagens consultadas[] , utilizadas[] , nao_utilizadas[] {url,…"
},
{
"page": "api",
"pageLabel": "API",
"id": "9-get-apiv1pipelineid-pesquisastream",
"title": "9. GET /api/v1/pipeline/{id_pesquisa}/stream",
"text": "SSE de progresso. Query params opcionais: Param Tipo Efeito snapshot_only boolean Envia apenas o snapshot do banco e encerra max_events inteiro Encerra após N eventos Sequência: snapshot ( pipeline.status , point.status…"
},
{
"page": "api",
"pageLabel": "API",
"id": "10-post-apiv1admincredentials",
"title": "10. POST /api/v1/admin/credentials",
"text": "Cria ou atualiza uma credencial cifrada. O valor nunca é devolvido."
},
{
"page": "api",
"pageLabel": "API",
"id": "11-get-apiv1admincredentials",
"title": "11. GET /api/v1/admin/credentials",
"text": "Lista metadados mascarados: { \"credenciais\": [ { \"chave\": \"OPENAI_API_KEY\", \"tipo\": \"llm\", \"base_url\": \"https://api.openai.com/v1\", \"origem_ativa\": \"banco_cifrado\", \"mascarado\": \"sk-a****9f2c\", \"atualizado_em\":…"
},
{
"page": "api",
"pageLabel": "API",
"id": "12-rotas-públicas",
"title": "12. Rotas públicas",
"text": ""
},
{
"page": "api",
"pageLabel": "API",
"id": "13-contrato-do-webhook",
"title": "13. Contrato do webhook",
"text": "Entrega apenas quando o dossiê é publicado com status = concluido e há URL de callback resolvida (payload > CALLBACK_WEBHOOK_URL )."
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "",
"title": "Introdução",
"text": "Guia de instalação, configuração, execução, testes e diagnóstico. Para o desenho técnico, consulte ARCHITECTURE.md ; para os contratos HTTP, API.md ."
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "1-requisitos",
"title": "1. Requisitos",
"text": "Item Versão / observação Python ≥ 3.11 ( pyproject.toml ); ambiente de desenvolvimento atual em 3.14.7 Node.js / npm Node 20+ (build do frontend; não é necessário em produção) SQLite Embutido no Python via aiosqlite…"
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "2-variáveis-de-ambiente",
"title": "2. Variáveis de ambiente",
"text": ""
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "3-modos-de-execução",
"title": "3. Modos de execução",
"text": ""
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "4-banco-de-dados",
"title": "4. Banco de dados",
"text": ""
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "5-verificação-de-saúde",
"title": "5. Verificação de saúde",
"text": "curl -s http://127.0.0.1:8010/health # {\"status\":\"healthy\"} curl -s http://127.0.0.1:8010/api/v1/pipeline/<id>/status \\ -H \"X-API-Key: $API_SECRET_KEY\" Checklist pós-deploy: /health responde 200 . / entrega o index.html…"
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "6-testes",
"title": "6. Testes",
"text": "# Backend: 509 testes coletados .venv/bin/python -m pytest # Falha rápida e verbosa .venv/bin/python -m pytest -x -q # Apenas unitários .venv/bin/python -m pytest tests/unit -q # Apenas integração .venv/bin/python -m…"
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "7-diagnóstico",
"title": "7. Diagnóstico",
"text": "Sintoma Causa provável Ação 503 \"Frontend bundle não compilado ou ausente\" frontend/dist/index.html não existe cd frontend && npm ci && npm run build 403 em /app/session Host não local, Origin / Referer divergente ou…"
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "8-observabilidade",
"title": "8. Observabilidade",
"text": "Status consolidado: GET /api/v1/pipeline/{id}/status . Progresso ao vivo: GET /api/v1/pipeline/{id}/stream (SSE). Telemetria de LLM: tabela generation_attempts (etapa, persona, modelo, prompt hash, uso, custo, latência,…"
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "9-segurança-operacional",
"title": "9. Segurança operacional",
"text": "Checklist mínimo para exposição remota: Feche a API: defina API_SECRET_KEY e reinicie. Sem isso, /api/v1/* aceita requisições anônimas. Não exponha 127.0.0.1 diretamente: use reverse proxy com TLS e repasse Host ,…"
},
{
"page": "operacoes",
"pageLabel": "Operações",
"id": "10-manutenção",
"title": "10. Manutenção",
"text": "Crescimento do banco: conteudo_coletado e generation_attempts crescem por pesquisa. Monitore o tamanho de data/deep_research.db . Coleta acumulada: cada rodada gera uma linha em conteudo_coletado (chave id_pesquisa +…"
}
];
