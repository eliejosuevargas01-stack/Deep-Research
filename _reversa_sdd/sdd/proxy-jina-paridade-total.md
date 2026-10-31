# Spec: Proxy Jina (Cloudflare Worker) — Paridade Total e Pass-through

**Versão:** 1.0
**Status:** Planejada (normativa — substitui o contrato implícito anterior)
**Autor:** reversa-spec-sdd
**Data:** 2026-10-27
**Reviewers:** Equipe Deep Research
**Escopo:** contrato de transporte entre a tool de busca do Deep Research (`app/tools/jina_client.py`) e a API da Jina (`s.jina.ai` / `r.jina.ai`), nas duas rotas de acesso: **direta** e **via Cloudflare Proxy Worker**.

---

## 1. Resumo

🟡 Este documento fixa o contrato de **paridade total** entre a chamada direta à Jina e a chamada intermediada pelo Cloudflare Proxy Worker (`/home/eliezer/Escritorio/cloudflare-worker-jina/worker.js`).

🟡 Regra única, inegociável: **o Worker é um túnel**. Tudo o que o Deep Research envia à Jina deve chegar à Jina; tudo o que a Jina devolve deve chegar ao Deep Research. Qualquer transformação — de path, query string, header, corpo, status ou stream — é **violação de contrato**, mesmo que "pareça" equivalente.

🟡 A tool de busca (`JinaClient`) **não pode** saber por qual rota a requisição passou. Se o comportamento observável diferir entre `JINA_BASE_URL=https://s.jina.ai` e `JINA_BASE_URL=https://<worker>`, a tool quebra em `plan` e `search` por erro de parsing ou de schema.

---

## 2. Contexto e Motivação

**Problema:**
🟡 O Worker foi originalmente escrito como *gateway* (rotação de chaves, banimento automático, inspeção de erros embutidos, CORS, deadline de 18s, re-encode de path). Cada uma dessas funções altera o payload observável. O Deep Research passou a depender de campos e cabeçalhos que o Worker não garante, e a falha aparece como erro de parsing na tool — indistinguível de um erro real da Jina.

**Evidências (estado atual do `worker.js`):**

| # | Local | Comportamento atual | Efeito no contrato |
|---|---|---|---|
| 1 | `SAFE_FORWARD_HEADERS` (linha ~1089) | Só 12 headers são repassados | Todo header Jina fora da allowlist (`X-Engine`, `X-Locale`, `X-With-Shadow-Dom`, `X-Set-Cookie`, `X-Md-Heading-Style`, `X-Proxy-*`…) é **descartado** |
| 2 | `safeEncodeSearchPath` (linha ~433) | Re-encoda `"`, espaço, `^ \` < > \ { } \|` | Path enviado ≠ path recebido; risco de duplo-encoding e de query divergente |
| 3 | `TOTAL_REQUEST_DEADLINE_MS = 18000` (linha ~40) | Aborta o **stream de resposta** no deadline | Corpo entregue **truncado** ao cliente, sem sinalização — violação direta da regra de zero truncamento |
| 4 | `MAX_PROXY_BODY_SIZE = 2 MiB` (linha ~39) | Rejeita (413) corpos maiores | `POST` legítimo da Jina é recusado pelo proxy e aceito na rota direta |
| 5 | `inspectEmbeddedError` (linha ~788) + failover | Lê até 4 KiB do corpo, e em `{"code": >= 400}` com HTTP 200 troca de chave e pode devolver **outro status** | Status e corpo deixam de ser os da Jina |
| 6 | `X-Revolver-Chamber` / `X-Revolver-Total-Chambers` (linha ~1377) | Headers extras na resposta | Contrato de resposta ≠ contrato direto |
| 7 | `authenticateClient` + reescrita de `authorization` | Substitui o Bearer do cliente pela chave do pool | Aceitável **apenas** como credencial de transporte; o valor do header do cliente não pode vazar para a Jina nem o header do cliente pode ser ecoado |

**Por que agora:**
🟡 `plan` e `search` já consomem a tool em produção. A divergência entre rotas produz falhas intermitentes que não são reproduzíveis na rota direta, consumindo tentativas de auditoria (1+3) e queimando cota.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 Garantir que a requisição observada pela Jina seja byte-a-byte equivalente nas rotas direta e proxy (path, query string, método, headers relevantes e corpo).
- [ ] G-02: 🟡 Garantir que a resposta observada pela tool seja equivalente nas duas rotas (status, headers essenciais, corpo integral e integridade do stream).
- [ ] G-03: 🟡 Proibir qualquer corte de corpo, de stream ou de payload no Worker, inclusive em timeout e em failover de chave.
- [ ] G-04: 🟡 Fazer a rotação/banimento de chaves de forma **invisível** ao contrato HTTP público.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Paridade de requisição (path+query+headers+body) entre rotas | não medida (divergente por allowlist) | = 100% dos campos | 2026-10-31 |
| 🟡 Paridade de resposta (status+body+content-type) entre rotas | não medida (deadline e failover alteram) | = 100% | 2026-10-31 |
| 🟡 Respostas truncadas entregues como sucesso | > 0 (deadline de 18s) | = 0 | 2026-10-31 |
| 🟡 Falhas de parsing da tool atribuídas ao proxy | > 0 | = 0 | 2026-10-31 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O Worker **não** deve normalizar, resumir, compactar, reordenar ou "limpar" corpos JSON ou Markdown.
- NG-02: 🟡 O Worker **não** deve implementar regra de negócio do Deep Research (não sabe o que é SERP, persona, ponto ou auditoria).
- NG-03: 🟡 O Worker **não** deve impor deadline de execução menor que o timeout configurado no `JinaClient`.
- NG-04: 🟡 O Worker **não** deve retornar payload de erro próprio (`{"error": ...}`) quando existe resposta da Jina para repassar — exceto em falha total de transporte (nenhuma resposta recebida), e nesse caso o status deve ser `502`/`504` **clássicos de gateway**, nunca um código da Jina.
- NG-05: 🟡 O Worker **não** deve expor headers internos (`X-Revolver-*`, `X-Proxy-*`) na resposta pública.

---

## 5. Contrato de Requisição (direta ↔ proxy)

### 5.1 Rota de busca (SERP)

```
GET {JINA_SEARCH_BASE}/{query_percent_encoded}
Accept: application/json
Authorization: Bearer <chave>
X-Retain-Images: none
X-No-Cache: true            # opcional, controlado por fresh=True
```

- 🟡 **Path:** o proxy deve repassar o path **exatamente** como recebido, sem re-encode, sem normalizar `%XX`, sem colapsar `/`, sem lower/upper case. `{query}` já chega percent-encoded pelo `JinaClient` (`urllib.parse.quote(query, safe="")`); re-encodar é proibido.
- 🟡 **Query string:** preservar ordem, repetição e encoding dos parâmetros; remover **somente** `proxy_key` (credencial do proxy), que nunca deve existir na rota direta.
- 🟡 **Método:** `GET` permanece `GET`. `POST`/`PUT`/`PATCH` chegam intactos com corpo binário integral.

### 5.2 Rota de leitura (Reader)

```
GET {JINA_READER_BASE}/{target_url}
Accept: text/markdown
Authorization: Bearer <chave>
X-No-Cache: true            # opcional
```

- 🟡 O proxy deve aceitar as três formas canônicas de destino: `/{https://…}`, `/r/{https://…}`, `/?url={https://…}` — **sem** alterar a URL aninhada. Query string da URL de destino (incluindo `?` e `&`) deve ser preservada integralmente.

### 5.3 Regras de header

| Header | Regra no proxy |
|---|---|
| `host`, `connection`, `keep-alive`, `proxy-*`, `te`, `trailer`, `transfer-encoding`, `upgrade` | Remover (hop-by-hop, RFC 9110 §7.6.1) |
| `authorization` | **Substituir** pela chave do pool upstream. O header do cliente autentica o proxy; nunca é repassado |
| `x-proxy-auth`, `x-admin-key`, `proxy_key` (query) | Remover (credenciais do proxy) |
| `accept`, `content-type`, `content-length`, `x-no-cache`, `x-retain-images`, `x-respond-with`, `x-timeout`, `x-target-selector`, `x-wait-for-selector`, `x-return-format`, `x-with-generated-alt`, `x-with-links-summary`, `x-with-images-summary` | Repassar idêntico |
| **Qualquer outro header não-hop-by-hop** | **Repassar idêntico** (allowlist fechada é proibida) |

🟡 `content-length` só pode ser recalculado quando o corpo foi efetivamente reescrito; como o proxy não reescreve corpo, o valor deve ser o do cliente.

### 5.4 Regras de corpo

- 🟡 Nenhum limite de bytes pode causar perda silenciosa. Se houver limite operacional (proteção de memória), o comportamento obrigatório é **rejeitar explicitamente** (HTTP `413` com erro de proxy documentado) **antes** de iniciar a leitura, nunca servir corpo parcial.
- 🟡 O limite deve ser ≥ ao maior corpo que o `JinaClient` pode enviar. Como o `JinaClient` usa `GET` e o corpo é vazio, o limite existe apenas como defesa; valor normativo mínimo: **10 MiB**.

---

## 6. Contrato de Resposta (direta ↔ proxy)

| Elemento | Regra |
|---|---|
| `status` | Repassar **o status da Jina**. Proibido converter `200` em `402`, `429` em `200`, etc. |
| `statusText` | Repassar quando disponível |
| `content-type` | Repassar idêntico (`application/json` na SERP, `text/markdown` no Reader) |
| `content-encoding` | Repassar idêntico (o runtime do Worker já descomprime; o valor final deve refletir o corpo entregue) |
| Corpo | **Byte-a-byte integral**. Nenhum corte, nenhum `slice`, nenhuma re-serialização |
| Headers da Jina (`x-ratelimit-*`, `x-request-id`, `x-cache`, `retry-after`…) | Repassar idênticos |
| Headers do proxy | Proibidos na resposta pública (`X-Revolver-*`, `X-Proxy-*`, `X-Relay-*`) |

### 6.1 Erros embutidos (HTTP 200 com `code >= 400`)

- 🟡 A decisão de tratar `{"code": 4xx, "data": null}` como erro é **do `JinaClient`**, não do Worker.
- 🟡 O Worker **pode** inspecionar para efeito de rotação de chave (telemetria interna), mas:
  - a resposta entregue ao cliente deve ser **a última resposta recebida da Jina, sem alteração**, com o status HTTP original; **ou**
  - se o corpo inspecionado já foi consumido, o Worker deve **reconstruir o stream exato** a partir dos bytes lidos (buffer integral do corpo, não apenas os 4 KiB de inspeção) antes de decidir failover.
- 🟡 É proibido responder `402`/`403`/`429` sintéticos quando a Jina devolveu `200`.

### 6.2 Failover e banimento de chaves

- 🟡 Failover só pode ocorrer em: `401`, `402`, `403`, `429` (HTTP) — e, quando a inspeção do corpo for integral, em `code` embutido equivalente.
- 🟡 O failover **nunca** pode alterar o payload de uma resposta que será entregue; se a última tentativa falhou, entrega-se a resposta dessa última tentativa tal como veio.
- 🟡 Se todas as chaves estiverem banidas e nenhuma resposta da Jina existir no ciclo, o status deve ser `503` de proxy com corpo de erro do proxy (documentado), pois não há resposta da Jina a repassar.

### 6.3 Deadline e timeout

- 🟡 O deadline total do Worker deve ser **maior ou igual** ao timeout do `JinaClient` (`httpx.Timeout(20s)`) somado à latência de streaming. Valor normativo: deadline de produção **≥ 120s**, configurável por env (`PROXY_TOTAL_DEADLINE_MS`).
- 🟡 Se o deadline for atingido **depois** do início da resposta, o Worker deve **abortar com erro de transporte** (fechar o stream com erro), e não fechar o stream "com sucesso" entregando corpo parcial. Um corpo parcial seguido de `finish` normal é a pior falha possível: o cliente acredita ter o documento inteiro.
- 🟡 O timeout de cada tentativa (`PROXY_FETCH_TIMEOUT_MS`) deve ser ≥ 20s (o `JinaClient` já espera 20s antes de considerar falha; um proxy mais impaciente que o cliente produz 502 espúrio).

---

## 7. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-PX-01 | 🟡 O Worker deve repassar o path da requisição sem qualquer re-encoding, normalização ou reescrita. | Must | 🟡 Dado `GET /php%20mysql%20erro`, quando o proxy encaminha, então a Jina recebe exatamente `/php%20mysql%20erro`. |
| RF-PX-02 | 🟡 O Worker deve repassar todo header não-hop-by-hop, substituindo apenas `authorization` e removendo credenciais do proxy. | Must | 🟡 Dado `X-Engine: browser` e `X-Locale: pt-BR`, quando o proxy encaminha, então ambos chegam à Jina. |
| RF-PX-03 | 🟡 O Worker deve repassar status, statusText, content-type e corpo integral da Jina. | Must | 🟡 Dado corpo de 3 MiB e status 200, quando o cliente lê, então recebe 3 MiB íntegros e status 200. |
| RF-PX-04 | 🟡 O Worker não pode impor deadline que interrompa streams legítimos; ao exceder, deve falhar o stream em vez de truncá-lo silenciosamente. | Must | 🟡 Dado stream acima do deadline, quando o cliente lê, então recebe erro de transporte, nunca `finish` normal com corpo parcial. |
| RF-PX-05 | 🟡 O Worker não pode emitir headers internos na resposta pública. | Must | 🟡 Dado qualquer resposta, quando o cliente inspeciona headers, então não há `X-Revolver-*` nem `X-Proxy-*`. |
| RF-PX-06 | 🟡 O Worker não pode sintetizar status da Jina; erro de proxy usa `502`/`503`/`504` e corpo de erro do proxy. | Must | 🟡 Dado `200` com `{"code": 402}` da Jina, quando o cliente lê, então recebe `200` com o corpo original e é o `JinaClient` quem classifica. |
| RF-PX-07 | 🟡 O Worker deve aceitar corpos de até 10 MiB por requisição. | Should | 🟡 Dado `POST` de 5 MiB, quando o proxy encaminha, então a Jina recebe o corpo integral. |
| RF-PX-08 | 🟡 O Worker deve expor `/health` sem exigir credencial e sem afetar a rota de proxy. | Should | 🟡 Dado `GET /health`, quando o Worker responde, então retorna `200` com versão e commit. |

---

## 8. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-PX-01 | 🟡 Latência adicional do proxy | < 250 ms p95 (sem streaming) | Medido entre recebimento e primeiro byte do upstream |
| RNF-PX-02 | 🟡 Deadline total | ≥ 120 s (env `PROXY_TOTAL_DEADLINE_MS`) | Deve exceder o timeout do `JinaClient` (20 s) com folga |
| RNF-PX-03 | 🟡 Timeout por tentativa | ≥ 20 s (env `PROXY_FETCH_TIMEOUT_MS`) | Alinhado ao timeout do cliente |
| RNF-PX-04 | 🟡 Limite de corpo | ≥ 10 MiB | Rejeição explícita `413`, nunca corte |
| RNF-PX-05 | 🟡 Isolamento de credenciais | 0 vazamentos | Chaves mascaradas em log (`maskKey`), nunca em corpo de resposta |
| RNF-PX-06 | 🟡 Compatibilidade | Nenhuma mudança no `JinaClient` | A tool deve funcionar nas duas rotas sem flag |

---

## 9. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-PX-01 | 🟡 Query com aspas ou espaço (`"IA no Brasil"`) | Path repassado como recebido; nenhum re-encode no Worker |
| EC-PX-02 | 🟡 Cliente desconecta no meio do stream | Worker cancela upstream e encerra; não grava nem resume resposta |
| EC-PX-03 | 🟡 Jina devolve `429` | Failover de chave; se todas esgotarem, entrega o `429` da última tentativa |
| EC-PX-04 | 🟡 Jina devolve `200` com `code=402` | Corpo e status repassados intactos; classificação é do `JinaClient` |
| EC-PX-05 | 🟡 Todas as chaves banidas, sem resposta upstream | `503` do proxy com corpo de erro do proxy e lista mascarada |
| EC-PX-06 | 🟡 Corpo maior que o limite | `413` explícito antes da leitura; nenhum byte parcial entregue |
| EC-PX-07 | 🟡 Deadline atingido com stream aberto | Stream encerrado com erro de transporte |
| EC-PX-08 | 🟡 Header `content-length` divergente do corpo | Prevalecer o corpo real; `content-length` recalculado apenas se o corpo foi reescrito (não é o caso) |

---

## 10. Verificação de Paridade (obrigatória)

🟡 A paridade deve ser provada por teste de contrato, não por inspeção:

1. **Fixture de upstream:** subir um servidor local que grava a requisição crua (método, path, query, headers, body) e devolve um corpo fixo grande (≥ 1 MiB) com headers canônicos.
2. **Duas execuções do mesmo `JinaClient`:** uma com `base_url` apontando para o upstream, outra para o Worker apontando para o upstream.
3. **Comparação:** o registro da requisição deve ser **idêntico** exceto `authorization` (chave do pool) e headers hop-by-hop; a resposta observada pelo cliente deve ser **idêntica** exceto headers do proxy (que devem ser **ausentes**).
4. **Teste de truncamento:** upstream envia corpo em vários chunks com atraso acima do deadline → o cliente deve receber **erro**, nunca `finish` com corpo incompleto.

🟡 Critério de aceite do teste: igualdade de dicionário (não de "campos relevantes"), com lista explícita de exceções permitidas.

---

## 11. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Allowlist de headers substituída por denylist hop-by-hop | Manter allowlist e ir adicionando headers | Allowlist fechada quebra novos headers da Jina sem aviso; denylist é o único contrato estável |
| 🟡 Remover re-encode de path | Manter `safeEncodeSearchPath` como "correção" do runtime | O `JinaClient` já envia percent-encoded; o runtime que decodifica deve ser contornado no cliente, não reescrito no proxy |
| 🟡 Deadline deixa de truncar e passa a falhar o stream | Manter deadline curto para "proteger" o Worker | Corpo parcial silencioso é pior que erro: contamina o corpus e a auditoria |
| 🟡 Inspeção de erro embutido não altera a resposta pública | Sintetizar `402` quando `code=402` | A tool já classifica `code >= 400`; dupla classificação gera divergência de rota |
| 🟡 Headers internos removidos da resposta | Manter para observabilidade | Observabilidade não pode fazer parte do contrato público; usar log/telemetria |

---

## 12. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-PX-01 | 🟡 Qual o teto real de corpo que o Cloudflare aceita em `POST` no plano contratado? | Médio | dev-integrador | 2026-10-31 |
| OQ-PX-02 | 🟡 A rotação de chaves precisa sobreviver a isolates distintos (Durable Objects) para consistência de banimento? | Médio | dev-integrador | 2026-10-31 |

---

## Apêndice — Mapa de conformidade com o código atual

| Regra | Arquivo | Linha/símbolo | Ação necessária |
|---|---|---|---|
| RF-PX-02 | `cloudflare-worker-jina/worker.js` | `SAFE_FORWARD_HEADERS` (~1089) | Trocar allowlist por denylist hop-by-hop |
| RF-PX-01 | `cloudflare-worker-jina/worker.js` | `safeEncodeSearchPath` (~433), `buildJinaTarget` (~446) | Remover re-encode; repassar path cru |
| RF-PX-04 | `cloudflare-worker-jina/worker.js` | `TOTAL_REQUEST_DEADLINE_MS` (~40), `deliverStreamToClient` (~949) | Deadline maior + abortar em vez de fechar |
| RF-PX-07 | `cloudflare-worker-jina/worker.js` | `MAX_PROXY_BODY_SIZE` (~39) | Elevar para ≥ 10 MiB |
| RF-PX-06 | `cloudflare-worker-jina/worker.js` | `inspectEmbeddedError` (~788), failover (~1341-1398) | Não sintetizar status; buffer integral antes de failover |
| RF-PX-05 | `cloudflare-worker-jina/worker.js` | `X-Revolver-Chamber` (~1377) | Remover da resposta pública |
| RNF-PX-03 | `cloudflare-worker-jina/worker.js` | `FETCH_TIMEOUT_MS` (~41) | Elevar para ≥ 20 s |
| — | `Deep-Research/app/tools/jina_client.py` | `search` / `read` | Nenhuma mudança de transporte; opcional: `search_raw()` para consumo integral |
