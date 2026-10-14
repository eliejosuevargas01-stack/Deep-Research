# Roadmap: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`
> Data: `2026-10-14`
> Requirements: `_reversa_forward/002-investigacao-personas/requirements.md`
> Confidência: 🟢 decisões de produto confirmadas Q1–Q16; 🟡 interpretação arquitetural explicitada onde requirements não fixa implementação.

---

## 1. Resumo da abordagem

> **Estado:** proposta documental; feature está em fase de planejamento/alinhamento de contratos pré-coding dos novos fluxos consolidados em 2026-10-14. Itens registrados em `progress.jsonl` não substituem aceite: falhas baseline e teste sensível a ordem/DNS seguem gates obrigatórios (Q2).

O ciclo de pesquisa inicia com `POST /briefings`, que persiste a linha em `research` antes do briefing com UUID unificado (`research_id`), valida o tema entre 3 e 300 caracteres (rejeitando temas > 300 com HTTP 422 e erro explícito), gera o rascunho inicial via Scout e o entrega em status `draft` (`PENDING_APPROVAL` em `research`).

O operador dispõe de duas vias exclusivas de progressão, sem a existência do endpoint `/approve`:
1. **Caminho A (Investigação direta com aprovação implícita):** Acionar `POST /briefings/{research_id}/investigate` diretamente sobre o primeiro briefing válido em status `draft`. A chamada opera aprovação implícita e início da investigação na mesma operação. O status `draft` e a ausência prévia de registros em `research_points` não geram HTTP 409 Conflict. Os pontos do briefing são validados e persistidos atomicamente em `research_points` vinculados ao `research_id` com status inicial `SCRAPER_IN_PROGRESS` e `attempt_count = 0`, a pesquisa transita para `SCRAPER`, e o despacho assíncrono dos workers é agendado em background via FastAPI `BackgroundTasks`, retornando HTTP 202 Accepted. Re-disparos e operações concorrentes retornam HTTP 409 Conflict.
2. **Caminho B (Revisão única por feedback com início automático em background):** Enviar feedback textual único via `PATCH /briefings/{research_id}` com payload `{"note": "texto do feedback"}` (3 a 4000 caracteres). O Scout executa obrigatoriamente exatamente 1 nova consulta de busca SERP Jina formulada pela IA a partir do tema original e do feedback. Com base nos novos resultados, a IA preserva os pontos não afetados e ajusta ou acrescenta foco aos demais conforme as novas evidências, gerando a versão revisada em `briefing_versions`. Na mesma operação, o sistema aprova e inicia a investigação automaticamente em background, persistindo os pontos em `research_points` (`SCRAPER_IN_PROGRESS`) e transitando a pesquisa para `SCRAPER`, sem segunda chamada a `/investigate` e sem confirmação intermediária do usuário. A resposta é síncrona HTTP 200 contendo o briefing revisado. Qualquer tentativa posterior de nova revisão via PATCH é bloqueada com HTTP 409 Conflict. Se a busca SERP Jina ou a geração do briefing revisado falhar de forma terminal após esgotar retries, a API responde HTTP 500 (configuração), HTTP 502 (modelo indisponível) ou HTTP 503 (busca Jina indisponível); a pesquisa transita para `FAILED`, o briefing para `failed`, e nenhuma investigação é iniciada.

Iniciada a investigação (seja pelo Caminho A ou pelo Caminho B), o sistema investiga concorrentemente cada ponto de pesquisa instanciado (3 a 7 pontos) disparando quatro workers assíncronos com papéis cognitivos distintos: **historian**, **skeptic**, **pragmatist** e **futurist**. Para $N$ pontos aprovados, são instanciadas exatamente $N \times 4$ execuções simultâneas em background (`asyncio.gather` concorrente irrestrito, até 28 workers simultâneos).

Cada worker executa um loop de reflexão com LiteLLM nativo e memória conversacional mantida estritamente em RAM, invocando a ferramenta Jina Search (via POST direto ou proxy configurado). Cada worker possui orçamento estrito de até 3 consultas de busca Jina por ponto, podendo encerrar voluntariamente ao atingir síntese suficiente. O harness captura 100% das URLs retornadas pela Jina e as persiste em `read_urls` (sem presumir leitura integral ou citação verbatim). O modelo entrega sua análise final estruturada em JSON com `result` e `used_urls` (com suporte a até 3 chamadas corretivas dedicadas de JSON).

Os resultados finais de cada persona são persistidos de forma imutável (append-only) em `research_step_results` com status `AUDIT_PENDING` (em sucesso) ou `FAILED` com mensagem de erro sanitizada (em falha definitiva). Cada falha definitiva incrementa atomicamente o contador `attempt_count` do respectivo ponto. Ao término de todos os workers de um ponto, o ponto transita para `AUDIT_PENDING` (se pelo menos 1 worker teve sucesso) ou `SCRAPER_FAILED` (se os 4 falharam). Ao término de todos os pontos da pesquisa, a pesquisa transita para `AUDIT` se pelo menos 1 ponto obteve sucesso analítico, ou para `FAILED` se 100% dos pontos falharem definitivamente.

---

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| **I. Rastreabilidade Factual Estrita (Verbatim Citation)** | O harness registra todas as URLs retornadas pela Jina (`read_urls`), sem afirmar leitura integral ou prova verbatim, e o modelo referencia explicitamente as URLs utilizadas (`used_urls`), preparando os dados para a auditoria factual futura (Feature 003). Prompts exigem citação factual estrita (*verbatim*). | Respeita |
| **II. Defesa de Privacidade e Isolamento de Prompts** | Prompts/CoT ficam somente em RAM; `result` persiste síntese final ou erro sanitizado de até 500 caracteres, sem expor chaves de API, credenciais ou segredos em banco, logs públicos ou respostas. 🟢 decisão confirmada. | Respeita |
| **III. Resiliência por Degradação Graciosa e Limites Rígidos** | Falha de uma persona isolada não interrompe os outros workers (`return_exceptions=True`). Timeout de 90s por chamada externa Jina/LLM, timeout global de 600s por worker e até 3 tentativas totais externas (1 inicial + 2 retries com backoff 2s/4s e respeito a `Retry-After`). Se todos os workers de um ponto falharem, o ponto fica `SCRAPER_FAILED`; a pesquisa segue para `AUDIT` se ao menos um ponto tiver sucesso, e vai a `FAILED` somente se todos os pontos falharem. | Respeita |
| **IV. Concorrência Segura e Idempotência** | O módulo `app/investigation/` opera com **concorrência irrestrita** via `asyncio.gather` (até 28 workers simultâneos), conforme formalizado na Emenda da Feature 002 ao Princípio IV em `.reversa/principles.md`. Idempotência e prevenção de concorrência garantidas com HTTP 409 em re-disparos e chamadas sobre pesquisas já iniciadas. | Respeita (Princípio IV emendado formalmente em `.reversa/principles.md`: concorrência irrestrita na 002, governada por timeouts e retries) |

---

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| **D-01** | Identificador unificado `research_id` gerado antes do briefing | Briefing, passos, investigação e auditoria compartilham o mesmo UUID canônico da pesquisa | Criar IDs desconectados ou tabela de mapeamento intermediária | 🟢 |
| **D-02** | Módulo isolado em `app/investigation/` | Mantém separação limpa de responsabilidades e desacoplamento do código legado monolítico | Misturar workers dentro de `app/services/research.py` | 🟢 |
| **D-03** | Tabela dedicada `research_step_results` append-only | Permite auditoria histórica e repesquisa futura sem conflitar com constraints legadas de `Evidence` | Reutilizar `Evidence` ou salvar em coluna JSON nos passos | 🟢 |
| **D-04** | Concorrência irrestrita via `asyncio.gather` | Executar simultaneamente todos os pontos x 4 personas (até 28 workers) sem gargalos de semáforo | Usar semáforo 4 do `llm.py` ou semáforo 20 | 🟢 |
| **D-05** | Tool Calling nativo LiteLLM com mensagens em RAM | Padrão robusto da OpenAI, sem frameworks pesados; histórico descartado da RAM ao fim da execução | LangChain, LlamaIndex, ou salvar histórico de tool calls no banco | 🟢 |
| **D-06** | Jina Search via POST com suporte a proxy | POST `https://s.jina.ai/` com payload JSON `{"q": query}` e headers `Accept: application/json` / `X-Engine: direct`; ou proxy se configurado | GET com query string na URL | 🟢 |
| **D-07** | Teto de 3 buscas com parada antecipada | O modelo reflete se tem dados suficientes e para; se atingir 3 queries, o harness encerra e exige o JSON final | Busca infinita ou número fixo obrigatório de 3 queries | 🟢 |
| **D-08** | Retries e backoff para chamadas externas | Até 3 tentativas totais; respeita `Retry-After` ou espera exponencial de 2s e 4s; retries não consomem o teto de 3 buscas | Sem retries ou retry imediato sem backoff | 🟢 |
| **D-09** | Até 3 correções de JSON final do modelo | Se a resposta não parsear no schema esperado, faz até 3 chamadas corretivas dedicadas sem descontar das buscas | Descartar imediatamente ou aceitar texto não estruturado | 🟢 |
| **D-10** | Disparo assíncrono com HTTP 202 e re-disparo com HTTP 409 | Chamador recebe confirmação de início em background imediatamente; se já disparado, rejeita com 409 Conflict | Execução síncrona com timeout HTTP longo | 🟢 |
| **D-11** | Retomada automática pós-reinício | Servidor retoma apenas personas sem linha em `research_step_results`; `SCRAPER_IN_PROGRESS` é estado de ponto, não de pesquisa | Perder execuções em andamento ou marcar tudo como falha | 🟢 decisão / 🟡 mecanismo derivado |
| **D-12** | Desativação do agendamento de pipeline legado (`schedule(run_research)`) | A investigação é disparada exclusivamente em background via workers da Feature 002 (Caminho A ou B); a rotina legada `schedule(run_research)` é desativada e não é acionada na aprovação implícita ou revisão | Manter `schedule(run_research)` no fluxo legado | 🟢 Q1 / Decisões 2026-10-14 |
| **D-13** | Títulos ilimitados (Q11) + tema 3–300 (Q13) | `step_title` e `research_points.title` passam a `sa.Text` (migração 007); títulos gerados pelo Scout NÃO têm teto de 500; tema do usuário 3–300 com HTTP 422 e erro explícito | Truncar título ou aplicar 500 ao tema | 🟢 Q4/Q6 (superadas por Q11/Q13) |
| **D-14** | Falhas baseline são gate de aceite | Corrigir 9 falhas herdadas e 1 sensível a ordem/DNS antes do aceite; não dispensar como dívida prévia | Excluir testes do gate | 🟢 Q2 |
| **D-15** | Exaustão de reparos de JSON produz FAILED | Inicial + até 3 correções; ao esgotar, grava FAILED, result="Invalid JSON response after 3 corrections" e used_urls=[] | Descartar sem persistir ou salvar JSON quebrado | 🟢 Q7 |
| **D-16** | Contador de falhas definitivo | `attempt_count` nasce em 0 e incrementa +1 atomicamente por falha de worker; retomada ignora personas já persistidas | Contar falhas transitórias ou duplicar incremento na retomada | 🟢 Q8 |
| **D-17** | Isolamento de prompts e CoT | Apenas RAM; `result` contém análise final ou erro sanitizado de até 500 caracteres, sem prompts ou segredos | Persistir histórico bruto de mensagens | 🟢 Q9 |
| **D-18** | Modelo e credenciais por persona | `app_settings.models.<persona>` com fallback scout; resolver chave e base URL do provedor correspondente para cada execução | Reutilizar chave scout para provedores diferentes | 🟢 RN-10 / 🟡 resolução técnica |
| **D-19** | Fronteira de acesso e reserva | Admin obrigatório; inexistente 404, não admin 401/403, estado inválido ou zero pontos 409; reserva atômica antes de 202 | Disparo duplicado ou retorno 202 sem pontos | 🟢 Q5/Q10 |
| **D-20** | Discriminação de erros HTTP no PATCH | HTTP 500 para erro interno/configuração, HTTP 502 para geração pelo modelo indisponível e HTTP 503 para busca Jina indisponível; pesquisa FAILED e briefing failed | Agrupar erros ou mascarar causa externa | 🟢 Q12 |
| **D-21** | Extinção definitiva do endpoint `/approve` | O endpoint `POST /briefings/{research_id}/approve` é eliminado sem nenhum endpoint substituto. A aprovação ocorre exclusivamente de forma implícita (ao chamar `POST /briefings/{research_id}/investigate` sobre o briefing em rascunho) ou automática (ao concluir a revisão única via `PATCH /briefings/{research_id}`) | Manter `/approve` como passo intermediário manual ou criar novo endpoint de confirmação | 🟢 Decisões 2026-10-14 / RF-02 |
| **D-22** | Aprovação implícita e início da investigação no investigate direto | `POST /briefings/{research_id}/investigate` sobre o primeiro briefing válido em status `draft` opera aprovação implícita e início da investigação na mesma operação. O status `draft` e a ausência prévia de registros em `research_points` não geram HTTP 409. Os pontos são persistidos diretamente em `research_points` com status `SCRAPER_IN_PROGRESS`, pesquisa passa atomicamente para `SCRAPER`, e workers são despachados em background (HTTP 202) | Exigir endpoint de aprovação prévia ou retornar 409 para briefings em rascunho | 🟢 Decisões 2026-10-14 / RF-03 / RN-01 |
| **D-23** | Revisão única por feedback com busca SERP Jina por IA e auto-investigate em background no PATCH | `PATCH /briefings/{research_id}` aceita exclusivamente `{"note": "texto"}` (3–4000 chars), dispara obrigatoriamente 1 nova consulta SERP Jina formulada pelo modelo com base no tema original e no feedback, preserva pontos não afetados, ajusta ou acrescenta foco conforme as novas evidências, gera a nova versão em `briefing_versions`, e aprova e inicia a investigação automaticamente em background na mesma operação (inserindo pontos em `SCRAPER_IN_PROGRESS`, pesquisa em `SCRAPER`, despachando workers em background) com resposta síncrona HTTP 200 contendo o briefing revisado | PATCH manual por lista de pontos, permitir múltiplas revisões iterativas, ou exigir chamada posterior a `/investigate` | 🟢 Decisões 2026-10-14 / Q14-Q15 / RF-12 / RN-01 |
| **D-24** | Bloqueio de 2ª revisão e discriminação de falhas terminais no PATCH | O operador só pode revisar o briefing uma única vez; qualquer tentativa subsequente de chamada a `PATCH /briefings/{research_id}` retorna HTTP 409 Conflict. Em caso de falha terminal da busca SERP Jina ou geração do briefing revisado após retries técnicos: responde HTTP 500 (configuração LLM), HTTP 502 (modelo indisponível) ou HTTP 503 (busca Jina indisponível); a pesquisa transita para `FAILED`, o briefing para `failed`, nenhuma investigação é iniciada, e recuperação exige novo `POST /briefings` | Permitir revisões indefinidas, mascarar erros com HTTP 500 genérico ou iniciar investigação com pontos incompletos após falha no PATCH | 🟢 Decisões 2026-10-14 / Q12, Q16 / RF-12 |

---

## 4. Premissas

Nenhuma premissa de produto permanece em aberto após as deliberações Q1–Q16 registradas em `requirements.md`. Escolhas de tradução técnica marcadas 🟡 são interpretações arquiteturais, não deliberações adicionais.

---

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `InvestigationService` | `app/investigation/service.py` | componente-novo | Orquestrador de investigação assíncrona, instanciação atômica de pontos a partir do briefing, fan-out de workers e transições de estado |
| `PersonaWorker` | `app/investigation/worker.py` | componente-novo | Executa o loop de tool calling com LiteLLM, limite de 3 queries e extração de fontes |
| `JinaToolAdapter` | `app/investigation/tools.py` | componente-novo | Cliente HTTP para Jina Search (POST direto ou proxy) com timeouts e retries |
| `InvestigationRouter` | `app/investigation/router.py` | componente-novo / contrato-novo | Expõe `POST /briefings/{research_id}/investigate` com aprovação implícita sobre rascunho inicial válido e início da investigação em background (HTTP 202); bloqueia re-disparos e concorrência com HTTP 409 |
| `BriefingRouter` | `app/briefing/router.py` | regra-alterada / contrato-alterado | Adota `research_id`, instancia `Research` antes do briefing, extingue `POST /briefings/{research_id}/approve`, bloqueia reopen pós-aprovação (HTTP 409) e implementa revisão única via `PATCH /briefings/{research_id}` por feedback `{"note"}` com nova busca SERP Jina por IA, geração revisada, aprovação e início automático da investigação em background (HTTP 200 síncrono), bloqueando 2ª revisão com HTTP 409 e discriminando falhas terminais em 500/502/503 |
| `ResearchService` | `app/services/research.py` | regra-alterada | Adaptação para o novo enum de status `ResearchStatus` unificado e desativação do agendamento legado `schedule(run_research)` |

### Âncoras reais e recorte

`architecture.md`, `domain.md`, `c4-context.md`, `state-machines.md`, `dependencies.md` e `code-analysis.md` estão ausentes na extração. Não representam regras herdadas verificadas. Âncoras físicas: `_reversa_sdd/prd.md`, componente **Módulo backend de briefing** em `_reversa_sdd/sdd/briefing.md` e **Módulo de Briefing (Backend)** em `_reversa_sdd/addenda/001-modulo-briefing.md`. O adendo da 001 registra contratos anteriores; §2.1 e decisões Q1 a Q16 da 002 autorizam substituição de edição manual, extinção de `/approve`, aprovação implícita, revisão única com auto-investigate e identificador público canônico. A tabela acima aponta arquivos reais de código, não componentes inventados de uma extração inexistente.

Arquivos afetados adicionais: `app/briefing/schemas.py`, `app/briefing/storage.py`, `app/briefing/domain.py`, `app/briefing/service.py`, `app/routers/research.py`, `app/main.py`, `app/services/pipeline/writer.py`, `app/services/webhook.py`, migração `0007`, testes de briefing/investigação e três suítes de regressão do baseline. Alvos exatos e sprints constam de `actions.md`. Templates locais e hooks ausentes; fallback canônico apenas lido, conforme `investigation.md`.

---

## 6. Delta no modelo de dados

- **Nova tabela `research_step_results`**: armazena os resultados das personas (`id`, `research_id`, `step_id`, `step_title`, `result`, `used_urls`, `read_urls`, `worker`, `status`, `created_at`). `step_title` usa `sa.Text` (sem limite de 500 caracteres, conforme Q11).
- **Instanciação de `research_points`**: pontos não são criados durante a geração do briefing; passam a existir em `research_points` no momento da aprovação implícita (via `POST /briefings/{research_id}/investigate` sobre rascunho) ou automática pós-revisão (via `PATCH /briefings/{research_id}`). Em ambos os casos, nascem diretamente com status `SCRAPER_IN_PROGRESS` e `attempt_count = 0`, com títulos em `sa.Text` (Q11).
- **Novo enum de status em `Research.status`**: `PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`.
- **Novos status em `ResearchPoint.status`**: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`, `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`. O status legado `SEARCH_SUCCESS` é expurgado do enum e migrado para `AUDIT_PENDING`.
- **Backfill em migração Alembic 0007**: instancia linhas em `research` para briefings legados da Feature 001 e copia pontos de briefings aprovados para `research_points` com status `SCRAPER_PENDING`.
- Detalhe completo em: `_reversa_forward/002-investigacao-personas/data-delta.md`.

---

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `POST /briefings/{research_id}/investigate` | HTTP | `_reversa_forward/002-investigacao-personas/interfaces/investigate.md` |
| `Briefings API (Contrato Atualizado)` | HTTP | `_reversa_forward/002-investigacao-personas/interfaces/briefings.md` |

*Nota de extinção de contrato:* O endpoint `POST /briefings/{research_id}/approve` foi completamente extinto do contrato da Briefings API, sem endpoint substituto.

---

## 8. Plano de migração

1. **Alembic Migration (versão `0007_investigation_step_results_and_status`)**:
   - Criação da tabela `research_step_results` com FKs para `research.id` e `research_points.id`, usando tipos portáteis (`sa.Uuid`, `sa.JSON`, `sa.DateTime(timezone=True)`, `sa.Text` para `step_title`).
   - Ampliação da coluna `research_points.title` de `String(500)` para `sa.Text` (Q11).
   - Atualização da coluna `research.status` (conversão segura de tipos/strings).
   - Migração de dados legados de `research.status` para o novo enum unificado.
   - Migração de `research_points.status`: converter `SEARCH_SUCCESS` para `AUDIT_PENDING`.
   - Backfill: para cada registro existente em `briefings`, se não existir em `research`, criar registro correspondente em `research` com o mesmo UUID; para briefings com status `approved`, instanciar os pontos em `research_points` como `SCRAPER_PENDING` com `attempt_count = 0`.
2. **Atualização da Feature 001**:
   - Atualizar `POST /briefings` para criar `Research` antes de gerar o rascunho, validando tema entre 3 e 300 caracteres (rejeitando > 300 com HTTP 422 e erro explícito).
   - Atualizar schemas para retornar `research_id` no lugar de `id`.
   - Extinguir definitivamente a rota `POST /briefings/{research_id}/approve`.
   - Implementar aprovação implícita e instanciação direta dos pontos em `SCRAPER_IN_PROGRESS` ao receber `POST /briefings/{research_id}/investigate` sobre primeiro briefing válido em `draft`.
   - Substituir `PATCH /briefings/{research_id}` por feedback textual `{"note": "texto"}` (3 a 4000 caracteres): Scout executa 1 nova busca SERP Jina formulada pela IA (tema + feedback), preserva pontos não afetados, ajusta/acrescenta foco, gera versão revisada, persiste pontos em `research_points` (`SCRAPER_IN_PROGRESS`), transita pesquisa para `SCRAPER` e despacha investigação automaticamente em background; resposta síncrona HTTP 200; bloqueio de 2ª revisão com HTTP 409; falhas terminais retornam 500, 502 ou 503 com pesquisa `FAILED` e briefing `failed`.
   - `POST /briefings/{research_id}/reopen` em briefing aprovado ou pesquisa em `SCRAPER` passa a retornar 409.
   - Ajustar a suíte de testes da 001 para validar o novo contrato (ausência de `/approve`, aprovação implícita no `/investigate`, revisão única no PATCH com início automático, e bloqueio 409 para segundas revisões) e manter 100% de aprovação.
3. **Implementação do Módulo `app/investigation/`**:
   - Schemas, Tools (Jina direta/proxy), Worker (LiteLLM com tool calling e RAM isolada), Storage, Service e Router.
   - Registro do router no `app/main.py`.
   - Registro de hook de inicialização do FastAPI para retomar workers em `SCRAPER_IN_PROGRESS`.

---

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Rate limit (HTTP 429) no gateway LLM pelo disparo de 20-28 conexões | Alto | Média | Tratamento nativo com backoff exponencial (2s, 4s) e respeito estrito ao header `Retry-After`. Resiliência parcial evita derrubar o lote. |
| Timeout na API da Jina Search | Médio | Média | Timeout de 90s por chamada, timeout global de 600s por worker, 3 tentativas totais (1 inicial + 2 retries, backoff 2s/4s) e isolamento por worker. |
| Modelo emite JSON final com sintaxe inválida | Médio | Média | Harness realiza até 3 chamadas corretivas dedicadas instruindo o modelo a corrigir o JSON sem descontar da cota de buscas. |
| Reinício do container interrompe workers em andamento | Médio | Baixa | Startup inspeciona pesquisa em `SCRAPER` com pontos `SCRAPER_IN_PROGRESS` e retoma somente personas sem linha gravada em `research_step_results`. |
| Tentativa de múltiplas revisões desestabilizar pipeline | Médio | Média | Regra estrita de revisão única no PATCH com retorno HTTP 409 Conflict para qualquer segunda chamada. |
| Falha terminal em busca externa durante revisão no PATCH | Alto | Média | Discriminação clara em 500, 502 ou 503 conforme a origem; pesquisa transita atomicamente para `FAILED` e briefing para `failed`, sem agendar investigação fantasma. |

---

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Nove falhas baseline de `8bfd529` e um teste sensível a ordem/DNS corrigidos, sem dispensa (Q2)
- [ ] Endpoint `POST /briefings/{research_id}/approve` completamente extinto do sistema, sem substituto
- [ ] Disparo direto via `POST /briefings/{research_id}/investigate` opera aprovação implícita sobre primeiro briefing válido em `draft`, instanciando pontos em `SCRAPER_IN_PROGRESS` e pesquisa em `SCRAPER` (HTTP 202) sem erro 409 por status `draft`
- [ ] `PATCH /briefings/{research_id}` aceita `{"note": "..."}`, executa 1 nova busca SERP Jina formulada pela IA (tema + feedback), preserva pontos não afetados, ajusta/acrescenta foco, gera briefing revisado, aprova e inicia investigação automaticamente em background (HTTP 200 síncrono)
- [ ] Segunda tentativa de revisão via PATCH bloqueada com HTTP 409 Conflict
- [ ] Falhas terminais no PATCH discriminadas em HTTP 500, 502 ou 503 com pesquisa em `FAILED` e briefing em `failed`
- [ ] Nenhuma aprovação ou revisão agenda o pipeline legado `schedule(run_research)` (Q1, D-12)
- [ ] Migração Alembic `0007` executada com sucesso (tabela `research_step_results`, `title` em `sa.Text`, unificação de enums e backfill)
- [ ] Suíte de testes da Feature 001 adaptada ao novo contrato e 100% passando
- [ ] Testes de unidade e integração do módulo `app/investigation/` implementados e verdes
- [ ] Teste E2E de disparo assíncrono e paralelismo das 4 personas aprovado
- [ ] Auditoria Reversa (`/reversa-audit` e `/reversa-quality`) sem inconformidades

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-12 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-10-13 | Delta reconciliado com esclarecimentos Q1–Q10; plano futuro separado do estado de coding e dos gates abertos | reversa-plan |
| 2026-10-14 | Sincronização com decisões Q14–Q16: extinção de `/approve`, aprovação implícita no `/investigate`, revisão única no PATCH com nova busca SERP Jina e início automático da investigação, bloqueio 409 de 2ª revisão, discriminação 500/502/503 e novas decisões D-21 a D-24 com alinhamento de D-12 | reversa-plan |
