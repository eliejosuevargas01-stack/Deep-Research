# Actions: Pesquisa Profunda MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Roadmap: `_reversa_forward/001-pesquisa-profunda-mvp/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 44 |
| Concluídas | 44 |
| Em aberto | 0 |
| Paralelizáveis (`[//]`) | 23 |
| Maior cadeia de dependência | 10 |

## Fase 1, Preparação

<!-- Setup, scaffolding, modelos relacionais, conexão assíncrona SQLite em modo WAL e serviços de segurança. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Configurar dependências e empacotamento em pyproject.toml com FastAPI, uvicorn, sqlalchemy>=2.0, aiosqlite, httpx, tenacity, cryptography, pydantic>=2.0, pydantic-settings, pytest e pytest-asyncio (DT-01, DT-02). | - | `[//]` | `pyproject.toml` | 🟢 | `[X]` |
| T002 | Implementar modelo de configurações Settings em app/config.py via Pydantic Settings para carregamento estrito de variáveis de ambiente sem fallback hardcoded (DT-01, RN-02, RF-12). | T001 | `[//]` | `app/config.py` | 🟢 | `[X]` |
| T003 | Implementar CryptoService em app/services/crypto_service.py com cifra reversível Fernet (AES-128-CBC + HMAC-SHA256) baseada em CREDENTIALS_MASTER_KEY para proteção de segredos em repouso (DT-03, RN-10, RF-12). | T001 | `[//]` | `app/services/crypto_service.py` | 🟡 | `[X]` |
| T004 | Configurar conexão de banco assíncrona em app/db/session.py com SQLAlchemy 2.0 e aiosqlite, ativando pragmas journal_mode=WAL, synchronous=NORMAL, foreign_keys=ON e busy_timeout=30000 (DT-02, RNF-08). | T001 | `[//]` | `app/db/session.py` | 🟢 | `[X]` |
| T005 | Definir modelos ORM em app/db/models.py para as tabelas pesquisa, pontos, conteudo_coletado e credenciais com chaves estrangeiras com CASCADE, índices e restrições de unicidade (RF-02, RF-05, RF-12). | T004 | - | `app/db/models.py` | 🟢 | `[X]` |
| T006 | Implementar rotina de inicialização em app/db/init_db.py com função assíncrona init_db() para execução de DDL idempotente (create_all) e conferência de pragmas WAL no boot (DT-02). | T005 | - | `app/db/init_db.py` | 🟢 | `[X]` |
| T007 | Implementar CredentialsRepository em app/db/credentials_repository.py para persistência cifrada com Fernet e aplicação estrita da regra RN-10 de precedência de variáveis de ambiente (RF-11, RF-12, RN-10). | T003, T005 | - | `app/db/credentials_repository.py` | 🟡 | `[X]` |
| T008 | Implementar ResearchRepository em app/db/research_repository.py com operações assíncronas para criação de pesquisa, listagem/atualização de pontos, salvamento de conteudo_coletado e deduplicação de URLs (RF-02, RF-04, RF-05, RF-06, RF-08). | T005 | - | `app/db/research_repository.py` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes unitários e de integração escritos antes do núcleo (TDD), cobrindo regras de negócio, mocks e contratos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T009 | Configurar fixtures e infraestrutura de testes em tests/conftest.py com engine SQLite assíncrono temporário em modo WAL, ciclo de sessão limpa por teste e gerador de chave Fernet de teste (DT-02, RNF-08). | T004, T005 | `[//]` | `tests/conftest.py` | 🟢 | `[X]` |
| T010 | Implementar utilitário de simulação de rede em tests/mocks/http_mock.py com httpx.MockTransport para simulação determinística de Jina SERP/Reader, OpenAI LLM Light/Strong e Webhook (DT-11, RNF-06). | T001 | `[//]` | `tests/mocks/http_mock.py` | 🟢 | `[X]` |
| T011 | Criar testes unitários em tests/unit/test_crypto_service.py cobrindo cifragem e decifragem com Fernet, validação de chaves mestras inválidas ou ausentes e comportamento seguro em erro (DT-03, RN-10). | T003, T009 | `[//]` | `tests/unit/test_crypto_service.py` | 🟡 | `[X]` |
| T012 | Criar testes unitários em tests/unit/test_credentials_repository.py cobrindo regra RN-10 de precedência de os.environ sobre a tabela cifrada e erro explícito quando ausente em ambos (RF-11, RF-12, RN-10). | T007, T009 | `[//]` | `tests/unit/test_credentials_repository.py` | 🟡 | `[X]` |
| T013 | Criar testes unitários em tests/unit/test_database.py cobrindo esquema DDL, verificação de pragmas WAL e foreign_keys ativas, unicidade uq_pesquisa_ponto_n e deleção em cascata (DT-02, RF-02). | T005, T006, T009 | `[//]` | `tests/unit/test_database.py` | 🟢 | `[X]` |
| T014 | Criar testes unitários em tests/unit/test_schemas.py validando contratos Pydantic v2 de entrada e saída para todos os endpoints operacionais e administrativos (RF-01 a RF-12). | T001 | `[//]` | `tests/unit/test_schemas.py` | 🟢 | `[X]` |
| T015 | Criar testes unitários em tests/unit/test_jina_client.py cobrindo isolamento de metadados na SERP (vedado download de corpo), raspagem integral via Reader e retentativas 1+3 com backoff em 429/5xx (DT-06, DT-11, RN-03, RN-05). | T010 | - | `tests/unit/test_jina_client.py` | 🟢 | `[X]` |
| T016 | Criar testes unitários em tests/unit/test_llm_client.py cobrindo chamadas OpenAI-compatible leve e forte via /v1/chat/completions, parsing JSON estruturado, retries 1+3 e erro de configuração (DT-11, RN-02, RNF-11). | T010 | - | `tests/unit/test_llm_client.py` | 🟢 | `[X]` |
| T017 | Criar testes unitários em tests/unit/test_webhook_client.py cobrindo cálculo da assinatura HMAC-SHA256 no header X-Signature, validação timing-safe e tratamento de códigos 2xx versus 5xx com falha_definitiva (DT-04, RN-09, RF-10). | T010 | - | `tests/unit/test_webhook_client.py` | 🟡 | `[X]` |
| T018 | Criar testes unitários em tests/unit/test_domain_modules.py cobrindo formulação de N pontos do planejador, varredura concorrente das 4 personas e deduplicação no pesquisador, checklist das 12 perguntas no auditor e síntese com 100% de fontes no redator (DT-07 a DT-10, RN-04 a RN-08). | T008, T010 | - | `tests/unit/test_domain_modules.py` | 🟢 | `[X]` |
| T019 | Criar testes de integração em tests/integration/test_endpoints.py cobrindo fluxo feliz ponta a ponta dos endpoints /api/v1/plan, /api/v1/search, /api/v1/audit, /api/v1/writer e /api/v1/admin/credentials com httpx.AsyncClient (RF-01 a RF-12). | T009, T010 | - | `tests/integration/test_endpoints.py` | 🟢 | `[X]` |
| T020 | Criar testes de integração em tests/integration/test_edge_cases.py cobrindo cenários negativos: ausência de N_PONTOS (500), pesquisa inexistente (404), auditoria sem coleta (400) e bloqueio estrito de redação com pontos pendentes (400) (RN-07, RF-07, RF-09). | T009, T010 | - | `tests/integration/test_edge_cases.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Modelos de contrato Pydantic e módulos de domínio isolados que orquestram cada estágio do pipeline. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T021 | Criar esquemas Pydantic em app/schemas/plan.py com PlanRequest (tema entre 5 e 500 caracteres, id_pesquisa opcional) e PlanResponse (com n_pontos e lista estruturada de pontos gerados) (RF-01). | T001, T014 | `[//]` | `app/schemas/plan.py` | 🟢 | `[X]` |
| T022 | Criar esquemas Pydantic em app/schemas/search.py com SearchRequest (UUID id_pesquisa, ponto_id opcional) e SearchResponse (com sumário de processamento, total de URLs e tamanho textual) (RF-03). | T001, T014 | `[//]` | `app/schemas/search.py` | 🟢 | `[X]` |
| T023 | Criar esquemas Pydantic em app/schemas/audit.py com AuditRequest, AuditEvaluationResult (resposta estruturada do LLM para as 12 perguntas de qualidade) e AuditResponse (RF-06). | T001, T014 | `[//]` | `app/schemas/audit.py` | 🟢 | `[X]` |
| T024 | Criar esquemas Pydantic em app/schemas/writer.py com WriterRequest e WriterResponse (dossiê analítico em Markdown, contagem de caracteres e metadados de webhook_entrega) (RF-08, RF-10). | T001, T014 | `[//]` | `app/schemas/writer.py` | 🟢 | `[X]` |
| T025 | Criar esquemas Pydantic em app/schemas/admin.py com CredentialCreateRequest, CredentialResponse e CredentialSanitizedListItem com suporte a mascaramento seguro de valores (RF-11). | T001, T014 | `[//]` | `app/schemas/admin.py` | 🟢 | `[X]` |
| T026 | Implementar orquestrador da persona planejador em app/core/planner.py para formulação de queries, consulta restrita a metadados da SERP, geração de N pontos via LLM leve e validação quantitativa estrita (DT-06, RN-02, RN-03, RF-01). | T002, T008, T018, T021 | - | `app/core/planner.py` | 🟢 | `[X]` |
| T027 | Implementar orquestrador de busca em app/core/searcher.py com processamento concorrente dos N pontos via asyncio.gather sob as 4 personas (historiador, visionario, cetico, futurista), desduplicação de URLs por pesquisa e gravação sem truncamento em conteudo_coletado (DT-07, DT-08, RN-04, RN-05, RF-03, RF-04, RF-05). | T002, T008, T018, T022 | - | `app/core/searcher.py` | 🟢 | `[X]` |
| T028 | Implementar orquestrador de auditoria em app/core/auditor.py com avaliação crítica do conteúdo coletado frente ao checklist das 12 perguntas de qualidade via LLM forte, deliberação de aprovação/reprovação e registro de pontos_fracos (DT-09, RN-06, RF-06, RF-07). | T002, T008, T018, T023 | - | `app/core/auditor.py` | 🟢 | `[X]` |
| T029 | Implementar orquestrador de redação em app/core/writer.py com validação de bloqueio HTTP 400 para pontos pendentes, consolidação de evidências e 100% de fontes canônicas rastreadas, geração de Markdown em 4 seções estruturadas e gravação na tabela pesquisa (DT-10, RN-07, RN-08, RF-08, RF-09). | T002, T008, T018, T024 | - | `app/core/writer.py` | 🟢 | `[X]` |

## Fase 4, Integração

<!-- Clientes de integração HTTP externa (Jina, LLM, Webhook), endpoints REST e roteamento principal FastAPI. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T030 | Implementar cliente assíncrono JinaClient em app/tools/jina_client.py conectando a Jina Search (s.jina.ai) e Jina Reader (r.jina.ai) com 1+3 retries com backoff exponencial e timeout de 600s (DT-11, RNF-06, RNF-07). | T001, T002, T015 | `[//]` | `app/tools/jina_client.py` | 🟢 | `[X]` |
| T031 | Implementar cliente assíncrono LLMClient em app/tools/llm_client.py para inferência via rota OpenAI-compatible /v1/chat/completions (modelos leve e forte) com retries 1+3 e suporte a response_format em JSON (DT-11, RNF-06, RNF-11). | T001, T002, T016 | `[//]` | `app/tools/llm_client.py` | 🟢 | `[X]` |
| T032 | Implementar cliente de entrega WebhookClient em app/services/webhook_client.py com assinatura HMAC-SHA256 (X-Signature: sha256=<hex>) sobre raw bytes, retries 1+3 e atualização de webhook_status como entregue ou falha_definitiva (DT-04, RN-09, RF-10). | T001, T002, T017 | `[//]` | `app/services/webhook_client.py` | 🟡 | `[X]` |
| T033 | Implementar endpoint POST /api/v1/plan em app/api/v1/endpoints/plan.py validando requisição, invocando planner, persistindo pesquisa e N pontos com status pendente e retornando HTTP 201 (RF-01, RF-02). | T019, T020, T026, T030, T031 | - | `app/api/v1/endpoints/plan.py` | 🟢 | `[X]` |
| T034 | Implementar endpoint POST /api/v1/search em app/api/v1/endpoints/search.py validando pesquisa (404 se inexistente), disparando busca paralela das 4 personas via searcher e retornando HTTP 200 com resumo (RF-03, RF-04, RF-05). | T019, T020, T027, T030, T031 | - | `app/api/v1/endpoints/search.py` | 🟢 | `[X]` |
| T035 | Implementar endpoint POST /api/v1/audit em app/api/v1/endpoints/audit.py verificando coletas prévias (400 se ausente), acionando auditor com as 12 perguntas e atualizando parecer relacional dos pontos com retorno HTTP 200 (RF-06, RF-07). | T019, T020, T028, T031 | - | `app/api/v1/endpoints/audit.py` | 🟢 | `[X]` |
| T036 | Implementar endpoint POST /api/v1/writer em app/api/v1/endpoints/writer.py bloqueando requisições com pontos pendentes (400), gerando dossiê via writer, salvando na tabela pesquisa e despachando webhook assinado (RF-08, RF-09, RF-10). | T019, T020, T029, T031, T032 | - | `app/api/v1/endpoints/writer.py` | 🟢 | `[X]` |
| T037 | Implementar endpoints administrativos POST e GET /api/v1/admin/credentials em app/api/v1/endpoints/admin.py para gravação de segredos cifrados com Fernet e listagem sanitizada com indicação de precedência de ambiente (RF-11, RF-12, RN-10). | T007, T012, T019, T025 | - | `app/api/v1/endpoints/admin.py` | 🟡 | `[X]` |
| T038 | Implementar roteador unificado em app/api/v1/router.py agregando os endpoints operacionais (plan, search, audit, writer) e administrativos (admin) sob o prefixo /api/v1 (DT-01). | T033, T034, T035, T036, T037 | - | `app/api/v1/router.py` | 🟢 | `[X]` |
| T039 | Implementar aplicação FastAPI em app/main.py com ciclo de vida assíncrono lifespan executando init_db(), rota GET /health e tratamento global de exceções (DT-01). | T006, T038 | - | `app/main.py` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Containerização Docker, volumes persistentes, script de smoke-test e documentação operacional de onboarding. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T040 | Criar arquivo .env.example na raiz com catálogo completo de variáveis de ambiente do pipeline (N_PONTOS, PERSONAS_CONFIG, CREDENTIALS_MASTER_KEY, WEBHOOK_HMAC_SECRET, etc.) e documentação inline sem fallbacks hardcoded (RN-02). | T002 | `[//]` | `.env.example` | 🟢 | `[X]` |
| T041 | Criar Dockerfile multi-stage com Python 3.11-slim, instalação de dependências sem cache, usuário não-root seguro e diretório /data para persistência (RNF-08). | T001 | `[//]` | `Dockerfile` | 🟢 | `[X]` |
| T042 | Criar docker-compose.yml mapeando serviço api, expondo porta 8000, carregando variáveis do .env e montando volume permanente host ./data:/data para a base SQLite (RNF-08). | T041 | `[//]` | `docker-compose.yml` | 🟢 | `[X]` |
| T043 | Criar script de verificação ponta a ponta em scripts/verify_pipeline.py executando testes sequenciais automatizados das 4 etapas e validando integridade relacional do SQLite (DT-01 a DT-11). | T039 | `[//]` | `scripts/verify_pipeline.py` | 🟢 | `[X]` |
| T044 | Atualizar e validar guia _reversa_forward/001-pesquisa-profunda-mvp/onboarding.md garantindo alinhamento de 100% dos comandos de execução, parâmetros de curl e schemas com as ações implementadas. | T039, T040, T042 | `[//]` | `_reversa_forward/001-pesquisa-profunda-mvp/onboarding.md` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgirem durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-21 | Versão inicial gerada por `/reversa-to-do` em cenário greenfield | reversa-to-do |
