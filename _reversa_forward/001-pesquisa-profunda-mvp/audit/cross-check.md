# Relatório de Auditoria Cruzada: Pesquisa Profunda MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data da Auditoria: `2026-10-21`
> Tipo: Auditoria Leitora Estrita de Planejamento e Conformidade (`/reversa-audit`)
> Artefatos Analisados:
> - Requirements: `_reversa_forward/001-pesquisa-profunda-mvp/requirements.md`
> - Roadmap: `_reversa_forward/001-pesquisa-profunda-mvp/roadmap.md`
> - Actions: `_reversa_forward/001-pesquisa-profunda-mvp/actions.md`
> - Data Delta: `_reversa_forward/001-pesquisa-profunda-mvp/data-delta.md`
> - Interfaces: `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/`
> - Código-Fonte de Referência: `app/` e `tests/`
> - Especificações SDD/PRD de Origem: `_reversa_sdd/prd.md`, `_reversa_sdd/sdd/`

---

## 1. Resumo Executivo da Auditoria

O pipeline de planejamento da feature `001-pesquisa-profunda-mvp` foi submetido à auditoria cruzada leitora estrita para verificar a coerência, completude e conformidade entre os requisitos funcionais e não-funcionais, as decisões técnicas do roadmap, a decomposição em ações atômicas, os contratos de interface e o código-fonte implementado.

### Contagem de Findings por Severidade

| Severidade | Quantidade | Descrição Sintética |
|------------|------------|---------------------|
| 🔴 **CRITICAL** | **0** | Nenhum conflito fatal com regras do legado, quebra de integridade relacional ou ciclo de dependência. |
| 🟠 **HIGH** | **3** | Inconsistência numérica no resumo de ações, descompasso entre checkboxes de ações e código existente, e incompatibilidade em `PERSONAS_CONFIG` no guia de onboarding. |
| 🟡 **MEDIUM** | **4** | Divergência no formato do payload do webhook de callback, ausência de campo `dossier_resumo` no schema do Writer, acoplamento de mocks de teste dentro de endpoints e ausência de `pythonpath` em `pyproject.toml`. |
| 🟢 **LOW** | **2** | Ausência dos arquivos operacionais opcionais `docker-compose.yml` e `scripts/verify_pipeline.py`, e variação ortográfica na grafia de `cetico`/`cectico`. |
| **TOTAL** | **9** | **Avaliação geral: Planejamento robusto e código funcional, requerendo alinhamento documental.** |

---

## 2. Matriz Consolidada de Findings

| ID | Severidade | Eixo | Descrição | Onde está |
|----|------------|------|-----------|-----------|
| **A001** | 🟠 HIGH | Sanidade do actions | Divergência numérica no resumo de ações concluídas/em aberto: a tabela de métricas indica 20 concluídas e 24 em aberto, mas a tabela física possui 21 ações marcadas como `[X]` (T001 a T020 e T027) e 23 ações marcadas como `[ ]`. | `_reversa_forward/001-pesquisa-profunda-mvp/actions.md` (linhas 12-13 e 63) |
| **A002** | 🟠 HIGH | Consistência | Descompasso temporal entre checkboxes de `actions.md` e a base de código real: as ações T021 a T026 e T028 a T040 constam com status `[ ]` (em aberto), porém todos os seus arquivos-alvo em `app/schemas/`, `app/core/`, `app/tools/`, `app/services/` e `app/api/v1/` já estão integralmente codificados, testados e com 100% de aprovação na suíte de testes. | `_reversa_forward/001-pesquisa-profunda-mvp/actions.md` vs diretório `app/` |
| **A003** | 🟠 HIGH | Consistência | Incompatibilidade estrutural na configuração de `PERSONAS_CONFIG`: o guia `onboarding.md` exemplifica a variável como um JSON dict com a chave `"redator"`, enquanto o código em `app/config.py`, `app/core/writer.py` e `app/services/credential_resolver.py` processa uma string separada por vírgula e valida estritamente a presença da persona `"redator final"`. A utilização do exemplo de onboarding causará erro HTTP 500/ValueError na inicialização do Writer. | `_reversa_forward/001-pesquisa-profunda-mvp/onboarding.md` (linha 26) vs `app/core/writer.py` (linhas 42-44) |
| **A004** | 🟡 MEDIUM | Consistência | Divergência estrutural no contrato de despacho do Webhook: `interfaces/external-webhook.md` prescreve um payload contendo blocos aninhados `metricas` (`pontos_aprovados`, `pontos_reprovados`) e `dossier` (`formato`, `conteudo`), enquanto `app/core/writer.py` emite um payload simplificado plano com chaves diretas `total_pontos`, `total_caracteres_dossier` e `dossier_final`. | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/external-webhook.md` vs `app/core/writer.py` (linhas 154-162) |
| **A005** | 🟡 MEDIUM | Consistência | Discrepância contratual no contrato de resposta da etapa 4: `interfaces/endpoint-writer.md` define o atributo `dossier_resumo` no payload JSON de retorno HTTP 200, enquanto o modelo Pydantic `WriterResponse` em `app/schemas/writer.py` declara apenas `dossier_final`, descartando `dossier_resumo` na serialização final do endpoint. | `_reversa_forward/001-pesquisa-profunda-mvp/interfaces/endpoint-writer.md` vs `app/schemas/writer.py` (linhas 51-83) |
| **A006** | 🟡 MEDIUM | Coerência com o legado | Acoplamento de mocks de teste na camada de aplicação em produção: os arquivos `app/main.py` e `app/api/v1/endpoints/plan.py`, `search.py`, `audit.py`, `writer.py` contêm funções internas (`_setup_integration_test_env` e `_get_transport`) que verificam `PYTEST_CURRENT_TEST` e importam diretamente `tests.mocks.http_mock`, violando o isolamento entre código de produção e de teste. | `app/main.py` e `app/api/v1/endpoints/*.py` |
| **A007** | 🟡 MEDIUM | Sanidade do actions | Dependência de `PYTHONPATH=.` para execução da suíte de testes: a execução direta do utilitário `pytest` no diretório raiz falha com `ModuleNotFoundError: No module named 'tests'` devido a imports absolutos (`from tests.mocks.http_mock import ...`) sem a configuração `pythonpath = ["."]` sob `[tool.pytest.ini_options]` em `pyproject.toml`. | `pyproject.toml` e arquivos em `tests/` |
| **A008** | 🟢 LOW | Cobertura | Tarefas operacionais de infraestrutura pendentes de artefatos físicos: as ações T042 (`docker-compose.yml`) e T043 (`scripts/verify_pipeline.py`) estão pendentes e seus arquivos alvo correspondentes ainda não existem no repositório (consistente com status `[ ]`). | Raiz do projeto (`docker-compose.yml`, `scripts/`) |
| **A009** | 🟢 LOW | Consistência | Variação ortográfica na nomenclatura da persona do sistema: no PRD (`_reversa_sdd/prd.md`) e no `state.json` foi utilizada a grafia `cectico`, ao passo que nos requisitos, roadmap, interfaces, código e testes foi padronizada a grafia correta `cetico`. | `_reversa_sdd/prd.md` vs `requirements.md` / `app/core/searcher.py` |

---

## 3. Detalhamento dos Findings Críticos e Altos

### 3.1 Finding A001 (HIGH) — Divergência Numérica nas Métricas de `actions.md`
- **Impacto:** A tabela de resumo quantitativo de `actions.md` apresenta valores defasados (`Concluídas: 20`, `Em aberto: 24`, soma 44). Contudo, a ação `T027` (Implementar orquestrador de busca em `app/core/searcher.py`) já se encontra formalmente marcada com checkbox `[X]`. Portanto, o total real de tarefas concluídas é 21 e o saldo em aberto é 23. Essa divergência prejudica métricas automatizadas de progresso e sincronização.
- **Sugestão de Correção:** O operador deve atualizar a tabela de resumo em `actions.md` via edição manual ou invocar `/reversa-to-do` para recalcular as métricas a partir das linhas físicas.

### 3.2 Finding A002 (HIGH) — Descompasso de Checkboxes no `actions.md` frente ao Código Real
- **Impacto:** Todas as ações da Fase 3 (T021 a T026, T028 e T029), da Fase 4 (T030 a T039) e a ação T040 da Fase 5 encontram-se implementadas com código completo e plenamente funcional em `app/` (rotas FastAPI, schemas Pydantic, orquestradores de domínio `Planner`, `Searcher`, `Auditor` e `Writer`, clientes HTTP resilientes `JinaClient`, `LLMClient` e `WebhookClient`, e banco relacional). Porém, os checkboxes permanecem `[ ]`. Isso gera um falso alerta de incompletude do projeto.
- **Sugestão de Correção:** Executar a etapa de sincronização de progresso via `/reversa-coding` ou atualizar manualmente os checkboxes em `actions.md` para refletir o estado real do monólito.

### 3.3 Finding A003 (HIGH) — Incompatibilidade em `PERSONAS_CONFIG` no Guia de Onboarding
- **Impacto:** No arquivo `onboarding.md`, a instrução para a variável `PERSONAS_CONFIG` é apresentada como um JSON serializado (`'{"planejador":"persona-planejador", ... ,"redator":"persona-redator"}'`). No entanto, o código real da aplicação (`app/config.py`, `app/core/planner.py`, `app/core/writer.py`) realiza parse como lista separada por vírgulas (`split(",")`) e verifica estritamente se `"redator final"` está contido na lista configurada. Se um operador configurar o ambiente copiando o snippet de `onboarding.md`, o endpoint de redação rejeitará as requisições com `ValueError: Configuração inválida: persona 'redator final' não encontrada em PERSONAS_CONFIG`.
- **Sugestão de Correção:** O operador deve alinhar o exemplo em `onboarding.md` para o formato canônico: `PERSONAS_CONFIG="planejador,historiador,visionario,cetico,futurista,auditor,redator final"`.

---

## 4. Itens Verificados e Aprovados (Conformidade Confirmada)

### Eixo 1: Cobertura Funcional e Rastreabilidade
- [X] **RF-01 a RF-12 Cobertos:** Todos os doze requisitos funcionais especificados em `requirements.md` possuem decisões técnicas correspondentes no `roadmap.md` e ações dedicadas em `actions.md`.
- [X] **Cenários Gherkin:** Todos os 10 cenários de aceitação de `requirements.md` encontram-se cobertos por suítes de teste de integração em `tests/integration/test_endpoints.py` e `tests/integration/test_edge_cases.py`.
- [X] **Endpoints Implementados:** Os quatro endpoints principais (`POST /api/v1/plan`, `POST /api/v1/search`, `POST /api/v1/audit`, `POST /api/v1/writer`) e os dois endpoints administrativos (`POST` e `GET /api/v1/admin/credentials`) estão implementados e mapeados no roteador unificado `app/api/v1/router.py`.

### Eixo 2: Consistência Conceitual e de Contratos
- [X] **Tratamento de N_PONTOS:** A regra **RN-02** é cumprida à risca. Caso `N_PONTOS` não esteja definida em variáveis de ambiente nem na tabela de credenciais, o sistema não assume fallback hardcoded e rejeita a execução em `POST /api/v1/plan` com código HTTP 500 (`CONFIG_ERROR`), validado no teste `test_plan_missing_n_pontos_returns_500`.
- [X] **Loop Agêntico do Searcher com 4 Personas:** O módulo `app/core/searcher.py` orquestra concorrentemente via `asyncio.gather` as quatro personas analíticas (`historiador`, `visionario`, `cetico`, `futurista`). Cada persona opera autonomamente com padrão ReAct, formulando suas próprias queries (teto máximo de 3 queries por ponto), executando busca via Jina SERP, filtrando URLs redundantes por pesquisa (RN-04) e persistindo o conteúdo textual completo em `conteudo_coletado` sem truncamento (RN-05).
- [X] **Segurança e Criptografia:** A regra **RN-10** e decisão **DT-03** foram plenamente atendidas por `CryptoService` utilizando cifra reversível Fernet (AES-128-CBC + HMAC-SHA256) atrelada à chave mestra `CREDENTIALS_MASTER_KEY`, aplicando precedência estrita de variáveis de ambiente do contêiner sobre registros salvos em banco.
- [X] **Assinatura HMAC de Webhook:** A regra **RN-09** e decisão **DT-04** foram implementadas em `WebhookClient` com cálculo de assinatura HMAC-SHA256 (`X-Signature: sha256=<hex>`) sobre os raw bytes do JSON e comparação timing-safe com `hmac.compare_digest`.

### Eixo 3: Coerência com o Legado e Arquitetura
- [X] **Restrição de Acesso à SERP no Plano:** O `Planner` restringe as chamadas do Jina estritamente a metadados da SERP (`title`, `url`, `description`), respeitando o Non-Goal `NG-01` da SDD de planejamento e vedando raspagem de corpo de páginas antes da busca.
- [X] **Checklist de 12 Perguntas na Auditoria:** O `Auditor` submete o conteúdo de cada ponto investigativo ao LLM forte avaliando formalmente os doze critérios de qualidade (clareza temática, corroboração canônica, atualidade temporal, coerência interna, embasamento factual, aderência ao plano, profundidade, precisão numérica, neutralidade, densidade de evidências, declaração de incertezas e solidez lógica).
- [X] **Bloqueio Estrito de Redação:** O endpoint `POST /api/v1/writer` valida a integridade de status de todos os N pontos cadastrados, rejeitando imediatamente pesquisas com pontos não auditados com código HTTP 400 (`PENDING_AUDIT_POINTS`).
- [X] **Persistência SQLite em Modo WAL:** A camada de banco de dados em `app/db/` implementa SQLAlchemy 2.0 assíncrono com driver `aiosqlite`, ativando obrigatoriamente os pragmas `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` e `busy_timeout=30000`.

### Eixo 4: Sanidade do Grafo de Ações
- [X] **Grafo Acíclico (DAG):** Não foram detectados ciclos de dependência entre as 44 tarefas de `actions.md`.
- [X] **Isolamento de Arquivos em Tarefas Concorrentes:** Todas as tarefas marcadas com o modificador de paralelismo `[//]` possuem arquivos-alvo distintos, prevenindo conflitos de escrita durante a codificação concorrente.

---

## 5. Veredito Final

O planejamento e a base de código do monólito modular da feature `001-pesquisa-profunda-mvp` demonstram **alta qualidade de arquitetura, excelente cobertura de requisitos e plena conformidade operacional**. O monólito está funcional, todos os 70 testes automatizados passam com sucesso e as regras críticas de isolamento de personas, desduplicação de URLs, integridade sem truncamento e ausência de fallbacks hardcoded foram implementadas com rigor.

Os apontamentos levantados nesta auditoria referem-se primordialmente à sincronização cadastral de `actions.md`, consistência de documentação em `onboarding.md` e refinamentos de desacoplamento de contratos e mocks.

**Veredito:** **APROVADO COM RESSALVAS** (Nenhum finding CRITICAL; 3 findings HIGH de natureza documental e de sincronização).

---

## 6. Aviso de Integridade e Próximos Passos

> **Aviso:** Nenhum dos artefatos analisados (`requirements.md`, `roadmap.md`, `actions.md`, `onboarding.md`, `interfaces/` ou código em `app/`) foi alterado durante esta auditoria.

### Próximos Passos Recomendados:
1. **Revisão Documental Manual:** Ajustar `onboarding.md` (Finding A003) para que `PERSONAS_CONFIG` reflita o formato string separado por vírgula com `"redator final"`.
2. **Sincronização de Progresso:** Atualizar a tabela de resumo e os checkboxes das ações já concluídas em `actions.md` (Findings A001 e A002).
3. **Alinhamento de Contrato:** Ajustar o modelo Pydantic do Webhook em `app/core/writer.py` para espelhar as chaves aninhadas `metricas` e `dossier` descritas em `interfaces/external-webhook.md` (Finding A004).

---

Digite **CONTINUAR** para prosseguir conforme a sugestão acima.
