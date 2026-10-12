# Actions — 001-modulo-briefing

## Resumo

- Total de ações: 37 (emendas adicionais listadas ao final)
- Paralelizáveis `[//]`: 11 (T001, T003, T008, T018, T019, T027, T028, T032, T033, T034, T035)
- Maior cadeia de dependência: T001 → T009 → T016 → T010 → T017 → T023 → T028 → T032 → T029 → T030 → T031 → T025 → T026 → T012 → T013 (15 níveis)
- Cobertura: RF-01 a RF-10; NFR modularidade/segurança/rastreabilidade/confiabilidade/testabilidade
- Propostas técnicas (módulo `app/briefing/`, rotas, entidade) distinguem-se das decisões aprovadas em `requirements.md`; nada aqui amplia escopo para pesquisa/frontend

## Sprints sugeridos (1–3 ações)

- S1: T001, T002, T003
- S1 corretiva: T014, T015 (findings F-01–F-03 e observação O-01 da inspeção)
- S2: T009 (adapter SERP Jina isolado)
- S2 corretiva: T016 (configuração inválida do adapter, antes de auditoria e QA)
- S3: T004, T005 (entrega RED local, ações abertas até gates integrados)
- S4: T007 (GREEN do domínio puro contra RED T004/T005)
- S5: T006, T010 (geração/orquestração; T008 já entregue em isolamento)
- S5 corretiva: T017 (F-contratos-01; validação numérica antes de reauditoria e QA local)
- S5 cobertura complementar: T018, T019 (recortes independentes, test-only; verificação e auditoria/QA locais antes de T011)
- S6 (Sprint A de T011 — persistência SQL durável): T020, T021, T022
- S7 (Sprint B de T011 — binding LLM real e orquestração integrada): T023, T024
- S7 corretiva: T027, T028 (falhas reproduzidas; arquivos disjuntos, estado compartilhado pelo Orchestrator)
- S7 binding corretiva: T029, T030, T031 (delta contratual auditado PASS; gates de implementação, inspeção e QA separados)
- S7 evidência T029: T032, T033 (observações LOW confirmadas; teste e documentação disjuntos, em paralelo, antes de reauditoria/QA)
- S8 preparação: refinar contrato HTTP T025/T026 e D4; T034 rastreabilidade pós-QA em paralelo, arquivos disjuntos. Coding somente após auditoria do delta.
- S8 (Sprint C de T011 — HTTP endpoints e publicação read-only): T035 (schemas D4), T025, T026
- S9: T012 (QA funcional runtime)
- S10: T013 (auditoria segurança/rastreabilidade)

## Fase 1 — Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| [//] T001 | Definir fronteira `app/briefing/` e decidir entidade isolada vs reutilização seletiva de `Research` (decisão isolada registrada em T015); registrar estados `generating/draft/failed/approved` | — | [//] | `app/briefing/domain.py` | 🟡 | [X] |
| T002 | Congelar contratos HTTP briefing e matriz de erros (422 conteúdo, 409 conflito/estado, 404 ausente, 503 falha externa) sem segredos (corrigido por T014) | T001 | — | `app/briefing/schemas.py` | 🟡 | [X] |
| [//] T003 | Verificar contrato oficial Jina Search: confirmar mecanismo Google e campos da resposta; guardar fixture redigida e mapear parser; registrar decisão se não comprovado | — | [//] | `_reversa_forward/001-modulo-briefing/investigation.md` | 🟢 | [X] |

## Fase 1.1 — Correções de Inspeção (Sprint 1)

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T014 | Corrigir F-01 e F-02 da inspeção em `schemas.py`: tipar `BriefingResponse.status` com `BriefingStatus` e validar 3–7 pontos em conteúdo aprovado/draft; adicionar testes | T002 | — | `app/briefing/schemas.py` | 🟢 | [X] |
| T015 | Registrar decisão de entidade briefing isolada (F-03), alinhar representação HTTP e data delta; corrigir proveniência T001/T002 via append-only com checks reproduzíveis (O-01) | T001, T014 | — | `_reversa_forward/001-modulo-briefing/data-delta.md` | 🟢 | [X] |

## Fase 2 — Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T004 | Testar validação de tema 3–300 (trim e limites) e contrato local `new_briefing`/`validate_theme` do adendo T007; testes RED contra o contrato antes da implementação; rejeição antes de chamadas externas é gate integrado pendente de T010 (RF-01, RF-08) | T001, T002, T014 | — | `tests/test_briefing_validation.py` | 🟢 | [ ] |
| T005 | Testar ciclo local draft/aprovado/reabertura, edição inválida atômica, bloqueio aprovado, limites 3–7, identidade/versão/snapshot isolado/read-approved segundo adendo T007; testes RED contra o contrato; gate parcial: RF-05 exige versão durável consultável em T011, ação permanece aberta até integração (RF-05, RF-06, RF-09) | T001, T002, T014 | — | `tests/test_briefing_lifecycle.py` | 🟢 | [ ] |
| T006 | Testar geração isolada conforme adendo T006/T010 do roadmap (matriz a–m): happy path tema→SERP→LLM→DRAFT 3–7; tema inválido com zero I/O (gate integrado de T004); falha SERP não chama LLM e marca FAILED; falha LLM reusa SERP sem nova busca; esgotamento de 4 tentativas marca FAILED; prompt ausente/vazio/não-string falha antes de SERP/LLM (A004); parse/conteúdo inválido conta tentativa com mensagem segura de shape/count (A002); CancelledError propaga; timeout por tentativa; config inválida `ValueError` antes de I/O (A002); retorno não-string consome tentativa (A002); exceção desconhecida propaga 1 chamada sem retry (A002); instrução JSON no payload `user` assercionada (A003) (RF-02, RF-03, RF-04, RF-10) | T001, T003 | — | `tests/test_briefing_generation.py` | 🟢 | [X] |

## Fase 3 — Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T007 | Implementar domínio puro stdlib em `app/briefing/domain.py` (sem DB/HTTP/I-O/persistência): `Briefing`/`BriefingPoint` congelados + `new_briefing`/`complete_briefing`/`fail_briefing`/`edit_briefing`/`approve_briefing`/`reopen_briefing`/`read_approved`; validação atômica 3–7 com título/descrição, snapshot/identidade/isolamento; reutilizar helpers auditados (RF-01, RF-03, RF-05, RF-06, RF-09) | T001 | — | `app/briefing/domain.py` | 🟢 | [X] |
| [//] T008 | Implementar carregador e prompt de arquivo (`prompts/briefing.md`): alvo habitual de 5 pontos, adaptável entre 3–7; validar ausência/vazio/formato e falhar sem chamar agente (RF-04, RF-08) | T001 | [//] | `app/briefing/prompt_loader.py` | 🟢 | [X] |
| T009 | Implementar adapter SERP Jina exclusivo: uma chamada ativa, sem Reader/outras tools, retry sequencial até 4 totais por operação (RF-02, RF-10) | T001, T003 | — | `app/briefing/serp_client.py` | 🟢 | [X] |

## Fase 3.1 — Correção de verificação do adapter

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T016 | Corrigir verificação T009: validar chave como token ASCII imprimível sem espaços/controles antes de I/O; erro fixo sem chave; testes RED/GREEN. Registrar reparo estrutural JSONL (separador T015/T009), preservando valores históricos | T009 | — | `app/briefing/serp_client.py` | 🟢 | [X] |
| T017 | Corrigir F-contratos-01 da inspeção em `service.py`: validar `llm_timeout_s` contra limites de conversão/sinal antes de `math.isfinite` para garantir `ValueError` mesmo em inteiros extremos negativos/positivos, mantendo zero I/O; adicionar testes RED/GREEN | T010 | — | `app/briefing/service.py` | 🟢 | [X] |
| [//] T018 | Completar cobertura O-01/O-05 de T006/T010: matriz de tipos/limites do tema e configuração com zero I/O, campos inválidos isolados em lista de 3 pontos e cercas inválidas; somente testes do serviço real, sem correção de produção | T010, T017 | [//] | `tests/test_briefing_generation_boundaries_qa.py` | 🟢 | [X] |
| [//] T019 | Completar cobertura O-02/O-03/O-04 de T006/T010: canaries realmente injetados, factory real com identidade/snapshots por fluxo, retries sequenciais/exaustão e cancelamento externo; somente testes do serviço real, sem correção de produção | T010, T017 | [//] | `tests/test_briefing_generation_flow_qa.py`, `tests/test_briefing_generation_concurrency_qa.py` | 🟢 | [X] |

## Fase 4 — Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T010 | Orquestrar geração no mesmo registro via `generate_briefing` (assinatura no adendo T006/T010 do roadmap): new_briefing→prompt_loader (string não-vazia após strip, A004)→search UMA vez por geração (retry 4 é interno do cliente T009, sem retry duplo)→loop LLM ≤4 tentativas sequenciais reusando SERP→complete_briefing/fail_briefing com erro seguro; llm_complete one-attempt injetado, sem binding real (binding LLM real é sub-passo de T011; fakes provam orquestração, não geração runtime); sequencial POR INVOCAÇÃO — o lock de busca pertence à instância `JinaSerpClient` (T009) e não serializa o serviço nem LLMs concorrentes; serialização mais ampla, se aprovada, fica T011 (A005); gate integrado de T004 fecha só com execução real + auditoria/QA (RF-03, RF-08, RF-10) | T007, T008, T009, T016 | — | `app/briefing/service.py` | 🟢 | [X] |
| T020 | Definir ORM `BriefingRecord` e `BriefingVersion` com conversores domain↔snapshot (D1, D2); mapear UUID4 nativo, campos monotônicos e tupla imutável | T007, T015 | — | `app/models/domain_models.py`, `app/briefing/storage.py` | 🟢 | [X] |
| T021 | Criar migração Alembic aditiva para tabelas `briefings` e `briefing_versions` com FK cascade, unique(briefing_id, version) e índices (D2) | T020 | — | `alembic/versions/` | 🟢 | [X] |
| T022 | Implementar storage assíncrono: inserção curta generating Tx1, consulta atual, histórico ASC, e CAS update Tx2 com atomicidade transacional e 409 em colisão (D2, D3) | T020, T021 | — | `app/briefing/storage.py`, `tests/test_briefing_storage.py` | 🟢 | [X] |
| T023 | Implementar binding LiteLLM one-attempt via factory `make_scout_complete(session_factory, default_timeout_s=30.0)` para role `scout`, com timeout finito, transporte seguro e sem retry/router interno (D5) | T010, T017 | — | `app/briefing/llm_binding.py`, `tests/test_briefing_llm_binding.py` | 🟢 | [X] |
| T024 | Integrar orquestração persistida em serviço/storage: reservar Tx1, executar fora de Tx, persistir CAS Tx2, reuso SERP entre tentativas e captura de aborto de emergência (D1, D3) | T022, T023 | — | `app/briefing/service.py`, `tests/test_briefing_persisted_orchestration.py` | 🟢 | [X] |
| [//] T027 | Corrigir verificação de T024: saída JSON válida com pontos inválidos deve consumir tentativa e reutilizar SERP; sucesso posterior DRAFT, exaustão FAILED com erro seguro e histórico v2. TDD contra orquestração persistida real | T024 | [//] | `app/briefing/service.py`, `tests/test_briefing_persisted_orchestration.py` | 🟢 | [X] |
| [//] T028 | Corrigir verificação de T023: normalizar timeout extremo para ValueError seguro e validar override antes de I/O; preservar valores positivos finitos acima de 30s. TDD via fábrica/callable reais | T023 | [//] | `app/briefing/llm_binding.py`, `tests/test_briefing_llm_binding.py` | 🟢 | [X] |
| T029 | Corrigir F-CONTRACT-01: desligar retries internos LiteLLM/SDK por chamada; uma tentativa do binding gera um request OpenAI em erro 503, sem fallback. TDD com acompletion real e HTTPX MockTransport | T023, T028, T032, T033 | — | `app/briefing/llm_binding.py`, `tests/test_briefing_llm_binding.py` | 🟢 | [X] |
| T030 | Corrigir F-ERROR-01: APIConnectionError e InternalServerError/HTTP 500 elegíveis produzem LLMAttemptError seguro sem segredo; preservar falhas reconhecidas 429/502/503/504 e timeout de provider, sem mascarar auth/config e programação desconhecida; sem alterar complete legado | T029 | — | `app/briefing/llm_binding.py`, `tests/test_briefing_llm_binding.py` | 🟢 | [X] |
| T031 | Corrigir F-CONSISTENCY-01: refinar/auditar ownership de sessão e assinatura da fábrica; resolver settings/modelo/chave em sessão curta própria fechada antes de LLM, sem commit/rollback da sessão arbitrária do chamador; preservar keyword default_timeout_s e override timeout_s, validação antes de sessão/I/O e valores finitos positivos >30s (T028); implementar após auditoria do delta com teste integrado SQLite/settings reais | T030 | — | `app/briefing/llm_binding.py`, `tests/test_briefing_llm_binding.py`, `interfaces/briefing-http.md` | 🟡 | [X] |
| [//] T032 | Sanar O-TEST-01 da inspeção T029: teste SDK deve restaurar follow_redirects dos dois clientes globais mesmo quando semeados True; desativar telemetry somente no escopo do teste, preservar helper real e LLMAttemptError/count1; somente teste | T023, T028 | [//] | `tests/test_briefing_llm_binding.py` | 🟢 | [X] |
| [//] T033 | Sanar O-DOC-01/O-DOC-02 da inspeção T029: qualificar RED/GREEN histórico vs teste atual com helper real; corrigir T024/T027 já entregues sem fechar T030/T031; comando discover físico já correto não editar | T023, T028 | [//] | `_reversa_forward/001-modulo-briefing/audit/t029-execution.md`, `_reversa_forward/001-modulo-briefing/regression-watch.md` | 🟢 | [X] |
| [//] T034 | Alinhar rastreabilidade pós-QA T030/T031: factory session_factory e settings encerrados antes de LLM; registrar T030/T031 fechadas por inspeção/QA, T025 desbloqueada mas não entregue; preservar histórico e IDs W | T030, T031 | [//] | `_reversa_forward/001-modulo-briefing/legacy-impact.md`, `_reversa_forward/001-modulo-briefing/regression-watch.md` | 🟢 | [X] |
| [//] T035 | Enriquecer schemas HTTP D4: adicionar version, error e approved_at em BriefingResponse e criar BriefingVersionResponse (extra=forbid, version>=1, created_at, points default []); adicionar testes em tests/test_briefing_schemas.py | T014, T020 | [//] | `app/briefing/schemas.py`, `tests/test_briefing_schemas.py` | 🟢 | [ ] |
| T025 | Implementar router `/briefings` com auth `require_admin`, CSRF em mutações, rollback de leitura auth antes de I/O, endpoints POST/GET/PATCH/approve/reopen e registro em `app/main.py` (D1, D3, D4) | T014, T024, T027, T028, T031, T035 | — | `app/briefing/router.py`, `app/main.py`, `tests/test_briefing_api.py` | 🟢 | [ ] |
| T026 | Implementar endpoint `GET /briefings/approved/{id}` (read-only 409 se não aprovado) e `GET /briefings/{id}/versions` com `BriefingVersionResponse` (D2, D4) | T025, T035 | — | `app/briefing/router.py`, `tests/test_briefing_api.py` | 🟢 | [ ] |

## Fase 4.1 — Ajuste de conformidade integrado ao lote final

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T036 | Remover timeout HTTP fixo em 30s: usar configuração existente com default 30s, finita e positiva, por tentativa; mesmo valor em Jina, binding e serviço. Validar antes de settings/I/O e provar valores >30s aceitos, sem deadline global nem teto novo (requirements:161–162; interfaces/briefing-http.md:40). Executar no mesmo lote da suíte de aceitação T012 | T025, T026 | — | `app/briefing/router.py`, `tests/test_briefing_api.py`, `tests/test_briefing_acceptance.py` | 🟢 | [ ] |

## Fase 5 — Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T012 | QA funcional pelos cenários Gherkin RF-01–RF-10; gate de runtime obrigatório para binding LLM real de T011: executar geração via role/modelo configurados, verificar timeout acordado, no máximo 4 chamadas totais sem retry/fallback aninhado, uma chamada ativa por tentativa e erro seguro sem segredo/payload bruto; registrar evidência sem executar pesquisa (separado de implementação, sem DevOps). Fakes não satisfazem gate do binding (A001) | T004, T005, T006, T010, T024, T025, T026, T036 | — | `tests/test_briefing_acceptance.py` | 🟢 | [ ] |
| T013 | Auditoria de segurança e rastreabilidade: relatório independente sem segredos em resposta/erro/log, proveniência de prompt e histórico de edições/aprovação (sem criar código do produto) | T012 | — | `_reversa_forward/001-modulo-briefing/audit/seguranca-rastreabilidade.md` | 🟡 | [ ] |

## Fase 5.1 — Convergência documental pós-auditoria

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| T037 | Corrigir draft pós-quality sem ampliar produto: remover idempotência de estado inventada e garantia terminal absoluta; distinguir referência de prompt de conteúdo proibido; completar critérios textuais e alinhar A013/A014/status/rastreabilidade da entrega HTTP. Reusar contratos aprovados; gates QA/runtime permanecem abertos | T031, T034 | — | `_reversa_forward/001-modulo-briefing/requirements.md`, `_reversa_forward/001-modulo-briefing/roadmap.md`, `_reversa_forward/001-modulo-briefing/interfaces/briefing-http.md`, `_reversa_forward/001-modulo-briefing/legacy-impact.md`, `_reversa_forward/001-modulo-briefing/regression-watch.md` | 🟡 | [ ] |
| T038 | Sanar 6 reprovações da quality (Q-010, Q-011, Q-014, Q-015, Q-019, Q-020) e LOW A014–A017 só em texto: cenários Gherkin de timeout por tentativa e saída inválida, unidade/strip/fronteiras 2/3/300/301, SERP vazio e prompt inválido, glossário, termo timeout persistido, distinção CAS vs duplicidade/concorrência de criação (decisão não tomada marcada como fora de escopo, sem inventar); alinhar roadmap:178, atribuição de `orchestrate_persisted_briefing` a `service.py` e referências numéricas. Sem código e sem testes | T037 | — | `_reversa_forward/001-modulo-briefing/requirements.md`, `_reversa_forward/001-modulo-briefing/roadmap.md`, `_reversa_forward/001-modulo-briefing/legacy-impact.md`, `_reversa_forward/001-modulo-briefing/regression-watch.md` | 🟡 | [ ] |

## Emendas

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confiança | Status |
|----|-----------|--------------|-------------|--------------|-----------|--------|
| E001 | Configurar modelo padrão da role scout para `gemini/gemini-3.8-flash` com fallback explícito em `runtime_settings()` | - | - | `app/services/settings.py`, `tests/test_briefing_llm_binding.py` | 🟢 | [X] |

