# Roadmap: Convergência do pipeline

> Feature: `005-convergencia-pipeline`; sprint documental PLAN-005-A.
> Status: proposta técnica reconciliada, não aprovada. Produto não implementado.
> Autoridade: `requirements.md` desta pasta e `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md`; decisões aprovadas preservadas. Premissas operacionais em `questions.md` não são respostas humanas.

## 1. Delta e fronteiras

Convergir execução em `InvestigationService.run_investigation` (`app/investigation/service.py:157`), reutilizando workers tool-calling, armazenamento individual e auditor modular. `run_research` (`app/services/research.py:124`) passa a adaptador desse ciclo, preservando assinatura, eventos, dependências entre pontos e callbacks. Não manter dois motores com regras duplicadas. Reutilizar `ready_point_batches` (`app/services/research.py:79`) no ciclo modular para preservar dependências/`is_parallelizable` do legado; dentro de cada lote executar quatro personas concorrentes por ponto. Não reconstruir frontend, criar framework ou trocar modelo/provedor.

Observed: legado chama `_write_report` após seus lotes (`research.py:137-144`); modular só transita para `WRITE` (`investigation/service.py:362-385`). Chamar Writer no modular é mudança futura, não integração existente. Referências de código abaixo descrevem disco atual; verbos de implementação descrevem proposta.

## 2. Princípios aplicados

| Princípio (`.reversa/principles.md`) | Aplicação proposta / tensão |
|---|---|
| I, linhas 9-12: citação verbatim | Preservar `Evidence` e validação de trechos; URL conhecida isolada não prova afirmação. Relatório limitado declara ausência, não fabrica fatos. |
| II, linhas 16-19: privacidade | Fonte e operador delimitados como dados não confiáveis; sanitizar saídas antes da persistência, erros/eventos sem corpos, segredos, prompts ou raciocínio privado. HTML limpo não neutraliza prompt injection sozinho. |
| III, linhas 23-26: degradação e limites | Quarta reprovação encerra busca e permite Writer após todos conclusivos. Exemplos antigos de fallback/`blocked` não autorizam falso sucesso Jina; adendo vigente exige `AUDIT_CAVEAT`. Recuperação upstream permanece pendente. |
| IV, linhas 30-33: concorrência/idempotência | Emenda 002 mantém quatro personas concorrentes sem semáforo legado; sessões curtas por gravação, rede fora de transação, append-only e CAS. Não impor `Semaphore(20)` legado ao worker modular. |

Sem conflito normativo novo identificado; implementação e provas ainda pendentes. Falha técnica não pode ser transformada em quarta reprovação para cumprir degradação.

## 3. Decisões técnicas (dez decisões)

- **DT-501 🟡 — coleta.** Em `JinaToolAdapter._single_attempt` (`app/investigation/tools.py:158-190`), enviar explicitamente `{"q": query, "num": 10}`. Escolha técnica fechada: `num`, alias `count` não será enviado em paralelo. Search existente permanece transporte; Reader não é compulsório. Retornar itens estruturados com consulta, título, URL e corpo completo; `description`/`snippet` não substituem corpo. Dez corpos legíveis por toolcall, sem cortes silenciosos. Remover fallback DDG de sucesso investigativo (`tools.py:177-183`), sem afetar contrato SERP do Scout. Verificação de runtime Jina não executada.
- **DT-502 🟡 — autonomia limitada.** Evoluir `PersonaWorker._run` (`app/investigation/worker.py:339-480`): primeira query obrigatoriamente formulada pelo modelo; rejeitar final antes da primeira busca. Até três queries distintas por persona/ponto/rodada; chave de deduplicação `query.strip()` com igualdade exata, sem normalização semântica destrutiva. Duplicata reutiliza resultado em memória e não busca nem gasta orçamento. Limites existentes de turnos/reparos evitam loop de duplicatas; retries de transporte permanecem internos. Parada antecipada após aprendizado válido é normal. Legado **já** tem teto três (`pipeline/worker.py:89-92`), mas primeira query é montada pelo código (`:93-97`) e contexto é cortado (`:128-139`); não alegar ausência do teto.
- **DT-503 🟢 norma / 🟡 desenho — resultado e barreira.** Persistir individualmente as quatro personas reais `historian`, `skeptic`, `pragmatist`, `futurist` (`app/investigation/prompts.py`, `PERSONA_NAMES`). Sucesso requer análise estruturada não vazia após strip, aprendizado e atribuição; `used_urls` deve ser subconjunto de URLs com corpos efetivamente entregues/lidos, não links recursivamente encontrados no JSON. Erro não é análise. Barreira no banco exige exatamente as quatro personas distintas válidas no mesmo ponto e rodada. `save_step_result` atual não oferece essa garantia (`storage.py:66-78`).
- **DT-504 🟢 norma / 🟡 desenho — merge e auditoria.** Merge determinístico estruturado, sem LLM adicional: cópia integral das quatro análises em ordem `PERSONA_NAMES`, IDs de origem, fontes, contradições e lacunas por persona. Não suprimir divergências nem criar fatos. Commit do merge precede chamada ao auditor. `AuditService.get_point_evidence` e `audit_point` passam a consumir merge identificado e rodada, nunca todas as linhas históricas do ponto.
- **DT-505 🟢 norma / 🟡 desenho — teto.** Quatro avaliações factuais totais, inicial mais três retries. Quarta reprovação produz `AUDIT_CAVEAT`; sem quinta pesquisa. Numerar rodada nova somente após reprovação válida da anterior; infraestrutura inconclusiva não incrementa tentativa nem cria rodada. Remover incremento por falha de persona (`storage.py:58-64`) e teto forçado por falhas (`service.py:330-343`). Persistência de veredito vincula rodada/merge e ordinal no mesmo commit. Aprovação exige guardrails da 003, não simples presença de quatro textos.
- **DT-506 🟢 norma / 🟡 desenho — Writer compartilhado.** Após consulta nova de todos os pontos não vazios em `AUDIT_APPROVED`/`AUDIT_CAVEAT`, transição CAS para `WRITE`, fechar sessão, chamar `_write_report` (`app/services/pipeline/writer.py:24`), persistir `Report`/`DONE` e só depois callback existente. Retomada em `WRITE` sem Report deve tentar escrita, não retornar por falta de workers pendentes (`service.py:217-218`). `DONE` com Report é no-op; falha Writer explícita preserva material para retomada, não sucesso fictício. Unicidade `reports.research_id` (`domain_models.py:103-110`) e CAS impedem dois relatórios; colisão relê registro, não sobrescreve.
- **DT-507 🟢 norma / 🟡 desenho — relatório honesto.** Alterar `_write_report` e `validate_report_quality` (`writer.py:14-76`). Para pontos sem conteúdo aproveitável, seção curta declarando limitação, sem mínimo artificial, links ou Evidence inventados. Para relatório misto, separar limitações por ponto e fatos sustentados. Caminho zero evidência pode produzir template determinístico por título/estado seguro, sem chamada criativa necessária. Não confundir alvo de 400 palavras do prompt (`:35`) com mínimo validado de 200 (`:17`). Corrigir negrito tratado como lista (`:60`), sem liberar afirmação factual em prosa, lista, tabela ou negrito. Proposta não factual não precisa fonte; rótulo ou URL conhecido não cria isenção geral.
- **DT-508 🟢 preservada — HTTP.** `POST /briefings` 201 e `PATCH /briefings/{research_id}` 200 síncronos; revisão única `{"note": ...}` autoaprova e agenda investigação; repetição 409. `POST /briefings/{research_id}/investigate` 202 em background continua alternativa exclusiva. Scout mantém SERP-only, sem dez corpos. Contratos completos na seção 5.
- **DT-509 🟡 premissa — upstream/contexto.** Menos dez corpos, página inacessível ou contexto insuficiente: falha segura explícita, preservar dados válidos, não truncar nem promover parcial a sucesso. Não adotar recuperação/buscas novas indefinidas. `questions.md#q-501` permanece pendente de política.
- **DT-510 🟡 premissa — falha individual.** Persistir erro seguro quando possível, preservar demais resultados, encerrar invocação daquele ponto sem merge/auditoria. Não contar reprovação nem concluir ponto; Writer aguarda todos conclusivos. Crash não garante persistência; retomada limitada à rodada identificada e tarefas realmente ausentes, sem recuperação fatal automática indefinida (`questions.md#q-502`).

## 4. Modelo mínimo escolhido para data-delta

Tudo nesta seção é **proposto**, inexistente no schema observado (`app/models/domain_models.py:44-89`). Não fazer backfill `round=1`: linhas históricas podem misturar retries e falhas, promovendo falsa barreira.

1. Acrescentar `research_points.investigation_round` INTEGER nullable, sem default para históricos; novas execuções recebem 1 explicitamente. Acrescentar `research_step_results.round` INTEGER nullable, sem default histórico; novas linhas exigem rodada positiva na fronteira de gravação. Constraints positivas quando não nulo. Histórico NULL permanece consultável, inelegível para barreira/auditoria nova.
2. Preservar campos reais `research_step_results.step_id`, `worker`, `result`, `used_urls`, `read_urls`, `status`; `result` Text passa a JSON estruturado serializado com análise, aprendizados, citações `{claim, exact_quote, source_url, source_title}`, contradições e lacunas. Não converter histórico textual automaticamente nem persistir corpos completos ou prompts. Campos vazios/nulos/falha são inválidos para barreira. Schema Pydantic real em `app/investigation/schemas.py` deve evoluir e sanitizar todos os campos.
3. Unicidade proposta `(research_id, step_id, round, worker)` para resultados novos. NULL histórico não entra na barreira. Uma linha terminal por persona/rodada, imutável; retries técnicos precedem gravação. Reenvio idêntico relê linha; payload divergente é conflito, não sobrescrita. Erro fatal gravado não se converte em sucesso na mesma rodada por recuperação tácita.
4. Escolha fechada: tabela nova **proposta** `investigation_merges` com `id` UUID PK, `research_id` FK, `step_id` FK, `round` positivo e `content` JSON não vazio, `created_at`; UNIQUE `(research_id, step_id, round)`. `content` guarda quatro IDs de resultado, cópias estruturadas atribuídas e contradições/lacunas preservadas. Banco/serviço verificam associação research/ponto. Não usar pseudo-persona merge em `research_step_results`, pois confundiria barreira e API histórica.
5. `ResearchPoint.audit` e `AuditTrail.details` JSON existentes guardam `merge_id`, `round`, ordinal e veredito sanitizado. CAS sobre ponto/rodada/estado antes de registrar merge/veredito evita corrida; leitura da barreira e insert único de merge numa transação curta, nunca rede dentro dela. Auditor só recebe snapshot committed; revalidar rodada na escrita do veredito e descartar resposta obsoleta com erro seguro.
6. Preservar `Evidence` como projeção de citações verificadas para Writer e compatibilidade das consultas. Reutilizar `_quote_supported` (`pipeline/worker.py:26-38`) antes da projeção; validar sobre corpo integral limpo em memória. Não remover `version_id_col` nem `uq_evidence_source` (`domain_models.py:78-89`). Mesma persona/URL em rodada nova mantém primeiro Evidence imutável; novos aprendizados/citações dessa URL ficam integralmente no resultado/merge. Writer passa a montar bundle das citações verificadas dos merges concluídos, junto do Evidence legado autorizado, sem perder aprendizado por essa unicidade. Material de rodada pendente/histórico sem proveniência não vira fato automaticamente. Verbatim e URL são guardrails necessários, não prova semântica completa de entailment.
7. Históricos `DONE`/Report não são reprocessados nem reclassificados. Pesquisa ativa sem rodada identificável permanece retida com diagnóstico explícito; não inferir rodada de timestamps/attempt_count. Migração não reinicia pesquisa. Replay manual futuro exigirá política, fora deste sprint.

Head local observado estaticamente: `0007`, descendente de `0006`; migrations 0001–0007 criam tabelas do domínio inclusive `research_step_results`. Não fixar próxima revisão: coding consulta grafo novamente. Upgrade/downgrade em PostgreSQL efêmero deverá provar instalação limpa e dados históricos NULL preservados; `create_all()` SQLite não prova Alembic. Downgrade remove somente dados/estruturas novas sob ciência de perda dessas estruturas no ambiente de teste; nunca executado aqui.

## 5. Contratos reais e impactos

`app/main.py:95-100` inclui routers sem prefixo adicional. `app/briefing/router.py:53` e `app/investigation/router.py:24` não têm prefixo; legado `app/routers/research.py:21` tem `/api`.

| Método e rota externa | Dono observado | Preservar / delta |
|---|---|---|
| POST `/briefings` | `briefing/router.py:141`, `create_briefing`; `briefing/service.py`, `generate_briefing` | 201 com briefing pronto; Scout SERP-only. |
| PATCH `/briefings/{research_id}` | `briefing/router.py:232-315`, `patch_briefing`; `revise_briefing_with_feedback` | 200 após nova SERP e revisão única; background só investigação. Payload note; 409 repetição/CAS, 422 inválido, erros 500/502/503 existentes preservados, sem escrita parcial em conflito. |
| POST `/briefings/{research_id}/investigate` | `investigation/router.py:29-116`, `investigate_briefing` | 202; reserva atômica e um agendamento; 404/409 existentes. Ciclo converge até Report/DONE. |
| POST `/api/research` | `routers/research.py:134-197`, `create_research` | 201 legado; não renomear para rota de briefing inexistente. |
| POST `/api/research/{research_id}/resume` | `routers/research.py:414-452`, `resume` | Mantém contrato; `schedule` chama `run_research`, futuro adaptador do ciclo modular. Não promover histórico sem rodada. |
| GET `/api/reports/{identifier}` | `routers/research.py:387-394`, `report` | Consulta mesmo Report, sem novo frontend. |
| POST `/api/reports/{identifier}/retry-callback` | `routers/research.py:396`, `retry_callback` | Preservar segurança/callback após Report; falha callback não desfaz DONE. |

Rotas legadas de edição/aprovação ainda têm decorators em `routers/research.py:257/316`; existência não significa contrato novo autorizado. Não introduzir approve modular, polling ou novas rotas; preservar bloqueios/precedência documental existentes e cobri-los com regressão. Não fazer refactor frontend para resolver convergência interna.

## 6. Matriz completa de donos e provas futuras

Paths abaixo relativos a `app/`; símbolos reais indicados, novos campos/tabela marcados na seção 4. Nenhuma prova de runtime executada neste sprint.

| ID | Donos reais / delta | Prova a derivar para ações |
|---|---|---|
| RF-501 | `investigation/tools.py`, `JinaToolAdapter._single_attempt`, `_parse_body`; `services/search.py`, `_SafeHTMLTextExtractor` | MockTransport confirma num=10, dez corpos com marcador final além de 100000 caracteres, remoção header/footer/nav/script/style/anúncios sem corte informativo. |
| RF-502 | `investigation/worker.py`, `PersonaWorker._run`; `investigation/prompts.py` | Primeira query LLM, final sem busca rejeitado, duplicata não busca, até três distintas, parada cedo. |
| RF-503 | `investigation/storage.py`, `save_step_result`; `investigation/schemas.py`; `models/domain_models.py` | Quatro linhas válidas committed; branco/falha/URL não lida/histórico NULL não completam barreira. |
| RF-504 | `investigation/service.py`, `run_investigation`; `investigation/storage.py`; `audit/service.py`, `audit_point/get_point_evidence` | Banco 3/4, duplicata e rodada errada não liberam; merge committed antes de qualquer chamada auditor; conteúdo integral atribuível. |
| RF-505 | `audit/domain.py`, `next_audit_state`; `audit/service.py`; `investigation/service.py` | Exatamente quatro reprovações, nenhuma quinta coleta; falha técnica não conta; Writer aguarda todos conclusivos. |
| RF-506 | `services/pipeline/writer.py`, `_write_report/validate_report_quality` | Zero Evidence e todos ressalvados persistem Report curto por ponto e DONE, sem fonte inventada; relatório misto não perde fatos sustentados. |
| RF-507 | `services/pipeline/writer.py`, `_write_report` | Proposta não factual em negrito aceita; fatos sem fonte em negrito/prosa/lista/tabela rejeitados; sem isenção geral por rótulo. |
| RF-508 | `services/research.py`, `run_research`; `investigation/service.py`, `run_investigation`; `services/webhook.py`, `dispatch_callback` | EntryPoints HTTP reais e retomada WRITE resultam exatamente um Report/DONE; concorrência/CAS e callback falho preservam integridade. |
| RF-509 | `briefing/router.py`, `create_briefing/patch_briefing`; `briefing/service.py`; `investigation/router.py` | POST201/PATCH200 concluídos; revisão repetida409; investigate202; Scout nunca recebe corpos integrais. |
| RN-501 | mesmos donos RF-501 | Dez corpos, atribuição consulta/URL/título, sem snippet substituto nem fallback falso. |
| RN-502 | mesmos donos RF-502 | Orçamento distinto por persona/ponto/rodada, retries transporte separados. |
| RN-503 | `investigation/worker.py`, `_run`; `schemas.py`; `storage.py` | Análise estruturada não vazia, used_urls subset read_urls reais; preservação do aprendizado. |
| RN-504 | `investigation/storage.py`, `save_step_result`; `service.py` | Barreira no banco, quatro personas distintas válidas da rodada. |
| RN-505 | `investigation/storage.py`; `audit/service.py` | Merge persistido referencia quatro IDs antes audit; contradições/lacunas mantidas. |
| RN-506 | `audit/domain.py`, `next_audit_state`; `audit/service.py`; `investigation/service.py` | Inicial+3 retries, quarta reprovação caveat; falha persona não vira reprovação. |
| RN-507 | `services/pipeline/writer.py`, `_write_report/validate_report_quality` | Relatório honesto por ponto, inclusive zero Evidence. |
| RN-508 | `services/pipeline/writer.py`, `_write_report` | Formato Markdown não libera fatos sem fonte nem proíbe proposta não factual. |
| RN-509 | mesmos donos RF-509; `briefing/serp_client.py`, `JinaSerpClient` | Síncrono SERP-only e uma decisão, sem approve modular/polling. |
| RN-510 | `tools/outbound.py`, `validate_public_url/PinnedResolver`; `services/llm.py`, `apply_output_guardrail`; `investigation/worker.py`, `_sanitize_error`; `audit/service.py` | SSRF/redirects/DNS privados bloqueados, fontes não confiáveis isoladas, segredos/prompts ausentes em persistência e eventos. |

## 7. Sequência fechada para ações

1. **C16:** testes negativos de tool/worker e coleta integral; estruturar itens Jina e parser stdlib sem cortes; num=10 apenas investigação; orçamento/deduplicação/saída estruturada e fronteiras de segurança.
2. **C17:** migration após novo check de head; modelo nullable histórico, rodada explícita, unicidade e merge; testes PostgreSQL efêmero upgrade/downgrade e barreira concorrente; Evidence/proveniência verbatim preservados.
3. **C18:** ligar auditor ao merge, retirar contagem por falha técnica, CAS/ordinal; compartilhar ciclo modular com adaptador legado, lotes de dependências e retomada WRITE. Testar quatro reprovações e todos conclusivos antes Writer.
4. **C19:** Writer limitado/misto e Markdown, Report único/DONE, callback, regressões dos entrypoints reais e briefing SERP-only. Fixtures controladas, não provedor live.

## 8. Riscos, premissas e gate real

Jina pode retornar menos dez ou não garantir integralidade; tamanho do contexto pode inviabilizar rodada. Falhar explicitamente, não ocultar corte nem aprovar parcial (Q-501). Falha fatal individual/crash não possui política aprovada de recuperação (Q-502). Relatório limitado vale para pontos **conclusivos**, não contorna barreira incompleta. Sanitização HTML deve remover também anúncios e ruído identificado por markup/atributos sem apagar conteúdo substantivo; limpeza semântica arbitrária pelo LLM não substitui parser.

Invalidam-se autochecks/aprovações e alegações de buscas zero dos rascunhos anteriores; nomes citados como correção não constituem ausência textual. DT-501..510 são dez, não nove. Histórico preservado nesta nota, sem logs editoriais repetidos. `investigation.md` invalida conclusões técnicas falsas anteriores com fontes.

Estado real: somente roadmap/questions/investigation reconciliados. Data-delta, ações, onboarding e contratos detalhados ainda precisam ser produzidos em etapa autorizada; auditor independente após ações. Critério de entrada em coding: artefatos coerentes e revisão independente, não este checklist. Critério de entrega futura: todos RF/RN com provas determinísticas, migration efêmera, entrypoints até Report/DONE, guardrails negativos e regressões. Nenhum gate aprovado, teste runtime, chamada com credencial ou deploy neste sprint.
