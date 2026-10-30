# Frontend Remediation Progress

## Status: IN_PROGRESS (Hermes Implementation Worker - ag/gemini-3.8-flash-high reasoning high)
- Authority: `.impeccable/remediation-20261026/frontend-critique-r1-fix-task.md`, `frontend-worker-task.md`, `requirements.json`.
- Scope: `frontend/**`, `DESIGN.md`, `.impeccable/surface-brief.md`, `docs/frontend/remediation/*`.
- Rules: Hermes-only execution; no native subagents; root handles live verification and independent auditor; do NOT execute visual Cucumber yet.

### Corrective Batch Progress (Crítica Rodada 1)
1. [x] **Responsividade e Quebra de Layout:**
   - Breakpoint do navbar ajustado para `max-width: 992px` (corrigindo colisão entre doclink e badge em 916px e zoom 200%).
   - Grade de sugestões de temas (`.sample-topics-grid`) configurada para coluna única em `max-width: 768px`, eliminando compressão em 375px.
   - Painel de preferências (`.preferences-panel`) delimitado pelo viewport com `max-height: min(80vh, 520px); overflow-y: auto;` e cabeçalho fixo (`position: sticky; top: 0`), garantindo botão fechar acessível mesmo em landscape/telas curtas.
2. [x] **Texto de Entrada, Ajuda e Validação:**
   - Texto de introdução em `EmptyState.tsx` reescrito de forma conversacional e task-first ("O que você deseja investigar hoje?").
   - Texto de ajuda do compositor ampliado para `>= 13px` (`0.88rem`) com alto contraste e instruções dinâmicas de caracteres faltantes ou excedentes.
   - Remoção do `maxLength={600}` restritivo para preservar texto longo colado pelo usuário sem truncamento silencioso.
3. [x] **Correção do Bug de Snapshot de Histórico:**
   - `historyService.sanitizeRecord` atualizado para preservar publicamente `preferencias: { n_pontos, personas }`.
   - Ao reabrir pesquisas ou em planos legados sem snapshot, a busca não faz fallback indevido para as escolhas atuais do compositor; passa `undefined` para que o backend utilize o snapshot persistido ou padrão do servidor.
4. [x] **Status e Rótulos Fidedignos de Personas na Execução:**
   - `ExecutionView.tsx` recebe `plan` e reflete dinamicamente a contagem real de personas e seus nomes ("Varredura web em andamento com 2 personas analíticas (Historiador, Cético)..."). Em planos legados sem snapshot, utiliza descrição honesta sem inventar contagem de 4.
5. [x] **Revisão Compacta Inicial e Continuidade Imediata:**
   - `PlanView.tsx` colapsa todos os pontos analíticos por padrão na carga inicial para qualquer contagem de pontos (incluindo N=1 e N=2 extensos), assegurando que a única ação `Iniciar pesquisa` esteja imediatamente visível e desobstruída em 1280x720 e mobile.
   - Botão "Editar tema" adicionado ao banner do plano permitindo recuperar o texto no compositor.
   - Compositor limpo estritamente após a criação bem-sucedida do plano, evitando duplicações e concorrência com o botão Iniciar. Em caso de erro, o texto permanece no compositor.
6. [x] **Recuperação e Retentativa Sensível ao Estágio (Stage-Aware Retry):**
   - Tratamento explícito de timeout (504), erro de provedor (502) e diagnósticos com mensagens orientadas ao usuário.
   - Botão de retry no `ExecutionView` retenta especificamente o estágio afetado: se a auditoria já aprovou, retenta apenas o redator (`handleRetryWriter`); se a busca/auditoria falhou, retenta o ciclo de busca sem replanejamento.
7. [x] **Verificação de Build e Testes:**
   - `npx tsc --noEmit` executado com 0 erros.
   - `npm run build` executado com sucesso gerando bundle de produção limpo em 3.49s.
   - Cenários Gherkin e passos de teste atualizados em `frontend/features/`.
