# Relatório de Remediação e Polimento da Tela de Execução (ExecutionView)

Data: 26 de outubro de 2026  
Alvos: 
- `frontend/src/components/ExecutionView.tsx`
- `frontend/src/components/ContextSidebar.tsx`
- `frontend/src/App.tsx` (fiação mínima de estado de `auditCycleNumber`)
- `frontend/src/styles/execution-view.css` (NOVA folha de estilos de escopo isolado)
- `frontend/src/tests/execution-view-regression.ts` (testes de regressão focados de produção)

Ambiente de Validação: Fixture isolada em `http://localhost:8011` (sem navegação/interferência na sessão de usuário em `3002` e sem chamadas a provedores pagos)  
Base de Diretrizes: `docs/frontend/remediation/critiques/user-execution-20261026/A.md`, `B.md`, `DESIGN.md`, `PRODUCT.md`, Impeccable reference (`polish.md`, `clarify.md`, `craft-floor.md`).

---

## 1. Síntese dos Defeitos Críticos Tratados

A partir da imagem de execução real do usuário (`/tmp/codex-clipboard-65e55b65-19fd-4934-ba8c-9f0382556121.png`) e dos relatórios de avaliação técnica A e B, foram identificados e corrigidos cinco defeitos centrais:

1. **[P1] Parede Vermelha e Despejo de Dados Técnicos em "Fragilidades apontadas":**
   - *Problema:* O campo `pontos_fracos` despejava uma string serializada bruta com 14 linhas de texto ininterrupto em vermelho intenso (`--color-danger-text`), exibindo sintaxe crua de dicionários Python, IDs internos de alegações (`clm_historiador_2_fe580774`), IDs de fontes (`src_7406715`), IDs de chunks (`chk_567`) e URLs sem hyperlink.
   - *Solução:* Substituído por bloco de diagnóstico estruturado a partir do vetor tipado `item.criterios`, mapeando para nomes canônicos do backend (ex: `Critério 4: Ausência de Contradições`). Exibição limpa de `lacuna`, `correcao` e `personas_pertinentes`. O registro técnico bruto integral com todos os identificadores e URLs é estritamente preservado dentro de um disclosure colapsável acessível (`<details className="audit-technical-details">`). Texto vermelho maciço eliminado em favor de tipografia estruturada e legível.

2. **[P1] Ambiguidade Temporal e Rotulagem Erônea de Auditoria do Ciclo Anterior:**
   - *Problema:* No Ciclo 2, a busca ativa era exibida junto ao parecer de reprovação do Ciclo 1 sem demarcação temporal clara, induzindo pânico de que a busca atual havia falhado.
   - *Solução:* Adicionado o estado explícito `auditCycleNumber` em `App.tsx`, capturado exclusivamente na resposta com sucesso do endpoint `/audit`. Passado como prop a `ExecutionView`. No Ciclo 2 com busca ativa, a seção é rotulada como `Auditoria do ciclo 1 — revisão em andamento no ciclo 2`, acompanhada de banner explicativo de que a busca do Ciclo 2 visa enriquecer evidências e superar os apontamentos. Quando o ciclo de auditoria for nulo/legado, exibe honestamente `Última auditoria disponível`, sem inferir cegamente `cycleNumber - 1`.

3. **[P1] Omissão do Tema da Investigação e Título Técnico:**
   - *Problema:* A tela exibia o título de implementação interna `Execução Síncrona da Investigação` e omitia `plan.tema`, violando a heurística de reconhecimento sobre memorização.
   - *Solução:* Título atualizado para linguagem concisa de produto: `Investigação em andamento`. Injetado banner destacado `.execution-theme-banner` exibindo claramente `plan.tema`. Preservado o snapshot fidedigno de personas do plano.

4. **[P2] Critérios Numéricos Misteriosos e Acessibilidade em Justificativas:**
   - *Problema:* Grade com pílulas estáticas "Critério 1"..."Critério 12" sem nomes, com justificativas presas no atributo HTML `title` inacessível a teclado, toque e leitores de tela.
   - *Solução:* Critérios mapeados para o dicionário canônico de 12 nomes formais (`Clareza Temática`, `Corroboração Canônica`, `Atualidade`, etc.). Pílulas transformadas em disclosures acessíveis (`<details className="criterion-disclosure">`) com foco via teclado (`:focus-visible`), touch target adequado (≥36px), revelando avaliação, lacuna e correção sob demanda. Critérios reprovados são destacados prioritariamente no bloco superior de diagnóstico.

5. **[P2] Acessibilidade `aria-live`, Classes de Badge, Singular e Tracker de Falha:**
   - *Problema:* `aria-live="polite"` no card inteiro provocava leitura de centenas de caracteres em cada atualização; classe de ciclo fixa em `auditando`; plural incorreto `1 pontos`; e o tracker de busca marcava "done" mesmo quando a busca falhava (`failedStage === 'searching'`).
   - *Solução:* 
     - `aria-live` removido do `<article>` principal e transferido para região atômica `.sr-only` com status sucinto de uma frase.
     - Classe do badge reflete o estágio real (`buscando`, `auditando`, `redigindo`, `concluido`, `reprovado`).
     - Concordância singular corrigida para `1 ponto` no sidebar e na contagem de aprovação de auditoria (`0/1 ponto aprovado`).
     - Tracker de estágios exibe classe `failed` no passo 1 caso `failedStage === 'searching'`, nunca marcando como `done`.
     - Preservadas semânticas de retry, bloqueio estrito do Writer (gating de 11 critérios), e guarda contra respostas obsoletas.

---

## 2. Arquivos Modificados e Criados

1. **`frontend/src/styles/execution-view.css` (NOVO):**
   - Folha de estilos dedicada e isolada para `ExecutionView`.
   - Evitou qualquer alteração ou poluição em `components.css` e `main.css`.
   - Contém tokens de `.sr-only`, `.execution-theme-banner`, `.audit-diagnostics-container`, `.failed-criterion-card`, `.audit-technical-details`, `.audit-criteria-grid`, e estados de `.stage-step.failed` e badges.

2. **`frontend/src/components/ExecutionView.tsx`:**
   - Implementação completa dos novos blocos estruturados, títulos canônicos (`CANONICAL_CRITERIA_NAMES`), helpers puros de status e rotulagem temporal (`getAuditContextualLabel`, `getSuccinctStatus`, `getCycleBadgeClass`).
   - Preservação integral de dados brutos e IDs no disclosure técnico colapsado.
   - Remoção de `aria-live` do container geral.

3. **`frontend/src/components/ContextSidebar.tsx`:**
   - Correção gramatical da contagem de pontos: `{plan.n_pontos} {plan.n_pontos === 1 ? 'ponto' : 'pontos'}`.
   - Ajuste em `getStatusBadgeClass` para retornar classes semânticas distintas (`auditando`, `redigindo`, `buscando`).

4. **`frontend/src/App.tsx`:**
   - Adicionado estado `auditCycleNumber: number | null`.
   - Captura `setAuditCycleNumber(ciclo)` na resolução bem-sucedida de `api.auditResearch`.
   - Limpeza de `auditCycleNumber` em `handleStartExecution`, `handleResetResearch`, `handleSelectRecord` e `handleCreatePlan`.
   - Propagação via `<ExecutionView auditCycleNumber={auditCycleNumber} ... />`.

5. **`frontend/src/tests/execution-view-regression.ts` (NOVO):**
   - 9 testes de comportamento real de componentes SSR e helpers puros.

---

## 3. Evidências de Verificação Técnica

### A. Execução dos Testes Focados de Regressão
Comando executado:
```bash
cd frontend && npx tsx src/tests/execution-view-regression.ts
```
Resultado:
```
=== Iniciando Testes de Regressão de Produção (ExecutionView & ContextSidebar) ===

[Teste 1] Auditoria do Ciclo 1 em andamento de busca no Ciclo 2 -> PASSOU
[Teste 2] Auditoria do mesmo ciclo durante a redação (Writing) -> PASSOU
[Teste 3] Ciclo de auditoria desconhecido/legado (fallback seguro) -> PASSOU
[Teste 4] Tracker de busca em falha no estágio searching -> PASSOU
[Teste 5] Diagnóstico estruturado canônico e detalhes técnicos preservados -> PASSOU
[Teste 6] Acessibilidade: aria-live restrito a status sucinto -> PASSOU
[Teste 7] Tema da pesquisa visível e título em linguagem de produto -> PASSOU
[Teste 8] Concordância gramatical singular ("1 ponto") -> PASSOU
[Teste 9] Lógica determinística dos helpers puros -> PASSOU

--- TODOS OS 9 TESTES DE REGRESSÃO PASSARAM COM SUCESSO! ---
Exit code: 0
```

### B. Verificação da Suíte Existente de Defeitos
Comando executado:
```bash
cd frontend && npx tsx src/tests/defects-regression.ts
```
Resultado:
```
--- Executando Testes com Código Real de Produção ---
[Teste 1] PlanView real (SSR): Plano legado sem preferências -> PASSOU
[Teste 2] PlanView real (SSR): Plano com snapshot exato de 2 personas -> PASSOU
[Teste 3] historyService real: Sanitização de plano legado sem preferências -> PASSOU
[Teste 4] historyService real: Preservação de snapshot e descarte de dados privados -> PASSOU
[Teste 5] SettingsView real (SSR): Estado inicial limpo -> PASSOU
[Teste 6] SettingsView real (SSR): Rascunho ativo em memória -> PASSOU

--- Todos os 6 testes de componentes e serviços reais passaram com sucesso! ---
Exit code: 0
```

### C. Verificação de Tipos TypeScript (`tsc --noEmit`)
Comando executado:
```bash
cd frontend && npx tsc --noEmit
```
Resultado:
- Todos os arquivos sob nossa posse (`ExecutionView.tsx`, `ContextSidebar.tsx`, `App.tsx`, `execution-view-regression.ts`) compilaram com **0 erros de tipagem**.
- Erros contemporâneos foram observados exclusivamente em `src/tests/sources-accounting.test.ts` (linhas 519-521), arquivo pertencente a outro worker ativo encarregado da frente de source accounting, respeitando o isolamento estrito de posse de arquivos.

### D. Inspeção em Browser Isolado (`localhost:8011`)
- Aba aberta via `browser_exec` na sessão isolada `execution_worker_8011` apontando para `http://127.0.0.1:8011/app`.
- Servidor de fixture de aceitação retornou HTTP 200 e montou árvore HTML do frontend sem erros.
- A sessão real de usuário na porta `3002` e o backend principal foram rigorosamente mantidos sem toques ou interferências.

### E. Correção de Craft-Floor e Verificação por Detector (Rodada 3)
- **Achado do Auditor:** Em `frontend/src/styles/execution-view.css`, a classe `.audit-breakdown.is-prior-cycle` utilizava `border-left: 3px solid var(--color-indigo, #4F46E5);` e `padding-left: 16px;`. Essa borda lateral espessa violava a regra explícita de `craft-floor.md` ("Surface habits: A colored border-left or border-right above 1px on cards, list items, callouts, or alerts").
- **Correção Aplicada:** Removida a borda lateral de 3px e o offset desnecessário de padding. A demarcação do ciclo anterior é mantida de forma elegante e quieta através da sutil opacidade (`opacity: 0.94`), da separação estrutural existente e do banner semântico textual `.audit-prior-cycle-banner`.
- **Varredura com Detector Estático (`impeccable detect`):**
  ```bash
  /home/eliezer/.claude/skills/impeccable/scripts/impeccable detect --json frontend/src/styles/execution-view.css frontend/src/components/ExecutionView.tsx
  ```
  Resultado: `[]` (0 violações detectadas, exit code 0).

---

## 4. Limitações e Fronteiras Honestas

1. **Fronteira Honesta de Prova de Navegador:**
   - A requisição e montagem inicial em `http://127.0.0.1:8011/app` retornando HTTP 200 e HTML estruturado comprova integridade de empacotamento estático, mas **NÃO constitui prova de produção do fluxo dinâmico real de execução nem da interação com os disclosures de critérios reprovados**. Esses cenários dinâmicos de ponta a ponta permanecem reservados à esteira formal de testes de integração/Cucumber pelo orquestrador raiz.
2. **Ausência de Endpoint de Cancelamento no Backend:**
   - Em conformidade estrita com o contrato do Checkpoint 1 e as instruções de raiz, **não** foi implementado botão falso de "cancelar"/"parar" no card de execução ligado a reset de frontend. O backend não possui endpoint para abortar tarefas em execução no pipeline síncrono. A ação `+ Nova pesquisa` existente na Navbar com confirmação atende à desistência de cliente.
3. **Nenhuma Certificação Injustificada de WCAG:**
   - As melhorias de acessibilidade (`sr-only` focado, disclosures de critérios substituindo atributos `title`, targets interativos) foram comprovadas por renderização real SSR e inspeção estrutural de DOM. Não foram emitidas declarações fictícias de conformidade universal sem auditoria independente.
4. **Preservação de Escopo de Outros Workers:**
   - Nenhum arquivo fora do escopo atribuído foi tocado. `Composer.tsx`, `ReportView.tsx`, `SourceBreakdown.tsx`, esquemas de backend, rotas e tipos foram preservados intactos.
