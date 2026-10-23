# Roadmap: Pesquisa Profunda MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Requirements: `_reversa_forward/001-pesquisa-profunda-mvp/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

---

## 1. Resumo da abordagem

A entrega da feature 001 implementa um monólito modular em Python e FastAPI estruturado em quatro etapas operacionais assíncronas e independentes (`/api/v1/plan`, `/api/v1/search`, `/api/v1/audit`, `/api/v1/writer`), mais rotas administrativas de credenciais. A persistência é assegurada em SQLite permanente com modo WAL e integridade relacional. A etapa de plano analisa estritamente metadados da SERP via Jina gerando N pontos de foco. A etapa de busca orquestra as quatro personas do sistema em paralelo com desduplicação de URLs por pesquisa e gravação sem truncamento sintático. A auditoria submete o material coletado a um checklist de 12 perguntas via LLM forte, persistindo parecer de aprovação ou reprovação com registro de pontos fracos. A redação sintetiza os pontos aprovados em dossiê Markdown com 100% de fontes canônicas rastreadas, bloqueando requisições com pendências e despachando o resultado final para webhook de callback assinado com HMAC-SHA256 (`WEBHOOK_HMAC_SECRET`). Credenciais são cifradas em repouso via Fernet com `CREDENTIALS_MASTER_KEY`, aplicando precedência de variáveis de ambiente.

---

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| I. Rastreabilidade Canônica Verbatim (`_reversa_sdd/prd.md#4-metricas-de-sucesso`) | O dossiê final gerado pelo redator referencia explicitamente fontes primárias canônicas em 100% dos tópicos abordados, vedando links fabricados ou alucinações. | respeita |
| II. Isolamento Modular dos Estágios (`_reversa_sdd/prd.md#6-nao-objetivos-out`) | Cada endpoint opera e persiste seu estado de forma autônoma na base relacional, sem execução monolítica engessada de ponta a ponta. | respeita |
| III. Transparência e Rigor Crítico sem Caixas-Pretas (`_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#1-resumo`) | A validação crítica ocorre antes da redação mediante 12 critérios formais, registrando expressamente as lacunas e pontos fracos identificados. | respeita |
| IV. Configuração Explícita sem Fallback Oculto (`_reversa_sdd/prd.md#9-variaveis-de-ambiente`) | O número N de pontos e a definição das personas são carregados exclusivamente de variáveis de ambiente ou da tabela cifrada; ausência resulta em erro explícito. | respeita |
| V. Segurança em Repouso e Integridade em Trânsito (`requirements.md#10-lacunas`) | Chaves de API armazenadas são cifradas com Fernet (`CREDENTIALS_MASTER_KEY`) e o webhook despachado é assinado com HMAC-SHA256 (`WEBHOOK_HMAC_SECRET`). | respeita |

---

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| DT-01 | FastAPI como framework web assíncrono em monólito modular | Atende ao prazo, simplicidade operacional, validação declarativa Pydantic e execução concorrente assíncrona com baixo overhead | Microsserviços distribuídos com Celery/RabbitMQ, Flask, Django | 🟢 (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) |
| DT-02 | SQLite permanente em modo WAL via SQLAlchemy 2.0 assíncrono (`aiosqlite`) | Sobrevive a reinicializações de contêiner, dispensa banco de dados externo no MVP e suporta leitura concorrente com latência sub-milissegundo | PostgreSQL externo, SQLite em memória, arquivos JSON em disco | 🟢 (`_reversa_sdd/prd.md#8-modelo-de-dados-tabelas`) |
| DT-03 | Criptografia reversível Fernet (AES-128-CBC + HMAC-SHA256) com `CREDENTIALS_MASTER_KEY` para tabela `credenciais` | Exigência técnica de recuperação das chaves para chamadas a APIs externas; Fernet garante confidencialidade e autenticidade da cifra | HMAC puro (irreversível, quebraria chamadas externas), AES-GCM manual, texto claro | 🟡 (`requirements.md#10-lacunas`) |
| DT-04 | Assinatura HMAC-SHA256 no cabeçalho `X-Signature` do webhook via `WEBHOOK_HMAC_SECRET` com comparação timing-safe | Padrão robusto da indústria contra spoofing, garantindo que o receptor possa validar a integridade do corpo cru recebido | Webhook sem assinatura, token estático na URL, Bearer token simples | 🟡 (`requirements.md#10-lacunas`) |
| DT-05 | Ausência de teto orçamentário automático de consumo de tokens | Resposta explícita do usuário no clarify; custos controlados unicamente pelos limites estáticos do PRD (até 3 queries/ponto e até 10 URLs/query) | Mecanismo de corte financeiro por limite em dólares ou tokens | 🟡 (`requirements.md#10-lacunas`) |
| DT-06 | Restrição de acesso estritamente a metadados da SERP na etapa de plano | Previne latência excessiva e consumo desnecessário de cotas na fase de formulação dos N pontos de investigação | Baixar corpo integral dos top links da busca durante o plano | 🟢 (`_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#4-non-goals-fora-do-escopo`) |
| DT-07 | Processamento concorrente paralelo dos N pontos na etapa de busca via `asyncio.gather` | Reduz o tempo de coleta total mantendo o ciclo completo do pipeline abaixo de 10 minutos (600s) | Processamento sequencial ponto a ponto, workers distribuídos em background | 🟢 (`_reversa_sdd/sdd/endpoint-busca-com-personas.md#3-goals-objetivos`) |
| DT-08 | Deduplicação de URLs por `id_pesquisa` antes do acionamento do scraper Jina | Evita desperdício de requisições de raspagem e custos para endereços web já catalogados na mesma pesquisa | Raspar links cegamente sem verificar histórico de leituras | 🟢 (`_reversa_sdd/sdd/endpoint-busca-com-personas.md#61-requisitos-principais`) |
| DT-09 | Checklist estruturado de 12 perguntas de qualidade na auditoria via LLM forte | Estabelece régua analítica objetiva e transparente, distinguindo evidências de lacunas informativas | Resumo livre sem critérios formais, aprovação automática sem crivo | 🟢 (`_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#61-requisitos-principais`) |
| DT-10 | Bloqueio estrito de redação com código HTTP 400 caso haja pontos pendentes de auditoria | Impede relatórios incompletos, enviesados ou sem crivo de qualidade analítica | Permitir redação preliminar com pontos não auditados | 🟢 (`_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#4-non-goals-fora-do-escopo`) |
| DT-11 | Resiliência com 1 tentativa inicial + 3 retries e timeout operacional de 600s | Garante robustez contra instabilidades transitórias de rede nas APIs do Jina e provedores de LLM | 1 tentativa única sem retry, retries infinitos sem backoff | 🟢 (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) |

---

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Não há teto orçamentário de consumo de tokens | `requirements.md#10-lacunas` e `questions.md#1` | Pesquisas com temas hiper-amplos gerarem custo superior ao esperado pelo operador |
| Criptografia reversível Fernet com chave mestra `CREDENTIALS_MASTER_KEY` no contêiner | `requirements.md#10-lacunas` e `questions.md#2` | Sistema abortar inicialização se a variável de ambiente não for informada no contêiner |
| Assinatura HMAC-SHA256 no webhook com validação timing-safe | `requirements.md#10-lacunas` e `questions.md#3` | Sistemas receptores que esperem outro esquema de autenticação rejeitarem as notificações |
| Volume persistente fornecido na implantação Docker para o arquivo SQLite | `_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais` | Perda total do histórico de pesquisas e credenciais em caso de recriação do contêiner |

---

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado (SDD) | Tipo de mudança | Resumo |
|------------|-----------------------------------|-----------------|--------|
| `app/main.py` | `_reversa_sdd/prd.md#5-escopo-in` | componente-novo | Ponto de entrada FastAPI, ciclo de vida lifespan, middlewares de erro e autenticação |
| `app/api/v1/router.py` | `_reversa_sdd/prd.md#5-escopo-in` | componente-novo | Roteador mestre unificando endpoints operacionais e administrativos sob prefixo `/api/v1` |
| `app/api/v1/endpoints/plan.py` | `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#8-design-e-interface` | contrato-novo | Rota `POST /api/v1/plan` com validação de payload e geração de N pontos via SERP |
| `app/api/v1/endpoints/search.py` | `_reversa_sdd/sdd/endpoint-busca-com-personas.md#8-design-e-interface` | contrato-novo | Rota `POST /api/v1/search` com despacho de busca concorrente e filtro de URLs |
| `app/api/v1/endpoints/audit.py` | `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#8-design-e-interface` | contrato-novo | Rota `POST /api/v1/audit` com checklist das 12 perguntas e parecer estruturado |
| `app/api/v1/endpoints/writer.py` | `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#8-design-e-interface` | contrato-novo | Rota `POST /api/v1/writer` com síntese em Markdown e despacho via webhook |
| `app/api/v1/endpoints/admin.py` | `_reversa_sdd/prd.md#7-requisitos-funcionais` | contrato-novo | Rotas `POST` e `GET /api/v1/admin/credentials` para gestão de parâmetros operacionais |
| `app/core/planner.py` | `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#8-design-e-interface` | componente-novo | Módulo orquestrador da persona `planejador` com chamadas restritas à SERP |
| `app/core/searcher.py` | `_reversa_sdd/sdd/endpoint-busca-com-personas.md#8-design-e-interface` | componente-novo | Módulo de processamento paralelo dos N pontos sob as 4 personas e desduplicação |
| `app/core/auditor.py` | `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#8-design-e-interface` | componente-novo | Módulo de auditoria com aplicação do checklist das 12 perguntas via LLM forte |
| `app/core/writer.py` | `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#8-design-e-interface` | componente-novo | Módulo de síntese analítica do dossiê com rastreabilidade canônica de fontes |
| `app/services/webhook_client.py` | `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#8-design-e-interface` | componente-novo | Cliente HTTP de despacho do webhook com assinatura HMAC-SHA256 (`X-Signature`) |
| `app/services/crypto_service.py` | `requirements.md#10-lacunas` | componente-novo | Serviço criptográfico Fernet para encriptação e decriptação de credenciais |
| `app/tools/jina_client.py` | `_reversa_sdd/sdd/endpoint-busca-com-personas.md#8-design-e-interface` | componente-novo | Cliente assíncrono para Jina Search (SERP) e Jina Reader (`s.jina.ai`) com retries 1+3 |
| `app/tools/llm_client.py` | `_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais` | componente-novo | Cliente assíncrono para LLMs OpenAI-compatible (leves e fortes) com retries 1+3 |
| `app/db/` | `_reversa_sdd/prd.md#8-modelo-de-dados-tabelas` | componente-novo | Modelos SQLAlchemy assíncronos (`pesquisa`, `pontos`, `conteudo_coletado`, `credenciais`) |

---

## 6. Delta no modelo de dados

- Resumo das mudanças: Em cenário greenfield, é estabelecida a criação do banco de dados relacional permanente SQLite em modo WAL composto pelas tabelas `pesquisa`, `pontos`, `conteudo_coletado` e `credenciais`, com integridade referencial por chaves estrangeiras, deleção em cascata e índices cobrindo buscas e ordenações temporais. Credenciais são cifradas com Fernet em repouso.
- Detalhe completo em: `_reversa_forward/001-pesquisa-profunda-mvp/data-delta.md`

---

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `POST /api/v1/plan` | HTTP REST (Exposto) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/endpoint-plan.md` |
| `POST /api/v1/search` | HTTP REST (Exposto) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/endpoint-search.md` |
| `POST /api/v1/audit` | HTTP REST (Exposto) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/endpoint-audit.md` |
| `POST /api/v1/writer` | HTTP REST (Exposto) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/endpoint-writer.md` |
| `/api/v1/admin/credentials` | HTTP REST (Exposto) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/endpoint-admin.md` |
| Jina SERP e Scrapper (`s.jina.ai`) | HTTP REST (Consumido) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/external-jina.md` |
| Provedor LLM OpenAI-Compatible | HTTP REST (Consumido) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/external-llm.md` |
| Callback Webhook Notification | HTTP POST (Emitido) | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/external-webhook.md` |

---

## 8. Plano de migração

Como o projeto inicia em cenário greenfield, o plano de implementação organiza-se em 4 fases progressivas:

1. **Fase 1: Fundações de Arquitetura, Persistência e Segurança**
   - Configurar estrutura de pastas do monólito modular (`app/api`, `app/core`, `app/db`, `app/services`, `app/tools`).
   - Implementar conexão SQLAlchemy 2.0 assíncrona com SQLite permanente em modo WAL (`PRAGMA journal_mode=WAL`, `foreign_keys=ON`).
   - Implementar DDL inicial e repositórios para as 4 tabelas (`pesquisa`, `pontos`, `conteudo_coletado`, `credenciais`).
   - Implementar `CryptoService` com cifra reversível Fernet baseada em `CREDENTIALS_MASTER_KEY` e precedência de variáveis de ambiente.
   - Implementar clientes de integração HTTP com política de 1+3 retries e timeout de 600s (`JinaClient`, `LLMClient`).

2. **Fase 2: Implementação dos Quatro Endpoints Operacionais e Administrativos**
   - Implementar Etapa 1: `POST /api/v1/plan` com persona `planejador` e consulta restrita a metadados da SERP.
   - Implementar Etapa 2: `POST /api/v1/search` com execução paralela dos N pontos via 4 personas analíticas, desduplicação de URLs por pesquisa e salvamento integral sem truncamento.
   - Implementar Etapa 3: `POST /api/v1/audit` com checklist estruturado das 12 perguntas de qualidade via LLM forte e gravação de parecer e `pontos_fracos`.
   - Implementar Etapa 4: `POST /api/v1/writer` com validação de pontos finalizados (bloqueio 400 se pendente), geração de Markdown com 100% de fontes canônicas e despacho de webhook assinado com HMAC-SHA256 (`WEBHOOK_HMAC_SECRET`).
   - Implementar rotas administrativas `POST` e `GET /api/v1/admin/credentials`.

3. **Fase 3: Suíte de Testes Automatizados e Resiliência**
   - Criar mocks de transporte HTTP (`httpx.MockTransport`) para isolamento completo de rede nos testes de unidade e integração.
   - Cobrir cenários felizes das 4 etapas e rotas administrativas.
   - Cobrir cenários negativos e edge cases: ausência de configuração de N pontos (500), pesquisa não encontrada (404), bloqueio de redação com pontos pendentes (400), falhas transitórias com retentativas 1+3, e integridade da assinatura HMAC timing-safe.

4. **Fase 4: Empacotamento Docker e Homologação Ponta a Ponta**
   - Criar `Dockerfile` enxuto e `docker-compose.yml` mapeando volume persistente para `/data`.
   - Executar validação E2E via guia `onboarding.md`.

---

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Custo elevado de tokens por inferências extensas | alto | média | Sem teto orçamentário no MVP por definição do usuário; custo mitigado pelos limites estruturais do PRD (até 3 queries/ponto e até 10 URLs/query). |
| Bloqueio ou indisponibilidade temporária na API Jina ou LLM | alto | média | Política de resiliência ativa com 1 tentativa + 3 retries com backoff exponencial e timeout de 600s. |
| Inconsistência ou travamento por concorrência de escrita no SQLite | médio | baixa | Ativação obrigatória de modo WAL (`journal_mode=WAL`), `PRAGMA busy_timeout=30000` e transações assíncronas curtas. |
| Violação de segurança de credenciais salvas no banco | alto | baixa | Criptografia em repouso com algoritmo padrão Fernet (AES-128-CBC + HMAC-SHA256) e chave externa `CREDENTIALS_MASTER_KEY`. |
| Falha no receptor do webhook de callback | médio | média | Persistência do dossiê no SQLite antecede o disparo de rede; em caso de falha definitiva após retries, registra `falha_definitiva` e preserva o documento. |

---

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` geradas por `/reversa-to-do` marcadas `[X]`
- [ ] Banco de dados SQLite permanente configurado em modo WAL com integridade referencial ativa
- [ ] Endpoints operacionais `/api/v1/plan`, `/api/v1/search`, `/api/v1/audit`, `/api/v1/writer` implementados e funcionais
- [ ] Restrição de acesso apenas à SERP na etapa de plano validada por teste unitário
- [ ] Varredura paralela com as 4 personas, desduplicação de URLs e armazenamento sem truncamento testados
- [ ] Auditoria com as 12 perguntas estruturadas e atualização relacional de `pontos_fracos` validada
- [ ] Bloqueio estrito de redação com código HTTP 400 para pesquisas com pontos pendentes comprovado
- [ ] Dossiê gerado com estrutura em Markdown e rastreabilidade de 100% de fontes canônicas
- [ ] Despacho do webhook com cabeçalho `X-Signature: sha256=<hmac>` e comparação timing-safe validado
- [ ] Criptografia Fernet em repouso da tabela `credenciais` com precedência de variáveis de ambiente testada
- [ ] Suíte de testes automatizados executando com 100% de sucesso sem depender de credenciais ativas

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-21 | Versão inicial gerada por `/reversa-plan` em cenário greenfield | reversa-plan |