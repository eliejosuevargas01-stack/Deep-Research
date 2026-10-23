# Requisitos — Falhas de Coleta e Diagnóstico

**Feature 004 · deep-research**
**Data:** 2026-10-22
**Origem:** incidente real observado na pesquisa `7ce84db3-9451-4239-a8a6-32529e11ac0b` (ponto 1, `d15841fc-4eab-4522-a9ae-a4142d7b42f7`), onde a etapa de busca produziu uma análise com 20.299 caracteres, zero URLs lidas e zero URLs fonte, com status `coletado` e sem nenhum erro reportado à API.

## 1. Contexto e problema raiz

Um dossiê foi gerado integralmente a partir do conhecimento paramétrico do modelo, sem qualquer evidência web, e o pipeline o tratou como legítimo. Causa raiz identificada em três camadas:

1. **Cliente Jina (`app/tools/jina_client.py:96`)** — respostas `402 Payment Required` e `401 Unauthorized` não disparam `raise_for_status()` (que só cobre 429/500/502/503/504 e `is_server_error`). O corpo da resposta é então interpretado como uma SERP sem resultados, e o método retorna `[]`.
2. **Orquestrador de busca (`app/core/searcher.py:263`)** — a lista vazia é indistinguível de "nenhuma fonte encontrada". Nenhuma exceção sobe; o loop ReAct segue para a síntese final.
3. **Prompt de síntese sem evidência (`app/core/searcher.py:317-325`)** — instrui o modelo a "produzir sua síntese analítica final com base em todas as evidências coletadas" quando o conjunto real de evidências é vazio. Resultado: análise convincente e inventada.

O defeito é silencioso em três níveis: o ponto é marcado `coletado`, a pesquisa é marcada `coletado` (HTTP 200), e o dossiê final é despachado ao webhook como resultado válido.

## 2. Escopo

### 2.1 Em escopo

- RF-01: o cliente Jina deve classificar e expor falhas de erro HTTP da Jina (401, 402, 403, 429 e família 5xx) em tipo de erro distinguível, sem convertê-las em lista vazia.
- RF-02: falhas de autenticação e billing da Jina (401/402/403) devem ser terminais, sem retry, com mensagem que identifique a causa provável e a ação corretiva.
- RF-03: o Searcher deve tratar "zero URLs lidas em todas as personas de um ponto" como falha de coleta, não como resultado aceitável.
- RF-04: a resposta da etapa de busca deve expor, por ponto, o detalhe da falha de coleta (categoria, mensagem, URLs encontradas, queries executadas), e não apenas contadores zerados.
- RF-05: nenhuma análise sintética pode ser gerada sem evidência bruta coletada; a ausência de evidência deve abortar a síntese da persona com razão explícita.
- RF-06: o ponto deve receber status de falha (`falha_coleta`) e justificativa persistida, para que a auditoria e a redação final compartilhem o mesmo diagnóstico.
- RF-07: a auditoria deve reprovar automaticamente pontos sem evidência real, com justificativa determinística, sem depender de julgamento do LLM.
- RF-08: o writer deve bloquear a redação final quando todos os pontos do escopo estão em falha de coleta, evitando dossiê 100% inventado.
- RF-09: o pipeline autônomo deve registrar o diagnóstico da falha no campo de erro da pesquisa, sem mascarar a causa.
- RF-10: endpoint de disponibilidade que valide a conectividade real com a Jina e com o LLM, expondo o status de cada provedor.

### 2.2 Fora de escopo

- Alterar o número de personas, a estratégia de queries ou o desenho do loop ReAct.
- Reintentar coleta com outro provedor de busca.
- Migrar banco, alterar contrato de webhooks já publicados, ou mudar modelos configurados.
- Tratar custo de tokens por persona (telemetria já sinalizada como dívida em `app/schemas/search.py:126`).

## 3. Requisitos Funcionais

### RF-01 — Classificação de erro da Jina

O cliente Jina deve inspecionar o código HTTP da resposta e, quando houver falha, levantar exceção tipada carregando: código HTTP, categoria (`billing`, `autenticacao`, `rate_limit`, `indisponibilidade`, `desconhecido`) e mensagem extraída do corpo da resposta quando disponível.

Critérios de aceitação:
- `CA-01.1`: resposta `402` com corpo `{"error": "InsufficientBalanceError ..."}` produz exceção de categoria `billing`.
- `CA-01.2`: resposta `401` produz exceção de categoria `autenticacao`.
- `CA-01.3`: resposta `429` mantém o comportamento atual de retry 1+3 e, esgotado, levanta exceção de categoria `rate_limit`.
- `CA-01.4`: respostas 5xx continuam sendo retentadas e, esgotadas, levantam exceção de categoria `indisponibilidade`.
- `CA-01.5`: nenhum caminho de erro retorna lista vazia como se fosse resultado legítimo.
- `CA-01.6`: a mensagem de erro nunca expõe a chave de API.

### RF-02 — Falhas terminais sem retry

Erros de billing e autenticação não são transientes.

Critérios de aceitação:
- `CA-02.1`: uma sequência de 4 respostas `402` gera exatamente 1 requisição HTTP (sem retry).
- `CA-02.2`: a mensagem de erro indica a ação corretiva (recarregar saldo / verificar chave).
- `CA-02.3`: o tempo de resolução da falha não inclui backoff.

### RF-03 — Detecção de coleta vazia no Searcher

O Searcher deve computar, por ponto, o total de URLs efetivamente lidas (não apenas candidatas) considerando todas as personas.

Critérios de aceitação:
- `CA-03.1`: se todas as personas de um ponto retornarem zero URLs lidas, o ponto é classificado como `falha_coleta`.
- `CA-03.2`: a classificação independe de o LLM ter produzido texto analítico extenso.
- `CA-03.3`: a query executada é registrada no diagnóstico mesmo em falha.

### RF-04 — Exposição do diagnóstico na resposta

O schema de resposta da busca deve carregar o diagnóstico da coleta.

Critérios de aceitação:
- `CA-04.1`: `SearchColetaResumo` passa a expor `falha_coleta: bool` e `diagnostico: str`.
- `CA-04.2`: o diagnóstico descreve a categoria da falha e a ação corretiva.
- `CA-04.3`: respostas de sucesso mantêm os campos existentes inalterados (retrocompatibilidade).
- `CA-04.4`: o campo `status` do ponto reflete `falha_coleta` quando aplicável.

### RF-05 — Bloqueio da síntese sem evidência

A persona não deve produzir análise final sem evidência bruta.

Critérios de aceitação:
- `CA-05.1`: se `raw_evidence_chunks` estiver vazio ao final do loop ReAct, nenhuma chamada de síntese é feita.
- `CA-05.2`: a análise retornada nesse caso é uma declaração explícita de falha, não conteúdo inventado.
- `CA-05.3`: a persona retorna `urls_lidas: []`, `evidencia_vazia: true` e o detalhe do erro propagado pelo cliente Jina.
- `CA-05.4`: nenhum prompt solicita síntese sobre "evidências coletadas" quando não há evidências.

### RF-06 — Persistência do estado de falha

O ponto em falha deve refletir a falha no banco e na cadeia de auditoria.

Critérios de aceitação:
- `CA-06.1`: o ponto recebe `status = "falha_coleta"`.
- `CA-06.2`: a justificativa da falha é persistida em `pontos_fracos` do ponto, com categoria e ação corretiva.
- `CA-06.3`: coletas anteriores do ponto não são apagadas.
- `CA-06.4`: `status_pesquisa` da pesquisa passa a `coleta_falhou`.

### RF-07 — Reprovação determinística na auditoria

A auditoria não deve decidir por LLM aquilo que é verificável por evidência.

Critérios de aceitação:
- `CA-07.1`: ponto cuja última coleta tem zero URLs lidas é reprovado sem chamada ao LLM.
- `CA-07.2`: `pontos_fracos` registra a categoria da falha de coleta e a ação corretiva.
- `CA-07.3`: a reprovação incrementa `tentativas_auditoria` como nas demais reprovações.

### RF-08 — Bloqueio da redação final

O writer não deve produzir dossiê quando não há evidência real em nenhum ponto.

Critérios de aceitação:
- `CA-08.1`: se todos os pontos estão em `falha_coleta`, o writer levanta `ValueError` com código `NO_EVIDENCE_COLLECTED`.
- `CA-08.2`: se ao menos um ponto tem evidência real, a redação prossegue normalmente.
- `CA-08.3`: o erro é registrado em `erro_pipeline` pelo pipeline autônomo sem ser mascarado.

### RF-09 — Diagnóstico no pipeline autônomo

O `PipelineRunner` deve propagar o diagnóstico sem engoli-lo.

Critérios de aceitação:
- `CA-09.1`: falha de coleta na Jina resulta em `status = "falha"` com `erro_pipeline` descrevendo a categoria e a ação corretiva.
- `CA-09.2`: o log registra o identificador da pesquisa e a causa.
- `CA-09.3`: o ciclo de retentativas não repete indefinidamente uma falha de billing (terminal).

### RF-10 — Endpoint de disponibilidade

Deve existir verificação explícita de conectividade real dos provedores.

Critérios de aceitação:
- `CA-10.1`: `GET /api/v1/health/providers` executa chamada real de baixo custo à Jina e ao LLM configurado.
- `CA-10.2`: a resposta informa, por provedor, `status` (`ok` / `erro`) e `detalhe` com categoria da falha.
- `CA-10.3`: o endpoint não expõe chaves nem URLs completas sensíveis.
- `CA-10.4`: diferente de um healthcheck de processo, ele falha quando o provedor externo falha.

## 4. Requisitos Não-Funcionais

- **RNF-01 — Sem regressão:** toda a suíte de testes existente deve continuar passando. Os testes de `tests/unit/test_regressao_data_null.py` cobrem o comportamento de `{"code":401,"data":null}` e devem ser atualizados conscientemente quando o contrato do cliente mudar.
- **RNF-02 — Falha ruidosa:** nenhuma falha de provedor externo pode resultar em resposta HTTP 200 com conteúdo sintetizado sem fonte.
- **RNF-03 — Mensagens acionáveis:** toda mensagem de erro deve dizer o que aconteceu e o que fazer, em português, sem jargão de implementação.
- **RNF-04 — Baixo acoplamento:** a classificação de erro deve viver no cliente HTTP, não espalhada pelos orquestradores de domínio.
- **RNF-05 — Custo:** o endpoint de disponibilidade deve usar queries mínimas e modelos leves.
- **RNF-06 — Determinismo:** as classificações de falha devem ser testáveis com `httpx.MockTransport` sem rede.

## 5. Rastreabilidade

| Requisito | Situação atual | Situação alvo |
|---|---|---|
| RF-01 | jina_client.py:103 filtra só 429/5xx | erro tipado com categoria |
| RF-02 | 402/401 retornam `[]` silenciosamente | terminal, com ação corretiva |
| RF-03/05 | searcher.py:294-299 não distingue vazio de falha | falha explícita e sem síntese |
| RF-04 | schemas/search.py sem diagnóstico | `falha_coleta` + `diagnostico` |
| RF-06 | repository marca `coletado` sempre | `falha_coleta` + justificativa |
| RF-07 | auditor.py depende de LLM | reprovação determinística |
| RF-08 | writer gera dossiê de texto inventado | bloqueio sem evidência |
| RF-09 | pipeline_runner engoli detalhe | diagnóstico em `erro_pipeline` |
| RF-10 | sem verificação de provedor | `GET /api/v1/health/providers` |

## 6. Decisões sobre dúvidas (resolvidas sem bloquear a entrega)

- **[DÚVIDA-01 — resolvida: corrigir]** `jina_client.read()` tem exatamente o mesmo defeito de classe (401/402 não disparam `raise_for_status` e o corpo de erro é devolvido como se fosse Markdown legítimo). Corrigir na mesma feature, compartilhando o classificador de erro entre `search()` e `read()`.
- **[DÚVIDA-02 — resolvida: retrocompatível]** O campo `status_pesquisa` é consumido pelo webhook `research.completed` já publicado pelo n8n. **Não** introduzir valor novo no nível da pesquisa. A falha é exposta por ponto (`status` do ponto + `falha_coleta` + `diagnostico`), e `status_pesquisa` permanece `coletado`. O pipeline autônomo, que é o caminho que realmente precisa sinalizar falha, usa `erro_pipeline`/`status_pipeline`, que não é lido pelo consumidor externo.
