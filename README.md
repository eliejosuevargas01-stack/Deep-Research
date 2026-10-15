# Deep Research

Criei o Deep Research inicialmente no n8n. Cheguei à primeira versão funcional em 15 dias; até o 17º dia do projeto, nas minhas execuções, reduzi o tempo de pesquisa de pelo menos 20 para cerca de 4 minutos, varrendo mais de 100 sites.

Depois acrescentei RAG e vetorização para o agente reaproveitar informações coletadas. Agora estou migrando a ideia para **Python e FastAPI**. Essa implementação continua em desenvolvimento; os resultados de tempo acima pertencem à versão n8n.

## O que construí no n8n

Organizei o sistema em planejamento, coleta, auditoria e redação, com chamadas por API e entrega do relatório por callback:

- **Planejamento com quatro personas:** fatos essenciais, análise técnica, mercado/consumidor e verificação cética. Consolido as perguntas, removo duplicidades e gravo as etapas em n8n Data Tables.
- **Coleta:** integro APIs de LLMs, SERP Google via Apify, leitura de páginas com Jina e uma alternativa de busca Jina/Bing. Também utilizo SerpApi em fluxos auxiliares do meu ecossistema.
- **RAG:** consulto e alimento um cache vetorial no Supabase com embeddings de 768 dimensões e metadados de fontes, confiabilidade e idade da informação, para reduzir coletas repetidas.
- **Controle de execução:** mantenho fases, tentativas e marcações de processamento em Data Tables. Um fluxo agendado identifica etapas travadas e prepara sua retomada.
- **Entrega:** o redator consolida o relatório e o envia à URL de callback informada pelo cliente.

A configuração n8n consultada pela API em 15/10/2026 contém 5 fluxos habilitados de pesquisa e recuperação, com 111 nós. O fluxo separado de limpeza de cache em 30 dias está desabilitado nessa configuração; não prometo atualização automática de todo conteúdo reutilizado.

## Migração para Python/FastAPI

Neste repositório, estou levando a arquitetura para código com apoio de IA e Spec-Driven Development (SDD), conectando requisitos, cenários de aceite, implementação e testes. As seções abaixo documentam o desenho da versão Python e suas interfaces; a integração completa com provedores reais segue em desenvolvimento.

---

## 1. Briefing & Scout

Agente inicial de exploração cognitiva equipado com:
* **Tool de Pesquisa Web**: busca rápida e direcionada via Jina SERP.
* **Tool de Leitura de Arquivos**: varredura de referências e documentos prévios.

### Operação via API

- Geração de briefing: LLM **assíncrono** (Jina SERP + ag. LLM 3–7 pontos), aprovação humana única, controle CAS de versão v1..vN, reabertura, leitura read-only e histórico de versões.
- Documentação técnica detalhada da API: [docs/api/briefing-scout.md](docs/api/briefing-scout.md).

#### Quickstart via API (cURL)

```bash
# 1. Criar briefing (assíncrono; 201 retorna snapshot do draft)
BRIEFING_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $API_AUTH_SECRET" \
  -H "Content-Type: application/json" \
  https://api.deepresearchengine.com/v1/briefings \
  -d '{"theme": "impacto da IA na medicina"}' | jq -r '.id')

# 2. Consultar status / pontos
curl -s -H "Authorization: Bearer $API_AUTH_SECRET" \
  https://api.deepresearchengine.com/v1/briefings/$BRIEFING_ID | jq '{status, points}'

# 3. Opcional: editar pontos (somente em draft, versão +1)
curl -s -X PATCH -H "Authorization: Bearer $API_AUTH_SECRET" \
  -H "Content-Type: application/json" \
  https://api.deepresearchengine.com/v1/briefings/$BRIEFING_ID \
  -d '{"points":[{"title":"p1","description":"d1"},{"title":"p2","description":"d2"},{"title":"p3","description":"d3"}]}'

# 4. Aprovar (draft → approved, versão +1, define approved_at)
curl -s -X POST -H "Authorization: Bearer $API_AUTH_SECRET" \
  https://api.deepresearchengine.com/v1/briefings/$BRIEFING_ID/approve -d '{}'

# 5. Consumir aprovado (read-only; 409 se não aprovado)
curl -s -H "Authorization: Bearer $API_AUTH_SECRET" \
  https://api.deepresearchengine.com/v1/briefings/approved/$BRIEFING_ID | jq '.'
```

> [!TIP]
> Erros 409 (concorrência CAS): reenviar a operação com a versão corrente. Erros 503 (SERP/LLM): retry exponencial, ≤4 tentativas. Veja o guia de referência completo em [docs/api/briefing-scout.md](docs/api/briefing-scout.md).

### Objetivo
Realizar o *scout* do assunto, reconhecer o terreno e responder perguntas preliminares essenciais:
* *O que é central para este tema?*
* *Quais tópicos e debates são recorrentes em fontes independentes?*
* *Quais dimensões exigem aprofundamento investigativo?*

> **Interação Humana (Human-in-the-Loop):**
> O rascunho de escopo (composto por 5 pontos centrais e definição de paralelismo/sequencialidade) é apresentado ao usuário para aprovação ou edição em rodada única. Uma vez aprovado ou ajustado, o pipeline avança automaticamente para a etapa de pesquisa massiva.

---

## 2. Workers de Pesquisa (4 Personas Especialistas)

Para cada um dos 5 pontos definidos no briefing, 4 agentes com vieses cognitivos complementares atuam em paralelo (totalizando até 20 workers simultâneos):

### Personas e Perspectivas

1. **O Historiador Contextual (Perspectiva de Base e Evolução)**
   * **Função:** Mapeia definições fundamentais, termos técnicos, antecedentes históricos e o consenso do estado da arte. Impede que o relatório comece sem base sólida.
   * **Pergunta Interna:** *"O que já está universalmente aceito sobre isso até o momento e como chegamos aqui?"*

2. **O Cético Analítico (Perspectiva de Contraponto e Crítica)**
   * **Função:** Varre a web em busca de críticas acadêmicas, falhas, vieses de confirmação, contra-argumentos de mercado e gargalos técnicos, assegurando imparcialidade.
   * **Pergunta Interna:** *"Onde estão as falhas nessa teoria/tecnologia e quais são os principais argumentos contra ela?"*

3. **O Pragmático Aplicado (Perspectiva Prática e Estudo de Caso)**
   * **Função:** Foca em dados empíricos do mundo real, benchmarks, métricas de desempenho, casos de uso práticos, custos de implementação e impacto operacional.
   * **Pergunta Interna:** *"Como isso funciona na prática, quais são os exemplos reais e o que os dados numéricos comprovam?"*

4. **O Visionário Futurista (Perspectiva de Tendência e Inovação)**
   * **Função:** Investiga patentes recentes, artigos de vanguarda, pesquisas em andamento e previsões de especialistas para os próximos 5 a 10 anos.
   * **Pergunta Interna:** *"Para onde isso está evoluindo e quais são as tendências emergentes ou tecnologias disruptivas associadas?"*

### Arquitetura da Tool de Coleta e Leitura
Os workers utilizam uma tool unificada com subfluxo integrado:
* **Entrada:** Query refinada pelo agente.
* **Mecanismo de Busca:** Consulta via Jina Scraper, Apify ou SerpAPI.
* **Leitura Massiva:** Extração e parsing de 5 a 10 páginas por rodada utilizando Jina Reader (ou correspondente).
* **Processamento & Limpeza:** Função de sanitização que consolida, limpa o ruído do HTML/Markdown e devolve o compilado de evidências estruturadas diretamente ao agente.

---

## 3. Auditor (Orquestrador & Juiz)

* **Lente Cognitiva:** Isenta, crítica, fria e focada na qualidade, lógica e conformidade dos dados coletados.
* **Operação:** Opera sem tools de busca externas — atua exclusivamente na validação analítica e síntese estrutural.

### Responsabilidades
* **Mapeamento de Contradições:** Identifica divergências entre as evidências dos agentes (ex: Cético vs. Visionário) e define como estruturar o debate.
* **Controle de Alucinação & Veracidade:** Audita se todas as alegações contêm links e citações de fontes reais auditadas.
* **Criação do Roteiro (Outline):** Constrói a estrutura hierárquica ideal de tópicos em formato de esqueleto/sumário para o Redator.
* **Loop de Qualidade:** Avalia se o ponto de pesquisa foi satisfatório (`APPROVED` / `RETRY`). Limite máximo de **3 retries após a execução inicial**, totalizando até 4 execuções dos workers por ponto. Atingido o limite, o *blocker* é ativado e os dados acumulados seguem diretamente para o redator final com as devidas ressalvas.

> **Prompt de Perspectiva:**
> *"Você é um editor-chefe acadêmico e auditor de fatos. Seu trabalho é garantir que a pesquisa coletada seja robusta, sem furos lógicos e estruturada no melhor sumário possível."*

---

## 4. Redator (Sintetizador & Lapidador)

* **Lente Cognitiva:** Didática, fluida, integradora e focada na experiência do leitor final.
* **Operação:** Opera sem tools externas, consumindo estritamente as evidências e o roteiro aprovados pelo Auditor.

### Responsabilidades
* **Fluidez Textual:** Transforma notas brutas e descobertas isoladas em uma narrativa técnica coesa, eliminando redundâncias.
* **Garantia de Tom & Formatação:** Gera relatório Markdown de alta densidade informativa, utilizando tabelas comparativas, destaques e links canônicos de fontes.
* **Fidelidade ao Roteiro:** Respeita com rigor a taxonomia do Auditor, sem adicionar inferências não respaldadas por evidências coletadas.
* **Callback & Entrega:** Para o frontend, a URL de callback é opcional e configurada na página de configurações. Clientes backend-to-backend não têm essa página e podem enviar `callback_url` opcional em cada request de pesquisa. O relatório final é sempre persistido e pode ser consultado por ID pela API ou pela interface frontend; quando houver callback, o backend também despacha o relatório para esse destino. Falha no webhook não remove nem bloqueia o acesso ao relatório.

> **Prompt de Perspectiva:**
> *"Você é um redator técnico sênior especializado em transformar relatórios complexos em documentos Markdown claros, escaneáveis e didáticos, sem adicionar qualquer informação que não tenha sido explicitamente fornecida."*

---

## Arquitetura

- Fluxo: scout aprovação humana (cas único) workers paralelos (4 personas) auditor LLM writer
- Backend FastAPI (SQLite por defeito) with JWT cookie + CSRF double-submit, API key fallback, alembic migrations, SSRF guards, fail-closed on provider misconfig
- **Refatoração T010**: `app/services/research.py` é uma facade fina (161 LOC) que orquestra módulos em `app/services/pipeline/` (scout.py, worker.py, audit_stage.py, point_executor.py, writer.py, constants.py)
- Módulos pipeline: implementam a lógica padrão: scraper, searcher, extractor, verifier, synthesizer
- Frontend (placeholder): point to your own UI or consume API/stream directly; reverse-proxy `/static` optional (StaticFiles apenas se o diretório não estiver vazio)

Meu objetivo é entregar relatórios estruturados com fontes rastreáveis e tornar explícitas as lacunas que ainda precisam de validação.

