# Cross-check — T037 / A011–A014 — revisão documental final afetada

Data: 2026-10-11T20:23:02.374091+00:00. Feature `001-modulo-briefing`; branch `main`; estágio registrado `coding`.

Artefatos: [requirements.md](../requirements.md), [roadmap.md](../roadmap.md), [actions.md](../actions.md), [HTTP](../interfaces/briefing-http.md), [legacy-impact.md](../legacy-impact.md), [regression-watch.md](../regression-watch.md).

## Veredito vigente

**Documental: PASS COM RESSALVAS LOW. Local: implementação entregue e verificada pelo parent; não reaprovada funcionalmente nesta revisão. Global: CONDICIONAL, sem aceite DONE/sync.**

Findings ativos: **CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 4**. A011–A013 sanados; A014 parcialmente sanado, com instrução residual pré-schemas. Nenhum defeito de produto demonstrado. Lacunas de redação não foram promovidas a bugs.

T037 entregue documentalmente, não fechado pelo auditor. 36 ações únicas, 27 `[X]`, 9 `[ ]`: T004, T005, T035, T025, T026, T036, T012, T013, T037. Abertura representa gates, não ausência de implementação. T012 com provedor real e QA final independente **não executados**. Evidência herdada: `progress.jsonl:101,103–104`, parent execution39, suíte 183 testes exit0; não executada novamente. Relatório `audit/t012-t036-execution.md:58` realmente contém comando discover e resultado 183 OK; não prova rede/provedor real.

## Resolução estável dos findings anteriores

| ID | Severidade original | Disposição atual | Evidência atual |
|---|---|---|---|
| A011 | MEDIUM | SANADO: T012 depende explicitamente de T036 | `actions.md:104` |
| A012 | LOW | SANADO: resumo 36, inclui T037; recomputado das linhas físicas | `actions.md:5,111` |
| A013 | LOW | SANADO: factory preserva session_factory e default_timeout_s=30.0, sem perder contrato de timeout/override | `actions.md:80,86`; `roadmap.md:142–143`; `interfaces/briefing-http.md:106`; assinatura AST `app/briefing/llm_binding.py:101` |
| A014 | LOW | PARCIAL: status entregue/histórico convergiu; permanece instrução não qualificada para criar schemas já entregues | `roadmap.md:174,178`; `interfaces/briefing-http.md:47–51,68` |

## Findings ativos

| ID | Severidade | Eixo | Descrição | Onde está |
|---|---|---|---|---|
| A014 | LOW | Status documental | Adendo vigente afirma schemas implementados, mas última linha ainda manda parent inserir ação de schemas e afirma campos/tipo inexistentes. Marcar esta linha histórica/supersedida em próxima edição do dono; não reenviar implementação já entregue. | `roadmap.md:174,178`; `actions.md:90–92`; `interfaces/briefing-http.md:49` |
| A015 | LOW | Rastreabilidade de símbolo | Linha de storage atribui orchestrate_persisted_briefing/emergência ao arquivo errado; definição pertence a service.py. Corrigir atribuição em próxima edição do dono, sem mudança runtime. | `legacy-impact.md:199–200`; `app/briefing/service.py:104`; `app/briefing/storage.py:64,79,89` |
| A016 | LOW | Processo/whitespace | Blank EOF confirmado por no-index, sem impacto runtime. Tracked diff-check não comprova limpeza destes documentos untracked. | `actions.md:112`; `legacy-impact.md:206`; `regression-watch.md:206` |
| A017 | LOW | Citação numérica | T036 aponta requirements:161–162 como timeout, mas essas linhas são MoSCoW; decisão correta está :193–194. Citação roadmap:10 de rastreabilidade aponta :68, que trata SERP, em vez de :76/:163. IDs/regras existem, referências numéricas precisam atualização. | `actions.md:98`; `requirements.md:68,76,161–164,193–194`; `roadmap.md:10` |

Sem finding CRITICAL/HIGH: não há recomendação de reparo de código ou ampliação de escopo. LOW deve entrar em próxima edição documental autorizada, sem dispensar nenhum gate.

## Cobertura e consistência verificadas

### Produto e T037

- Fonte de produto: requirements aprovados e contratos vigentes, não código antigo (`requirements.md:14–21`, `roadmap.md:5,9–12`). Sem recuperação de regras históricas, pesquisa, frontend, Reader, webhook/SSE, scheduler, lock global ou semântica nova de deduplicação.
- CAS protege versão concorrente, **não deduplica requests**. Repetir approve no estado approved ou reopen no draft continua 409 (`requirements.md:84`; HTTP:14–15,27). Body omitido/null/{} aceito não torna transição idempotente: expressão “body no-op” significa ausência de alteração de payload, não sucesso de transição repetida. Criação idempotente segue não decidida (HTTP:100).
- Emergência failed é **best-effort**; crash/falha catastrófica DB pode impedir persistência (`requirements.md:83`; HTTP:35; roadmap:176). Cenário normal de esgotamento (:115–119) não vira promessa de recuperação após morte do processo.
- Referência de prompt = metadado relativo/hash, nunca texto integral (`requirements.md:76,82,208`). Rastreabilidade é **Should/inferida** (:163), não entrega Must inventada. Proveniência de prompt/busca ainda não persistida: exemplo HTTP:68–84 declara esses campos históricos, não implementados/não planejados nesta rodada. Roadmap:10,37 expressa intenção/proposta; não prova entrega nem autoriza adicionar colunas. T013 deve registrar limite de proveniência, não declarar implementado o metadado ausente nem promover bug sem desvio Must demonstrado.
- HTTP consumo aprovado somente leitura, sem SERP/LLM/pesquisa; reabertura bloqueia consumo com 409 até nova aprovação; histórico ASC append v2+, não v1 (`requirements.md:45–46`; HTTP:16–17; roadmap:176; W031 `regression-watch.md:204`).
- Factory alinhada session_factory/default_timeout_s; timeout finito positivo por tentativa, default 30s sem teto novo, override antes sessão/I/O. Preservação documental não prova todos provedores nem execução live.

### Cenários afetados e gates

Contagem física atual: **11 cenários Gherkin** (`requirements.md:89–155`), não 8 do relatório anterior nem equivalente aos 10 métodos/cenários reportados na suíte. Revisão verifica cobertura planejada, não reexecuta testes nem certifica assert runtime.

| Cenário | Decisão/contrato | Ações e evidência local existente; gate aberto |
|---|---|---|
| Gerar rascunho | roadmap:23–25,124–127; HTTP:11 | T006/T010/T024/T025; QA T012 real pendente |
| Editar rascunho | roadmap:75–79; HTTP:13,17 | T005/T007/T022/T025; versão consultável e QA final pendentes de aceite |
| Tema inválido antes I/O | roadmap:74,124; HTTP:11 | T004/T006/T025; aceite T004/QA aberto |
| Consumir aprovado | roadmap:81; HTTP:16 | T026; sem investigação; QA final aberta |
| Esgotar agente | roadmap:160; HTTP:29,35 | T006/T024/T027/T012; best-effort crash/DB distinto do caminho normal |
| Rejeitar quantidade | roadmap:75–78,162,168; HTTP:13–14,25 | T005/T006/T014/T022/T025; snapshot anterior protegido |
| Aprovar | roadmap:77–79; HTTP:14,27 | T005/T007/T025; repetição de estado 409 |
| Reabrir | roadmap:77–79; HTTP:15–17,27 | T005/T007/T025/T026; limpa aprovação, consumo draft 409 |
| Falha busca | roadmap:126,158; HTTP:29 | T009/T016/T024; sem rascunho parcial |
| Retentar sem repetir sucesso | roadmap:127,159–160; HTTP:41 | T006/T010/T024/T027/T029; T012 real aberto |
| Prompt ausente/inválido | roadmap:125,161; HTTP:28 | T008/T006/T024; falha segura antes agente |

### Sanidade documental

- Grafo stdlib recomputado: 36 IDs únicos, zero dependências inexistentes, zero ciclos; T012 inclui T036. T037 alvos cinco documentos autorizados em `actions.md:111`; parent alinhou actions separadamente. Sem novos alvos runtime atribuídos nesta revisão.
- 47 cabeçalhos de tabela e 184 linhas de dados inspecionados. Literal cerca JSON em `roadmap.md:168` e `regression-watch.md:73` não é início de bloco fenced: scanner que remove pares simples de crases produz falso width mismatch em W013; inspeção semântica confirma cinco células. Não registrar defeito de tabela derivado desse falso positivo.
- Seis documentos têm **zero links Markdown locais**: zero links efetivamente checados, não “todos links passam”. Onze caminhos de entrega/citações T037 conferidos, todos existem; citação :58 conferida. Símbolos citados conferidos por AST, sem import/execução de produto: factory :101; orquestração service :104; storage create/get_versions/save :64/:79/:89; schemas BriefingResponse/BriefingVersionResponse :72/:90. A015 descreve erro de atribuição, não símbolo inexistente no produto.
- `git diff --check` exit0, saída vazia; no-index requirements/roadmap/HTTP exit1 sem aviso (diferença de arquivo); actions/legacy-impact/regression-watch exit3 com blank EOF acima. Não declarar whitespace limpo.

## Limites, manifesto e preservação

Preflight leu AGENTS, state, active-requirements e `.reversa/reversa-config.json`. Feature resolvida pelo active-requirements; state sem forward_folder, output `_reversa_sdd`. Config permite caminhos gerais, mas auditor limitado exclusivamente a este relatório. Nenhum arquivo de hook encontrado em `.reversa`; before/after-audit não inventados. Nenhum todo_list, delegação, suíte, rede, DB, migração, deploy ou promoção de bug.

Manifesto congelado `progress.jsonl:104`: **230 entradas, 230 arquivos existentes, zero hashes divergentes** antes da escrita. Outputs mutáveis cross-check/requirements-audit e progress já excluídos do manifesto; nenhuma leitura/hash do relatório quality sibling. Conferência SHA-256 é proteção contra mudança, não reinspeção de código/projeto. Revisão semântica limitada aos seis documentos e símbolos/citação acima. Relatório anterior foi lido integralmente e preservado integralmente abaixo, SHA-256 `fcc053ecd794744649df3c0e28000a507484c83bc0c1d2628dd7617c26805218`. Seus veredictos, contagens, linhas e instruções são históricos, não prontidão vigente.

Única escrita: `audit/cross-check.md`. Nenhum requisito, plano, actions, interface, legacy-impact, regression-watch, progress, código ou teste corrigido pelo auditor. Verificação pós-escrita executada: mesmos 230 hashes, zero divergências; conteúdo anterior integral confirmado como substring exata, sem alteração. Único arquivo modificado pela ferramenta: este relatório.

## Próximo gate

Consolidar revisão documental afetada com quality independente; concluir inspeção aplicável e QA final independente; obter autorização e executar T012 no provedor real configurado; registrar T013 com limites reais. Só então avaliar fechamento das ações e sync verificado antes de DONE. Não repetir implementação entregue, não pular gates por suíte183 verde. Sem interação solicitada nesta execução leaf.

## Histórico integral — versão anterior, não veredito vigente

<details>
<summary>Relatório anterior integral preservado</summary>

# Cross-check — auditoria cruzada final requirements vs roadmap vs actions

Data: 2026-10-11T19:43:58.276479+00:00. Branch `main`; feature `001-modulo-briefing`, estágio registrado `coding`.

Artefatos analisados:
- [requirements.md](../requirements.md)
- [roadmap.md](../roadmap.md)
- [actions.md](../actions.md)

Documentos complementares:
- [data-delta.md](../data-delta.md)
- [interfaces/briefing-http.md](../interfaces/briefing-http.md)
- [interfaces/jina-serp.md](../interfaces/jina-serp.md)
- [audit/t011-integration-decomposition.md](t011-integration-decomposition.md)
- [audit/t012-t036-execution.md](t012-t036-execution.md)

## Veredito consolidado

**Veredito documental: PASS COM RESSALVAS. Aceite global: CONDICIONAL; DONE bloqueado.**

Status consolidado por camada:
1. **Implementação local:** ENTREGUE segundo parent e relatório de execução; não reaprovada por este auditor. 183 testes de briefing exit 0, 10 cenários de aceitação Gherkin exit 0, 12 testes de API exit 0, compilação Python limpa, `git diff --check` sem erros.
2. **Parent verification:** verificação local reportada. Verificação de suíte informada pelo parent em L93 e qualificada por L94; L95 não utilizado como evidência nesta auditoria.
3. **Aprovação independente:** PENDENTE. Inspeção de código/segurança e QA formal independente em andamento.
4. **Gate de runtime real (provedor externo):** PENDENTE. T012 validado localmente com SDK LiteLLM real e MockTransport HTTPX; gate com credencial e rede reais do provedor ainda não executado (bloqueio mandatário para `DONE`).
5. **Estado das ações em `actions.md`:** 27 concluídas `[X]`, 8 abertas `[ ]` (T004, T005, T035, T025, T026, T036, T012, T013). As 7 primeiras foram reabertas deliberadamente pelo parent após L93 para evitar encerramento prematuro antes das revisões formais e do teste com provedor real. T013 é a auditoria de segurança/rastreabilidade. Abertura das ações reflete governança de gates, não ausência de código.

Findings ativos deste ciclo: **CRITICAL: 0 / HIGH: 0 / MEDIUM: 1 / LOW: 3**.

## Tabela de findings

| ID | Severidade | Eixo | Descrição | Onde está |
|---|---|---|---|---|
| A011 | MEDIUM | Sanidade do actions | Ação T036 (timeout HTTP configurável) não consta na lista de dependências formais de T012, embora T012 cubra cenários de aceitação de T036 na suíte de testes. | `actions.md:104` |
| A012 | LOW | Consistência | Cabeçalho de `actions.md` indica "Total de ações: 34", mas a tabela possui 35 ações atômicas (T001–T010, T012–T036) após inclusão de T036. | `actions.md:5` |
| A013 | LOW | Consistência | Descrição da ação T023 ainda menciona assinatura histórica `make_scout_complete(db)` em vez da assinatura refatorada com `session_factory` consolidada em T031. | `actions.md:80` |
| A014 | LOW | Consistência | Drift textual residual pré-implementação: `roadmap.md:174` mantém frase "Proposta pendente de auditoria; não autoriza coding" e contratos citam esquemas inexistentes pré-T035, superados pela entrega de código. | `roadmap.md:174`, `interfaces/briefing-http.md:105` |

## Detalhamento dos findings e orientações

### A011 — Dependência formal de T036 ausente em T012 (MEDIUM)
- **Impacto:** O grafo de dependências declara que T012 depende de `T004, T005, T006, T010, T024, T025, T026`. Como T036 foi adicionada na Fase 4.1 para flexibilização de timeout e sua cobertura integra `tests/test_briefing_acceptance.py`, a omissão de T036 em `actions.md:104` deixa a dependência implícita em vez de explícita.
- **Sugestão de correção:** Ajuste manual em `actions.md` ou invocação de `/reversa-to-do` para acrescentar `T036` nas dependências de `T012`. Este skill de auditoria não altera `actions.md`.

### A012 — Divergência numérica no resumo de ações (LOW)
- **Impacto:** Metadado descritivo ("Total de ações: 34") desatualizado em 1 unidade frente às 35 linhas presentes na tabela de ações. Não afeta integridade do pipeline nem execução de testes.
- **Sugestão de correção:** Atualização manual da contagem no cabeçalho de `actions.md`.

### A013 — Drift descritivo na assinatura de T023 (LOW)
- **Impacto:** Texto de T023 em `actions.md:80` ainda menciona `make_scout_complete(db)`, enquanto o contrato vigente pós-T031 e o código entregue utilizam `make_scout_complete(session_factory: async_sessionmaker[AsyncSession])`. O adendo T029–T031 e os testes já estão alinhados.
- **Sugestão de correção:** Ajuste cosmético no texto da linha de T023 em `actions.md`.

### A014 — Drift de marcadores documentais históricos (LOW)
- **Impacto:** Frases como "Proposta pendente de auditoria; não autoriza coding" em `roadmap.md:174` e referências a schemas inexistentes em notas contratuais representam notas datadas da fase de planejamento pré-T035/T025/T026, e não regras conflitantes vigentes.
- **Sugestão de correção:** Limpeza e sincronização documental na fase `/reversa-sync`.

## Itens verificados que passaram

### 1. Cobertura funcional e cenários Gherkin (PASS)
- **RF-01 (Tema 3–300 caracteres):** Coberto em `roadmap.md:5,103`, ações T004, T007, T010, T025. Testado em `tests/test_briefing_validation.py` e cenário Gherkin 1 de `tests/test_briefing_acceptance.py`. Rejeição antes de I/O prevista e coberta na evidência local reportada.
- **RF-02 (SERP Jina exclusiva sem leitura de páginas):** Coberto em `roadmap.md:20`, ações T003, T009, T016. Adapter usa cabeçalho `X-Respond-With: no-content`, sem fetch de URLs nem Reader.
- **RF-03 (Rascunho de 3 a 7 pontos de foco, habitual 5):** Coberto em `roadmap.md:24`, ações T002, T006, T007, T008, T010, T014, T018. Validação atômica em geração, edição e aprovação.
- **RF-04 (Instrução de prompt via arquivo):** Coberto em `roadmap.md:25`, ações T008, T010. Prompt carregado em tempo de execução de `app/prompts/briefing.md`, sem fallback de texto embutido no código. Falha em arquivo ausente/vazio testada.
- **RF-05 (Edição de rascunho mantendo 3–7 pontos):** Coberto em `roadmap.md:5`, ações T005, T007, T022, T024, T025. Snapshot imutável, versionamento append v2+, histórico consultável em `/briefings/{id}/versions`.
- **RF-06 (Aprovação do briefing e bloqueio de edição direta):** Coberto em `roadmap.md:26`, ações T005, T007, T025. `approved_at` registrado; edição direta em `approved` responde 409 Conflict.
- **RF-07 (Exposição para etapas posteriores):** Coberto em `roadmap.md:27`, ações T025, T026. Endpoint read-only `/briefings/approved/{id}` retorna snapshot puro sem disparar pesquisa.
- **RF-08 (Tratamento seguro de falhas):** Coberto em `roadmap.md:23,25,26`, ações T004, T006, T010, T016, T017, T024, T030. Contrato exige mensagens fixas seguras; ausência de vazamento depende da auditoria independente T013.
- **RF-09 (Reabertura de briefing aprovado):** Coberto em `roadmap.md:26`, ações T005, T007, T025. Transita `approved → draft`, limpa `approved_at`, incrementa versão e reabilita edição.
- **RF-10 (Retentativas automáticas no mesmo registro):** Coberto em `roadmap.md:20,21,23`, ações T006, T009, T010, T023, T024, T027, T029, T030. Até 4 tentativas sequenciais; reuso de resultados SERP em falha de LLM; desativação de retries aninhados (`num_retries=0`, `max_retries=0`).
- **Cenários Gherkin (8/8):** Todos os 8 cenários de `requirements.md:74–124` possuem cobertura documental no roadmap/actions e matriz reportada em `audit/t012-t036-execution.md`. Suite não executada por este auditor.

### 2. Consistência e integridade referencial (PASS)
- **Terminologia uniforme:** Uso uniforme dos termos `theme`, `BriefingPoint`, `generating`, `draft`, `approved`, `failed`, `reopen`, `version`, `versions`.
- **Identificadores citados:** Todos os identificadores de requisitos (RF-01 a RF-10, RN-01 a RN-07) e decisões (D1 a D5) são válidos e correspondem aos documentos fonte.
- **Contratos de interface:** Interfaces HTTP e SERP possuem decisões correspondentes no roadmap; conformidade runtime não certificada por esta auditoria.

### 3. Coerência arquitetural e regras de domínio (PASS)
- **Isolamento de domínio:** Entidade `Briefing` estritamente desacoplada do modelo legado `Research`/`ResearchPoint`.
- **SERP sem scraping:** Invocação isolada de `s.jina.ai` com `X-Respond-With: no-content` e parser tolerante com três campos obrigatórios (`title`, `url`, `description`).
- **Timeout configurável:** Suporte a timeout configurável por tentativa via `SEARCH_TIMEOUT_SECONDS` (default 30s), repassado de forma homogênea a SERP, LLM binding e serviço, aceitando valores finitos positivos > 30s sem deadline global extra.
- **Versionamento e integridade transacional:** Modelo append-only v2+ em `briefing_versions`, CAS com verificação de colisão e 409 em corrida.

### 4. Sanidade do grafo de ações (PASS)
- **Total de ações:** 35 ações na tabela.
- **Ciclos de dependência:** 0 ciclos detectados via DFS.
- **Dependências fantasmas:** 0 dependências para IDs inexistentes.
- **Paralelismo:** 11 ações com tag `[//]`; pares com arquivos compartilhados têm dependência transitiva que impõe ordem (T028/T032 e T033/T034). Zero pares potencialmente concorrentes com alvo compartilhado.
- **Status factual:** 27 ações `[X]`, 8 ações `[ ]`. Parent distingue código local entregue de aprovação independente pendente. T013 não é implementação; relatório próprio pendente, não lido.

---

## Próximos passos recomendados

1. Aguardar conclusão das inspeções finais de código e segurança.
2. Executar QA formal independente.
3. Submeter ao gate de runtime com provedor LLM real e credenciais autorizadas para encerramento de T012 e liberação para `/reversa-sync`.
4. Atualizar pequenos desvios documentais de `actions.md` (A011, A012, A013) durante o fechamento.

---

## Limites, referências e preservação

Auditoria leitora documental; nenhuma suíte, rede, migração ou provedor executado. Números 183/10/12 são evidência reportada pelo parent e relatório de execução, não execução deste auditor. Reports siblings mutáveis segurança/quality não consultados. Hooks before/after-audit não configurados; nenhum hook inventado. State não define forward_folder; active-requirements resolve pasta exata. Legado excluído como fonte de produto por requirements:12–21.

T011 não possui linha atômica vigente: representa agrupamento histórico explicitamente decomposto em T020–T026 por audit/t011-integration-decomposition.md e sprints do actions. Não é dependência fantasma. RF-01–RF-10 cobertos 10/10; oito cenários 8/8. Decisões: fronteira T001/T015/T007; persistência T020–T022/T024; SERP T003/T009/T016; retry LLM T006/T010/T023/T027/T029–T031; saída T005–T007/T014; prompt T008/T006; estado T005/T007/T025; API T035/T025/T026; timeout T036; segurança T013. Versão corrente inicia v1; histórico append começa v2, conforme adendo HTTP do roadmap, D2 e T022/T026/T027.

Única escrita: cross-check.md. Rewrite atômico final; relatório anterior integral preservado, sem herdar findings históricos na contagem ativa. Hashes requirements/roadmap/actions e cinco complementos verificados inalterados. Sem autocorreção, sem fechamento de ações, sem todo_list. Próximo passo não é novo despacho de código por checkbox aberto: revisão das ressalvas, gates independentes e autorização do provedor real antes de DONE.

## Histórico anterior mantido integralmente

<details>
<summary>Cross-check anterior integral (Sprint 8 T035/T025/T026 e anteriores)</summary>


# Cross-check — reauditoria documental Sprint8 T035/T025/T026

Data: 2026-10-11T15:53:21.328740+00:00. Branch `main`; feature `001-modulo-briefing`, estágio `coding`.

**Verdict do gate de PLANO: PASS. Readiness global de entrega: CONDITIONAL.** A007–A010 resolvidos documentalmente; zero findings ativos neste recorte. Plano HTTP consumível sem novo preflight LLM nem alteração de service/binding. T035/T025/T026 permanecem `[ ]`: aprovação documental não aprova código T035, não substitui inspeção/QA e não fecha aceite runtime T012 ou segurança T013. T026 só executa após dependências T025/T035 satisfeitas.

Fontes produto: [requirements](../requirements.md), [PRD](../../../_reversa_sdd/prd.md), [SDD briefing](../../../_reversa_sdd/sdd/briefing.md). Fontes técnicas: [actions](../actions.md):90–92, [roadmap](../roadmap.md):172–178, [HTTP](../interfaces/briefing-http.md):3–49,104–107, [delta completo](t025-t026-planning-delta.md):1–41, [D1–D4/D5](t011-integration-decomposition.md):6–77,95–120. Produto greenfield; legado somente integração.

## Disposição dos findings estáveis

Ativos: **CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0**. Reavaliados: 4; resolvidos: 4; abertos: 0; novos IDs: 0. Severidades originais abaixo não integram contagem ativa. A001–A006 preservados no histórico, não reauditados nem reabertos.

| ID | Severidade original | Disposição | Evidência documental e compatibilidade estática |
|---|---|---|---|
| A007 | HIGH | resolvido | Delta:15,37 e HTTP:30,39 retiram promessa LLM pré-Tx1: factory valida timeout; settings/modelo/chave somente na invocação após Tx1/SERP. Binding:101–127 e service:123–126,138,156 sustentam ordem. Sem preflight novo, sem reabrir T031. |
| A008 | HIGH | resolvido | Delta:15,37, HTTP:34 e roadmap:176 distinguem ausência de retry/LLMAttemptError de emergência FAILED best-effort após Tx1. Mensagem fixa `Processamento abortado ou cancelado`; mesma exceção repropaga; HTTP500 genérico quando aplicável. D3:54 e service:182–194 compatíveis. CancelledError repropaga, não vira resposta HTTP500 normal. |
| A009 | MEDIUM | resolvido | Delta:15 e HTTP:31,34 definem AuthenticationError/PermissionDeniedError concretas; APIError.status_code e HTTPStatusError.response.status_code inteiro não-bool 401/403. Sem texto/atributo de exceção arbitrária como classifier. ProviderConfigurationError separado; ValueError capturado só construção/verificação Jina pré-Tx1, nunca handler inteiro. Binding:34–43,72–86,154–159 preservado. |
| A010 | MEDIUM | resolvido | Delta:17,31–32 e HTTP:14–19 convergem: omitido/null/{} sucesso; []/string/número/bool/extras 422, snapshot+history intactos. Parâmetro HTTP opcional dos schemas vazios existentes resolve omissão/null; não ampliar schema request T035. |

A008 residual em delta:37 foi conferido inteiro: não retry/LLMAttemptError; tenta emergência FAILED best-effort; repropaga; HTTP500 seguro. Não resta frase normativa negando emergência nesse parágrafo. D5:116 refere delimitação do callable/loop, não elimina captura externa persistida D3:54; histórico do serviço puro não é prescrição alternativa HTTP.

## Readiness por ação

| Ação | Gate plano | Readiness entrega | Condição restante |
|---|---|---|---|
| T035 | PASS | CONDITIONAL | D4:57–77 e actions:90 explícitos; depende T014/T020. Schemas presentes em schemas.py:72–106 são leitura estática, não aprovação: inspeção e QA independentes ainda necessárias; teste/evidência sibling não lidos. |
| T025 | PASS | CONDITIONAL | actions:91 depende T014/T024/T027/T028/T031/T035. Contrato consumível; executar somente após gate T035 satisfeito. Router e testes HTTP próprios ainda entregas, não evidência desta auditoria. |
| T026 | PASS | CONDITIONAL | actions:92 depende T025/T035. Consulta aprovada read-only e histórico ASC v2+ definidos; aguarda entregas/dependências e checks HTTP. |

Delta:18, roadmap:178 e HTTP:49 ainda dizem “hoje/atual não possui”, “ação a inserir” ou “sem código”. Contexto anterior ao schema entregue e à inclusão actions:90–92: descrição histórica do motivo D4, não prova de ausência atual nem novo bug produto. Prescrição dos campos e dependências permanece inequívoca. Código presente não prova gate T035.

## Critério → ação → verificação exigida (não executada)

| Critério | Ação / fronteira | Assert futuro |
|---|---|---|
| D4 exato | T035; BriefingResponse/BriefingVersionResponse | version>=1, status enum, error/approved_at, created_at obrigatório na versão, points default []; extra forbid; draft/approved 3–7; generating/failed vazios legítimos; serialização completa. |
| Criação e validação | T025; service real com I/O substituído | POST síncrono 201 draft UUID; Tx1 corrente v1, final/histórico v2. Auth válida: inválido422 com zero settings-runtime/SERP/LLM e zero mutação briefing; SELECT auth legítimo. |
| Configuração e emergência | T025; composição Jina/binding/wrapper | Jina constructor inválido préTx1 500 sem registro. LLM config apósTx1/SERP: sem retry, emergência segura tentada, propagação identidade e 500 genérico; injetar falha emergência sem prometer persistência garantida. |
| Classifier e cancelamento | T025; HTTP/service | Classes/status A009 positivos e negativos string/bool/RuntimeError; sem retry desconhecido. Cancelamento real repropaga após tentativa emergência, sem resposta normal de falha. |
| Falhas reconhecidas | T025; snapshot devolvido pelo service | Prompt500; SERP/LLM503 fixos; traduzir snapshot FAILED, não esperar exceções já encapsuladas; estado/histórico exatos e sentinelas ausentes. |
| Auth/transação | T025; require_admin/get_db reais | Cookie SELECT e CSRF concluem antes rollback condicional request; nenhum Principal ORM lido depois. Sem commit auth, sem finalizar sessão caller-owned; 401/403/400 e sucessos cookie+CSRF/bearer/API-key em SQLite isolado. |
| Timeout/retries | T025; JinaSerpClient/make_scout_complete | Finito positivo por tentativa default30, >30 permitido; mesmo llm_timeout_s/default_timeout_s; até4, SERP sucesso reusado, sem deadline global/nested retry; uma ativa por operação, lock Jina por instância. |
| PATCH/approve/reopen | T025; domínio/storage/schema request | Conversão explícita pontos schema para dict/domain; CAS409, estado409, ausente404, inválido422 sem mutação; +1 e append; omitted/null/{} sucesso e demais bodies422; reopen approved_at null. |
| Leitura corrente/histórico | T025/T026; get_briefing/get_briefing_versions | Corrente generating v1 visível durante espera; history vazio na reserva, v2+ ASC depois. Confirmar pai para404; helper history sozinho não valida pai; sem insert v1/migration. |
| Publicação | T026; read_approved/ApprovedBriefingResponse | Read-only exato, ausente404/não aprovado409; SELECT permitido, zero I/O externo/pesquisa, zero incremento/histórico alterado. |

## Checks executados e proveniência

- Preflight CLI `pwd; git status --short; git branch --show-current; python - <<'PY'`: exit0; root `/root/projects/deep-research`, main, árvore previamente suja. AGENTS raiz/ancestors e três JSON canônicos lidos. output_folder `_reversa_sdd`; forward_folder ausente; active-requirements resolve feature coding. Sem AGENTS adicionais nos diretórios pertinentes examinados e sem arquivos hook em `.reversa`; nenhum hook inventado.
- Check documental stdlib `python - <<'PY'` em root: exit0; **34 ações/34 IDs únicos, 0 dependências ausentes, 0 ciclos**. T035: T014/T020; T025: T014/T024/T027/T028/T031/T035; T026: T025/T035. Sem paralelismo novo em arquivos compartilhados: T035 schemas/test próprio, T025/T026 router/test compartilhados seriais. T034 fora do recorte.
- Mesmo check: cinco documentos actions/roadmap/HTTP/delta/D1–D5, **15 tabelas, 0 divergências delimiter; 0 links Markdown locais efetivos, 0 links quebrados; 65 referências T distintas por documento, 0 IDs ausentes**. T011 pai histórico decomposto aceito. Backticks caminhos não são hyperlinks. Links novos deste cabeçalho verificados após escrita. Sintaxe não prova semântica nem valida todos anchors históricos.
- `git diff --check`: exit0 sem saída; tracked somente. Não audita diff código T035 nem testes mutáveis. Nenhum runner executado.
- progress: **84 objetos JSON**, checkpoint L84 `2026-10-11T15:46:53.465578+00:00`, manifest **108 hashes**. Auditor verificou **105/105 próprios contra L84**, zero ausentes/diferenças antes e depois rewrite. Denominador exclui cross-check próprio e dois paths ativos: `tests/test_briefing_schemas.py`, `audit/t035-execution.md`; hashes desses dois HERDADOS L83, não lidos/checados. Novo report sibling T034 recheck não lido/hash. legacy-impact/regression-watch/t034-execution somente hash, sem reauditoria. Não inferir estabilidade dos excluídos a partir do parent.
- Suite **157 testes exit0** é **HERDADA** de `progress.jsonl:L83.software_checks.briefing_suite`, comando parent `python3 -B -m unittest discover -s tests -p 'test_briefing*.py' -v`. Não reexecutada; não prova estado atual dos testes sibling, aprovação código T035, runtime HTTP ou provider. L83.schema_unittest 23 também herdado, não usado como QA desta auditoria.
- Rewrite atômico com SHA pré-escrita validado contra L84: `9c921ba4f6bc52a74eb0c3cda4f072e3251dfd1562ac9b3b577e05c3d43f44cf`; histórico prévio **58197 bytes** preservado integralmente como tail UTF-8 abaixo. Comparação tail byte-a-byte e SHA executada pós-escrita, além dos 105 hashes. Única escrita persistente: este relatório; nenhum requirements/roadmap/actions/interface/delta/código/teste/progress/state/skill modificado.

## Limites e próximo gate

Auditoria leaf documental A007–A010, não implementação/QA T035 nem reauditoria T034. Sem runner/test discovery, import produto/main, HTTP dinâmico, SQLite/DB, DNS/rede/provider, .env/segredos, install, migração, commit/push/deploy, subdelegação/todo_list ou alteração de ações. Nenhuma garantia nova de logs/traceback/provider. Cancelamento não é resposta HTTP500 normal. Gates de inspeção/QA T035, execução HTTP T025/T026 e runtime T012/segurança T013 permanecem abertos.

Parent pode consumir PASS do plano; concluir inspeção/QA T035 separadas antes T025, depois T026 conforme dependências. Não fecha T025/T026, não autoriza release/deploy. Histórico abaixo conserva verdicts antigos apenas para proveniência; primeiro verdict acima é vigente.

## Histórico anterior INTEGRAL — não usar como verdict vigente

# Cross-check — Sprint8 T035/T025/T026 — modulo-briefing

Data: 2026-10-11T15:03:53.172750+00:00. Branch `main`; feature ativa `coding`. **Verdict global: FAIL — plano HTTP não liberado para coding conjunto.** T035 PASS documental; T025 FAIL; T026 CONDITIONAL, condicionado à aprovação/entrega T025 e T035. Nenhuma ação fechada; T031 permanece entregue, inspecionada e QA fechada. Não exigir implementação futura para aprovar plano.

Fontes produto: [requirements](../requirements.md), [PRD](../../../_reversa_sdd/prd.md), [SDD briefing](../../../_reversa_sdd/sdd/briefing.md). Fontes técnicas: [actions](../actions.md), [roadmap](../roadmap.md), [HTTP vigente](../interfaces/briefing-http.md), [delta completo](t025-t026-planning-delta.md), [D1–D4 e adendo T031](t011-integration-decomposition.md). Produto greenfield; não recuperar regras de legado.

## Findings ativos

**CRITICAL 0 / HIGH 2 / MEDIUM 2 / LOW 0.** IDs novos A007–A010 continuam namespace existente até A006; não clonam achados históricos A001–A006. Estes permanecem históricos, sem reabertura de gates T029–T031.

| ID | Severidade | Eixo | Contradição demonstrada | Localizadores |
|---|---|---|---|---|
| A007 | HIGH | Ordem/configuração e callable real | Delta promete detectar configuração LLM inválida antes de Tx1, mas fábrica só valida timeout; configurações/modelo/chave são resolvidos quando callable executa, depois de Tx1 e SERP. Plano não nomeia preflight capaz de cumprir promessa e proíbe alterar binding/serviço. | delta:15,37; HTTP:30,39,105; binding:101–127; service:123–126,138,152–156 |
| A008 | HIGH | Persistência de emergência | Prescrição declara desconhecidos sem FAILED e auth/config sem FAILED genérico, ao lado da captura de emergência que tenta persistir FAILED e repropaga. Aplicar literalmente ausência de FAILED após Tx1 contradiz D3 entregue. | delta:15,37; HTTP:34; D3:54; service:182–194 |
| A009 | MEDIUM | Tradução segura upstream | HTTP determina 500 fixo para 401/403, mas fronteira implementável ainda diz tipos litellm/httpx reconhecidos sem mapear classes e predicado status exatos. Matriz interna descreve negativos/retry, não define tradução HTTP completa. | delta:15; HTTP:31,34,106; binding:34–43,72–86,154–159; D5:117 |
| A010 | MEDIUM | Body/matriz de teste | Regra aceita null explícito; matriz approve diz corpo non-object 422 e omite null entre sucessos. Reopen herda mesmas regras. null é valor JSON não objeto, criando expectativas incompatíveis no teste futuro. | delta:17 vs 31–32; HTTP:14–15,19; schemas:60–69 |

### A007 — promessa pré-Tx1 sem caminho executável

Evidência estática: `make_scout_complete` retorna fechamento após `_checked_timeout`; não consulta settings/modelo/chave na criação. `scout_complete` abre sessão em binding:113 e verifica modelo/chave em :119–127. Serviço reserva em :123–126, obtém SERP em :138, só invoca callable em :156. Construir factory por request não é preflight LLM. Sem configuração, caminho atual pode criar briefing, consumir SERP, tentar emergência FAILED e propagar `ProviderConfigurationError`. Não é acusação contra T031: ownership e contrato de resolução na invocação estão corretos e fechados.

Mudança mínima sugerida por revisão manual/planejamento: ou retirar promessa pré-Tx1 e documentar 500 seguro com emergência D3 após reserva, ou nomear explicitamente preflight HTTP novo, sua validação/modelo/chave/base URL, sessão curta, responsabilidade T025 e teste de zero reserva/SERP. Reusar `runtime_settings` isoladamente não basta: retorna valores, não valida seleção provider/chave; `get_record` pode flush transitório (settings:273–300). Não invocar callable LLM para validar configuração. Não impor refatoração de T031 nem antecipar código nesta auditoria.

### A008 — distinguir serviço puro, loop e wrapper persistido

Serviço puro/loop não converte desconhecido em retry/falha externa. Wrapper persistido tenta emergência FAILED após Tx1, antes de repropagar mesmo objeto; persistência pode falhar, portanto não prometer FAILED garantido. Handler padrão 500 seguro não apaga emergência e não implica vazamento de exceção. Mudança mínima: substituir frases absolutas por “sem retry/LLMAttemptError; após Tx1 preserva tentativa de emergência FAILED D3; exceção repropaga; HTTP retorna 500 genérico”. Configuração detectada antes Tx1 não cria briefing; descoberta no callable segue emergência. Qualificar falha entre Tx1/Tx2: crash pode deixar generating; exceção capturada tenta emergência. Revisão manual antes de liberar T025, não correção pelo auditor.

### A009 — classifier HTTP mínimo concreto

Registrar classes explícitas `litellm.exceptions.AuthenticationError` e `PermissionDeniedError`, e casos de `litellm.exceptions.APIError`/`httpx.HTTPStatusError` reconhecidos com `status_code`/`response.status_code` inteiro não-bool em {401,403}; não inferir autorização de qualquer exceção com atributo 401/403. Mensagem/substring/nome de classe/string status não classificam. Capturar `ProviderConfigurationError` separadamente; `ValueError` apenas no escopo construtor/configuração Jina conhecido, não em toda rota. Matriz futura deve cobrir cada classe/status, 401/403 numéricos, strings/bools e `RuntimeError` com texto/atributo semelhante preservado como desconhecido. Default HTTP500 genérico continua seguro, mas não substitui decisão explícita de tradução tipada nem prova persistência/retry. Não alterar classificador binding T030.

### A010 — corrigir expectativa de null

Alteração documental mínima: matriz approve/reopen listar omitido/null/{} como sucesso; non-object *exceto null* e extras como 422. T025 usa parâmetro opcional do schema vazio para null/omissão; não precisa mudar schemas T035 ou criar request alternativo. Casos futuros: omitido, null, {}, [], string, número, bool, objeto extra; comparar snapshot/histórico antes/depois das rejeições.

## Readiness por ação

| Ação | Verdict | Base e condicionantes |
|---|---|---|
| T035 | PASS | actions:90 depende T014/T020. D4:57–77 e delta:18 especificam version>=1, error, approved_at, novo BriefingVersionResponse com created_at/points default []/extra forbid. Ausência atual dos campos/símbolo é entrega futura atribuída, não defeito bloqueador do plano. Preservar enum status e 3–7 para conteúdo draft/approved. |
| T025 | FAIL | actions:91 inclui T035, T031 e persistência entregue. Rotas/composição básicas consumíveis; A007/A008 bloqueiam ordem e semântica de falha. A009/A010 precisam convergir antes de execução HTTP. |
| T026 | CONDITIONAL | actions:92 depende T025/T035. Contrato próprio read-only/404 pai/409 não aprovado/ASC v2+ consumível. Não libera coding enquanto dependências/gate conjunto não aprovados. |

## Mapa critério → ação → teste futuro

Todos testes abaixo são **planejados**, não executados. `tests/test_briefing_api.py` ainda entrega T025/T026; schemas em `tests/test_briefing_schemas.py` entrega T035.

| Critério | Ação/símbolo | Assert futuro mínimo |
|---|---|---|
| Payload D4 exato | T035; BriefingResponse/BriefingVersionResponse | Campos públicos, version>=1, enum, created_at obrigatório em versão, points default [], extra forbid; draft/approved 3–7; generating/failed vazio legítimo. Sem prompt/search/updated_at/briefing_id extra. ApprovedBriefingResponse mantém id/theme/points/approved_at. |
| POST síncrono UUID/domain, 201 draft | T025; orchestrate_persisted_briefing | Uma invocação real com I/O fake; Tx1 current v1, sucesso current/history v2; nenhum schedule/background/pesquisa; sem alias /api/briefings. |
| Tema inválido 422 | T025; BriefingCreateRequest/validate_theme | Auth válida, zero settings-runtime/SERP/LLM e zero mutação briefing; SELECT auth permitido antes validação. Não prometer zero auth DB nem precedência 422 sobre 401/403. |
| Timeout e retries | T025; JinaSerpClient + make_scout_complete | Configuração por tentativa default30, valor positivo finito >30 aceito; mesmo llm_timeout_s/default_timeout_s; até4, sucesso SERP reusado; sem deadline global ou retry nested; uma chamada ativa por operação, lock Jina local. |
| Configuração Jina/LLM | T025; runtime_settings, construtor Jina, ProviderConfigurationError | Jina ausente/inválida 500 fixo préTx1; LLM expectativa após resolver A007; sessão curta encerrada antes I/O; sem mensagem original. |
| Prompt/SERP/LLM esgotado | T025; snapshot FAILED devolvido pelo serviço | Traduzir resultado seguro reconhecido (não esperar exceções já encapsuladas): prompt500, SERP/LLM503, detalhes fixos conforme HTTP:28–29; FAILED v2 persistido, sentinelas ausentes. |
| Desconhecido/cancelamento/upstream auth | T025; wrapper e classifier HTTP | Sem retry; emergência tentada apósTx1, propagação preservada, 500 seguro para HTTP aplicável; classes/status A009; não converter cancelamento em resposta de falha comum. |
| Auth/request session | T025; require_admin + get_db | SQLite real, 401/403/400 e sucessos cookie+CSRF/bearer/API-key; rollback leitura auth antes I/O, sem commit, nenhum ORM Principal acessado depois. |
| PATCH/approve/reopen | T025; edit_briefing/approve_briefing(now())/reopen_briefing/save_briefing_transition | Pontos schema convertidos explicitamente para dict/domain antes edit_briefing (domain:107–119 não aceita Pydantic arbitrário); +1/history append, aprovado edit409, CAS409, ausente404, inválido422 sem mutação; body conforme A010; reopen approved_at null. |
| GET corrente durante geração | T025; get_briefing | generating v1 pode ser lido enquanto POST síncrono espera I/O; schema aceita points []; ausente404; consulta não incrementa versão. |
| Histórico | T026; get_briefing + get_briefing_versions | Confirmar pai antes lista: helper versions não faz check pai; 404 ausente, [] pai generating v1, snapshots v2+ ASC; sem migration/insert v1. |
| Publicação aprovada | T026; get_briefing/read_approved | ApprovedBriefingResponse exata, ausente404/não aprovado409; SELECT legítimo, zero I/O externo e zero incremento/mutação histórica. |

## Consistência aprovada e seams suficientes

Prefixo `/briefings` único; POST sem background/pesquisa. `orchestrate_persisted_briefing(session_factory, theme, *, serp_client, llm_complete, ..., llm_timeout_s=30.0)` e `make_scout_complete(session_factory, default_timeout_s=30.0)` existem. Não usar `complete` legado. Binding resolve settings em sessão própria e fecha antes LiteLLM. Timeout por tentativa finito positivo/configurável, sem teto30/global; SERP reusado, loop≤4, dupla desativação SDK preservada. Client por operação torna lock local, não global.

Auth cookie SELECT em security:80 abre autobegin; security:86–92 valida CSRF e devolve Principal com ORM. `get_db` lifecycle database:25–37; dependência reutilizada FastAPI permite mesma sessão request. Prescrição rollback condicional antes query/I/O, sem leitura ORM posterior é compatível; validar dinamicamente só em T025. GETs podem abrir transação de leitura de domínio legítima. Nenhum zero-DB global exigido.

Seams mínimos para T025: dependência injetável que retorna session_factory (não abrir settings antes body validado), composição SERP/LLM chamada dentro handler depois validação/auth/rollback, I/O substituível preservando service real, get_db isolado compartilhado com require_admin real. Não precisa arquitetura extra/singleton/nova auth. Plano exige overrides DB/session_factory/I/O, suficiente para desenhar esses seams em router futuro; não exigir símbolos ainda não implementados. ASGITransport não executa lifespan legado; evitar TestClient com lifespan sem neutralização. `main.py:18–42` faria DB/scheduler se lifespan iniciado; :45,69–71 permite registro router novo. `config.py:8` declara env_file: fixture futura deve isolar ambiente/impedir leitura .env antes imports; auditor não importou produto nem leu .env. Requirements incluem FastAPI/Pydantic2/SQLAlchemy async/aiosqlite/httpx, sem install necessário para plano.

## Checks CLI reais e preservação

- Preflight `pwd; git status --short; git branch --show-current; python ...`: exit0; root absoluto correto, main, árvore já suja. AGENTS raiz/ancestors e JSON canônicos lidos; sem AGENTS adicionais nos diretórios pertinentes. state output_folder `_reversa_sdd`, forward_folder ausente; active-requirements resolve feature coding. Política autoriza continuidade, não ignora gate FAIL. Hooks não encontrados, nenhum inventado.
- Check stdlib `python - <<'PY'` executado em root: **34 ações/34 IDs únicos; zero dependências ausentes; zero ciclos**. T035→T014/T020; T025→T014/T024/T027/T028/T031/T035; T026→T025/T035. Referências T verificadas nos cinco documentos do recorte, T011 é pai decomposto histórico, não ID fantasma.
- Check cinco documentos actions/roadmap/HTTP/delta/D1–D5: **zero divergências de delimitadores de tabelas, zero links Markdown locais quebrados, zero referências T ausentes**. Afirmação restrita: strings em backticks não são hyperlinks; delta:41 lista referências textuais, não contagem de links efetivos. Provas sintáticas não provam semântica.
- `git diff --check`: exit0, sem saída; cobre tracked, não valida untracked ou comportamento HTTP.
- progress: **80 objetos JSON válidos**, L80 checkpoint pós-reparos documentais `2026-10-11T14:57:21.495985+00:00`. Manifest possui **106 hashes**: cross-check anterior coincide antes rewrite; **105/105 restantes intactos**, zero ausentes/diferenças antes e depois escrita. Sibling `inspections/t034-traceability/report.md` excluído caso apareça; não lido. legacy-impact/regression-watch/t034-execution congelados só hash, sem reauditoria T034.
- Suite140 exit0 é **evidência herdada do parent antes dos reparos documentais, código unchanged**; não rerodada, não prova runtime HTTP nem plano agora aprovado. L80 referencia sucesso, não representa nova execução nesta auditoria.
- Histórico anterior preservado integralmente em bytes UTF-8 após seção abaixo; SHA-256 anterior `80ea07ef501e660339d8c96b8febff0ce793698773333881bf8fca5b1f05afae`. Única escrita este arquivo, rewrite; nenhum código/teste/spec/actions/progress/state/skill/bug/view alterado. Resultado pós-escrita hashes e diff exit0 verificado na execução que acompanha entrega.

## Limites e próximo passo

Auditoria leaf estática de **plano**, não QA/código/projeto inteiro; sem subdelegação/todo_list. Nenhum teste runner, HTTP dinâmico, SQLite, provider, DNS, rede, DB externo, .env/segredo, install, migração, deploy, commit/push executado. Não inferir confidencialidade de logs/tracebacks/capture_locals nem interoperabilidade de provider; HTTP500 padrão não é leak comprovado. T012/T013 e gates runtime permanecem próprios. Ausência de router/schemas futuros não foi usada para reprovar plano.

Revisão manual A007–A010 nos documentos, depois reauditoria do delta. T035 tem plano consumível, mas este relatório **não autoriza coding conjunto Sprint8**; sem correção/fechamento por auditor.

## Histórico anterior integral — não usar como verdict vigente

# Cross-check — 001-modulo-briefing — reauditoria T029–T031

Data: 2026-10-11T10:30:52.017471+00:00. Branch `main`; feature ativa em `coding`.

Fontes: [requirements.md](../requirements.md), [roadmap.md](../roadmap.md), [actions.md](../actions.md), [D3/D5](t011-integration-decomposition.md), [delta](t029-t031-planning-delta.md), [interface HTTP](../interfaces/briefing-http.md).

## Verdict documental

**PASS para iniciar coding T029, T030 e T031, na sequência das dependências.** A001 HIGH, A002 MEDIUM e A003 LOW sanados documentalmente. Contratos e mínimos RED/GREEN consumíveis. Não exige produto corrigido para aprovar plano; defeitos runtime registrados continuam responsabilidade das ações abertas.

Findings ativos: **CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0**. Nenhum finding novo. IDs A001–A003 preservam identidade da rodada T029–T031 anterior; severidades abaixo são originais, não contagem ativa.

| ID | Severidade original | Eixo | Resultado da reauditoria | Arquivos/linhas vigentes |
|---|---|---|---|---|
| A001 | HIGH | Assinatura / cobertura T028 | SANADO: factory com `session_factory`, `default_timeout_s=30.0`; callable com `timeout_s=None`; validação antecipada e overflow seguro preservados. D5 antigo marcado histórico/substituído. | roadmap:140–148; D3/D5:79–92,101–110; delta:9,34–39,48–49; HTTP:58; actions:81,84 |
| A002 | MEDIUM | Classificação / segurança | SANADO: matriz concreta LiteLLM/httpx/builtin conserva 429/500/502/503/504 e timeout provider; desconhecidos/auth/config/programação propagam identidade; fronteiras e exibição segura explicitadas. | roadmap:117–119,146–147; D3/D5:112–120; delta:23–30,46–47; HTTP:59; actions:83 |
| A003 | LOW | Proveniência / retarget | SANADO: nota retarget agora histórica; T031 aponta interface canônica existente. | delta:11,51–55; actions:84; interfaces/briefing-http.md:56–59 |

## Prontidão por ação e cobertura

| Ação | Verdict | Contrato e mínimo RED/GREEN consumíveis | Gate remanescente |
|---|---|---|---|
| T029 | PASS documental | `num_retries=0` e `max_retries=0`; `acompletion` real com HTTPX MockTransport devolvendo 503; observar exatamente 1 request e ausência de fallback, sem trocar função SDK por fake. delta:19,45; D5:111,120; actions:82. | Executar RED/GREEN no binding real; ação `[ ]`. |
| T030 | PASS documental | Cada classe/status elegível produz `LLMAttemptError` fixo; negativos propagam mesmo objeto. Sentinelas em args/mensagem/causa exibida/traceback; casos de builtin TimeoutError separados do callable arbitrário e deadline. delta:23–30,46–47; actions:83. | Executar matriz e segurança; depende T029; ação `[ ]`. |
| T031 | PASS documental | Testes keywords/default/override, inválidos com zero factory/settings/record/transport/LLM; >30 aceito; SQLite e helpers reais para ownership, primeira leitura e fechamento antes de rede. delta:34–39,48–49; actions:84. | Implementar factory e testes após T030; ação `[ ]`. |

RF-08 e segurança (requirements:58,67) cobertos por erro seguro. RF-10 (requirements:60,113–117) mantém mesmo registro, teto quatro tentativas externas sequenciais e reuso SERP; retry SDK desligado evita multiplicação do loop (roadmap:114–120,126–128,145). Proposta técnica não cria novo requisito de modelo/provider nem arquitetura/endpoint.

## Consistência e compatibilidade verificadas

- **Assinatura preserva timeout T028: SIM.** Única mudança deliberada é `db` caller-owned virar `session_factory`. Default validado na factory, override antes de sessão/settings/transporte. Int/float positivo finito não-bool; NaN/inf/zero/negativo/não-número rejeitados; overflow convertido em `ValueError` fixo; `None` usa default; >30s permitido. Código atual binding:30–53 e testes:61–72,136–215 servem só como baseline de compatibilidade.
- D5:79–92 explicitamente histórico e substituído; actions:78 descreve T023 entregue, não contrato novo. D5 vigente:105–120 prevalece. Role `scout` e escolhas runtime preservadas; cenário OpenAI 503 é fixture SDK, não modelo obrigatório de produto.
- Matriz LiteLLM usa `litellm.exceptions.Timeout`, não `APITimeoutError`; status vem atributo `status_code`/`response.status_code`, não texto. Classes concretas elegíveis em D5:113–115 e delta:24–26; auth 401/403, config, BadRequest e desconhecidos permanecem negativos. `RuntimeError`/`TypeError` com timeout/quota/429/503 não muda classificação.
- Timeout SDK/transporte dentro do binding é falha externa; TimeoutError arbitrário de callable propaga. Serviço distingue deadline por `asyncio.timeout.expired()` (service:84–96,152–164). Política de emergência da orquestração persistida (service:182–194; D3:54) não é retry/fail genérico do loop nem conversão no binding; não é reaberta nesta auditoria.
- Segurança exigida limita-se a args, mensagem, causa observável e traceback formatado padrão. `from None` não prova `__context__` fisicamente inexistente. Não amplia para `capture_locals` ou introspecção arbitrária. Segurança runtime ainda não aprovada.
- D3 vigente:101–103 exige sessão própria curta, cópia de escalares e fechamento antes da rede, sem finalizar sessão caller-owned. First-use `get_record` com flush sem commit é revertido ao fechar; defaults atendem chamada corrente sem persistência silenciosa. SQLite/helpers reais são teste futuro exigido, não prova executada aqui.
- Probe SDK real + MockTransport anterior preservado como evidência histórica: LiteLLM 1.104.0/OpenAI 503, 1 request. Não rerodado nem generalizado a todos providers/configurações globais. T029 deve produzir própria prova binding.

## Checks reais desta execução

- Preflight AGENTS.md e três JSON canônicos lidos; active-requirements resolve pasta `001-modulo-briefing` em coding. State tem output_folder `_reversa_sdd`, não forward_folder. Hooks before/after-audit não encontrados em `.reversa`; nenhum inventado.
- Git branch `main`; árvore já suja, com documentos antigos deletados e feature untracked. Nada restaurado. `git diff --check`: exit 0 antes do rewrite; não valida funcionalidade ou arquivos untracked.
- Parsing stdlib: **30 ações / 30 IDs únicos / 0 dependências ausentes / 0 ciclos**. T029 depende T023/T028; T030 depende T029; T031 depende T030. T025 depende T014/T024/T027/T028/T031, portanto bloqueio T029/T030 transitivo. Delta serial compartilha binding/testes, sem paralelismo novo conflitante.
- Referências RF dos seis documentos auditados existem em requirements; referências T e caminhos explícitos do delta resolvem. Os seis documentos não contêm links Markdown locais; links do cabeçalho deste relatório resolvem. Não revalida referências históricas como contratos atuais.
- Import local somente de `litellm.exceptions`/httpx: classes listadas existem; `Timeout` True, `APITimeoutError` False; seis classes httpx True. Sem chamada provider, DB ou leitura de `.env`; probe anterior não repetido.
- progress.jsonl: **59 objetos JSON válidos**. Última linha parent `2026-10-11T10:26:20.741458+00:00`, action `T029-T031 factual repairs verified; re-audit baseline captured`, status `re_audit_pending`. Seus **37 SHA-256 pre_dispatch** coincidem: zero diferenças. Suite126 informada nessa linha não foi executada nem usada como prova desta auditoria.
- Readset próprio: **15 arquivos**, hashes SHA-256 capturados antes do rewrite; inclui AGENTS, JSON, seis fontes documentais, progress e três arquivos Python. SHA progress: `76edb73e97d92af43a3a340de9f53a0c6652c6ee4b3d3e8b433a040eeaf95e04`. Cross-check anterior SHA: `cc1d1f7e34ae9dc7d7006ce98cee934e4630a560254952a28e26a4d29beb2729`.
- Verificação pós-rewrite executada: **15/15 hashes próprios e 37/37 hashes parent inalterados**, zero diferenças; seis links ativos do relatório resolvem; `git diff --check` exit 0, sem saída. Histórico anterior preservado integralmente. Checks não comprovam implementação ou funcionalidade runtime.

## Escopo excluído e próximo passo

Única escrita: este cross-check, rewrite integral via ferramenta de escrita; relatório anterior integral preservado abaixo, datado, sem incorporar findings históricos à contagem ativa. Nenhum requirements, roadmap, actions, D3/D5, interface, progress, state, código ou teste alterado.

Sem reauditoria do projeto/legado; requisitos aprovados são fonte de produto (requirements:12–21). Sem rede, live DB, `.env`, install, suite inteira, commit, push, deploy, delegação, todo_list ou nova rodada de planejamento. Não salvar skill nesta execução: limite de escrita prevalece.

Liberar `/reversa-coding` T029 → T030 → T031 conforme dependências, com RED/GREEN real. T025 continua aberta e bloqueada até T031 concluída; QA T012/segurança T013 e aceite runtime não liberados. Nenhum pedido CONTINUAR nesta execução autorizada.

## Histórico datado — 2026-10-11T09:56:47.553837+00:00

Relatório anterior integral; NÃO usar verdict, findings, números ou linhas históricas como estado presente.

<details>
<summary>Auditoria anterior integral — histórico</summary>

# Cross-check — 001-modulo-briefing — delta T029–T031

Data: 2026-10-11T09:56:47.553837+00:00. Branch `main`; feature ativa em `coding`.

Artefatos canônicos: [requirements.md](../requirements.md), [roadmap.md](../roadmap.md), [actions.md](../actions.md). Complementos: [D3/D5 e adendo](t011-integration-decomposition.md), [delta de planejamento](t029-t031-planning-delta.md), [interface HTTP](../interfaces/briefing-http.md).

## Resultado

**Prontidão: NÃO APROVADO para coding conjunto T029–T031.** Corrigir assinatura e esclarecer continuidade da classificação antes de liberar delta. T029 possui proposta consumível e controles compatíveis no caminho OpenAI verificado; isso não libera T031 nem T025.

Findings ativos: **CRITICAL 0 / HIGH 1 / MEDIUM 1 / LOW 1**. IDs desta rodada independentes dos IDs históricos.

| ID | Severidade | Eixo | Descrição | Onde está |
|---|---|---|---|---|
| A001 | HIGH | Consistência de assinatura / cobertura T028 | Proposta troca `default_timeout_s` por `timeout_s` na fábrica e tipa callable apenas com dois argumentos. Não preserva explicitamente override `scout_complete(..., timeout_s=...)` nem validação antecipada entregue em T028. Mudança de ownership não autoriza remover contrato de timeout. | D5 adendo:123; delta:17; binding:42–53; testes:61–72,136–215; actions:81,84 |
| A002 | MEDIUM | Consistência de classificação | Delta diz converter **apenas** conexão e 500, enquanto binding/testes anteriores cobrem 429,503 e timeout. Adendo não resolve se classes novas ampliam política existente ou a substituem; literalidade permite regressão no retry de falhas já reconhecidas. | delta:13; D5:108,127; roadmap:23,117–119; testes:88–99; actions:82–83 |
| A003 | LOW | Proveniência documental | Delta ainda afirma que T031 aponta interface invertida e exige retarget pelo parent; actions atual já aponta `interfaces/briefing-http.md`. Nota não marcada como histórica. | delta:35–36; actions:84 |

### A001 — contrato de timeout perde compatibilidade

Impacto: `make_scout_complete(..., default_timeout_s=...)` deixa de aceitar keyword existente; anotação proposta omite override por chamada, inclusive valores positivos finitos acima de 30s. T028 fica dependência formal de T029, mas suas garantias não constam do novo D5. Não é quebra comprovada de API HTTP externa; é incompatibilidade interna bloqueadora de planejamento. Revisão manual ou `/reversa-plan` seguida de `/reversa-to-do` deve explicitar `make_scout_complete(session_factory, default_timeout_s=30.0)` e callable `scout_complete(system, user, timeout_s=None)`, default validado na fábrica, override validado antes de abrir sessão/I/O, preservando rejeição de bool/NaN/inf/zero/negativo/overflow e aceitação >30s. Atualizar documentos canônicos e critérios T031 fora desta auditoria. Mudança deliberada de assinatura exige plano explícito de migração e testes; proposta atual não contém isso.

### A002 — fronteira de erro precisa continuidade explícita

Conexão/500 versus auth/config/programação estão bem separados na intenção nova. Porém “apenas” não define continuidade para falhas existentes. Esclarecer matriz completa de classes reconhecidas, inclusive 429/503 e timeout de provider versus timeout imposto pelo serviço, sem captura genérica de programação. Não ampliar RF-10 para bugs/auth/config. Fixação de mensagem segura e teste de causa/campos com sentinelas permanecem corretos. Revisão manual de D5/delta deve resolver ambiguidade antes de coding.

## Verificações aprovadas

### Cobertura

| Achado original | Proposta técnica | Ação |
|---|---|---|
| F-CONTRACT-01 | `num_retries=0`, `max_retries=0`, `acompletion` real com transporte fake, contar requests e negar fallback | T029; actions:82; delta:7–9; D5:126–127 |
| F-ERROR-01 | Conexão/500 em `LLMAttemptError` fixo seguro; auth/config/programação propagam; sentinelas na exceção | T030; actions:83; delta:11–13; ressalva A002 |
| F-CONSISTENCY-01 | `session_factory`, sessão própria curta, cópia de valores, fechamento antes da rede, sem finalizar sessão caller-owned; primeira leitura flush sem persistência | T031; actions:84; delta:15–19; D3:117–119; ressalva A001 |

Todos três achados possuem proposta e ação correspondentes. RF-08 exige motivo seguro (requirements:58,67); RF-10 preserva registro, teto4 e reuso SERP (requirements:60,113–117). Roadmap:114–120,126–138 mantém loop externo responsável, sem `complete` legado aninhado. Nenhum endpoint/arquitetura de pesquisa novo proposto.

### Assinatura, SDK e segurança

- **Resposta obrigatória sobre assinatura: NÃO**, proposta D5 não preserva explicitamente `default_timeout_s` nem override de callable testado em T028. A001 bloqueia aprovação conjunta.
- LiteLLM instalada: **1.104.0**. `acompletion` aceita kwargs; wrapper `_get_wrapper_num_retries` lê `num_retries` e preserva zero explícito; SDK OpenAI recebe `max_retries` como inteiro, incluindo zero. São superfícies distintas compatíveis no caminho auditado.
- Probe executado com `litellm.acompletion` real, `httpx.MockTransport`, modelo fake OpenAI, resposta 503 e ambos controles zero: **1 request HTTP; ServiceUnavailableError**. Nenhuma chamada externa feita pelo transporte; nenhuma credencial real usada. Prova do caminho SDK, não QA de binding nem de todos providers/configurações globais.
- T029 prevê exatamente essa prova no binding real; teste futuro deve observar count sem substituir `acompletion`. Critério OpenAI em actions é cenário de transporte, não requisito de mudar modelo runtime.
- Auth/config/programação desconhecida explicitamente preservadas (delta:13,27; D5:125,127–128). Erro elegível deve usar mensagem fixa sem causa crua observável. Segurança runtime ainda depende de testes T030 e T013; auditoria não afirma sanitização implementada.
- D3 preserva reserva/conclusão CAS e rede fora de transação. Sessão isolada fecha antes de LLM, sem commit/rollback no chamador; primeira leitura com flush é revertida ao fechar, defaults servem chamada atual. Teste SQLite/settings reais exigido, ainda não executado por esta auditoria.

### Sanidade de actions

Check stdlib executado: **30 ações / 30 IDs únicos; 0 dependências inexistentes; 0 ciclos**.

- T029 depende T023/T028.
- T030 depende T029.
- T031 depende T030.
- T025 depende T014/T024/T027/T028/**T031**. T031 traz bloqueio transitivo T030/T029; não falta bloqueio adicional direto.
- T029–T031 não marcadas paralelas; compartilham binding/testes de forma serial, sem conflito de paralelismo novo.
- T025 permanece aberta. Aprovação documental não fecha tarefa ou gate runtime.

## Preflight, limites e preservação

AGENTS.md, `.reversa/state.json`, `.reversa/active-requirements.json` e `.reversa/reversa-config.json` lidos. State define `_reversa_sdd`, não `forward_folder`; active-requirements resolve feature exata e stage coding. Config canônica está em `.reversa/`; ausência na raiz não é bloqueio. Hooks before/after-audit não encontrados no preflight; nenhum inventado ou executado. Branch main e árvore previamente suja, sem limpeza/restauração.

Legado não é fonte de regras de produto desta feature (requirements:12–21); não reauditar legado nem recuperar SDD eliminada. Produção/testes lidos somente como evidência de compatibilidade T028. Sem execução da suite de produto, sem migração, deploy, alteração de ações ou progress, sem delegação e sem ferramenta todo_list.

Única escrita autorizada: rewrite atômico deste relatório. Comparação SHA-256 pós-escrita cobre seis documentos canônicos e fontes Python em app/tests: **78 arquivos, zero diferenças**. Nenhum requirements, roadmap, actions, D3/D5, delta, interfaces, código ou teste alterado. Histórico anterior preservado abaixo apenas como referência, sem findings ativos herdados.

## Próximo passo

Revisão manual ou `/reversa-plan` + `/reversa-to-do` para A001/A002; corrigir nota A003. Reauditar delta antes de `/reversa-coding` conjunto. T025 continua bloqueada por T031. Não solicitar interação nesta execução leaf.

## Histórico anterior — não representa prontidão deste delta

<details>
<summary>Cross-check anterior integral</summary>

# Cross-check — 001-modulo-briefing — reauditoria Sprint 5 T006/T010

Data: 2026-10-11T05:28:53+00:00. Branch `main`; feature ativa em `coding`.

Artefatos: [requirements.md](../requirements.md), [roadmap.md](../roadmap.md), [actions.md](../actions.md). Complementos: [data-delta.md](../data-delta.md), [HTTP](../interfaces/briefing-http.md), [SERP](../interfaces/jina-serp.md), [PRD](../../../_reversa_sdd/prd.md), [SDD](../../../_reversa_sdd/sdd/briefing.md).

Escopo exclusivo: roadmap:85–160; data-delta:78–105; actions:45,65,66,72; convergência PRD:84 e SDD:78,130,154. Requisitos aprovados são fonte de produto; contrato novo é proposta de concretização técnica de RF-10, não aprovação literal pelo usuário de cada classe de erro. Legado não é fonte de requisitos.

## Resultado

**Readiness: PASS para iniciar coding local T006/T010.** Zero inconsistências bloqueadoras remanescentes no recorte. A001–A006 sanados documentalmente; isso não prova implementação nem execução de geração. `app/briefing/service.py` e `tests/test_briefing_generation.py` ausentes. T006/T010 permanecem `[ ]`.

Findings ativos: **CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0**. Histórico anterior preservado integralmente ao final, com status atual explícito abaixo. Severidades históricas não entram na contagem ativa.

Runtime/integrado **não liberado**: storage, auth e binding real em T011; QA real em T012; segurança/rastreabilidade em T013. Fakes locais não exigem resolver antecipadamente essas decisões e não satisfazem esses gates.

## Revalidação A001–A006

| ID | Severidade original | Eixo | Descrição / status atual | Onde está agora |
|---|---|---|---|---|
| A001 | HIGH | Cobertura / gates | SANADO no planejamento. T011 contém binding real explícito; data delta delimita role/modelo/chave/timeout/tentativas; T012 exige QA real. Escolha da role fica nomeada na execução T011, candidata scout; nenhuma role briefing inventada. | roadmap:134–138; data-delta:91–105; actions:66,72 |
| A002 | MEDIUM | Contrato / fronteira | SANADO no planejamento. LLMAttemptError pertence a service.py, mensagem fixa segura; attempts int não-bool 1..4; timeout int/float não-bool finito positivo; ValueError antes de I/O. Não-string é tentativa inválida por checagem explícita; parser aceita lista integral JSON puro ou cerca json única opcional. Erros desconhecidos propagam sem retry/fail. | roadmap:96–104,114–119,155–158; actions:45 |
| A003 | MEDIUM | Prompt / protocolo | SANADO. user inclui formato_saida com instrução explícita de lista JSON; system preserva string integral do arquivo. Assert no fake registra ambos. | roadmap:115–116,146,158; data-delta:85,102–103; actions:45 |
| A004 | MEDIUM | Substituibilidade / prompt | SANADO. Loader síncrono () -> str; serviço valida tipo e não-vazio após strip; retorno inválido ou PromptUnavailable resulta FAILED antes de SERP/LLM, preservando system válido integralmente. | roadmap:97,125,151; data-delta:101; actions:45,65 |
| A005 | MEDIUM | Concorrência / claim | SANADO. Sequencial por invocação; lock exclusivo de busca por instância JinaSerpClient; não serializa LLMs concorrentes nem instâncias distintas. Nenhum lock global/cross-process prometido nesta etapa. | roadmap:130–136; actions:65 |
| A006 | MEDIUM | Consistência / âncoras | SANADO. Saída estrutural inválida consome tentativa dentro do teto4, reusa SERP e exaure em FAILED. Foco sem conclusão orientado pelo prompt; sem julgador semântico nem retry extra. Concretização técnica RF-10, não nova aprovação literal. | roadmap:116–119,127,152; PRD:84; SDD:76,78,130,154 |

## Itens verificados que passaram

### Cobertura

- RF-01: new_briefing antes de prompt/SERP/LLM; T006 b cobre zero I/O e T010 implementa gate integrado de T004 (roadmap:124,147,160).
- RF-02/RF-10: search uma vez por geração; cliente possui retry SERP; loop LLM não refaz busca, usa mesmo registro e no máximo quatro tentativas totais (roadmap:126–127,149–150).
- RF-03/RF-08: saída válida passa complete_briefing; inválida não publica rascunho parcial; erro terminal fixo seguro; casos parse/faixa/não-string na matriz g/k/m (roadmap:116–128,152,156,158).
- RF-04: loader síncrono validado antes da busca, system não adulterado; matriz a/f cobre payload e prompt inválido (roadmap:125,146,151).
- RF-05/06/07/09, storage, consulta durável e auth permanecem fora do recorte local. Não exigir T011 para construir fakes T006.

### Consistência e fronteiras de erro

- `InvalidContent` originado **dentro do callable** propaga sem retry; `InvalidContent` conhecido originado **na validação local da saída parseada** consome tentativa. Capturas devem separar chamada de parse/complete (roadmap:119).
- `CancelledError` propaga sem retry e sem fail_briefing (roadmap:118,153).
- Apenas `TimeoutError` causado pelo deadline da fronteira é retentável. `TimeoutError` levantado pelo callable antes do deadline é exceção desconhecida e propaga; não usar captura ampla que confunda ambos (roadmap:114,117,119). `asyncio.Timeout.expired()` pode distinguir implementação; stdlib basta, sem nova arquitetura/dependência. Acrescentar estes limites ao check runnable T006 ao concretizar contrato; não é novo finding de planejamento.
- Timeout default **30s**, configurável, int/float não-bool finito >0, **sem teto rígido <=30s** (roadmap:99,104,138; data-delta:99). Não confundir default com máximo.
- Parser estrito exige lista integral, sem extração arbitrária de fragmentos; cerca json única opcional. Evitar `except TypeError` ou captura genérica que esconda bug (roadmap:116–119,156,158; data-delta:103).
- Binding real one-attempt não empilha complete legado com retries/fallbacks; proibição e gate definidos, sem exigir provider real nesta sprint (roadmap:120,138; actions:66,72).
- Tabelas Markdown do delta mantêm cabeçalhos/separadores e células; nenhuma mudança requerida.

### Sanidade actions e preflight

- Branch main; árvore já suja antes da execução. Nada restaurado ou atribuído a esta auditoria.
- State resolve output_folder `_reversa_sdd`; forward_folder ausente, feature resolvida por active-requirements para `_reversa_forward/001-modulo-briefing`, current-stage coding. AGENTS e reversa-config.json lidos, não modificados. Hooks before/after-audit não configurados (`.reversa` sem arquivos hook); nenhum hook inventado.
- Check stdlib executado: 16 IDs únicos, 9 `[X]`, 7 `[ ]`; nenhum ciclo/dependência inexistente; três ações paralelas T001/T003/T008 com alvos distintos. T006 depende T001/T003; T010 depende T007/T008/T009/T016.
- progress.jsonl: **30 linhas/30 objetos JSON válidos**, newline final presente. Nenhum append/reparo.
- Suite49exit0 informada pelo parent; não rerodada nem usada como prova de serviço ausente. Checks desta auditoria são documentais, não QA funcional.

## Preservação e verificação

Readset baseline próprio: 31 arquivos em `.reversa/`, feature e `_reversa_sdd/`, excluído apenas este output; inclui progress.jsonl. Guard adicional: 69 arquivos produto/tests/AGENTS (hash somente). Comparação pós-escrita deve validar conjunto e SHA-256 idênticos. Baseline progress: `d5338f7247211e9d0dd7714e2f35ce90323e913353ed0a7978c973945f9c29e4`.

Única escrita autorizada: rewrite atômico deste cross-check.md. Nenhum código, teste, requirements, roadmap, actions, data-delta, PRD, SDD, progress ou `.reversa/**` alterado; nenhuma ação marcada `[X]`. `git diff --check` executado após escrita; resultado efetivo retornado no resumo final. Diff check não cobre untracked nem comprova funcionalidade.

## Próximo passo e gates

Executar RED T006 e GREEN T010 via `/reversa-coding`; manter ações abertas até execução verificável. Aceite runtime aguarda binding/storage/auth T011, QA T012 e auditoria T013. Nenhum gate runtime foi fechado.

Digite **CONTINUAR** para prosseguir conforme sugestão acima.

## Histórico datado — auditoria precedente 2026-10-11T04:57:22Z

Cópia integral do relatório anterior, preservada para proveniência. Findings abaixo são **históricos e sanados documentalmente conforme tabela atual**, não findings ativos. Readiness CONDICIONAL, hashes, contagem progress25 e linhas antigas descrevem aquela rodada, não estado presente. Também mantém histórico T004/T005/T007 de 2026-10-11T03:13:44Z.

<details>
<summary>Relatório anterior integral — não usar como readiness atual</summary>

# Cross-check — 001-modulo-briefing — Sprint 5 T006/T010

Data real: 2026-10-11T04:57:22Z (01:57:22-03:00). Branch: `main`; feature ativa em `coding`.

Escopo: delta [roadmap.md](../roadmap.md):83–154, [data-delta.md](../data-delta.md):78–89, [actions.md](../actions.md):45,65 e dependências alcançadas. Fonte produto: [requirements.md](../requirements.md). Âncoras planejadas: [PRD](../../../_reversa_sdd/prd.md) e [spec](../../../_reversa_sdd/sdd/briefing.md). Contratos: [HTTP](../interfaces/briefing-http.md), [SERP](../interfaces/jina-serp.md). Produção lida somente para compatibilidade; legado não é verdade de produto.

## Resultado

**Readiness: CONDICIONAL para coding local T006/T010; FAIL para aceite runtime/integrado.** Sequência principal consumível, mas antes de GREEN ajustar fronteiras A002–A005. A001 bloqueia declaração de cobertura runtime, não construção com fakes. A006 exige convergência documental, sem pedir nova decisão de produto. Nenhum artefato corrigido; nenhum teste de geração executado. `app/briefing/service.py` e `tests/test_briefing_generation.py` ainda ausentes. T006/T010 permanecem abertas.

Contagem: **CRITICAL 0 / HIGH 1 / MEDIUM 5 / LOW 0**.

## Findings novos deste recorte

IDs A001–A006 pertencem exclusivamente a esta execução, não representam continuidade dos IDs históricos abaixo.

| ID | Severidade | Eixo | Descrição | Onde está |
|---|---|---|---|---|
| A001 | HIGH | Cobertura / gates | Binding real atribuído a T011 no roadmap e nota de T010, mas ausente na ação executora T011 e data delta; não há critério explícito de QA do binding one-attempt. | `roadmap.md:134–136,154`; `actions.md:65–66,72`; `data-delta.md:80–89` |
| A002 | MEDIUM | Contrato / fronteira | `LLMAttemptError` sem módulo dono/mensagem segura; rejeição de tipos de configuração e classificação de retorno não-string não delimitadas; matriz não testa propagação de erro desconhecido. | `roadmap.md:93–102,109–117,140–152`; `actions.md:45` |
| A003 | MEDIUM | Prompt / protocolo LLM | Serviço exige lista JSON, mas system congelado não pede JSON; user planejado contém só tema/SERP. Fakes de texto JSON não provam que instrução solicita formato consumido. | `roadmap.md:113–114`; `data-delta.md:85`; `app/prompts/briefing.md:1` |
| A004 | MEDIUM | Substituibilidade / falha de prompt | Prompt vazio retornado por loader substituto não tem validação explícita no serviço; apenas `PromptUnavailable` dispara FAILED antes da busca. | `roadmap.md:95,123,140,149`; `app/briefing/prompt_loader.py:10–23` |
| A005 | MEDIUM | Concorrência / claim | Await sequencial garante uma operação ativa por chamada, não por serviço sem instância/lock; lock SERP não cobre LLM de gerações concorrentes. | `roadmap.md:90–98,130`; `actions.md:65`; `app/briefing/serp_client.py:38–61` |
| A006 | MEDIUM | Consistência / âncoras | Adendo autoriza retry de parse/conteúdo dentro teto 4, enquanto âncoras ainda dizem retry semântico não aprovado e exigem aprovação prévia. | `roadmap.md:115,150`; `_reversa_sdd/prd.md:84`; `_reversa_sdd/sdd/briefing.md:78,130,154` |

### A001 — entrega runtime não rastreada até ação executora

**Esperado:** sub-passo explícito em T011, fronteira de dados/configuração no data delta e gate verificável em QA antes de aceite integrado. **Real:** `actions.md:65` menciona a atribuição, mas `:66` só exige router/persistência/read-only; `data-delta.md:89` posterga storage sem mencionar binding. QA `actions.md:72` cita Gherkin genericamente, não exercício do callable real e teto sem retry aninhado. **Impacto:** T011 pode ser fechada segundo descrição literal deixando geração runtime inexistente. Infraestrutura citada existe: `app/services/settings.py:289–300` resolve modelos por ROLES e chaves por provider; `app/services/llm.py:258–267` seleciona role/model/provider. Não implica role `briefing` disponível: defaults existentes em `settings.py:12–20` não incluem essa role. **Recomendação:** revisão manual ou `/reversa-plan` seguida de `/reversa-to-do` deve registrar binding como entrega de T011, escolher/reutilizar role existente explicitamente sem inventar credencial ou nova role implícita, delimitar entradas/settings no data delta e exigir QA do binding real one-attempt, timeout acordado, ausência de fallback/retry interno e erros seguros. Sem rede ou binding nesta sprint. Não reutilizar `complete` legado dentro loop4: timeout180, cinco tentativas e fallbacks estão em `llm.py:255–369`.

### A002 — política de erro/configuração incompleta

**Esperado:** contrato importável pelos testes e tratamento previsível de entradas inválidas antes de I/O. **Real:** nome novo de exceção apenas proposto; `attempts=1.5` e `True` não são excluídos literalmente por intervalo, timeout string/bool pode produzir TypeError/aceitação; retorno LLM não-string conflita entre erro externo conhecido e TypeError de parser. **Impacto:** implementações/tests podem divergir ou capturar TypeError genérico mascarando bug. **Recomendação:** definir `LLMAttemptError` em `app/briefing/service.py` com mensagem fixa, sem payload bruto; attempts int não-bool 1..4; timeout int/float não-bool finito positivo, demais `ValueError`, tudo antes de loader/search/LLM. Definir não-string como saída externa inválida da tentativa, converter por checagem explícita, não `except TypeError` amplo. Parser deve capturar somente `json.JSONDecodeError` e invalidez explícita de shape/conteúdo no trecho de parse/complete; delimitar cerca única opcional e lista completa, não extração arbitrária de fragmentos. Timeout de callable versus timeout da fronteira deve ter classificação explícita. Testar bool, float attempts, str, None, NaN/inf, zero/negativo, retorno None/dict e RuntimeError desconhecido propagando sem retry/fail; cancelamento também não chama fail. Não esconder erro de programação.

### A003 — instrução de saída ausente

**Esperado:** LLM recebe instrução do formato que serviço aceita, preservando system originário do arquivo. **Real:** prompt pede pontos, título/descrição, mas não lista JSON; user contém só dados. **Impacto:** saída em prosa coerente com prompt esgota quatro tentativas. **Recomendação:** registrar instrução explícita de lista JSON no payload user, sem substituir/adulterar system de arquivo nem alterar prompt congelado nesta sprint; adicionar campo de instrução de saída ao contrato/data delta e assert no fake. Não inventar protocolo provider/tools. Testar JSON puro e cerca opcional, 3/4/5/6/7 pontos aceitos, 2/8 recusados.

### A004 — prompt substituído vazio

**Esperado:** loader injetado continua respeitando RF-04/RF-08 e matriz f. **Real:** default real rejeita vazio, mas fake str previsto em `roadmap.md:140` pode retornar whitespace e etapa 2 só captura `PromptUnavailable`. **Impacto:** serviço pode chamar SERP/LLM com instrução vazia; substituibilidade não preserva limite. **Recomendação:** explicitar validação local de str não-vazia após strip do resultado do loader; vazio/tipo inválido retorna FAILED seguro antes de search/LLM. Preservar string original como system. Loader síncrono `() -> str`; erro desconhecido propaga, somente falha de prompt reconhecida vira FAILED. Testar `PromptUnavailable`, `""`, whitespace e retorno não-string, identidade via wrapper da factory real.

### A005 — alcance da serialização exagerado

**Esperado:** descrição distingue garantia por chamada da garantia por instância SERP. **Real:** função não possui instância de serviço/lock; duas gerações com mesmo cliente SERP serializam buscas, porém LLM da primeira pode coexistir com busca/LLM da segunda. **Impacto:** claim “uma chamada externa ativa por instância/serviço” não sustentado. **Recomendação:** limitar texto à sequência por invocação e busca serial na mesma instância `JinaSerpClient`. RN-02 exige busca serial; não impor lock global novo. Registrar necessidade de instância SERP compartilhada no binding T011 se desejada garantia entre chamadas; instâncias distintas/processos não coordenados. Teste proposto de concorrência deve afirmar só garantias escolhidas, sem atribuir lock do adapter ao serviço inteiro.

### A006 — plano versus âncoras planejadas

**Esperado:** leitores recebem mesma política explícita de saída inválida. **Real:** adendo trata parse/conteúdo como tentativa; PRD/spec antigos dizem não aprovado. **Impacto:** QA pode exigir falha terminal na primeira saída fora da faixa, enquanto T006 exige retry. **Recomendação:** convergir documentalmente âncoras para política explícita do delta, distinguindo shape/faixa inválidos de avaliação semântica “conclusivo”. Requirements RF-10 é fonte produto; não elevar OQ antigo a veto de regra aprovada nem criar heurística de conclusão. Cada retry permanece no teto 4 e reusa SERP; nenhuma chamada silenciosa além teto. Ajuste por revisão manual/planejamento, não pelo auditor.

## Matriz RF/cenário → decisão → ação/teste proposto

| RF / cenário | Decisão | Ação / evidência proposta |
|---|---|---|
| RF-01 / tema inválido, registro identificável | `roadmap.md:103,122` | T006 b + T010 serviço real com fakes: 2/301/strip vazio, zero loader/search/LLM; wrapper chama factory real e captura único id. Gate integrado T004 permanece aberto até execução/QA. |
| RF-02 / sucesso sem busca extra, nenhuma segunda tool | `roadmap.md:113,124–125`; SERP contrato `:170–175` | T006 a/d/e: search exatamente uma vez; sem Reader/fetch de URLs; adapter já cuida retry4. Não reauditar adapter. |
| RF-03 / gerar foco, faixa 3–7, alvo5 | `roadmap.md:114,125,144,150`; prompt arquivo | T006 a/g com 3/4/5/6/7 e 2/8, title/description vazio/ausente/tipo; formato JSON A003. Sem conclusão é instrução + QA T012, não certificação semântica do domínio. |
| RF-04 / prompt arquivo alterado, ausente/inválido | `roadmap.md:95,113,123,149` | T006 f + duas chamadas com loader real em arquivo temporário de teste: system idêntico à string lida e alteração observada; erro/vazio zero SERP/LLM; A004. |
| RF-08 / falha busca, geração ou prompt segura | `roadmap.md:123–126,146,148–152`; `data-delta.md:87` | T006 c/e/f/g/i: FAILED vazio, mesmo id, mensagem fixa; nunca logar exceção/prompt/saída bruta. T013 segurança runtime pendente. |
| RF-10 / retentar mantendo registro, sem repetir sucesso | `roadmap.md:112,115–118,124–125,147–148` | T006 d/e/i: 2 falhas e sucesso3, esgotamento4, timeout contado; SERP1 e factory1; pontos só publicados após complete. A002 adiciona erro desconhecido/cancel, tipos e limite. |
| RN-02 / concorrência de buscas | `roadmap.md:130`; lock adapter | T006 concorrência com mesma instância/fake serial: distinguir por chamada/instância SERP de serviço/global conforme A005. |
| RF-05/06/07/09, histórico e consumidor aprovado | dependências T007/T011, `data-delta.md:74–76,89` | Domínio congelado consumido, não reauditado; persistência/HTTP/auth/concurrency runtime T011; QA T012/T013. Não fechar gates integrados nesta dupla. |
| Runtime LLM / configuração por role/provider | `roadmap.md:134–136` | T011 binding real, depois QA do limite one-attempt e geração runtime. A001: ação executora/data delta/gate ainda incompletos. |

## PASS verificados

### Cobertura e compatibilidade

- Assinatura completa de `generate_briefing` e callable async(system,user) retorna str; dependências obrigatórias e loader default existente. Nenhum provider, DB ou HTTP necessário para testes locais.
- `new_briefing` primeiro, prompt antes da busca, search uma vez, retries LLM reutilizam SERP, final DRAFT/FAILED com mesmo id. Domínio existente `:94–139` preserva id, incrementa versão uma vez no complete/fail e não muda snapshot original.
- `PromptUnavailable` pertence a `app.briefing.prompt_loader`; `SerpSearchError` a `app.briefing.serp_client`; `InvalidContent`/`InvalidTransition` a `app.briefing.domain`. Nova exceção precisa dono A002.
- `CancelledError` explicitamente propaga, sem fail/retry; erros desconhecidos também. Timeout externo por tentativa usa asyncio stdlib; JSON stdlib evita importar providers legados.
- System vem arquivo sem equivalente embutido; JSON user contém tema normalizado e apenas title/url/description da SERP; nenhuma segunda tool/Reader prevista. Forma de saída precisa instrução A003.
- Erros finais fixos, sem corpo bruto/credencial/prompt; data delta declara descarte de saída bruta. Isso é contrato, não prova de segurança runtime.
- Domínio/prompt/adapter/helpers permanecem congelados. Cinco alvo habitual, nunca quantidade obrigatória. Testes com fakes não comprovam geração SaaS/runtime.

### Sanidade documental e preflight real

- `.reversa/active-requirements.json` resolve `_reversa_forward/001-modulo-briefing`, coding. State resolve `_reversa_sdd`; forward_folder ausente, caminho resolvido pelo active-requirements/instrução. AGENTS contém mapa antigo, não fonte de produto.
- `.reversa/reversa-config.json` lido, não modificado. `.reversa/hooks.yml` ausente; nenhum before/after-audit inventado/executado.
- Parsing por células: **16 ações / 16 IDs únicos / 9 [X] / 7 [ ]**. DFS: nenhum ciclo/dependência inexistente. Três `[//]` têm alvos distintos. T010 depende T007/T008/T009/T016; T006 depende T001/T003; executar RED T006 antes de GREEN T010, não fechar ação por planejamento.
- Todos RF citados em requirements/roadmap/actions/data delta existem. Links Markdown locais desses quatro documentos resolvem.
- progress JSONL: **25 objetos**, todos JSON válidos por linha física, newline final presente. Sem append/reparo.
- `git status --short`, branch e `git diff --check`: exit 0, branch main, árvore já suja; nada restaurado. Diff check não prova untracked/funcionalidade.
- Check stdlib `python -B -c` em workdir absoluto: exit0; sem import de produto, DB, auth, rede, secrets ou stack legado. Suite49exit0 informada pelo parent, não rerodada; não prova serviço ausente.

## Histórico preservado, não reauditado

Relatório anterior T004/T005/T007 registrado em **2026-10-11T03:13:44Z** foi lido antes do rewrite. Seus A001–A003 históricos eram MEDIUM: atribuição residual de persistência; ponte Sequence/Mapping; gate de zero I/O misturado ao domínio. No delta vigente encontram resolução documental em `data-delta.md:14,20,50,60–62,76` e `roadmap.md:81`. Esta execução não afirma ter conduzido auditoria passada nem reaprova implementação daqueles gates.

## Readset e preservação

Inventário SHA-256 capturado nesta execução: 29 arquivos (não reproduz integralmente inventário de 30 informado pelo parent), excluindo `legacy-impact.md`, `regression-watch.md` (worker paralelo) e este output. Esses dois arquivos mutáveis não foram lidos nem usados. Set inclui AGENTS, três JSON de configuração, quatro artefatos, progress, dois contratos, duas âncoras, requirements.txt, prompt, cinco módulos briefing, llm/settings e sete testes briefing (hash somente para testes). Leitura adicional restrita de constantes ROLES/PROVIDERS em `app/schemas/__init__.py:5–6` verificou compatibilidade de settings; sem import nem valores de credenciais.

Hashes principais antes/depois devem permanecer idênticos:

| Arquivo | SHA-256 baseline |
|---|---|
| requirements.md | `4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5` |
| roadmap.md | `f2405c714a1a3a50425e64e74f6e475604252ad08b622755013709de213c2aa9` |
| actions.md | `1fbface787f9fdaa104ec0c735275f2ce363fa6ab894e757ed23ebfe29d5828d` |
| data-delta.md | `0e8ea94d906d94f9dc3c257eb5619dce1d05b1a3fcc47f0ab307a054bf8cff18` |
| progress.jsonl | `be5fe07c50093d1dd923399d05ca48eabcf8bf83605402337e3c45e781ff7f49` |

Única escrita: rewrite completo deste relatório via ferramenta de escrita verificada. Verificação pós-escrita comparou todos 29 hashes: zero diferenças, mesmo conjunto; `git diff --check` exit 0 sem saída. Requirements/roadmap/actions/data-delta/state/progress/produto/tests não alterados pelo auditor. Sem fechar actions.

## Fora do escopo / próximo passo

Sem reauditoria do projeto, adapter, helpers, prompt ou domínio entregue; sem DB/HTTP/storage/runtime provider, deploy, instalações, rede ou credenciais. `legacy-impact.md` e `regression-watch.md` fora por concorrência. Correções documentais não executadas. Revisão manual dos findings antes de declarar GREEN/local concluído; depois RED T006 e coding T010. Gate runtime aguarda T011 e QA/auditoria T012/T013, especialmente A001.

Digite **CONTINUAR** para prosseguir conforme sugestão acima.

</details>


</details>

</details>

</details>

</details>
