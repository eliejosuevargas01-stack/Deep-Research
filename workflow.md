# Fluxo de Arquitetura e Execução (Workflow)

> [!IMPORTANT]
> **Diretrizes aprovadas vigentes (2026-10-19):** Este fluxo reflete as diretrizes normativas de produto do adendo `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md` (DIRETRIZES APROVADAS). A implementação operacional em código (`app/`) e sua verificação permanecem **não executadas/não verificadas** nesta sprint documental. O diagrama a seguir é representação histórica; trechos contrários ao adendo são superados pelos detalhes técnicos abaixo.

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
   │  - Tool: Leitura Interna de Prompt │ ◄── Carrega prompt do filesystem do projeto (não pesquisa web)
    │  - Tool: Pesquisa Web (SERP-only)  │ ◄── Jina SERP search apenas;
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
* **Briefing síncrono no transporte HTTP**: `POST /briefings` retorna `201` com o draft completo no corpo da resposta. Internamente usa corrotinas `async/await` normais — sem fila, sem polling do cliente.
* **Revisão única**: PATCH com `{"note": "..."}` revisa o briefing, aprova e inicia investigação automaticamente (via exclusiva — não combine PATCH + POST /investigate).
* **Investigação em background**: `POST /briefings/{research_id}/investigate` retorna `202 Accepted` e dispara investigação em background.

### 3. Subfluxo Unificado dos Workers (4 Personas por Ponto)
* **Até 20 Workers Simultâneos**: 4 personas x 5 pontos rodando concorrentemente via `asyncio.gather`.
* **Persona Workers**: `historian`, `skeptic`, `pragmatist`, `futurist` atuam em paralelo com viés cognitivo próprio.
* **Leitura Massiva**: A ferramenta de busca deve entregar ao worker 10 corpos integrais de páginas em texto limpo, sem resumos/snippets/corte silencioso. Limpeza prévia remove boilerplate mas preserva corpo informativo. Dizer requisito, não garantia observada do provedor; exceções permanecem pendentes conforme §1.6 do adendo. Não exige Reader obrigatório nem fallback novo.
* **Corpo Integral das Páginas**: O texto entregue ao worker é o corpo de texto limpo e informativo na íntegra, não resumos ou snippets.
* **Orçamento de Queries**: Máximo 3 queries distintas por persona/ponto por rodada. Parada voluntária antecipada ao atingir suficiência de informação.
* **Garantia de Saída Não-Vazia**: A resposta estruturada produzida pelo worker é não-vazia e contém todo aprendizado relevante coletado, limitações identificadas e atribuição às fontes reais e URLs lidas; sem inventar fatos ou fontes.
* **Persistência Individual**: Cada persona salva seu resultado no banco (`research_step_results`) assim que concluído, antes do merge.
* **Barreira das 4 Personas**: O ponto não transita para auditoria até que todas as 4 personas tenham concluído e persistido seus resultados para a mesma rodada.
* **Etapa Formal de Merge Inter-Personas**: O merge conecta as 4 visões mantendo origens, contradições e lacunas identificadas. Apenas após a gravação do merge o ponto é submetido ao Auditor.

### 4. Ciclo de Auditoria e Resolução de Bloqueio (Blocker)
* Para cada ponto concluído pelas 4 personas (merge já gravado), o Auditor lê as evidências agregadas.
* **Condição de Saída:**
  * Se `suficiente == True` + Motivo: O ponto é aprovado e marcado para o relatório final.
  * Se `suficiente == False` + Motivo: O Auditor ajusta as diretrizes do ponto e reinicia os 4 workers do ponto.
* **Teto de Tentativas:** O ciclo completo de investigação + auditoria por ponto possui teto rígido de **4 tentativas totais** (1 execução inicial + até 3 retentativas/reprovações).
* **Quarta Reprovação / Blocker**: Se o ponto atinge a 4ª reprovação na auditoria, a busca de novas evidências para esse ponto é encerrada definitivamente. O ponto é marcado como concluído com ressalvas (`AUDIT_CAVEAT`). O fluxo avança para a fase de redação (`WRITE`) somente após TODOS os pontos de pesquisa atingirem estado conclusivo (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`), não imediatamente ao quarto fracasso de um ponto isolado.

### 5. Finalização e Callback
* O Redator compila o documento final respeitando as diretrizes do Auditor e o roteiro (outline) aprovado.
* O estado final é persistido no banco de dados.
* É disparado um HTTP POST assíncrono para a URL de Webhook cadastrada no payload inicial.
