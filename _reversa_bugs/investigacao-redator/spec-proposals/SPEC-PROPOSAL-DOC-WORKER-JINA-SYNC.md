# Proposta de Especificação Técnica: Fluxo Cognitivo de Coleta Integral Jina, Barreira das 4 Personas e Briefing Síncrono

> **Identificador da Proposta:** `PROP-20261019-DOC-WORKER-JINA-SYNC`  
> **Status:** Proposta Documental Pré-Aprovação (Reversa Debugger / Spec-Proposals)  
> **Data:** 2026-10-19  
> **Contexto:** `investigacao-redator`  
> **Autoridade:** Decisão explícita do operador registrada no intake `relato-20261019-2100-doc-worker-jina-sync.md`  
> **Regra de Não-Regressão / Limite de Atuação:** Este documento é um adendo proposto para posterior consolidação via `/reversa-sync` e `/reversa-docs`. Conforme a regra do `reversa-debugger`, arquivos canônicos existentes em `_reversa_sdd/`, `_reversa_forward/` e código em `app/` permanecem intocados.

---

## 1. Declaração do Contrato Desejado pelo Operador

Em deliberação de 2026-10-19, o operador estabeleceu as seguintes regras taxativas para o pipeline de investigação e briefing:

1. **Garantia de Conteúdo Útil dos Workers:** O worker nunca deve retornar resposta analítica vazia. A premissa cognitiva é que a leitura das páginas fornecidas pela Jina sempre gera aprendizado relevante para o ponto investigado.
2. **Entrega de 10 Páginas Integrais em Texto Limpo:** A ferramenta Jina não deve entregar snippets, títulos soltos ou resumos recortados. Deve retornar 10 páginas prontas para leitura, enviadas **integralmente** ao worker.
3. **Limpeza e Parser Prévio de HTML:** Antes de o texto chegar ao modelo, o sistema deve aplicar parser de limpeza eliminando lixo de cabeçalho, navegação, rodapé, anúncios e scripts, preservando a totalidade do corpo informativo.
4. **Ciclo de Investigação por Ponto (Persona + Ponto + Tool):**
   - O worker é instanciado com `(personalidade, ponto_de_investigacao, tool_jina)`.
   - O worker formula e aciona a primeira query na tool Jina.
   - A tool executa a busca e entrega os 10 textos integrais limpos.
   - O worker analisa o material e coleta informações relevantes para o ponto.
   - O worker decide internamente se o material já é suficiente ou se necessita formular uma nova busca (teto rígido de até 3 queries no total).
   - O worker devolve resposta estruturada com tudo o que apurou relevante.
5. **Persistência Individual antes do Merge:** A resposta estruturada de cada uma das 4 personas é gravada individualmente no banco de dados antes de qualquer etapa de consolidação.
6. **Merge e Barreira das 4 Personas antes da Auditoria:** As 4 personas (`historian`, `skeptic`, `pragmatist`, `futurist`) executam sua busca e análise. O ponto só transita para auditoria quando **todas as 4 personas devolverem resposta** e os dados forem unificados por um procedimento de merge/conexão.
7. **Briefing Estritamente Síncrono (Sem Polling / Sem HTTP 202):** A geração do briefing é rápida e não deve exigir background tasks, filas nem polling periódico do cliente. A requisição HTTP de criação/revisão deve responder diretamente de forma síncrona com o briefing concluído e código HTTP 200/201.

---

## 2. Diagnóstico Técnico Somente Leitura: Código Atual vs Documentação

A confrontação estrita entre as decisões do operador, o código implementado e as especificações vigentes revelou as seguintes divergências estruturais:

### 2.1 Tool Jina: Snippets de SERP vs Leitura Integral de 10 Páginas
- **Código Atual (`app/investigation/tools.py:10, 58-78, 165-171`):**
  - O adaptador aponta para `https://s.jina.ai/` (Jina Search API).
  - O método `_parse_body` extrai apenas os campos `title`, `description`, `content`, `text` e `snippet` retornados pelo payload de busca JSON.
  - **Evidência limitada:** O parser concatena campos do payload, incluindo `content` e `text`. Isso não prova que todo retorno seja snippet nem que contenha páginas completas. Não existe nessa função verificação de dez corpos integrais. A forma real do payload deve ser comprovada antes de concluir que Jina Search precisa ser substituída ou acoplada a outro endpoint.
  - **Protocolo a verificar:** Search e Reader são endpoints distintos. O pedido determina conteúdo integral limpo, não troca de endpoint. Inspecionar contrato oficial e payload efetivo do adaptador antes de decidir se leitura adicional é necessária. Não pressupor retorno apenas SERP nem adicionar Reader sem evidência.
  - **Código Fallback DuckDuckGo (`app/investigation/tools.py:178-183`):** Retorna no máximo 5 snippets (`_duckduckgo_search(query, 5)`), em desacordo com o contrato de 10 páginas completas.
- **Spec Vigente (`_reversa_forward/002-investigacao-personas/requirements.md:86, 96`):**
  - Declarava em RN-05 apenas requisição POST a `s.jina.ai` com JSON `{"q": query}` e retenção de URLs em `read_urls` (RN-08), sem detalhar a leitura de 10 corpos integrais nem o parser anti-boilerplate.

### 2.2 Barreira das 4 Personas e Merge antes do Auditor
- **Código Atual (`app/investigation/service.py:280-355`):**
  - Executa as personas em paralelo via `asyncio.gather(*tasks)`.
  - Contudo, a spec de auditoria em `_reversa_forward/003-modulo-auditoria/requirements.md` e a regra RN-301 permitiam "sucesso parcial" (bastava 1 persona concluir para tentar auditoria), sem prever explicitamente a etapa formal de **merge dos dados das 4 personas** antes da auditoria.
  - O código atual não possui uma entidade ou rotina explícita de `merge` documental consolidando as 4 visões antes de repassar ao `AuditService`.
- **Contrato do Operador:** Exige barreira estrita (esperar todas as 4 personas devolverem resposta) e um merge de conexão antes da avaliação do auditor.

### 2.3 Briefing Síncrono vs Assíncrono / Polling
- **Código Atual (`app/routers/research.py:166-198`):**
  - O branch de trabalho já contém uma alteração síncrona: executa `points = await scout(research.theme, db)` diretamente dentro de `create_research` e retorna o rascunho preenchido em `briefing_draft` com status `PENDING_APPROVAL`.
  - Entretanto, o endpoint secundário e o histórico em `app/briefing/service.py` e `docs/api/briefing-scout.md:34` ainda instruem: *"A geração é assíncrona... repita GET /briefings/{id} até status ser draft"*.
  - O `README.md` (linhas 33-50) e `contracts.md` ainda descrevem a operação de briefing como assíncrona com polling.

---

## 3. Especificação do Novo Fluxo (Proposta SDD)

### 3.1 Arquitetura da Ferramenta de Pesquisa do Worker (`JinaFullReaderAdapter`)

```
                  +----------------------------------------------+
                  | Worker (Persona + Ponto de Investigação)     |
                  +----------------------------------------------+
                                         |
                            1. query(q)  | (máx 3 por rodada)
                                         v
                  +----------------------------------------------+
                  | Jina Tool Adapter (Investigação)            |
                  +----------------------------------------------+
                                         |
                     2. Search / Discover (10 URLs)
                                         v
                  +----------------------------------------------+
                  | Provedor Jina (Search + Reader)             |
                  +----------------------------------------------+
                                         |
                     3. Coleta de 10 páginas completas
                                         v
                  +----------------------------------------------+
                  | Pipeline de Limpeza / Boilerplate Parser    |
                  | (Remove headers, nav, footers, scripts, ads) |
                  +----------------------------------------------+
                                         |
                     4. 10 Textos Integrais Limpos
                                         v
                  +----------------------------------------------+
                  | Contexto do Worker (RAM / Tool Output)       |
                  +----------------------------------------------+
```

#### Regras de Extração e Limpeza:
1. **Seleção de Fontes:** Cada busca deve obter 10 fontes independentes com conteúdo substantivo.
2. **Parser Anti-Boilerplate:**
   - Remoção de tags `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>`, menus de acessibilidade e caixas de cookies/consentimento LGPD.
   - Extração do nó textual principal (ex.: `<main>`, `<article>`, ou heurística de densidade de texto com stdlib `HTMLParser`).
   - O texto entregue ao worker deve ser o corpo do artigo/página na íntegra, estruturado com títulos e parágrafos legíveis.

### 3.2 Ciclo Cognitivo do Worker (Persona + Ponto)
1. **Entrada do Worker:**
   - Prompt de Identidade da Persona (`historian`, `skeptic`, `pragmatist`, `futurist`).
   - Enunciado e descrição do Ponto de Investigação.
   - Definição da tool `jina_search` (capacidade de retornar páginas completas limpas).
2. **Loop de Deliberação (Orçamento de até 3 Queries):**
   - **Query 1:** Obrigatória. O worker elabora sua primeira pergunta investigativa direcionada à sua lente e ao ponto.
   - **Ingestão:** Recebe as 10 páginas integrais em texto limpo.
   - **Análise & Avaliação de Suficiência:** O modelo avalia se as evidências coletadas cobrem integralmente o ponto:
     - Se suficiente: interrompe voluntariamente as buscas e gera a síntese analítica final.
     - Se insuficiente e ainda dentro do teto (< 3 queries): formula uma nova query de refinamento.
   - **Teto Rígido:** Atingidas 3 queries, o loop é travado e o worker é obrigado a sintetizar todo o material acumulado.
3. **Garantia de Não-Vazio:**
   - O worker é instruído e validado para nunca retornar síntese nula ou vazia. Havendo lido páginas limpas, ele deve obrigatoriamente reportar os fatos, contextos, contradições ou dados apurados.

### 3.3 Persistência Individual, Barreira de Sincronização e Merge
1. **Persistência Imediata (Append-Only):**
   - Ao concluir sua síntese, cada persona grava seu resultado estruturado em `research_step_results` com status `COLLECTED` (ou equivalente).
   - O registro inclui: `result` (texto analítico), `used_urls` (fontes citadas), `read_urls` (as 10 URLs lidas por query) e identificador da persona.
2. **Barreira das 4 Personas:**
   - O ponto mantém status `SCRAPER_IN_PROGRESS` até que o contador de personas concluídas atinja exatamente 4 (`historian`, `skeptic`, `pragmatist` e `futurist`).
   - Nenhuma transição para auditoria ocorre antes de todas as 4 terem gravado seu resultado.
3. **Etapa de Merge Inter-Personas:**
   - Concluídas as 4 personas, executa-se a função de consolidação (`merge_point_personas_evidence`):
     - Unifica os 4 textos analíticos em uma visão integrada por facetas (histórica, cética, pragmática, prospectiva).
     - Consolida a lista unificada de alegações, evidências e URLs únicas.
     - Grava o artefato fundido (ex.: em campo dedicado ou tabela de auditoria).
4. **Disparo do Auditor:**
   - Somente após o merge concluído o ponto transita para `AUDIT_PENDING`, acionando o `AuditService.audit_point` sobre o conjunto completo das 4 personas.

### 3.4 Briefing Estritamente Síncrono
1. **Sem Polling / Sem HTTP 202:**
   - `POST /api/research` ou `POST /briefings` opera de forma estritamente síncrona no transporte HTTP.
   - A requisição aguarda o término da consulta e da formulação do Scout. Latência não foi medida neste diagnóstico.
   - Responde diretamente com o briefing concluído; preservar schema, quantidade de pontos e código de sucesso do contrato canônico, alterando apenas onde houver conflito explícito com ausência de polling.
2. **Preservação de Async Interno:**
   - O backend utiliza corrotinas nativas (`async/await`) sem delegar geração para tarefas desvinculadas de background que exijam polling por parte da UI. Investigação posterior pode continuar em background conforme contrato já aprovado.
3. **Tratamento de Timeout:**
   - Este pedido não define timeout numérico nem troca de modelo. Preservar configuração existente até decisão baseada no caminho efetivo de geração. Briefing síncrono não elimina possibilidade de falha externa.

---

## 4. Distinção entre Contrato Desejado e Realidade Operacional (Gaps Mapeados)

Para manter a integridade arquitetural do sistema e não gerar falsas premissas de engenharia, registra-se formalmente:

| Aspecto | Contrato Desejado pelo Operador | Realidade Operacional / Limite Físico Upstream | Lacuna Aberta (Decisão Requerida) |
|---|---|---|---|
| **Volume Upstream Jina** | "Jina SEMPRE devolve 10 sites prontos para leitura" | Provedor de busca externo pode retornar menos de 10 resultados para temas ultranichados ou indisponibilidade parcial | **G-NEW-01:** Como o pipeline deve se comportar se Jina retornar N < 10 (ex.: 6 resultados)? Aceitar os N disponíveis ou disparar retry automático? |
| **Janela de Contexto LLM** | 10 páginas integrais enviadas de uma vez ao worker | 10 páginas web integrais limpas podem somar de 20.000 a 100.000 tokens por busca. Com 3 buscas, até 300.000 tokens | **G-NEW-02:** O modelo selecionado para as personas suporta a janela necessária? Se uma página exceder 50.000 caracteres, há teto máximo por página antes da entrega? |
| **Falha de Rede / Erro 5xx no Reader** | Páginas sempre lidas | Falha de DNS, HTTP 403/429 ou paywall no site de destino | **G-NEW-03:** Em caso de falha de download de uma URL específica, descarta silenciosamente ou tenta URL substituta? |
| **Falha Definitiva de 1 Persona** | Auditoria aguarda as 4 personas | Uma persona pode estourar timeout fatal (ex.: 600s) | **G-NEW-04:** Qual a política de barreira se uma persona falhar terminalmente? O ponto aborta/retenta ou o auditor roda com as 3 restantes com caveat? |

---

## 5. Cenários de Aceite Verificáveis (BDD / Gherkin)

```gherkin
Cenário 1: Entrega de 10 páginas integrais em texto limpo ao worker
  Dado que o worker da persona "historian" foi instanciado para o ponto 1
  Quando o worker invoca a tool "jina_search" com a query "origem e precedentes da IA médica"
  Então a tool deve consultar o provedor de busca e leitura Jina
  E o parser anti-boilerplate deve expurgar cabeçalhos, menus, rodapés e scripts
  E o worker deve receber o corpo textual integral das 10 páginas
  E nenhum conteúdo deve ser reduzido a snippet curto de busca.

Cenário 2: Parada voluntária do worker respeitando teto de 3 queries
  Dado que o worker recebeu o conteúdo integral da primeira query
  Quando o worker avalia que as evidências respondem satisfatoriamente ao ponto
  Então o worker deve interromper as chamadas de busca sem atingir o teto de 3
  E retornar resposta estruturada não-vazia com as URLs utilizadas e citações verbatim.

Cenário 3: Respeito ao limite máximo de 3 queries pelo worker
  Dado que um worker necessita de aprofundamento adicional
  Quando o worker executa a 3ª consulta de busca
  Então a tool desativa chamadas adicionais
  E o worker é obrigado a compilar suas conclusões com base no material acumulado.

Cenário 4: Persistência individual e barreira sincronizada das 4 personas
  Dado um ponto de pesquisa em andamento na fase SCRAPER
  Quando as personas "historian", "skeptic" e "pragmatist" concluem suas sínteses
  Então seus resultados são gravados individualmente em "research_step_results"
  E o ponto NÃO é submetido à auditoria
  Quando a 4ª persona "futurist" conclui e grava seu resultado
  Então o sistema executa o merge das informações das 4 personas
  E transita o ponto para "AUDIT_PENDING", notificando o auditor.

Cenário 5: Criação de briefing síncrono sem polling
  Dado uma requisição POST para criação de briefing com tema válido
  Quando o servidor processa a requisição
  Então o Scout executa a SERP e a IA na própria requisição HTTP
  E a resposta HTTP retorna status 201 com os 3 a 7 pontos em "briefing_draft"
  E o cliente não necessita efetuar chamadas repetidas de polling (GET de espera).
```
