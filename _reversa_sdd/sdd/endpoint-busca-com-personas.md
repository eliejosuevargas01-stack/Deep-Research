# Spec: Endpoint /api/v1/search — Busca com Personas

**Versão:** 1.2
**Status:** Planejada (revisão normativa v3 — bruto volátil)
**Autor:** reversa-spec-sdd
**Data:** 2026-11-02 (original 2026-10-21)
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/search` constitui a segunda etapa do pipeline Deep Research, encarregado de executar a varredura aprofundada na web para os pontos de investigação previamente gerados na etapa de plano.

🟡 A execução opera conforme `execution_mode` explícito no payload (`parallel` por padrão, `sequential` sob demanda), aplicando quatro personas especializadas do sistema (`historiador`, `visionario`, `cetico`, `futurista`) acionadas via LLM leve OpenAI-compatible, com chamadas de ferramenta ao Jina SERP (`s.jina.ai`) e Jina Reader (`r.jina.ai`), filtragem de URLs previamente lidas, agregação das 4 personas **por ponto** e consolidação sem truncamento na base SQLite permanente.

🟡 **v1.1 (normativa):** incorpora os invariantes I-1..I-5 do PRD v2. Em caso de conflito com o texto original de 2026-10-21, prevalece a v1.1.

🟡 **v1.2 (normativa, v3):** o texto integral devolvido pela Jina é **insumo volátil de RAM**. Cada persona o consome, produz um **resumo denso** (`analise`) com dados, números, datas e fatos, e o bruto é descartado no mesmo ciclo. Persistem apenas `analise`, `urls_utilizadas` e `urls_lidas_nao_utilizadas` no catálogo do ponto. Não há armazenamento de corpo, excertos, offsets nem hashes de corpo. Precedência: [`prd.md`](../prd.md) I-2 v3 > [`app/CRITERIA.md`](../../app/CRITERIA.md) > esta spec.

---

## 2. Contexto e Motivação

**Problema:**
🟡 A busca manual por fontes e conteúdos aprofundados demanda tempo excessivo e gera leituras repetitivas das mesmas páginas, além de carecer de diversidade analítica na formulação de consultas.

**Evidências:**
🟡 No diagnóstico do PRD, ferramentas concorrentes tratam a busca como etapa opaca sem desduplicação de URLs e sem separação de perspectivas analíticas, inflando custos de processamento com scraping redundante.

**Por que agora:**
🟡 O processamento dos N pontos (paralelo ou sequencial, à escolha do chamador), associado ao filtro de URLs por pesquisa, assegura varredura abrangente com economia de chamadas externas e rastreabilidade total das fontes canônicas.

**Motivação da revisão v1.1:**
🟡 Três falhas observadas em execução real motivaram a v1.1: (a) respostas divergentes entre Jina direta e proxy quebravam o parser; (b) passagens de rodadas anteriores eram cortadas em 800 caracteres antes de entrar no contexto das personas; (c) o histórico de retries era usado de forma parcial (apenas a última coleta), fazendo o auditor e o redator avaliarem um ponto com informação incompleta.

**Motivação da revisão v1.2 (v3):**
🟡 Persistir cada corpo integral da Jina, com hashes e offsets de excertos, inchava a base SQLite e transformava o banco em arquivo morto de páginas já analisadas: 4 rodadas × 4 personas × N páginas de até 3 MiB. Pior, o resumo útil ficava enterrado sob material bruto que nenhum estágio a jusante precisava reler. A v3 corrige a raiz: o bruto existe **só em RAM** durante a rodada, o especialista devolve o resumo denso e o catálogo de URLs com uso, e o bruto morre com o processo da persona. O que atravessa estágios é conhecimento destilado, não texto de página.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 Processar os N pontos de uma pesquisa identificada por `id_pesquisa`, em paralelo ou sequencial conforme `execution_mode`.
- [ ] G-02: 🟡 Aplicar o filtro deduplicador de URLs por `id_pesquisa` evitando requisições repetidas a páginas já consultadas.
- [ ] G-03: 🟡 Preservar integralmente o **resumo denso** de cada persona e as listas de URLs (`utilizadas` e `lidas_nao_utilizadas`), sem truncamento em nenhuma camada.
- [ ] G-04: 🟡 Produzir, por ponto, um pacote consolidado das 4 personas, pronto para o `audit`.
- [ ] G-05: 🟡 Preservar, de forma append-only, todas as rodadas de coleta do ponto (nenhuma retry sobrescreve a anterior).
- [ ] G-06: 🟡 Garantir contrato idêntico entre Jina direta e Cloudflare Proxy Worker.
- [ ] G-07 (v1.2): 🟡 Manter o texto bruto da Jina exclusivamente em RAM e descartá-lo ao fim de cada persona, sem persistir corpo, excertos, offsets ou hashes de corpo.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Taxa de pontos processados com sucesso no modo escolhido | 0% | = 100% | 2026-10-31 |
| 🟡 Deduplicação de URLs já consultadas por pesquisa | 0% | = 100% | 2026-10-31 |
| 🟡 Tempo de resposta total da busca por ponto | N/A | < 300s | 2026-10-31 |
| 🟡 Rodadas de coleta preservadas por ponto | última apenas | = 100% das rodadas | 2026-10-31 |
| 🟡 Caracteres de resumo truncados em handoff | > 0 | = 0 | 2026-10-31 |
| 🟡 Corpo bruto de página persistido (v1.2) | não medido | = 0 bytes | 2026-11-02 |
| 🟡 Divergência de contrato Jina direta × proxy | não medida | = 0 campos | 2026-10-31 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve efetuar a avaliação crítica das 12 perguntas de qualidade, que compete privativamente ao endpoint `/api/v1/audit`.
- NG-02: 🟡 O sistema não deve redigir o dossiê final consolidado nem despachar notificações para webhooks, responsabilidades exclusivas de `/api/v1/writer`.
- NG-03: 🟡 O sistema não deve redefinir nem recriar os pontos de investigação na tabela `pontos`, consumindo estritamente os registros existentes.
- NG-04: 🟡 O sistema não deve reter histórico conversacional completo na memória do LLM entre chamadas de ferramenta distintas, operando sob memória transitória focada em chamadas de ferramentas.
- NG-05 (v1.1): 🟡 O sistema **não** deve limpar, resumir ou truncar conteúdo coletado para "caber" no contexto. Se não couber, falha explicitamente.
- NG-06 (v1.1): 🟡 O sistema **não** deve escolher silenciosamente um `execution_mode` diferente do solicitado.
- NG-07 (v1.2): 🟡 O sistema **não** deve persistir o corpo bruto da Jina nem derivados de posição (excertos, offsets, hashes de corpo) em `conteudo_coletado`, logs, artefatos ou backups. O bruto não é dado de negócio; é insumo transitório de inferência.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional que acompanha a coleta factual por ponto temático e necessita de integridade nas fontes extraídas.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor que integra a coleta automatizada e consome os dados estruturados de URLs e conteúdo.
**Personas do sistema:** 🟡 Quatro personas analíticas ativas (`historiador`, `visionario`, `cetico`, `futurista`), cada uma orientando a formulação de buscas e a interpretação sob seu respectivo viés temático.

**Jornada atual (sem a feature):**
1. 🟡 O analista abre dezenas de abas no navegador e copia passagens manualmente para blocos de notas.
2. 🟡 O analista revisita involuntariamente as mesmas páginas para diferentes pontos do tema gerando retrabalho.
3. 🟡 As fontes primárias perdem o vínculo com as passagens transcritas comprometendo a rastreabilidade.

**Jornada futura (com a feature):**
1. 🟡 O usuário submete requisição `POST /api/v1/search` informando o `id_pesquisa` e, opcionalmente, `execution_mode`.
2. 🟡 O sistema executa os trabalhadores no modo escolhido, aplicando as personas analíticas e a ferramenta Jina (direta ou proxy, indiferentemente).
3. 🟡 O sistema persiste o resumo consolidado das personas e o catálogo de URLs da rodada, sem sobrescrever rodadas anteriores e sem guardar o corpo bruto das páginas.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber requisições HTTP POST no endpoint `/api/v1/search` contendo obrigatoriamente o campo `id_pesquisa` em formato JSON. | Must | 🟡 Dado envio de payload com `id_pesquisa` válido, Quando o sistema processa a requisição, Então o sistema inicia a varredura dos pontos pendentes. |
| RF-02 | 🟡 O sistema deve recuperar todos os pontos com status `pendente` associados ao `id_pesquisa` na tabela `pontos`, retornando código HTTP 404 caso nenhum ponto seja localizado. | Must | 🟡 Dado um `id_pesquisa` inexistente no banco, Quando o sistema consulta a tabela `pontos`, Então o sistema responde código HTTP 404 informando ausência de registros. |
| RF-03 | 🟡 O sistema deve orquestrar a execução dos pontos recuperados conforme o campo `execution_mode`, com isolamento transacional de sessão por ponto quando em paralelo e barreira de sincronização. | Must | 🟡 Dado N pontos pendentes e `execution_mode=parallel`, o sistema processa N pontos em tarefas assíncronas concorrentes com sessões isoladas; com `sequential`, processa um ponto por vez, em ordem crescente de `ponto_n`, sem nunca ter dois pontos em voo. |
| RF-04 | 🟡 O sistema deve injetar os prompts diretivos das personas (`historiador`, `visionario`, `cetico`, `futurista`) configuradas via variáveis de ambiente para diversificar os ângulos de busca. | Must | 🟡 Dado o acionamento de cada trabalhador, Quando o LLM recebe o contexto, Então o sistema fornece as instruções da persona atribuída sem recorrer a fallback hardcoded. |
| RF-05 | 🟡 O sistema deve fornecer às instâncias do LLM a ferramenta Jina SERP (`s.jina.ai`) e o Jina Reader (`r.jina.ai`), interceptando cada URL antes da requisição para descartar links já catalogados na tabela de URLs lidas para a pesquisa corrente. | Must | 🟡 Dado o retorno de links pela SERP, Quando uma URL já existente é identificada pelo filtro, Então o sistema descarta o scrap redundante e preserva a cota de requisições. |
| RF-06 | 🟡 O sistema deve catalogar as URLs consultadas por rodada em `metadados_coleta.fontes` (com `status` de leitura, `titulo`, `data_fonte` e `uso`: `utilizada` ou `lida_nao_utilizada`) e manter memória restrita ao ciclo de chamadas de ferramentas. | Must | 🟡 Dado o término de leitura de uma página web, Quando o trabalhador conclui a iteração, Então a URL aparece no catálogo da rodada com `status=read_ok`; nenhum corpo de página é gravado. |
| RF-07 | 🟡 O sistema deve consolidar o **resumo denso** devolvido por cada persona, sem truncamento, gravando na tabela `conteudo_coletado` os campos `tema`, `id_pesquisa`, `ponto`, `ponto_id`, `rodada`, `conteudo_coletado` (síntese da rodada, nunca corpo de página), `urls_lidas`, `urls_fonte` e `metadados_coleta`. | Must | 🟡 Dado o encerramento da busca de um ponto, Quando o parser finaliza o empacotamento, Então persiste a síntese integral e as coleções de URLs da rodada, com o bruto já descartado da RAM. |
| RF-08 | 🟡 O sistema deve atualizar o status dos pontos correspondentes para `coletado` na tabela `pontos` e responder código HTTP 200 com o sumário de processamento. | Must | 🟡 Dado o processamento bem-sucedido de todos os pontos, Quando a resposta é emitida, Então o sistema entrega código HTTP 200 contendo total de pontos e URLs processadas. |

### 6.2 Requisitos das revisões v1.1 e v1.2 (normativos)

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-09 | 🟡 O payload de entrada deve aceitar `execution_mode` com valores exatos `"parallel"` e `"sequential"`, default `"parallel"`, governando o processamento **dos pontos** (as 4 personas de um mesmo ponto continuam concorrentes entre si). | Must | 🟡 `execution_mode="sequential"` com 3 pontos ⇒ timeline com no máximo 1 ponto em voo; `"invalid"` ⇒ HTTP 422 sem fallback. |
| RF-10 | 🟡 A resposta da tool de busca não pode ser truncada, resumida ou ter campos removidos por limite artificial, em nenhuma das rotas (Jina direta ou Cloudflare Proxy Worker). | Must | 🟡 Consulta com SERP de 200 itens retorna 200 itens; corpo de Reader de 3 MiB chega íntegro; a rota não altera status, headers essenciais nem corpo. |
| RF-11 | 🟡 O sistema deve agregar, **por ponto**, as respostas das 4 personas em um único pacote consolidado antes de disponibilizá-lo ao `audit`. | Must | 🟡 Para cada ponto, `metadados_coleta.resultados_personas` contém as 4 personas com `analise`, `conclusoes`, `lacunas`, `motivo_parada`, `sucesso`; nenhuma persona ausente quando ativa. |
| RF-12 | 🟡 Cada nova passagem do `search` sobre um ponto deve **acrescentar** uma rodada (`rodada = tentativas`), preservando integralmente as rodadas anteriores. Proibido `UPDATE` que substitua `conteudo_coletado`, `urls_fonte` ou qualquer campo de `metadados_coleta` de rodada anterior. | Must | 🟡 Após 1 tentativa + 3 retries, existem 4 registros em `conteudo_coletado` para o ponto, com `rodada` 1..4, todos legíveis. |
| RF-13 | 🟡 Ao reconstruir contexto de retry (persona parcialmente refeita), o sistema deve buscar a persona ausente em **todas** as rodadas anteriores, da mais recente para a mais antiga, e não apenas na última. | Must | 🟡 Retry focado em `cetico` reaproveita a análise de `historiador` da rodada mais recente que a possua, mesmo que a última rodada não a tenha. |
| RF-14 | 🟡 O histórico entregue às personas em retry deve conter o **resumo integral** (`analise`) das personas anteriores de todas as rodadas, mais o catálogo de URLs com uso; nunca o corpo bruto de página, que já não existe fora da RAM da rodada em que foi lido. | Must | 🟡 Rodada anterior com resumo de 9.000 caracteres entra no contexto com 9.000 caracteres; nenhuma leitura de corpo é refeita para reconstruir histórico. |
| RF-15 (v1.2) | 🟡 O texto bruto devolvido pela Jina deve ser descartado ao fim de cada persona, no mesmo escopo de execução que o recebeu. Proibido persistir, logar, versionar ou reter o bruto após a produção do resumo. | Must | 🟡 Após o ponto concluir, o banco não contém corpo de página nem derivado posicional; inspeção de `metadados_coleta` mostra apenas resumos, catálogo e pareceres. |
| RF-16 (v1.2) | 🟡 Cada persona deve registrar, além do resumo, `urls_utilizadas` (URLs que sustentaram o resumo) e `urls_lidas_nao_utilizadas` (URLs abertas e descartadas por inutilidade ou repetição); o catálogo do ponto consolida ambas com `uso`. | Must | 🟡 Persona que leu 6 URLs e usou 3 ⇒ 3 em `utilizadas` e 3 em `lidas_nao_utilizadas`; soma confere com `status=read_ok` do catálogo. |

### 6.3 Fluxo Principal (Happy Path)

1. 🟡 O usuário submete requisição `POST /api/v1/search` com payload contendo `id_pesquisa` (e opcionalmente `ponto_id`, `personas`, `execution_mode`).
2. 🟡 O sistema valida o payload, incluindo `execution_mode` (422 se inválido), e consulta os pontos associados na tabela `pontos`.
3. 🟡 O sistema distribui cada ponto para um trabalhador, paralelo ou sequencial conforme solicitado, configurado com a persona atribuída e modelo LLM leve.
4. 🟡 O trabalhador formula requisição de busca via Jina SERP e seleciona URLs relevantes para aprofundamento.
5. 🟡 O sistema valida as URLs contra o histórico da pesquisa corrente, descartando itens duplicados e despachando as novas para o Jina Reader (`r.jina.ai`).
6. 🟡 O modelo analisa o texto extraído **em RAM**, decide se necessita de buscas adicionais e devolve o resumo denso da persona com `urls_utilizadas` e `urls_lidas_nao_utilizadas`; o texto bruto é descartado nesse ponto (RF-15).
7. 🟡 O sistema agrega as 4 personas em um pacote consolidado do ponto (RF-11), persiste a rodada em `conteudo_coletado` (append-only, RF-12) sem qualquer corpo de página, atualiza o status na tabela `pontos` e retorna HTTP 200 com resumo das fontes catalogadas.

### 6.4 Fluxos Alternativos

**Fluxo Alternativo A — Reprocessamento de ponto específico falhado:**
1. 🟡 O usuário submete `POST /api/v1/search` informando `id_pesquisa` e o parâmetro opcional `ponto_id`.
2. 🟡 O sistema restringe o processamento exclusivamente ao ponto selecionado, **preservando** (não sobrescrevendo) as coletas anteriores, e cria uma nova rodada.

**Fluxo Alternativo B — Retry acionado pelo `audit` (v1.1):**
1. 🟡 O `audit` reprova um ponto e indica personas-alvo.
2. 🟡 O `pipeline_runner` chama o `search` com `personas=[...]` para aquele ponto.
3. 🟡 O sistema cria a rodada N+1, reaproveitando análises não refeitas a partir de **todas** as rodadas anteriores (RF-13), e mantém todas as rodadas no armazenamento.
4. 🟡 Ao final, o contexto do ponto passa a ser a união das rodadas 1..N+1.

**Fluxo Alternativo C — Execução sequencial (v1.1):**
1. 🟡 O chamador envia `execution_mode="sequential"`.
2. 🟡 O sistema processa os pontos em ordem crescente de `ponto_n`, aguardando cada ponto por completo antes do próximo.
3. 🟡 O status agregado é recalculado ao final, da mesma forma que no modo paralelo.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance de busca paralela | Tempo total < 300s para conjunto de N pontos | Processamento paralelo com LLM leve e raspagem assíncrona |
| RNF-02 | 🟡 Timeout operacional | Limite de 600s por chamada externa | Conforme restrição técnica do PRD |
| RNF-03 | 🟡 Resiliência de requisições externas | 1 tentativa inicial + 3 retries com backoff | Aplicado a requisições HTTP para Jina e endpoint LLM |
| RNF-04 | 🟡 Persistência | Banco de dados SQLite permanente | Sobrevivência de dados a redeploys de contêineres |
| RNF-05 | 🟡 Isolamento de memória | Memória conversacional restrita à chamada de ferramenta | Evita degradação de contexto e vazamento entre pontos |
| RNF-06 (v1.1) | 🟡 Zero truncamento | 0 caracteres cortados | Aplica-se a resposta da tool, histórico de retry e payload persistido |
| RNF-07 (v1.1) | 🟡 Paridade de transporte | 0 divergências entre Jina direta e proxy | Contrato em `sdd/proxy-jina-paridade-total.md` |
| RNF-08 (v1.1) | 🟡 Determinismo do modo sequencial | Ordem estrita por `ponto_n` | Sem concorrência entre pontos |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/search`
- 🟡 Orquestrador `core/searcher.py`
- 🟡 Cliente Jina SERP/Reader `tools/jina_client.py`
- 🟡 Repositório de persistência `db/research_repository.py`
- 🟡 Runner do pipeline `core/pipeline_runner.py` (propagação de `execution_mode` e retries)

**Comportamento esperado:**
🟡 Interface REST assíncrona que executa o pool de busca no modo solicitado, persistindo os resultados como nova rodada e devolvendo relatório estruturado com contagem de fontes e status de cada ponto investigado.

### 8.1 Contrato HTTP de entrada (v1.1)

```json
{
  "id_pesquisa": "uuid",
  "ponto_id": "uuid | null",
  "personas": ["historiador", "cetico"],
  "execution_mode": "parallel"
}
```

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `id_pesquisa` | string | sim | `min_length=1` |
| `ponto_id` | string \| null | não | Restringe o processamento a um ponto |
| `personas` | string[] \| null | não | Subconjunto não vazio, sem duplicatas, apenas as 4 canônicas |
| `execution_mode` | `"parallel"` \| `"sequential"` | não | Default `"parallel"`; valor fora do enum ⇒ 422 |

### 8.2 Contrato da tool de busca (v1.1)

🟡 A tool expõe duas operações; ambas devem ter comportamento **idêntico** nas rotas direta e proxy:

| Operação | Requisição | Resposta |
|---|---|---|
| `search(query, include_content, fresh)` | `GET {search_base}/{quote(query, safe="")}` com `Accept: application/json`, `Authorization: Bearer …`, `X-Retain-Images: none`, `X-No-Cache` opcional | Lista de itens com `title`, `url`, `description`, `timestamp` (quando houver) e `content` quando `include_content=True`. **Nenhum item descartado por tamanho.** |
| `read(target_url, fresh)` | `GET {reader_base}/{target_url}` com `Accept: text/markdown`, `Authorization: Bearer …`, `X-No-Cache` opcional | Texto Markdown **integral**, sem `slice`, sem limite de caracteres |

🟡 Erros: `{"code": >= 400, "data": null}` com HTTP 200 é erro de provedor, classificado pela tool (`classify_failure`) — nunca tratado como lista vazia nem como sucesso.

🟡 **Volatilidade (v1.2):** o texto integral devolvido por `read` é consumido em RAM pela persona e descartado ao fim do resumo. A tool não grava corpo em disco, cache persistente nem log; `include_content=True` da SERP segue a mesma regra.

### 8.3 Estados da API

- Estado vazio: 🟡 Requisição sem `id_pesquisa` retorna HTTP 422; `execution_mode` inválido retorna 422.
- Estado de carregamento: 🟡 Conexão mantida enquanto os trabalhadores realizam as chamadas externas.
- Estado de erro: 🟡 Resposta estruturada com detalhes da exceção, código interno e pontos que demandam reprocessamento.
- Estado de sucesso: 🟡 HTTP 200 contendo lista de pontos atualizados, volume de URLs lidas, total de conteúdo persistido e a rodada criada.

---

## 9. Modelo de Dados

```
conteudo_coletado {
  id: string (UUID)                // identificador exclusivo do registro de coleta
  id_pesquisa: string (UUID)       // referência à pesquisa raiz
  ponto_id: string (UUID)          // referência ao ponto de investigação
  rodada: integer                  // nº da passagem do ponto pelo search (1..4); append-only
  tema: string                     // tema de pesquisa associado
  ponto: string                    // descrição textual do ponto
  conteudo_coletado: text          // síntese da rodada a partir dos resumos das personas; nunca corpo de página
  urls_lidas: text (JSON array)    // todas as URLs consultadas na rodada
  urls_fonte: text (JSON array)    // URLs canônicas utilizadas na rodada
  metadados_coleta: text (JSON)    // fontes (catálogo com uso), resultados_personas, diario_acoes, recencia, auditorias
  criado_em: timestamp             // ISO 8601
}
```

🟡 **Invariante de escrita:** cada passagem cria nova linha com `rodada` incrementada. `UPDATE` em `conteudo_coletado`, `urls_lidas`, `urls_fonte` ou `metadados_coleta` de rodada anterior é proibido; apenas `metadados_coleta.auditorias` pode ser acrescentado pelo `audit` (histórico de pareceres).

**Estrutura de `metadados_coleta` (v1.2):**

```json
{
  "versao": 3,
  "fontes": {
    "src_1": {
      "source_id": "src_1",
      "url": "https://...",
      "titulo": "...",
      "status": "read_ok",
      "uso": "utilizada",
      "data_fonte": "YYYY-MM-DD"
    }
  },
  "resultados_personas": {
    "historiador": {
      "analise": "resumo denso com dados, números, datas e fatos",
      "conclusoes": [],
      "lacunas": [],
      "motivo_parada": "...",
      "sucesso": true,
      "urls_utilizadas": [],
      "urls_lidas_nao_utilizadas": [],
      "queries_executadas": 3
    }
  },
  "diario_acoes": { "historiador": [] },
  "recencia": {},
  "auditorias": []
}
```

🟡 Regras do resumo (`analise`):
- 🟡 É a **única** representação do conteúdo das páginas que atravessa estágios. Deve ser denso e autossuficiente: afirmações, números, métricas, datas, identificadores, tensões entre fontes e o que cada URL sustenta.
- 🟡 Não é transcrição literal nem recorte de página; é conhecimento destilado pelo especialista, sem limite artificial de tamanho (I-2).
- 🟡 `urls_utilizadas` lista as URLs que sustentaram o resumo; `urls_lidas_nao_utilizadas` lista as que foram abertas e descartadas por inutilidade ou repetição. Ambas são subconjuntos das URLs com `status=read_ok` no catálogo `fontes`.
- 🟡 `uso` no catálogo é atributo da URL no ponto (`utilizada` quando citada por alguma persona/rodada; `lida_nao_utilizada` caso contrário), não do parecer de auditoria.

🟡 **Campos proibidos no schema (v1.2):** qualquer chave que carregue corpo de página, excerto, offsets, hash de corpo ou seleção de excertos por orçamento. Uma rodada que os contenha viola o contrato e é rejeitada na escrita.

**Migrações necessárias:** 🟡 Nenhuma coluna nova: `rodada`, `conteudo_coletado` e `metadados_coleta` já existem. `conteudo_coletado` passa a receber a síntese da rodada, não o corpo. Linhas anteriores à v3 que ainda guardem corpo bruto **não são lidas** por `audit` nem `writer` (I-2 v3); o schema novo não admite esses campos em rodadas novas. Requer-se índice/queries ordenando por `rodada` crescente em `get_collected_content_for_point`.

---

## 9-A. Contrato do bruto volátil (v1.2)

🟡 O bruto da Jina é insumo de inferência, não dado de negócio.

| Dado | Onde vive | Ciclo de vida | Persistido? |
|---|---|---|---|
| Texto integral da página (Reader) e `content` da SERP | RAM do processo da persona | Da leitura até a produção do resumo | ❌ Nunca |
| Resumo denso (`analise`) | RAM → SQLite (`metadados_coleta.resultados_personas`) | Permanente, append-only por rodada | ✅ |
| Catálogo de URLs (`fontes` com `uso`) | SQLite | Permanente, consolidado por rodada | ✅ |
| Parecer de auditoria | SQLite (`metadados_coleta.auditorias`) | Permanente, append | ✅ |

🟡 Regras de descarte:
- 🟡 O buffer do bruto é liberado ao fim de cada persona, antes da consolidação do ponto. Não se mantém bruto "para o caso de retry".
- 🟡 Proibido gravar bruto em arquivo temporário, cache em disco, log, trace, artefato de teste ou backup. Diagnóstico registra metadados (URL, status, tamanho, latência), nunca o conteúdo.
- 🟡 Retry que precise reler uma página refaz a chamada à Jina; não existe reidratação de corpo a partir do banco.
- 🟡 Falha da persona antes do resumo ⇒ rodada registra a falha, as URLs lidas entram no catálogo com `uso=lida_nao_utilizada`, e nenhum bruto parcial é promovido a registro.
- 🟡 O que `audit` e `writer` recebem é sempre `resultados_personas[*].analise` + `urls_utilizadas` + `urls_lidas_nao_utilizadas` + catálogo `fontes`; nunca conteúdo de página.

🟡 Consequência para o zero truncamento (I-2): o corte proibido incide sobre o **resumo** e as listas de URLs. O bruto não é truncado porque não é retido — ele é consumido integralmente pela persona e descartado.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 Jina SERP (`s.jina.ai`) | Obrigatória | Erro HTTP 502 após 1 tentativa + 3 retries; gravação de coleta abortada |
| 🟡 Jina Reader (`r.jina.ai`) | Obrigatória | URL marcada como não lida; persona pode concluir com lacuna explícita |
| 🟡 Cloudflare Proxy Worker (opcional) | Opcional | Se configurado como base URL, deve ser indistinguível da rota direta; divergência é bug de contrato |
| 🟡 LLM OpenAI-compatible (Leve) | Obrigatória | Erro HTTP 502 ou 504 por expiração do timeout de 600s; ponto permanece pendente |
| 🟡 SQLite Permanente | Obrigatória | Erro crítico HTTP 500 impedindo consulta de pontos e persistência de coletas |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Pesquisa não encontrada no banco | 🟡 `id_pesquisa` ausente na tabela `pesquisa` | HTTP 404 com detalhe informando identificador não localizado |
| EC-02: Indisponibilidade de rede ou falha do Jina Reader | 🟡 Jina retorna erro 500, 502 ou 503 | 3 retries com backoff exponencial; mantida a falha, preserva dados parciais da SERP e registra a URL como não lida |
| EC-03: Timeout de execução do LLM leve | 🟡 Inferência ultrapassa o limite | Cancela a conexão, registra log estruturado e assinala o ponto para retry posterior |
| EC-04: Todas as URLs da SERP já catalogadas | 🟡 Filtro deduplicador rejeita 100% dos links | Sinaliza ao LLM para formular termos alternativos sob novo prisma |
| EC-05: Variáveis de ambiente de personas ausentes | 🟡 Inicialização sem definição das 4 personas | Falha crítica; recusa o processamento sem configuração hardcoded |
| EC-06 (v1.1): `execution_mode` inválido | 🟡 Valor fora de `parallel`/`sequential` | HTTP 422 com detalhe do enum; nenhum ponto processado |
| EC-07 (v1.1): `sequential` com N grande | 🟡 N pontos acima do tempo aceitável pelo cliente HTTP | Processamento continua; o cliente deve usar timeout compatível; o sistema não troca de modo |
| EC-08 (v1.1): resposta do proxy diverge da direta | 🟡 Status/corpo/headers diferentes para a mesma consulta | Erro de contrato: a tool classifica como falha de provedor e o caso vira bug bloqueante do proxy |
| EC-09 (v1.1): histórico de retry não cabe no LLM | 🟡 Acervo acumulado de resumos excede a janela do provedor | Insuficiência explícita com diagnóstico; proibido cortar resumo ou descartar rodada |
| EC-10 (v1.1): persona ausente na última rodada | 🟡 Retry focado em subconjunto de personas | Reaproveita a persona da rodada mais recente que a contenha (RF-13) |
| EC-11 (v1.2): persona termina sem resumo | 🟡 Falha do LLM antes de devolver `analise` | Rodada registra falha explícita; URLs lidas entram no catálogo como `lida_nao_utilizada`; nenhum bruto é persistido para "não perder o trabalho" |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Acesso condicionado a bearer token validado em camada de middleware FastAPI.
- **Autorização:** 🟡 Requisições autorizadas para usuários e sistemas integradores autenticados.
- **Dados sensíveis:** 🟡 Credenciais de acesso à API do Jina e aos modelos LLM armazenadas em tabela criptografada ou variáveis de contêiner. No proxy, a credencial do cliente autentica o proxy e nunca é repassada à Jina.
- **Auditoria:** 🟡 Registro de eventos com timestamps, `id_pesquisa`, `rodada`, URLs lidas, tempo de resposta por ponto, `execution_mode` e códigos HTTP gerados.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação direta modular em contêiner Docker com arquitetura monolito, validando os contratos de rota via testes automatizados, incluindo teste de paridade direta × proxy.
- **Como reverter (rollback):** 🟡 Restauração da imagem anterior estável do contêiner e retenção do arquivo SQLite em volume persistente.
- **Monitoramento pós-deploy:** 🟡 Latência de scraping, volume de URLs duplicadas descartadas, taxa de erro HTTP 5xx, contagem de rodadas por ponto, **bytes de bruto persistidos (deve ser 0)** e divergências de contrato do proxy nas primeiras 48h.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: Qual a quantidade máxima de iterações de busca que o LLM leve pode acionar por ponto investigativo? | Médio | dev-integrador | 2026-10-31 |
| OQ-02 | 🟡 ✅ RESOLVIDA em v1.1 e reafirmada em v1.2: não existe limite em megabytes para o acervo de resumos; volume excessivo gera insuficiência explícita no estágio consumidor, nunca corte. O corpo bruto não é retido, logo não há acervo de páginas a limitar. | Baixo | analista-research | 2026-11-02 |
| OQ-03 (v1.1) | 🟡 ⚠️ ABERTO: o modo `sequential` deve ser usado em produção para contornar rate limit da Jina ou permanece como ferramenta de diagnóstico? | Médio | dev-integrador | 2026-10-31 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Processamento concorrente em paralelo como default | Execução sequencial ponto a ponto como único modo | Mantém a meta de < 10 minutos; o modo sequencial passa a ser escolha explícita do chamador |
| 🟡 `execution_mode` no payload HTTP | Variável de ambiente global | O requisito é escolha por chamada; env global não permite alternar sem redeploy |
| 🟡 Descarte de URLs lidas por pesquisa via filtro de histórico | Repetir a leitura de páginas já consultadas | Minimiza latência e previne desperdício de cota |
| 🟡 Memória transitória restrita a chamadas de ferramentas | Manter histórico conversacional completo acumulado | Previne saturação de contexto no LLM leve e contaminação entre pontos |
| 🟡 (v1.1) Zero truncamento com falha explícita no lugar de corte | Cortar para caber no contexto | Corte silencioso contamina auditoria e redação; insuficiência explícita é auditável |
| 🟡 (v1.1) Histórico append-only por rodada | Sobrescrever a coleta do ponto a cada retry | Retries existem para ampliar evidência; descartar rodadas anteriores joga fora coleta paga |
| 🟡 (v1.1) Agregação das 4 personas por ponto em um pacote | Enviar personas separadas ao auditor | O auditor precisa da visão unificada para responder as 12 perguntas com triangulação |
| 🟡 (v1.1) Proxy tratado como túnel, não gateway | Manter rotação/inspeção alterando payload | Paridade é requisito de contrato; observabilidade vai para log, não para a resposta |
| 🟡 (v1.2) Bruto da Jina só em RAM, descartado ao fim da persona | Persistir corpo integral com hash e offsets por rodada | O bruto não é relido por nenhum estágio; persistir infla o banco e expõe conteúdo sem uso |
| 🟡 (v1.2) Resumo denso + listas de URLs como único handoff | Excertos literais com offsets e seleção por orçamento | Elimina offsets, seleção por corte e a tentação de reidratar páginas; auditoria passa a julgar afirmação + URL |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md` — I-2 v3, I-4, I-5)
- Adendo v9 — bruto volátil e contrato de dados v3 (`_reversa_sdd/sdd/addendum-confiabilidade-20261102-v9-bruto-volatil.md`)
- Critérios de auditoria (`app/CRITERIA.md` v3)
- Spec do Proxy Jina (`_reversa_sdd/sdd/proxy-jina-paridade-total.md`)
- Especificação de Personas (`_reversa_sdd/personas.md`)
- Documentação da API Jina Reader (`https://r.jina.ai`) e Search (`https://s.jina.ai`)

### Mapa de conformidade do código

| Requisito | Arquivo | Ponto | Estado |
|---|---|---|---|
| RF-09 | `app/schemas/search.py` | `SearchRequest` | ❌ campo inexistente |
| RF-09 | `app/core/searcher.py` | `execute_search` (gather ~1863) | ❌ somente paralelo |
| RF-14 | `app/core/searcher.py` | histórico de persona em retry | ❌ serializa passagens de rodada anterior em vez de resumos |
| RF-13 | `app/core/searcher.py` | `coletas_anteriores[-1]` (~1450) | ❌ só a última rodada |
| RF-10 | `app/tools/jina_client.py` | `search` / `read` | ✅ sem corte no corpo; documentar contrato |
| RF-12 | `app/db/research_repository.py` | `save_collected_content(rodada=...)` | ✅ append-only por rodada |
| RF-11 | `app/core/searcher.py` | `resultados_personas` (~1435) | ✅ consolidação por ponto |
| RF-15 / RF-16 | `app/core/searcher.py` | `fontes`/`chunks` da coleta (~677) | ❌ persiste corpo e derivados posicionais; catálogo `uso` existe parcialmente (~332) |

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração inicial da especificação formal do endpoint de busca com personas |
| 1.1 | 2026-10-27 | reversa-spec-sdd | Invariantes I-1..I-5; `execution_mode`; zero truncamento; agregação por ponto; histórico append-only; correção `s.jina.ai` (SERP) vs `r.jina.ai` (Reader) |
| 1.2 | 2026-11-02 | reversa-spec-sdd | Norma v3: bruto da Jina só em RAM e descartado ao fim da persona; `metadados_coleta` sem corpo/excertos/offsets; resumo denso + `urls_utilizadas`/`urls_lidas_nao_utilizadas` como único handoff; RF-15/RF-16; §9-A |
