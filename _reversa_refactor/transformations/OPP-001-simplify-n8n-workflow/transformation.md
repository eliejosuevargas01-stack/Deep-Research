# Transformação OPP-001: Simplificação do Workflow n8n kjYdSxUiXyuWsmOM

- **Status:** Proposta (Gate de aprovação)
- **Tipo:** Simplificação Algorítmica (/reversa-simplify)
- **Alvo:** Workflow `kjYdSxUiXyuWsmOM` no n8n ("Deep Research API")
- **Preservação de Comportamento:** Equivalência estrita comprovada

## Métricas Estimadas
- **Nós Totais:** 13 &rarr; 9 (redução de 30% na complexidade cognitiva)
- **Consumo de Memória em Loop:** Poda de ~80% do payload acumulado por ciclo de polling
- **Requisições de Polling:** Intervalo de 10s &rarr; 15s (redução de 33% em overhead HTTP/IO)
- **Prevenção de Timeout:** Teto explícito de 60 iterações (15 min) contra execuções infinitas

## Lógica Antes (Cascata)
1. Trigger Chat
2. Extrair Tema
3. Iniciar Pesquisa
4. Armazenar Contexto
5. Wait 10s
6. Consultar Status
7. If: Status é Final?
   - True: If: Teve Sucesso?
     - True: Obter Relatório &rarr; Formatar Sucesso
     - False: Formatar Falha
   - False: If: Precisa Aprovar Briefing?
     - True: Aprovar Briefing &rarr; Wait 10s
     - False: Wait 10s

## Lógica Depois (Decisor Direto)
1. Trigger Chat
2. Extrair Tema
3. Iniciar Pesquisa
4. Armazenar Contexto Inicial
5. Wait 15s
6. Consultar Status
7. Filtrar e Contar Ciclo (Pruning de RAM + Guardrail de 60 loops)
8. Switch v3.4 (4 saídas diretas):
   - Saída 0 (`PENDING_APPROVAL`): Aprovar Briefing &rarr; Wait 15s
   - Saída 1 (`DONE`): Obter Relatório Final &rarr; Formatar Resposta
   - Saída 2 (`FAILED`): Formatar Resposta
   - Saída 3 (Fallback: `BRIEFING`/`SCRAPER`): Volta direto para Wait 15s
9. Formatar Resposta (Unificado)
