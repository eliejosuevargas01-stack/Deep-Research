# Fluxo de Arquitetura e Execução (Workflow)

```
[ Requisição HTTP / Webhook Ingress ]
                  │
                  ▼
   ┌──────────────────────────────┐
   │    Router / Planner Engine   │
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Middleware de Segurança/Schema│ ◄── Validadores: Payload, Auth Headers (API Keys/JWT)
   └──────────────┬───────────────┘     (Se inválido: aborta com erro HTTP 400/401/422)
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Guardrails do Agente Briefing│ ◄── Sanitização de prompt & Limites éticos/escopo
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Agente Briefing & Scout      │ ◄── LLM de Alta Capacidade (GPT-4o/Claude 3.5/Gemini 1.5)
   │  - Tool: Pesquisa Web        │
   │  - Tool: Leitura de Arquivos │
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Rascunho Inicial (5 Pontos)  │ ◄── Define tópicos + Sequencialidade/Paralelismo
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Validação / Aprovação Humana │ ◄── Aprovação única pelo Usuário (Aprova ou Edita)
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │   Parser & Persistência BD   │ ◄── Grava Estado Inicial & Mapeamento de Tarefas
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │  Orquestrador de Paralelismo │ ◄── Gerenciador de Execução (AsyncIO/Celery/Temporal)
   └──────────────┬───────────────┘
                  │
                  ├───────────────────────────────────────────────────────┐
                  ▼                                                       ▼
   ┌──────────────────────────────┐                       ┌──────────────────────────────┐
   │ Loop de Pesquisa por Ponto   │ (Se 5 Pontos Paralelos)│  Até 20 Workers em Simultâneo│
   │   (Prevenção Race Condition) │                       │  (4 Personas × 5 Pontos)     │
   └──────────────┬───────────────┘                       └──────────────┬───────────────┘
                  │                                                       │
                  ├───────────────────────────────────────────────────────┘
                  │
                  ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 4 Workers de Pesquisa por Ponto (Execução Paralela com Viés Dedicado):  │
   │   1. O Historiador Contextual                                           │
   │   2. O Cético Analítico                                                 │
   │   3. O Pragmático Aplicado                                              │
   │   4. O Visionário Futurista                                             │
   │                                                                         │
   │ Subfluxo Unificado da Tool de Pesquisa:                                 │
   │   SerpAPI / Apify / Jina Scraper ──► Jina Reader ──► Limpeza & Fusão   │
   └──────────────────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │   Persistência de Resultados │ ◄── Grava Coletas & Evidências no Banco de Dados
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │     Agente Auditor (Juiz)    │ ◄── Avalia cada ponto individualmente (Sem Tools)
   └──────────────┬───────────────┘
                  │
         ┌────────┴────────┐
         │ Suficiente?     │
         └────┬───────┬────┘
              │       │
    True +    │       │ False + Motivo
    Motivo    │       │ (Tentativas < 3)
              │       │
              │       └───► [ Re-executa os 4 Workers do Ponto ] (Loop)
              │                     │
              │             Tentativas == 3 (Blocker Ativado)
              │                     │
              ├─────────────────────┘
              │
              ▼
   ┌──────────────────────────────┐
   │     Fim do Loop de Pesquisa  │
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │    Agente Redator Final      │ ◄── Compila e sintetiza na perspectiva editorial
   └──────────────┬───────────────┘     (Sem Tools, segue estritamente o Roteiro)
                  │
                  ▼
   ┌──────────────────────────────┐
   │  Persistência Final no BD    │ ◄── Armazena Relatório Completo & Trilha de Auditoria
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │  Webhook Callback (Dispatch) │ ◄── Envia o relatório final para o remetente original
   └──────────────────────────────┘
```

---

## Detalhamento Técnico das Etapas

### 1. Router & Middleware de Segurança
* **Autenticação:** Validação de headers HTTP (`Authorization: Bearer <JWT/API_Key>`).
* **Validação de Schema:** Pydantic / FastAPI interceptam payloads incompletos ou malformados sobre o tema de pesquisa, respondendo imediatamente com código HTTP de erro apropriado e cancelando a requisição antes do consumo de recursos.
* **Guardrails:** Sanitização contra injeções de prompt e validação de escopo.

### 2. Agente Briefing & Scout
* Modelo de alta capacidade cognitiva (LLM Top-Tier).
* Gera rascunho com 5 pontos principais de investigação e determina a dependência entre eles (paralelo ou sequencial).
* Interação Humana: Pausa a execução para aprovação/edição única pelo usuário.

### 3. Orquestração e Prevenção de Race Conditions
* **Paralelismo Máximo:** 5 pontos independentes x 4 personas = **20 workers concorrentes**.
* **Isolamento de Estado:** O controle de estado é gerenciado no banco de dados via transações ACID (PostgreSQL / SQLAlchemy) utilizando travas otimistas (*optimistic locking*) ou chave de bloqueio por id de ponto/pesquisa, evitando sobreposição e race conditions ao gravar coletas concorrentes.

### 4. Ciclo de Auditoria e Resolução de Bloqueio (Blocker)
* Para cada ponto concluído pelas 4 personas, o Auditor lê as evidências agregadas.
* **Condição de Saída:**
  * Se `suficiente == True` + Motivo: O ponto é aprovado e marcado para o relatório final.
  * Se `suficiente == False` + Motivo: O Auditor ajusta as diretrizes do ponto e reinicia os 4 workers do ponto.
* **Mecanismo de Blocker:** O limite máximo é de **3 iterações**. Se atingir 3 tentativas sem aprovação total, o *blocker* é ativado, forçando o avanço do material acumulado com ressalvas de auditoria anexadas para a etapa do Redator.

### 5. Finalização e Callback
* O Redator compila o documento final respeitando as diretrizes do Auditor.
* O estado final é persistido no banco de dados.
* É disparado um HTTP POST assíncrono para a URL de Webhook cadastrada no payload inicial.
