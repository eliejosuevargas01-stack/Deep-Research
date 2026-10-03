# Deep Research

Sistema autônomo e distribuído de pesquisa profunda (Deep Research) multiagente, estruturado em 4 etapas sequenciais e pipelines paralelos de alta fidelidade e checagem de fatos.

---

## 1. Briefing & Scout

Agente inicial de exploração cognitiva equipado com:
* **Tool de Pesquisa Web**: busca rápida e direcionada.
* **Tool de Leitura de Arquivos**: varredura de referências e documentos prévios.

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

## Objetivo Central do Fluxo

Garantir o mais alto padrão de profundidade informacional e veracidade documental, entregando relatórios extensos, estruturados e com 100% de rastreabilidade de fontes para tomada de decisão crítica.
