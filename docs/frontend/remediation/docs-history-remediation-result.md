# Relatório de Remediação: DocsView, HistoryView e Restauração de Histórico no App

Data: 26 de outubro de 2026  
Alvos:  
- `frontend/src/components/DocsView.tsx`  
- `frontend/src/components/HistoryView.tsx`  
- `frontend/src/App.tsx` (restauração de histórico e renderização independente de plano)  
- `frontend/src/styles/main.css` (layout unicolunar scoped)  
- `frontend/src/tests/docs-history-remediation.test.ts` (checagens focadas de produção)  

---

## 1. Diagnóstico dos Defeitos Raízes

1. **DocsView (Defeito P1 Round 4A):**
   - A Seção 5 de `DocsView.tsx` ainda afirmava que "variáveis de ambiente possuem precedência absoluta sobre o banco cifrado", contradizendo diretamente o documento normativo aprovado `_reversa_sdd/addenda/002-inversao-precedencia-credenciais.md` (Adendo 002 da RN-10) e a implementação em `app/services/credential_resolver.py` e `SettingsView.tsx`.
   - Faltava a especificação da exceção de bootstrap da chave-mestra `CREDENTIALS_MASTER_KEY` (obrigatoriamente restrita ao ambiente do SO).
   - As descrições nas Seções 1 e 3 indicavam execução fixa com "4 personas", quando o sistema suporta um subconjunto selecionável configurado nas preferências de pesquisa e capturado no plano.
   - Faltavam diretrizes públicas para as novas categorias de fontes conciliadas: fontes consultadas (`consultadas` = leitura confirmada via Jina Web Reader / `read_ok`), fontes utilizadas (`utilizadas` = citadas no dossiê final), fontes não utilizadas (`nao_utilizadas` = `consultadas - utilizadas`), estado desconhecido em relatórios legados exibido como `—` (nunca zero fictício) e garantia de que o carregamento da contabilidade de fontes não reprocessa a pesquisa.

2. **Restauração de Histórico e Renderização em `App.tsx`:**
   - Em `handleSelectRecord`, a atualização de plano era condicional: `if (record.planResponse) { setCurrentPlan(record.planResponse); }`. Ao selecionar um registro histórico legado somente de redação (`writerResponse` presente, mas `planResponse` ausente), o estado `currentPlan` mantinha os metadados do plano anterior, gerando um `ContextSidebar` descontextualizado e órfão (com tema, contagem de pontos, personas e IDs alheios).
   - No JSX principal, a condição era binária: `{!currentPlan ? <EmptyState ... /> : <div className="workspace-grid">...</div>}`. Consequentemente, em um contexto limpo/recarregado (`currentPlan === null`), selecionar um relatório histórico legado concluído não abria o dossiê, exibindo indevidamente o `EmptyState`.
   - Registros de falha sem plano não possuíam barreira de segurança contra retentativas impossíveis (`handleRetryExecution` requer `currentPlan`), correndo o risco de acionar reexecuções inválidas sem plano.

3. **Concordância Gramatical em `HistoryView.tsx`:**
   - Na listagem de pesquisas salvas, o metadado de pontos sempre renderizava `{record.total_pontos} pontos`, produzindo a incorreção `"1 pontos"` para pesquisas unitárias (`total_pontos === 1`).

---

## 2. Remediações Implementadas

### A. `frontend/src/components/DocsView.tsx`
- **Seção 1 (Visão Geral da Arquitetura):** Esclarecido que a busca agêntica executa um subconjunto selecionável de até 4 personas analíticas (Historiador, Visionário, Cético e Futurista) capturado no plano.
- **Seção 3 (Personas Investigativas):** Documentado expressamente que a etapa de busca utiliza o subconjunto selecionável configurado no plano via preferências `+`, sem impor obrigatoriamente todas as quatro.
- **Seção 5 (Credenciais, Segurança e Precedência RN-10):**
  - Atualizada a regra de precedência: Banco de Dados Relacional Cifrado (tabela `credenciais`) > Variáveis de Ambiente (`.env` / host) > Erro Explícito `ValueError` (RN-02).
  - Incluída a exceção de bootstrap de `CREDENTIALS_MASTER_KEY` restrita ao ambiente `os.environ`.
- **Seção 6 (Contabilidade e Categorias de Fontes):**
  - Orientação pública concisa para `consultadas`, `utilizadas` e `nao_utilizadas`.
  - Esclarecimento de que registros legados com contabilidade ausente ou parcial exibem `—` e nunca `0` fictício.
  - Garantia de isolamento operacional: carregar fontes consulta apenas dados persistidos e não reexecuta a pesquisa nem gera custos adicionais.
- Preservação estrita das cores, tipografia e ausência de componentes parasitas (sem TOC, busca ou expansão em massa).

### B. `frontend/src/components/HistoryView.tsx`
- Ajustada a interpolação para concordância gramatical singular/plural:
  ```tsx
  {`${record.total_pontos} ${record.total_pontos === 1 ? 'ponto' : 'pontos'}`}
  ```
- Nenhuma alteração destrutiva ou redesenho no histórico.

### C. `frontend/src/App.tsx`
- **Restauração Incondicional do Plano:**
  Em `handleSelectRecord`:
  ```tsx
  setCurrentPlan(record.planResponse ?? null);
  ```
  Ao selecionar qualquer registro, o estado `currentPlan` é atualizado para o plano real do registro ou `null`, eliminando completamente o vazamento de metadados de pesquisas anteriores.
- **Diferenciação Fidedigna de Estado no JSX Principal:**
  - `!currentPlan && !writerResult && pipelineStage === 'idle'`: Exibe `EmptyState` com sugestões investigativas para novas pesquisas.
  - `currentPlan !== null`: Exibe o layout de duas colunas (`.workspace-grid`) com a coluna principal de execução/relatório e o `ContextSidebar` contextualizado.
  - `!currentPlan` com conteúdo ativo (`writerResult` ou falha): Exibe o layout unicolunar (`.workspace-grid.single-column`), renderizando o relatório ou a visão de falha de forma independente e honesta, sem forjar planos nem exibir sidebars vazios.
- **Proteção e Honestidade em Falhas de Registros Sem Plano:**
  - Registros com falha sem plano direcionam para `pipelineStage = 'failed'` com diagnóstico registrado.
  - O parâmetro `onRetry` é desativado quando não há plano:
    ```tsx
    onRetry={currentPlan ? handleRetryExecution : undefined}
    ```
    Isso impede botões de retentativa inoperantes e exibe honestamente a mensagem diagnóstica com o botão de reset ("Formular novo tema").

### D. `frontend/src/styles/main.css`
- Adicionado estilo scoped para layout unicolunar quando o plano está ausente:
  ```css
  .workspace-grid.single-column {
    grid-template-columns: minmax(0, 1fr);
    max-width: 1040px;
    margin: 0 auto;
  }
  ```

---

## 3. Checagens Focadas de Produção e Resultados Exatos

O arquivo `frontend/src/tests/docs-history-remediation.test.ts` executa exclusivamente checagens SSR sobre os componentes reais de produção, sem testes espelhados ou duplicação de lógica interna do App:

1. **Execução das Checagens da Remediação (SSR Real de Componentes):**
   - Comando: `node --import tsx src/tests/docs-history-remediation.test.ts`
   - Saída:
     ```
     --- Executando Testes de Produção: DocsView e HistoryView SSR ---

     [Teste 1] HistoryView: Singular 1 ponto
       ✓ Singular "1 ponto" verificado com sucesso

     [Teste 2] HistoryView: Plural N pontos
       ✓ Plural "4 pontos" verificado com sucesso

     [Teste 3] DocsView: RN-10 Adendo 002 (Banco Cifrado > Ambiente) e Bootstrap
       ✓ Conteúdo normativo do DocsView verificado integralmente

     --- Todos os 3 testes de renderização de componentes reais passaram com sucesso! ---
     ```
   - Código de saída: 0 (3/3 testes reais aprovados).

2. **Total de Checagens Focadas em Componentes e Helpers Reais:**
   - `src/tests/docs-history-remediation.test.ts`: 3 testes (HistoryView singular/plural e DocsView markup real)
   - `src/tests/defects-regression.ts`: 6 testes
   - `src/tests/plan-settings-polish.test.ts`: 7 testes
   - `src/tests/sources-accounting.test.ts`: 13 testes
   - `src/tests/execution-view-regression.ts`: 9 testes
   - **Total Real:** 38 checagens reais de componentes e helpers de produção aprovadas (3 + 6 + 7 + 13 + 9 = 38). Não se reivindica a marca anterior de 41 checagens, pois os 3 casos espelhados foram integralmente expurgados.

3. **Compilação do Frontend:**
   - Comando: `npm run build` (`tsc && vite build`)
   - Saída:
     ```
     vite v6.4.5 building for production...
     transforming...
     ✓ 2221 modules transformed.
     rendering chunks...
     computing gzip size...
     dist/index.html                   0.97 kB │ gzip:   0.60 kB
     dist/assets/index-Wmy6xx4v.css   85.15 kB │ gzip:  25.45 kB
     dist/assets/index-DgWPKALl.js   510.96 kB │ gzip: 157.43 kB
     ✓ built in 4.12s
     ```
   - Código de saída: 0 (sem erros de compilação ou tipos TypeScript).

---

## 4. Limitações e Fronteiras Observadas

1. **Fiação Montada do App (App Mounted Wiring) NÃO PROVADA por Testes Unitários:**
   - As 3 checagens SSR em `docs-history-remediation.test.ts` validam com rigor o markup e a concordância gramatical reais gerados por `HistoryView` e `DocsView`.
   - A fiação montada do `App.tsx` (alternância entre registro com plano e registro writer-only, abertura a frio de registro writer-only e hidratação assíncrona de fontes) permanece estritamente **NÃO COMPROVADA** em runtime de navegador até a execução independente da suíte Cucumber pelo QA Worker.
   - Nenhuma evidência sintética de DOM ou screenshots simulados foram utilizados como falsa prova de montagem do App.
2. **Preservação de Escopo Exclusivo:** Apenas `DocsView.tsx`, `HistoryView.tsx`, fiação de restauração em `App.tsx`, regra CSS unicolunar em `main.css`, os 3 testes unitários SSR e este relatório foram alterados. `ReportView.tsx`, `SourceBreakdown.tsx`, `Composer.tsx`, `PlanView.tsx`, `SettingsView.tsx` e rotas de backend permaneceram estritamente intactos.
3. **Features e Steps de Teste Intactos:** Nenhum arquivo `.feature` ou `steps.ts` foi modificado (propriedade exclusiva do QA Worker).
4. **Sem Dados Fictícios ou Chamadas a Modelos:** Nenhum modelo ou chamada externa foi executada para fabricar planos ou recuperar relatórios legados.

---

## 5. Adendo de Confirmação Fidedigna de Troca de Registro

- Em `frontend/src/App.tsx`, o diálogo `window.confirm` disparado quando uma execução está em andamento foi atualizado para descrever com precisão técnica a ausência de cancelamento no servidor:
  `'Existe uma pesquisa em andamento. Alternar para este registro interrompe o acompanhamento na interface, mas o processamento no servidor continua em segundo plano. Deseja abrir esta pesquisa?'`
- Nenhuma API de cancelamento foi criada e nenhum fluxo de estado foi reescrito.

