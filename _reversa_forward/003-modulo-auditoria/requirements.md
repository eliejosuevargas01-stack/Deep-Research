# Requisitos: Módulo de Auditoria Factual e Julgamento de Evidências

> Identificador da feature: `003-modulo-auditoria`  
> Data: `2026-10-16`  
> Cenário: `forward` (ancorado em GOAL.md, plan.md, workflow.md e deliberações oficiais de 2026-10-16)  
> Status: 🟢 CONFIRMADO (100% deliberado pelo operador)

---

## 1. Visão Geral e Objetivo

O Módulo de Auditoria Factual é o juiz cognitivo independente da pesquisa profunda. Ele atua como um editor-chefe acadêmico que avalia as evidências agregadas das quatro personas investigativas (**historian**, **skeptic**, **pragmatist** e **futurist**) para cada ponto de pesquisa de forma isolada, assegurando rigor analítico, rastreabilidade factual por citações *verbatim*, detecção de contradições e formulação de diretrizes concretas de re-pesquisa (*missing research*).

---

## 2. Princípios Reversa Aplicados

| Princípio | Aplicação na Feature 003 |
|---|---|
| **I. Rastreabilidade Factual Estrita (Verbatim Citation)** | Cada alegação deve mapear diretamente para um trecho textual exato coletado e para sua respectiva URL de origem. A auditoria verifica correspondência textual e proíbe alucinações. |
| **II. Defesa de Privacidade e Isolamento de Prompts** | O raciocínio interno do auditor permanece em RAM; apenas o veredito estruturado (checklist, score, aprovação, findings, contradições, incertezas e missing research) é persistido. |
| **III. Resiliência por Degradação Graciosa e Limites Rígidos** | Falhas de rede ou de provedor LLM (500/502/503) recebem até 4 tentativas com backoff exponencial; persistindo a falha, registra-se tentativa inconclusiva sem queimar a contagem de tentativas do ponto. |
| **IV. Concorrência Segura e Idempotência** | Cada ponto é auditado isoladamente; pontos independentes são avaliados atomicamente com controle de concorrência e idempotência contra execuções repetidas. |

---

## 3. Os 12 Critérios Canônicos de Auditoria

Para cada ponto investigado, o Auditor avalia as evidências contra 12 perguntas booleanas (`q1` a `q12`):
1. **q1 (Pergunta Original):** A pergunta central e os objetivos do ponto foram respondidos satisfatoriamente?
2. **q2 (Subtópicos Essenciais):** Os aspectos críticos e variáveis chave do problema foram cobertos?
3. **q3 (Citações Verificáveis):** As principais alegações estão ancoradas em fontes rastreáveis e verificáveis?
4. **q4 (Fontes Primárias/Confiáveis):** As fontes consultadas possuem autoridade técnica, institucional ou acadêmica?
5. **q5 (Correspondência Textual):** As citações e excertos realmente sustentam as conclusões tiradas pelas personas?
6. **q6 (Diversidade de Fontes):** Não há dependência excessiva ou viés em uma única fonte ou domínio?
7. **q7 (Atualidade da Informação):** Os dados e referências são cronologicamente adequados ao tema investigado?
8. **q8 (Resolução de Contradições):** Contradições entre diferentes fontes ou personas foram identificadas e esclarecidas?
9. **q9 (Separação Fato vs Incerteza):** Fatos empíricos estão claramente distinguidos de hipóteses, projeções e opiniões?
10. **q10 (Ausência de Saltos Lógicos):** Não há saltos argumentativos, generalizações indevidas ou alucinações?
11. **q11 (Completude Factual):** Não restam lacunas críticas de informação que invalidem o ponto?
12. **q12 (Prontidão para Síntese):** O material acumulado fornece base sólida e suficiente para o Agente Redator?

---

## 4. Regras de Negócio e Comportamento Operacional

### RN-301: Disparo Automático por Ponto e Invocação Dedicada via API (D-301)
- Assim que os 4 workers de um mesmo ponto de pesquisa terminarem sua coleta, os resultados em `research_step_results` são consolidados atomicamente e enviados para o Agente Auditor sem esperar os demais pontos.
- A API expõe os endpoints administrativos idempotentes:
  - `POST /api/audit/{research_id}/run`: Dispara a auditoria de todos os pontos que estejam em `AUDIT_PENDING`.
  - `POST /api/audit/{research_id}/points/{point_id}/run`: Dispara a auditoria isolada de um ponto específico.

### RN-302: Regra de Aprovação e Score Mínimo
- Um ponto é considerado **APPROVED** se e somente se:
  1. `score >= 10` (pelo menos 10 das 12 perguntas respondidas como verdadeiras, ≥ 83.3%);
  2. `contradictions` estiver vazio (`[]`) ou todas as contradições tiverem sido explicitamente reconciliadas;
  3. Não houver falsificação de citação detectada na checagem determinística de citações.
- Se aprovado: O ponto transita para `AUDIT_APPROVED` e o veredito estruturado é persistido em `research_points.audit` e `audit_trails`.

### RN-303: Gestão de Reprovação (RETRY) e Filtro de Não-Releitura (D-302)
- Se o ponto for reprovado (`score < 10` ou contradição não resolvida) e `attempt_count < 4`:
  - O Auditor formula obrigatoriamente instruções concretas e direcionadas em `missing_research` (proibidas instruções vagas como "pesquise mais").
  - O ponto transita para `SCRAPER_RETRY` e incrementa seu `attempt_count`.
  - As 4 personas são re-executadas com as diretrizes de `missing_research` injetadas no contexto conversacional.
  - **Filtro Anti-Duplicação de URLs:** O harness injeta a lista completa de URLs já lidas (`read_urls`) das tentativas anteriores deste ponto, impedindo que os workers façam nova leitura/raspagem das mesmas páginas, forçando a descoberta de fontes complementares inéditas.
  - Novas evidências são adicionadas de forma append-only ao histórico existente do ponto.

### RN-304: Resiliência de Provedor e Erros Transitórios de IA (D-303)
- Chamadas de IA do Auditor sujeitas a falhas de rede, timeouts ou erros HTTP 500/502/503 recebem até 4 tentativas consecutivas (1 inicial + 3 retries) com backoff exponencial (1s, 2s, 4s).
- Se a instabilidade externa persistir após todas as retentativas, a tentativa é registrada como `AUDIT_INCONCLUSIVE` em `audit_trails`, **sem queimar o limite de tentativas (`attempt_count`) do ponto de pesquisa**.

### RN-305: Teto de 4 Execuções e Não-Bloqueio da Pesquisa (D-305)
- O número máximo de ciclos de pesquisa/auditoria por ponto é 4 (1 inicial + até 3 retries).
- Nenhum ponto permanece em estado de bloqueio permanente (`BLOCKED`) que aborte a pesquisa.
- Se na 4ª tentativa o Auditor ainda registrar reprovação (`score < 10`):
  - O ponto é marcado como `AUDIT_CAVEAT` (concluído com ressalvas).
  - O veredito registra formalmente as limitações, incertezas e lacunas não sanadas.
  - O material acumulado é integralmente preservado e liberado para o Agente Redator.

### RN-306: Transição Final para Síntese do Redator
- Quando 100% dos pontos da pesquisa atingirem estado conclusivo (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`):
  - O status geral da pesquisa em `research.status` transita atomicamente de `AUDIT` para `WRITE`.
  - O pipeline fica pronto para a ativação do Agente Redator (Feature 004).
