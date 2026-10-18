# Revisão Cruzada Independente — Specs vs Código vs 30 Deliberações (`/reversa-review`)

> Revisor técnico independente. Escopo: `_reversa_sdd/` + `_reversa_forward/001-modulo-briefing/` + `_reversa_forward/002-investigacao-personas/` confrontados com código real em `app/briefing/`, `app/investigation/`, `app/models/domain_models.py`, `app/core/security.py`, `app/services/settings.py`.
> Regra respeitada: nenhum código em `app/` nem testes em `tests/` foi alterado.
> Data: 2026-10-16.

---

## 1. Veredito da Revisão Cruzada: APONTAMENTOS (não "Aprovado" pleno)

O corpo documental está **coerente nas decisões de produto** (as 30 deliberações estão fielmente transcritas em `questions.md`, `confidence-report.md §3`, `gaps.md` e nos requirements/roadmap das Features 001/002, inclusive com notas de vigência/supersessão explícitas). A implementação do **núcleo já entregue (C1–C7 / T001–T035)** adere ao especificado nos pontos verificáveis.

Porém o selo de **`confidence-report.md`: "564 afirmações, 100% CONFIRMADO, 0 lacunas" é superdeclarado** e contradiz os próprios documentos forward:

- `_reversa_forward/002-investigacao-personas/requirements.md §10` ("Lacunas") admite expressamente: "Implementação pendente: aprovação implícita no `/investigate`, revisão única com nova consulta SERP Jina orientada pelo feedback, início automático após revisão e remoção de `/approve`. Auditoria e testes desses novos comportamentos também permanecem pendentes."
- `_reversa_forward/002-investigacao-personas/roadmap.md §1` declara: "proposta documental; feature está em fase de planejamento/alinhamento de contratos pré-coding dos novos fluxos consolidados em 2026-10-14."
- `_reversa_forward/002-investigacao-personas/actions.md` mantém **T036–T040 `[ ]` abertos (Sprint C8)** — e a inspeção do código confirma que estão de fato abertos (ver §2.2).
- `_reversa_forward/001-modulo-briefing/actions.md` mantém **T004, T005, T025, T026, T035, T036, T012, T013, T037, T038 `[ ]`**, embora o código já contenha router/storage implementados — divergência de status (stale checkboxes) que o relatório de 100% ignora.

**Veredito: APONTAMENTOS.** As specs refletem fielmente as decisões do operador; o que não reflete a realidade é o selo de 100% sem pendências. Recomendação: manter as specs como estão, mas emitir errata no `confidence-report.md` (rebaixar para "100% deliberado no produto, implementação C8 pendente") e sincronizar os checkboxes de `actions.md` antes de declarar prontidão.

---

## 2. Análise de Coerência entre Specs e Código Real

### 2.1 Pontos CONFORMES (spec == código)

| Tema | Spec | Código real | Resultado |
|---|---|---|---|
| Tema 3–300 após strip, 422 | 001 requirements RN-01; Q13 | `app/briefing/domain.py:10-11,34-35` (`THEME_MIN/MAX`, `strip`, `len`) | ✅ Conforme |
| Pontos 3–7, título/descrição não-vazios | RN-03/RN-03a; Q11 (alvo 5) | `app/briefing/domain.py:12-13,41,49-51` | ✅ Conforme |
| Reopen de aprovado → 409 | Q1; 002 RF-12 | `app/briefing/router.py:318-319` bloqueia `APPROVED` com 409 | ✅ Conforme |
| Auth dupla Bearer + X-API-Key | Q4 | `app/core/security.py:49-61` aceita ambos contra `API_AUTH_SECRET` | ✅ Conforme |
| Sessão admin 24h (`dr_session`) | Q26 | `app/core/config.py:15` (`SESSION_TTL_HOURS = 24`) + `app/core/security.py:99` | ✅ Conforme |
| Até 3 buscas web por ponto, parada voluntária | Q5 | `app/investigation/worker.py:16` (`_MAX_SEARCHES = 3`), teto + `tools=None` após teto, msg de teto | ✅ Conforme |
| Até 3 autocorreções JSON, msg literal | Q16/Q7 | `app/investigation/worker.py:17,343-351` (`_MAX_JSON_CORRECTIONS = 3`, `result="Invalid JSON response after 3 corrections"`) | ✅ Conforme |
| Timeout global 600s por worker | Q17 | `app/investigation/worker.py:18,208` (`asyncio.timeout(600)`) | ✅ Conforme |
| Sucesso parcial qualifica ponto; FAILED só com 100% falha | Q6/Q7 | `app/investigation/service.py:157-163` (`FAILED` só se todos `SCRAPER_FAILED`, senão `AUDIT`) | ✅ Conforme |
| Retomada seletiva pós-restart | Q9 | `app/investigation/service.py:110-112` (`get_pending_workers_for_research`, só sem linha gravada) | ✅ Conforme |
| Herança de modelo do Scout | Q10 | `app/investigation/prompts.py:79-95` (persona → scout fallback) + `app/services/settings.py:303` + default scout `app/services/settings.py:12-13` (`gemini/gemini-3.8-flash`, Q28) | ✅ Conforme (nota: fallback final literal `"openai/implement"` em `prompts.py:97` é placeholder quando nem persona nem scout configurados; na prática `runtime_settings` sempre preenche scout) |
| Títulos sem teto 500 (`sa.Text`) | Q11/D-13 | `app/models/domain_models.py:49,65` (`title` e `step_title` em `Text`) | ✅ Conforme |
| `read_urls` com 100% URLs da Jina | Q18/RN-08 | `app/investigation/worker.py:311-313` (`_merge_urls(read_urls, jina_result.urls)`) + persistência append-only | ✅ Conforme |
| Erros sanitizados ≤500 chars | Q24 | `app/investigation/worker.py:42-50` (`_sanitize_error`, `text[:500]`, máscaras Bearer/api-key/sk-/token) | ✅ Conforme |
| Proxy Jina opcional | Q27 | `app/services/settings.py:313-324` (`runtime_jina_proxy`) + adaptador Jina com proxy | ✅ Conforme |
| Briefing: 1 SERP por geração, sem Reader, retry até 4 totais com reuso SERP | Q12/Q15 | `app/briefing/service.py:87-111` (1 `search`, loop LLM ≤4 reusando SERP) | ✅ Conforme |
| Revisão PATCH usa tema + rascunho + feedback, 1 nova SERP (sem Reader) | Q14/Q15 | `app/briefing/service.py:188-202` (`search(theme)`, payload com `rascunho_atual` + `feedback`) | ✅ Conforme (primeira metade; ver §2.2 para a segunda metade pendente) |
| Enum unificado `ResearchStatus`, `attempt_count`, `research_step_results` append-only | 002 §4.2 | `app/models/domain_models.py:18-26,44-73` | ✅ Conforme |

### 2.2 Divergências REAIS — exatamente o escopo da Sprint C8 (T036–T040), corretamente marcada `[ ]`

| ID C8 | Exigência da spec vigente | Estado real do código | Conclusão |
|---|---|---|---|
| T036 (D-21/RF-02) Extinguir `/approve` | "endpoint `POST /briefings/{research_id}/approve` não deve existir, sem substituto" | `app/briefing/router.py:289-305` **a rota ainda existe e aprova normalmente** | ❌ Pendente — spec futura correta, código ainda no contrato antigo. `prd.md/sdd/briefing.md` tratam isso corretamente como "nota de vigência / C8 futura". |
| T037 (D-22/RF-03/RN-01) Aprovação implícita no `/investigate` sobre draft | Draft válido → 202, cria `research_points` em `SCRAPER_IN_PROGRESS`, pesquisa → `SCRAPER`, sem 409 por draft | `app/investigation/router.py:40-51` **exige** `research.status == SCRAPER` e pontos pré-existentes em `SCRAPER_PENDING`; draft sem pontos recebe **409** (`_CONFLICT`). Nenhuma criação de pontos nem aprovação no handler. | ❌ Pendente — comportamento atual é o pré-C8 (disparo sobre base já aprovada). |
| T038 (D-23/RF-12) PATCH com auto-investigate em background | PATCH gera revisão **e** aprova + insere pontos + despacha workers + responde 200 síncrono | `app/briefing/service.py:220-226` persiste revisão e volta pesquisa a `PENDING_APPROVAL`; **não insere `research_points`, não despacha `BackgroundTasks`**. | ❌ Pendente (metade implementada: nova SERP + revisão; falta o auto-investigate). |
| T039 (D-24) Bloqueio de 2ª revisão com 409 | Qualquer 2º PATCH → 409 | `app/briefing/router.py:241-242` bloqueia apenas "não-draft → 409". Como a revisão retorna a `PENDING_APPROVAL`/draft-equivalente sem iniciar investigação, um 2º PATCH **não é bloqueado pelo estado atual**. Discriminação 500/502/503 (Q12) existe no mapeamento de erros (`router.py:262-267`), mas o fluxo terminal `FAILED` sem investigação só vale para o caminho sem auto-investigate. | ❌ Pendente |
| T040 Suíte adaptada ao novo contrato | 202 sobre draft, `/approve` ausente (404/405), PATCH auto-investigate, 409 2ª revisão, 500/502/503 | Não verificável como verde neste escopo (sem execução de testes); os próprios `actions.md`/`requirements.md §10` declaram testes desses fluxos pendentes. | ❌ Pendente por dependência de T036–T039 |

**Nota sobre `briefing_versions` vs Q19 ("sobrescrita direta, só versão ativa"):** o código mantém `briefings` (versão ativa) + `briefing_versions` (histórico auditável), e a spec 002 §4.1/4.2 consagra as duas tabelas como "histórico canônico auditável". A redação de Q19/confidence §4 ("sobrescrevendo rascunhos antigos") é simplificação fiel à intenção (tabela ativa compacta), mas literalmente o histórico persiste em `briefing_versions`. Apontamento menor de redação, sem impacto funcional.

### 2.3 Divergência documental interna (a corrigir sem código)

- `confidence-report.md` (100%/0 lacunas) vs `002/requirements.md §10` + `002/roadmap.md §1` + `002/actions.md` (C8 aberta): o relatório global não pode estar 100% implementado enquanto T036–T040 estão `[ ]` e o código confirma a pendência. Corrigir por errata, não por código.
- `001/actions.md` com `[ ]` em T004/T005/T025/T026/T035/T036/T012/T013/T037/T038 enquanto `app/briefing/router.py`, `storage.py`, `schemas.py` já existem: ou as tarefas foram entregues e o checkbox não foi atualizado, ou os gates (aceitação/auditoria) seguem abertos — de todo modo o status está inconsistente com o selo 100%.

---

## 3. Validação das 30 Deliberações do Operador

Legenda: ✅ fiel e implementada · 🟡 fiel na spec, implementação parcial/pendente (C8) · ⬜ fora do escopo inspecionado (não refutado, apenas não verificado aqui).

| # | Deliberação (resumo) | Fidelidade documental | Aderência do código | Status |
|---|---|---|---|---|
| Q1 | Aprovação definitiva; reopen → 409 | ✅ (`questions.md:13-14`, 002 RF-12, `gaps.md` G-01/G-04) | ✅ `router.py:318-319` | ✅ |
| Q2 | Fluxo conversacional: tema → rascunho 3–7 → feedback → nova SERP (tema+rascunho+feedback) → ajuste + auto-aprovação; aprovação direta sem 2ª busca | ✅ (com notas de vigência 001→002) | 🟡 nova SERP + revisão OK (`service.py:188-202`); **auto-aprovação + avanço imediato pendentes (T038)** | 🟡 |
| Q3 | `POST …/investigate` = aprovação em etapa única | ✅ (RN-01/RF-03/D-22) | ❌ handler exige base já aprovada (`investigation/router.py:40-51`) | 🟡 (C8 T037) |
| Q4 | Bearer **e** X-API-Key oficiais | ✅ (`contracts.md` §1, `gaps.md` G-07) | ✅ `security.py:49-61` | ✅ |
| Q5 | Até 3 buscas com parada inteligente | ✅ (RN-06) | ✅ `worker.py:16` + parada voluntária | ✅ |
| Q6 | Sucesso parcial (≥1 persona → auditoria) | ✅ (RF-10) | ✅ `service.py:157-163` | ✅ |
| Q7 | FAILED só com 100% falha | ✅ | ✅ idem | ✅ |
| Q8 | Só síntese final + URLs no banco; CoT em RAM | ✅ (Princípio II) | ✅ `worker.py` RAM-only `messages`; `result` analítico/erro | ✅ |
| Q9 | Retomada seletiva (só pendentes) | ✅ (RF-13) | ✅ `service.py:110-112` | ✅ |
| Q10 | Personas herdam modelo do Scout | ✅ (RN-10) | ✅ `prompts.py:79-95`, `settings.py:303` | ✅ |
| Q11 | 3–7 pontos; títulos sem teto 500 | ✅ (Q11 superando Q4/Q6) | ✅ `domain.py:12-13,41`; `domain_models.py:49,65` Text | ✅ |
| Q12 | Briefing: só snippets Jina, sem scraping | ✅ | ✅ `serp_client` SERP-only; revisão sem Reader | ✅ |
| Q13 | Tema 3–300 após strip, 422 explícito | ✅ (RF-01) | ✅ `domain.py:34-35` | ✅ |
| Q14 | Ocultação total de chaves (só booleano) | ✅ | ✅ `settings.py:327-342` (`mask_secret`, `provider_configured`) + sanitize worker | ✅ |
| Q15 | Até 4 tentativas briefing, timeout 30s, reuso SERP | ✅ (RF-10; investigação tem regra própria de 3 totais — distinção documentada, não conflito) | ✅ `briefing/service.py:87-111` | ✅ |
| Q16 | Até 3 autocorreções JSON | ✅ (RN-13) | ✅ `worker.py:343-351` | ✅ |
| Q17 | Timeout 600s por agente | ✅ (RN-07) | ✅ `worker.py:18,208` | ✅ |
| Q18 | 100% URLs em `read_urls` | ✅ (RN-08) | ✅ `worker.py:313` | ✅ |
| Q19 | Só versão ativa (sobrescreve rascunhos) | ✅ intenção; redação simplificada (ver §2.2 nota `briefing_versions`) | 🟡 ativo + histórico coexistem por decisão 002 §4.1 | ✅ com nota de redação |
| Q20 | SSE tempo real por agente | ✅ na spec | ⬜ fora do escopo inspecionado (sem `routers/stream` verificado aqui) | ⬜ |
| Q21 | Segurança de rede delegada à Jina | ✅ (`gaps.md` G-12) | ✅ sem filtro SSRF redundante sobre busca; SSRF guard permanece em `outbound/base_url` para callbacks/proxy | ✅ |
| Q22 | Webhook em DONE/FAILED | ✅ na spec | ⬜ `webhook.py` fora do escopo inspecionado | ⬜ |
| Q23 | Markdown completo com citações diretas | ✅ na spec (Feature 004) | ⬜ Writer fora do escopo | ⬜ |
| Q24 | Erros sanitizados ≤500 chars | ✅ | ✅ `worker.py:42-50`; briefing erros fixos | ✅ |
| Q25 | Dark mode estilo Linear | ✅ na spec (frontend) | ⬜ frontend fora do escopo | ⬜ |
| Q26 | Sessão 24h (`dr_session`) | ✅ | ✅ `config.py:15` | ✅ |
| Q27 | Proxy Jina opcional | ✅ (RN-05) | ✅ `settings.py:313-324` | ✅ |
| Q28 | Scout default `gemini/gemini-3.8-flash` | ✅ (E001) | ✅ `settings.py:12-13` | ✅ |
| Q29 | Auditor pelo checklist de 12 perguntas | ✅ (`gaps.md` G-13; Feature 003) | ⬜ Auditor fora do escopo inspecionado | ⬜ |
| Q30 | Limpeza automática de transitórios | ✅ | ✅ RAM-only (parte verificada); purga de disco ⬜ não verificada neste escopo | ✅/⬜ parcial |

**Síntese:** as 30 deliberações estão **fielmente refletidas na documentação** (nenhuma decisão do operador foi contrariada ou omitida; supersessões 001→002 estão marcadas com notas de vigência). No código, **24–25 estão implementadas** no escopo inspecionado; **Q2/Q3 (partes de auto-aprovação/auto-investigate) pendem da C8**; 5 são de features/superfícies fora do escopo (SSE, webhook, writer, frontend, auditor) e não foram refutadas.

---

## 4. Parecer Final de Prontidão para a Sprint C8 (T036–T040)

**A Sprint C8 está corretamente definida e NÃO está pronta para aceite — e é exatamente assim que `actions.md` a declara (`[ ]`).** O parecer independente:

1. **Escopo C8 correto e completo:** T036 (extinguir `/approve`), T037 (aprovação implícita atômica no `/investigate`), T038 (PATCH com 2ª SERP + auto-investigate), T039 (409 na 2ª revisão), T040 (suíte adaptada) cobrem precisamente as divergências §2.2. Nada a acrescentar ou remover.
2. **Pré-requisitos de implementação (ordem sugerida):** T036 → T037 (decisão de atomicidade: validar pontos do briefing → inserir `research_points` `SCRAPER_IN_PROGRESS` + `research` → `SCRAPER` na mesma transação antes do 202) → T038 (inserir pontos + despachar `BackgroundTasks` no PATCH; resposta 200 síncrona com revisão) → T039 (guard de revisão única por flag de versão/investigação iniciada, não só `status != DRAFT`) → T040 (testes dos 5 cenários Gherkin novos + regressão 001).
3. **Gates antes do aceite C8:** (a) suíte 001 adaptada 100% verde no novo contrato; (b) E2E `investigate` sobre draft → 202 + N×4 workers + `AUDIT`/`FAILED` conforme regra 100%; (c) PATCH → 200 + investigação automática sem 2º `/investigate`; 2º PATCH → 409; falhas → 500/502/503 + `FAILED` sem investigação fantasma; (d) `/approve` ausente (404/405); (e) `/reversa-audit` + `/reversa-quality` sem inconformidades.
4. **Ação documental imediata (sem código):** publicar errata no `_reversa_sdd/confidence-report.md` ("decisões 100% deliberadas; implementação C8 pendente — ver `002/actions.md` T036–T040 e `requirements.md §10`") e reconciliar checkboxes `001/actions.md` vs código real. Só então reemitir selo de confiança.
5. **Risco se C8 for declarada pronta hoje:** clientes que seguirem a spec vigente (`investigate` sobre draft, PATCH auto-investigate, sem `/approve`) receberão 409/404 inesperados e pontos nunca instanciados — quebra de contrato silenciosa.

**Parecer: APONTAMENTOS — documentação fiel às 30 deliberações; código conforme no núcleo C1–C7; Sprint C8 pendente e bem delimitada; `confidence-report.md` de 100% requer errata antes de qualquer declaração de prontidão geral.**

---

*Fim do relatório de revisão cruzada independente. Nenhum arquivo em `app/` ou `tests/` foi modificado.*
