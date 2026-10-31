# Adendo Normativo de SDD — Atualização dos Contratos de Confiabilidade (v2)
**Referência:** Backlog DR-001 a DR-015 / Inspeção `confiabilidade-20261023`  
**Data da Aprovação:** 23/10/2026  
**Versão:** 2.0 (Preserva integralmente a versão 1.0 e as specs originais de `_reversa_sdd/sdd/`)  
**Status:** Veredito Normativo e Vinculante para as Próximas Etapas de Implementação

---

## 1. Contexto e Motivação da Revisão v2

A versão 1.0 deste adendo continha duas divergências em relação às diretrizes aprovadas pelo usuário:
1. Mencionava tolerância de entrega parcial com ressalvas para eixos reprovados no Writer (DR-012).
2. Declarava que tags de encapsulamento impediriam integralmente prompt injection.

A presente versão v2 formaliza as correções vinculantes estabelecidas na inspeção de confiabilidade de 23/10/2026 e registra as fundações técnicas implementadas em DR-005, DR-006, DR-009, DR-013, DR-014 e DR-015.

---

## 2. Deltas Normativos Atualizados

### 2.1. Redação do Dossiê (`endpoint-redacao-do-dossier.md`) — DR-003, DR-011, DR-012
1. **Política Estrita de Bloqueio por Eixos Reprovados (DR-012):**
   - *Correção normativa:* Qualquer pesquisa que contiver um ou mais eixos com status `reprovado` após o esgotamento das retentativas de auditoria **DEVE BLOQUEAR O WRITER POR PADRÃO**.
   - É expressamente vedada a entrega parcial silenciosa ou redação de dossiê para pesquisas reprovadas. O avanço para a etapa de redação é interceptado previamente à invocação do modelo e antes do cache. O status final é `reprovado`.
2. **Validação Estrutural e Truncamento (DR-003):**
   - O Writer deve validar deterministicamente a presença substantiva das quatro seções em ordem:
     1. `## 1. Sumário Executivo`
     2. `## 2. Desenvolvimento dos Eixos Temáticos`
     3. `## 3. Ressalvas e Limitações Metodológicas`
     4. `## 4. Referências e Fontes Canônicas`
   - Cercas de código abertas (``` ímpar), ausência de qualquer seção ou término com `finish_reason == "length"` impedem conclusão e resultam em estado `incompleto`.
3. **Idempotência com Validação de Integridade (DR-003):**
   - Antes de retornar dossiê salvo no banco de dados, deve-se revalidar o artefato. Dossiê truncado ou corrompido em cache nunca é devolvido como `concluido`.

### 2.2. Cliente LLM e Observabilidade (`app/tools/llm_client.py`) — DR-001, DR-005, DR-013
1. **API de Envelope Imutável e Isolado (`LLMEnvelope`):**
   - Toda chamada gera um envelope imutável contendo: `content_final`, `reasoning_content`, `finish_reason`, `is_regular_finish`, `model_requested`, `model_used`, `usage`, `cost_estimated`, `latency_seconds`, `attempts`, `errors`, `tool_calls`, `prompt_hash`, `system_message_sent` e `messages_sent`.
   - Proibição absoluta de estado global compartilhado (`last_response`) para garantir concorrência segura entre personas.
2. **Autenticidade de `finish_reason` e Streaming:**
   - Eliminação terminante de fallbacks do tipo `finish_reason or 'stop'`. Se o provedor não informar `finish_reason`, o campo permanece `None` e `is_regular_finish` é `False`.
   - `data: [DONE]` ou encerramento de socket não equivalem a término regular do modelo.
   - Leitura de `usage` inclusive em chunks SSE sem `choices`.
   - Erros de JSON/SSE malformado são registrados em `errors` e invalidam `is_regular_finish`.
3. **Falhas HTTP 4xx e Cancelamento:**
   - Erros HTTP 400, 401 e 403 falham imediatamente sem retries inúteis e sem retornar mensagem vazia.
   - Retries limitados (1 inicial + 3 retries) com backoff exponencial aplicam-se exclusivamente a erros retentáveis (429, 500, 502, 503, 504).
   - `asyncio.CancelledError` é preservado sem captura genérica.
4. **Segregação Estrita de Canais (DR-001):**
   - `content_final` e `reasoning_content` são rigorosamente segregados. `reasoning_content` nunca é promovido para análise pública nem parseado em `generate_json`.
5. **Custo e Higienização de Segredos:**
   - Custo estimado só é calculado com preço catalogado e contagem de tokens fornecida; caso contrário, é `None`.
   - Mensagens registradas são higienizadas contra Bearer tokens, chaves `sk-` e cabeçalhos de autorização.

### 2.3. Planejamento Investigativo (`endpoint-plano-de-investigacao.md`) — DR-006, DR-014, DR-015
1. **Plano Estruturado e Persistido (`PlanoInvestigacao` e `PlanoEixo`):**
   - Saída contratual contendo: `pedido_original`, `pedido_normalizado`, `publico`, `formato_entrega`, `recorte_temporal`, `pressupostos`, `ambiguidades`, `eixos`.
   - Cada eixo possui: `pergunta_principal`, `subperguntas`, `hipoteses`, `consultas_iniciais`, `fontes_primarias_desejadas`, `riscos_de_vies`, `evidencias_que_refutariam`, `criterio_de_conclusao`, `investigabilidade`, `eixo_essencial`.
2. **Deduplicação Determinística e Semântica:**
   - Rejeição de sobreposições textuais e paráfrases semânticas da mesma pergunta (regressão de 5 variações).
   - Suporte estrito a N configurável, inclusive N=1. Proibição de temas artificiais apenas para inflar N.
   - No prompt do Avaliador Semântico (`evaluate_plan_semantics`), a instrução para `sobreposicao_eixos` deve explicitar o contrato exato esperado pelo validador: lista vazia `[]` para `N=1` e, para `N > 1`, cobertura exaustiva e obrigatória de todos os $N(N-1)/2$ pares canônicos `(eixo_1, eixo_2)` com `1 <= eixo_1 < eixo_2 <= N` (listados nominalmente no prompt), preenchendo `"sobreposto": false` para pares complementares e `"sobreposto": true` quando houver redundância.
3. **Preservação de Intenção e Público:**
   - Se o pedido solicitar explicação para criança de 5 anos ou leigo, o campo `publico` e o `formato_entrega` devem preservar essa intenção, sem distorção em tutorial operacional.
4. **Fronteira dos Metadados SERP:**
   - Metadados da SERP são pistas preliminares e dados de terceiros NÃO CONFIÁVEIS. NUNCA provam fatos, cronologias ou autoria.
   - Tags como `<untrusted_evidence>` são delimitadores textuais de contexto, não garantia universal contra injeções.
5. **Resiliência e Falha Fechada:**
   - JSON array, null ou itens de tipo errado são reprovados com até 2 tentativas de reparo direcionado.
   - Falha de contrato final é fechada e aborta a transação sem criar pesquisa parcial no banco.

### 2.4. Persistência Estruturada e Migração Idempotente — DR-009, DR-013, DR-015
1. **Entidades de Rastreabilidade:**
   - `generation_attempts`: telemetria imutável de inferência por etapa e persona.
   - `search_evidences`: evidências documentais com trecho, proveniência e hash.
   - `research_claims`: afirmações factuais e inferências com nível de confiança.
   - `search_actions`: diário de bordo e justificativas de parada por persona.
   - `audit_results`: deliberação do vetor 12 e snapshot de evidências.
   - `writer_artifacts`: artefatos versionados e validados do redator final.
2. **Migrações Aditivas Idempotentes:**
   - Rotina `_run_additive_migrations(conn)` atualiza esquemas antigos adicionando colunas sem destruir registros.
   - Execuções consecutivas são seguras e mantêm registros existentes intactos.
   - Campos novos em registros legados permanecem honestamente `NULL`, sem dados fictícios.
