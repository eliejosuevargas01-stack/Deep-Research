# PRD: Deep Research

> Selo 🟡 PLANEJADO. Documento gerado a partir de brief, ideation + personas; revisado para os invariantes de dados v2.

**Versão:** 2.0
**Data:** 2026-10-27
**Autor:** reversa-drafter
**Revisão v2:** reversa-spec-sdd (invariantes de paridade, zero truncamento, modo de execução, agregação por ponto e acúmulo de retries)
**Status:** vigente

---

## 1. Visão geral

🟡 Pipeline simples de pesquisa profunda na internet composto de 4 etapas, cada uma com um endpoint próprio, em Python (FastAPI), monolito modular, cada endpoint funciona por separado.

🟡 Valor entregue: 🟡 pesquisa profunda auditada com rastreabilidade a custo baixo — o usuário passa de dias manuais a um dossiê completo em menos de 10 minutos, com cada ponto aprovado/reprovado e fontes canônicas marcadas.

---

## 2. Problema

🟡 Pesquisas manuais levam dias, fontes não auditadas, relatório sem rastreabilidade; o custo atual é alto.

### Quem sente

🟡 Analistas, redatores, devs e times de research, sempre que precisam produzir uma investigação profunda sob demanda.

🟡 **Analista de Research**: sente no momento da consulta ao briefing de campanha ou início do planejamento estratégico, quando surge a necessidade de embasar uma decisão com dados de terceiros.

🟡 **Redator/Dev integrador**: sente ao desenvolver um produto que depende de pesquisa (relatórios corporativos, blog, conteúdo institucional) ou ao precisar consultar o dossier gerado.

---

## 3. Personas-alvo

> 🟡 Referência completa em [`personas.md`](./personas.md). Resumo das personas de usuário:

- 🟡 **Analista de Research**: profissional de pesquisa de mercado, nível técnico intermediário (análise de dados e triangulação de fontes; conhece métricas de qualidade, mas não escreve código). Dor principal: pesquisas manuais levam dias, fontes não são auditadas e o relatório final perde a rastreabilidade das fontes canônicas. Objetivo: dossier auditado com fontes canônicas, N pontos aprovados, em menos de 10 minutos.
- 🟡 **Redator/Dev integrador**: profissional avançado em integração de APIs e automação; escreve scripts Python e configura variáveis de ambiente. Dor principal: ferramentas existentes (Perplexity, GPT Deep Research) são caixas pretas sem auditoria por ponto nem rastreabilidade de fontes. Objetivo: integrar os 4 endpoints como serviço reusável e consumir o dossier final via webhook ou banco.

### Personas do sistema (7)

🟡 planejador, historiador, visionario, cetico, futurista, auditor, redator final. Número e identidade definidos por variável de ambiente; sem fallback hardcoded.

---

## 4. Métricas de sucesso

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Dossier com fontes canônicas | 🟡 % de pontos com URLs de origem rastreadas | 🟡 100% | 🟡 21/10/2026 |
| 🟡 N pontos aprovados | 🟡 quantidade | 🟡 todos os N pontos definidos por variável de ambiente (padrão 5) com status `aprovado` | 🟡 21/10/2026 |
| 🟡 Tempo < 10 min | 🟡 minutos | 🟡 < 10 (ciclo completo: plano → busca → auditoria → redação) | 🟡 21/10/2026 |
| 🟡 Paridade Jina direta ↔ proxy | 🟡 % de campos idênticos (path, query, headers, body, status) | 🟡 100% | 🟡 31/10/2026 |
| 🟡 Zero truncamento entre estágios | 🟡 nº de campos truncados em qualquer handoff | 🟡 0 | 🟡 31/10/2026 |
| 🟡 Histórico de retries preservado | 🟡 % de rodadas de coleta presentes no contexto de audit e writer | 🟡 100% | 🟡 31/10/2026 |

---

## 5. Escopo (in)

- 🟡 Endpoint `/api/v1/plan` (Etapa 1 — Plano de investigação).
- 🟡 Endpoint `/api/v1/search` (Etapa 2 — Busca).
- 🟡 Endpoint `/api/v1/audit` (Etapa 3 — Auditoria).
- 🟡 Endpoint `/api/v1/writer` (Etapa 4 — Redação).
- 🟡 Endpoints administrativos extras permitidos para cadastrar pesquisa e carregar/salvar configuração (chaves, base URLs, preferências).
- 🟡 Persistência SQLite permanente (sobrevive a redeploy sem perder dados).
- 🟡 Tabela de credenciais criptografada com override por variável de ambiente do container.
- 🟡 Base URL de Jina e de LLM configuráveis e persistidas — incluindo a escolha entre Jina direta e Cloudflare Proxy Worker.

---

## 6. Não-objetivos (out)

- 🟡 Não fazer tudo de uma vez só (cada endpoint funciona por separado).
- 🟡 Não complicar a pesquisa.
- 🟡 Não entregar resultado mediano.
- 🟡 Não ter mais de 4 endpoints principais.
- 🟡 Compliance: nenhuma exigência regulatória no MVP (resposta da entrevista).

---

## 7. Invariantes de dados e execução (inegociáveis, v2)

> 🟡 Estas cinco regras têm precedência sobre qualquer decisão anterior deste PRD, das specs de endpoint e dos adendos de confiabilidade. Em caso de conflito, o invariante vence e a decisão anterior deve ser registrada como superada.

### I-1. Paridade total no Proxy Jina (Cloudflare Worker)

- 🟡 `plan` e `search` usam a mesma tool de busca (`app/tools/jina_client.py`), que fala com a Jina **direta** (`s.jina.ai` / `r.jina.ai`) ou **via Cloudflare Proxy Worker**.
- 🟡 O Worker é um **túnel transparente**: recebe, repassa exatamente, recebe a resposta da Jina e devolve exatamente.
- 🟡 Proibido no Worker: re-encode ou normalização de path, allowlist de headers, síntese de status, headers internos na resposta, re-serialização de corpo, deadline que corte stream.
- 🟡 O contrato de requisição e de resposta deve ser **100% idêntico** nas duas rotas, de modo que a tool funcione em `plan` e `search` sem erro de parsing ou de schema. Contrato normativo: [`sdd/proxy-jina-paridade-total.md`](./sdd/proxy-jina-paridade-total.md).

### I-2. Proibição estrita de truncamento (zero data loss)

- 🟡 Nenhuma informação coletada pode ser cortada, resumida indevidamente ou silenciosamente omitida no tráfego entre estágios.
- 🟡 São vedados: `text[:N]`, `slice`, `max_length` de conteúdo coletado, cap de tokens aplicado por corte, "resumo automático" que substitui o original.
- 🟡 Abrangência explícita: (a) resposta da tool de busca; (b) entrada de `plan` e `search`; (c) entrada de `audit` e `writer`.
- 🟡 **Volatilidade do bruto (v3)**: o texto integral das páginas devolvido pela Jina vive **apenas em RAM** durante a rodada. É proibido persistir `body`, `trechos`/`chunks` ou offsets/hashes de corpo em `conteudo_coletado`. O único artefato que atravessa estágios é o **resumo do especialista** (`analise`), acompanhado de `urls_utilizadas` e `urls_lidas_nao_utilizadas`. Auditor e redator nunca recebem o bruto.
- 🟡 Se o volume exceder o limite do provedor de LLM, o comportamento obrigatório é **insuficiência explícita** (erro/diagnóstico), nunca corte oculto e nunca aprovação parcial disfarçada.
- 🟡 Corolário: limites de **validação de entrada** (ex.: tamanho do briefing) não podem rejeitar material legítimo de pesquisa; quando existirem, devem ser justificados e documentados, e nunca operar por corte silencioso.

### I-3. Controle de execução via HTTP (paralelo vs sequencial)

- 🟡 O endpoint HTTP de entrada aceita o parâmetro explícito `execution_mode` com os valores `"parallel"` (default) e `"sequential"`.
- 🟡 O parâmetro governa o processamento **dos pontos de pesquisa** (não das personas dentro de um ponto).
- 🟡 Valor inválido é rejeitado com `422`; sem fallback silencioso.
- 🟡 `sequential` preserva ordem determinística (`ponto_n` crescente) e nunca abre mais de um ponto em voo.
- 🟡 `parallel` mantém isolamento de sessão por ponto (uma `AsyncSession` por corrotina); compartilhar sessão entre pontos concorrentes é proibido.

### I-4. Agregação das 4 personas por ponto antes do audit

- 🟡 Cada ponto é processado por 4 personas/workers (`historiador`, `visionario`, `cetico`, `futurista`).
- 🟡 As respostas das 4 personas de um ponto são **consolidadas em um único pacote por ponto** antes de ir para o `audit`.
- 🟡 O pacote contém, por persona: **resumo integral** (`analise`), `urls_utilizadas` (`urls_fonte`), `urls_lidas_nao_utilizadas` e `lacunas`. Conclusões estruturadas são opcionais e, quando existirem, citam URLs — nunca chunks.
- 🟡 O `audit` recebe essa visão unificada do ponto e responde às **12 perguntas de validação** sobre ela — nunca sobre uma persona isolada.

### I-5. Acúmulo integral do histórico em retries (sem sobrescrita)

- 🟡 Quando o `audit` reprova um ponto e dispara novo `search`, os dados das tentativas anteriores **não** podem ser descartados, sobrescritos ou substituídos.
- 🟡 Modelo obrigatório: histórico **append-only** por ponto. Cada passagem cria uma nova rodada de coleta (`rodada`), preservando todas as anteriores.
- 🟡 O contexto entregue a `audit` (inclusive em validações subsequentes), a `writer` e a `plan` (em reavaliação) deve conter **a soma acumulada e integral de todas as coletas daquele ponto** — nunca apenas a última.
- 🟡 Exemplo normativo: ponto com tentativa inicial + 3 retries ⇒ 4 rodadas ⇒ as 4 rodadas compõem o contexto, com seus resumos e o catálogo de URLs (utilizadas / lidas não utilizadas).
- 🟡 Compatibilidade com o controle de staleness: a decisão de aprovação continua exigindo evidência válida da rodada corrente (fence de concorrência), mas a **presença** das rodadas anteriores no contexto é obrigatória. Ver [`sdd/endpoint-auditoria-de-qualidade.md`](./sdd/endpoint-auditoria-de-qualidade.md) §9-A.
- 🟡 Esta regra **supera** o adendo v5 (Audit), que determinava uso exclusivo da coleta mais recente como corpus de avaliação.

### I-6. Streaming em tempo real sem perda (SSE)

- 🟡 O raciocínio e a resposta de cada agente devem chegar ao frontend **enquanto são gerados**, não apenas ao fim do estágio.
- 🟡 O canal SSE (`GET /api/v1/pipeline/{id}/stream`) entrega `agent.delta` por token/delta do provedor, coalescidos por agente sem reordenação, perda ou truncamento (I-2).
- 🟡 A publicação é escopada por `(id_pesquisa, stage, agent, ponto_id)`; fora do pipeline é no-op, impedindo vazamento entre pesquisas.
- 🟡 Eventos de snapshot (`pipeline.status`, `point.status`, `search.progress`, `audit.result`, `writer.progress`, `report.final`) permanecem como marcos; o delta é o conteúdo ao vivo. Ver [`sdd/sse-streaming-tempo-real.md`](./sdd/sse-streaming-tempo-real.md).

---

## 8. Requisitos funcionais

### Etapa 1 — Plano de investigação

- 🟡 **RF-001**: `POST /api/v1/plan` recebe tema/entrada → salva no banco → LLM + tool Jina SERP (só lê resultados SERP, nunca abre páginas) → LLM formula query e escolhe N pontos mais relevantes → Avaliador Semântico audita fidelidade de público/escopo/tempo e cobertura exaustiva dos $N(N-1)/2$ pares canônicos de sobreposição de eixos (`sobreposicao_eixos`, ou `[]` quando `N=1`) → parser → persiste pontos no banco (`tema`, `id_pesquisa`, `ponto_id`, `ponto_n`).
- 🟡 **RF-002**: N por pesquisa definido em variável de ambiente (padrão 5, sem fallback hardcoded).
- 🟡 **RF-002-A** (v2): a entrada do `plan` não sofre truncamento. Tema/briefing é aceito integralmente; nenhum limite de caracteres pode cortar ou rejeitar material legítimo de pesquisa.
- 🟡 **RF-002-B** (v2): em reavaliação de plano, o contexto inclui o histórico acumulado das coletas já realizadas para os pontos existentes (I-5), sem substituir rodadas anteriores.
- 🟡 **RF-002-C** (v2): `POST /api/v1/plan` aceita `execution_mode` e o propaga ao runner do pipeline quando `async_execute=true`.

### Etapa 2 — Busca

- 🟡 **RF-003**: `POST /api/v1/search` recebe `id_pesquisa` do banco → processa todos os pontos conforme `execution_mode` (paralelo por padrão, sequencial sob demanda) por LLM leve → aplica personas (`historiador`, `visionario`, `cetico`, `futurista`) → memória apenas para tool call.
- 🟡 **RF-004**: Tool Jina SERP (`s.jina.ai`) + Reader (`r.jina.ai`) → filtro de URLs já lidas por `id_pesquisa` → parser concatena resposta inteira (sem cortar) em 1 item com links → persiste URLs em background → modelo decide mais query ou devolve resposta → parser (`tema`, `id_pesquisa`, `ponto`, `ponto_id`, `conteudo_coletado`, `urls_lidas`, `urls_fonte`) → banco.
- 🟡 **RF-004-A** (v2): a resposta da tool de busca não é truncada em nenhuma camada, e a rota (direta ou proxy) não altera o contrato observável (I-1, I-2).
- 🟡 **RF-004-B** (v2): cada ponto produz um pacote consolidado das 4 personas (I-4).
- 🟡 **RF-004-C** (v2): nova passagem de `search` sobre um ponto **acrescenta** rodada; nunca sobrescreve as anteriores (I-5).

- 🟡 **RF-004-D** (v3): o texto bruto das páginas da Jina é descartado ao fim de cada persona; persistem apenas `resumo` (`analise`), `urls_utilizadas` e `urls_lidas_nao_utilizadas` no catálogo do ponto.

### Etapa 3 — Auditoria

- 🟡 **RF-005**: `POST /api/v1/audit` recebe `id_pesquisa` do banco → LLM forte responde 12 perguntas de qualidade sobre o conteúdo coletado → parser (`id_pesquisa`, `tema`, `id_ponto`, `ponto`, `aprovado|reprovado`, `pontos_fracos`) → banco.
- 🟡 **RF-005-A** (v2): a entrada do `audit` é a soma acumulada dos **resumos** das 4 personas de todas as rodadas do ponto (I-4, I-5), mais o catálogo de URLs com uso; nenhuma rodada é omitida e nenhum texto bruto é enviado.
- 🟡 **RF-005-C** (v3): a validação do auditor é sobre o conteúdo dos resumos e o catálogo de URLs; checagem de `body`/`hash`/offsets de trechos é inexistente porque o bruto não é persistido.
- 🟡 **RF-005-B** (v2): a entrada do `audit` não é truncada. Volume acima do limite do provedor gera insuficiência explícita, nunca corte.

### Etapa 4 — Redação

- 🟡 **RF-006**: `POST /api/v1/writer` recebe `id_pesquisa` do banco (somente quando todos os pontos finalizados) → concatena tudo → LLM forte gera dossier completo com fontes canônicas marcadas → parser → banco → POST para webhook de callback.
- 🟡 **RF-006-A** (v3): o contexto do `writer` contém os resumos integrais de todas as rodadas de cada ponto, mais as listas de URLs `utilizadas` e `lidas_nao_utilizadas`; nenhuma rodada anterior é descartada e nenhum texto bruto é enviado.
- 🟡 **RF-006-B** (v2): a entrada do `writer` não é truncada por limite artificial.

### Administração e configuração

- 🟡 **RF-007**: Endpoints administrativos extras para cadastrar pesquisa e carregar/salvar configuração (chaves, base URLs, preferências).
- 🟡 **RF-008**: Toda credencial (chave, base URL, preferência) persistida em tabela criptografada, com override por variável de ambiente do container.
- 🟡 **RF-008-A** (v2): a base URL de Jina é única para as duas rotas (direta ou proxy); a troca de rota não exige mudança de código nem flag adicional na tool.

---

## 9. Modelo de dados (tabelas)

- 🟡 **`pesquisa`** — usada pelo endpoint 1 (cadastro) e pelo writer (relatório final). Campos mínimos: 🟡 `id_pesquisa`, `tema`.
- 🟡 **`pontos`** — usada pelo plan (1 item por ponto) e pelo auditor (status). Campos: 🟡 `tema`, `id_pesquisa`, `ponto_id`, `ponto_n`, `ponto`, `aprovado|reprovado`, `pontos_fracos`, `tentativas`, `tentativas_auditoria`.
- 🟡 **`conteudo_coletado`** — usada pelo search, pelo auditor e pelo writer. Uma linha **por rodada** de coleta do ponto (append-only). Campos: 🟡 `tema`, `id_pesquisa`, `ponto`, `ponto_id`, `rodada`, `conteudo_coletado`, `urls_lidas`, `urls_fonte`, `metadados_coleta`.
- 🟡 **`metadados_coleta.resultados_personas`** — pacote consolidado das 4 personas do ponto (I-4), com `analise` (resumo acumulado), `urls_fonte`, `urls_lidas`, `lacunas`, `motivo_parada`, `sucesso`, `queries_executadas`.
- 🟡 **`metadados_coleta.fontes`** (v3) — catálogo de URLs do ponto acumulado entre rodadas: `url`, `status` (`read_ok`), `uso` (`utilizada` | `lida_nao_utilizada`), `titulo`, `data_fonte`. **Sem `body`, sem `body_hash`, sem `trechos`, sem offsets** — o bruto da Jina não é persistido (I-2 v3).
- 🟡 **`metadados_coleta.auditorias`** — histórico estruturado de pareceres por rodada (12 critérios, corte, contagem, percentual, decisão, tarefas).
- 🟡 **`credenciais`** (tabela criptografada) — 🟡 chave, base URL, preferência; override por variável de ambiente do container.

🟡 Regra de integridade: nenhuma operação de `search`, `audit` ou `writer` pode executar `UPDATE` que apague, resuma ou substitua o conteúdo de uma rodada anterior de `conteudo_coletado`. Somente inserção de nova rodada e atualização de status são permitidas.

---

## 10. Variáveis de ambiente

- 🟡 **N pontos por pesquisa** — padrão 5; sem fallback hardcoded (valor ausente exige configuração explícita).
- 🟡 **Personas do sistema** — número (7) e identidade (planejador, historiador, visionario, cetico, futurista, auditor, redator final); sem fallback hardcoded.
- 🟡 **Credenciais e base URLs** — override por variável de ambiente do container sobre a tabela criptografada (chaves, base URL de Jina, base URL de LLM, preferências).
- 🟡 **`JINA_BASE_URL` / `JINA_SEARCH_BASE_URL` / `JINA_READER_BASE_URL`** (v2) — determinam a rota: Jina direta ou Cloudflare Proxy Worker. A tool não distingue as rotas.
- 🟡 **`SEARCH_EXECUTION_MODE_DEFAULT`** (v2, opcional) — default do `execution_mode` quando o payload HTTP não envia o campo; ausente ⇒ `parallel`.
- 🟡 **`AUDIT_EVIDENCE_BUDGET_CHARS` / `AUDIT_JSON_BUDGET_CHARS`** (v2) — tetos de **insuficiência explícita** do audit; nunca produzem corte. Valores devem acomodar o histórico acumulado de rodadas.

---

## 11. Restrições (técnicas + não-funcionais)

| Tipo | Descrição |
|---|---|
| 🟡 Stack | 🟡 Python + FastAPI, monolito modular, exatamente 4 endpoints principais |
| 🟡 Prazo | 🟡 21 de outubro, 22h (horário de Brasília) |
| 🟡 Compliance | 🟡 Nenhuma exigência regulatória (LGPD ou outra) no MVP |
| 🟡 Orçamento | 🟡 [INDEFINIDO, validar com usuário] |
| 🟡 NFR — Retries | 🟡 1 tentativa inicial + 3 retries (histórico acumulado, nunca sobrescrito) |
| 🟡 NFR — Timeout | 🟡 600s por chamada |
| 🟡 NFR — LLM | 🟡 chamadas HTTP a modelos apenas OpenAI-compatible |
| 🟡 NFR — Jina | 🟡 Jina acessado via tool (SERP `s.jina.ai` + Reader `r.jina.ai`); base URL configurável e persistida, direta ou proxy |
| 🟡 NFR — Paridade de proxy | 🟡 Rota direta e rota proxy produzem contrato idêntico (I-1) |
| 🟡 NFR — Zero truncamento | 🟡 Nenhum corte de conteúdo coletado em nenhum handoff (I-2) |
| 🟡 NFR — Modo de execução | 🟡 `execution_mode` explícito no HTTP, sem fallback silencioso (I-3) |
| 🟡 NFR — Persistência | 🟡 SQLite permanente (sobrevive a redeploy sem perder dados) |
| 🟡 NFR — Config | 🟡 N e personas definidos exclusivamente por variável de ambiente, sem fallback hardcoded |
| 🟡 NFR — Personas | 🟡 7 personas do sistema: planejador, historiador, visionario, cetico, futurista, auditor, redator final |

---

## 12. Dependências externas

- 🟡 Jina SERP (`s.jina.ai`) + Jina Reader (`r.jina.ai`) — tool nas etapas plan e search.
- 🟡 Cloudflare Proxy Worker — rota alternativa opcional para a Jina, sob contrato de paridade total.
- 🟡 Modelos LLM OpenAI-compatible — LLM leve (busca em paralelo) e LLM forte (auditoria e redação); base URLs configuráveis e persistidas.
- 🟡 Webhook de callback — destino do POST do dossier final (writer).

---

## 13. Riscos

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 Custo de tokens (Jina SERP + LLM forte estoura orçamento viável) | 🟡 alto | 🟡 média | 🟡 limitar N pontos via variável de ambiente; monitorar consumo por endpoint |
| 🟡 Qualidade da persona (perda de coerência de tom e foco das 7 personas degrada output) | 🟡 alto | 🟡 média | 🟡 definir identidade via variável de ambiente; validar coerência antes da redação |
| 🟡 Complexidade do código (acoplamento entre os 4 endpoints gera bugs em produção) | 🟡 médio | 🟡 média | 🟡 manter monolito modular com endpoints isolados, cada um funcionando por separado |
| 🟡 Falhas em produção (dependência de Jina e LLM OpenAI-compatible) | 🟡 alto | 🟡 alta | 🟡 retries 1+3 e timeout 600s; credenciais com override por env do container |
| 🟡 Divergência de contrato entre Jina direta e proxy | 🟡 alto | 🟡 alta | 🟡 teste de contrato de paridade obrigatório (spec do proxy) |
| 🟡 Contexto acumulado de retries excede janela do LLM forte | 🟡 alto | 🟡 média | 🟡 insuficiência explícita + provisionamento de modelo com janela maior; nunca corte silencioso |
| 🟡 Orçamento não definido | 🟡 médio | 🟡 média | 🟡 validar com usuário antes do próximo estágio |

---

## 14. Critérios de aceite (alto nível)

- 🟡 **Dado** o Analista de Research envia um tema via `/api/v1/plan`, **Quando** o LLM formula a query e escolhe N pontos (só com resultados SERP), **Então** os pontos são persistidos no banco e o usuário recebe `id_pesquisa` e a lista de pontos para análise.
- 🟡 **Dado** os pontos persistidos, **Quando** o usuário dispara `/api/v1/search`, **Então** os pontos são processados conforme `execution_mode`, cada ponto é consolidado a partir das 4 personas, URLs já lidas são filtradas por `id_pesquisa`, e `conteudo_coletado` + `urls_lidas` + `urls_fonte` são persistidos sem cortar a resposta.
- 🟡 **Dado** conteúdo coletado, **Quando** o usuário executa `/api/v1/audit`, **Então** o LLM forte responde 12 perguntas de qualidade sobre a visão consolidada do ponto somada a todas as rodadas de coleta, e cada ponto recebe status `aprovado` ou `reprovado` com `pontos_fracos` persistidos.
- 🟡 **Dado** todos os N pontos finalizados, **Quando** o usuário chama `/api/v1/writer`, **Então** o dossier completo com fontes canônicas marcadas é gerado a partir de todas as rodadas, persistido e enviado via POST ao webhook de callback.
- 🟡 **Dado** o Redator/Dev integrador configura chaves e base URLs via endpoint administrativo, **Quando** o container define variáveis de ambiente de override, **Então** credenciais e N/personas são carregados sem fallback hardcoded.
- 🟡 **Dado** a mesma consulta executada com `JINA_BASE_URL` apontando para a Jina e para o Worker, **Quando** as duas respostas são comparadas, **Então** status, corpo e headers essenciais são idênticos e a tool parseia ambos sem erro.
- 🟡 **Dado** um ponto com 3 retries, **Quando** o `audit` e o `writer` montam o contexto, **Então** as 4 rodadas estão presentes na íntegra.
- 🟡 **Dado** `execution_mode="sequential"`, **Quando** o `search` executa 3 pontos, **Então** apenas um ponto está em voo por vez, na ordem de `ponto_n`.
- 🟡 **Dado** `execution_mode="invalid"`, **Quando** a requisição chega, **Então** o sistema responde `422` sem assumir default.

---

## Pendências de cobertura

- 🟡 [INDEFINIDO] Orçamento: limite viável de custo de tokens não definido nas fontes — validar com usuário antes de `/reversa-spec-sdd`.
- 🟡 [INDEFINIDO] Janela de contexto do LLM forte a ser provisionada para acomodar o histórico acumulado de retries.

---

Gerado por reversa-drafter em 2026-10-21T22:00:00Z
Revisado em 2026-10-27 (v2.0): invariantes I-1..I-5, RF-002-A/B/C, RF-004-A/B/C, RF-005-A/B, RF-006-A/B, RF-008-A, modelo append-only e critérios de aceite.
Fontes: newproject-brief.md, ideation.md, personas.md, state.json (newproject_progress.interview)
