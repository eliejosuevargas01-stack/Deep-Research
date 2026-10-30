# Relatório de Prontidão de Aceitação QA: Suíte Cucumber / Gherkin Final

**Data:** 2026-10-26T21:40:00-03:00  
**Autor:** Hermes QA Author (exclusivamente modelo `ag/gemini-3.8-flash-high` reasoning high via Render Router / 9router)  
**Status da Suíte:** **PRONTA PARA EXECUÇÃO PÓS-AUDITORIA (NENHUM CUCUMBER EXECUTADO ANTECIPADAMENTE)**  
**Diretório Canônico de Evidências:** `docs/frontend/remediation/evidence/cucumber/`  
**Escopo de Titularidade Estrita:**  
- `frontend/features/**` (5 arquivos de especificação BDD Gherkin)  
- `frontend/features/step_definitions/steps.ts` (definições de passos com Playwright embutido)  
- `frontend/features/support/world.ts` e `hooks.ts` (World tipado, manifesto de proveniência e isolamento)  
- `frontend/cucumber.json` (configuração do runner)  
- `frontend/src/tests/cucumber-static-inspection.ts` (harness estático de inspeção de passos e duplicatas)  
- `docs/frontend/remediation/plan-settings-polish-result.md` (correção de proveniência de evidências)  
- `docs/frontend/remediation/qa-readiness.md` (este documento de prontidão)  

Nenhum arquivo de código de produção (`frontend/src/**`), backend, banco de dados ou ambiente de produção foi modificado.

---

## 1. Correção de Proveniência em Relatório Anterior (`plan-settings-polish-result.md`)

Conforme diretriz obrigatória de QA e integridade de evidências, foi realizada a auditoria e correção formal no relatório `docs/frontend/remediation/plan-settings-polish-result.md`:

1. **Correção de Fuso Horário no Cabeçalho:**
   - O cabeçalho anterior declarava incorretamente `2026-10-26T20:45:00Z` (UTC). Na realidade, o horário registrado correspondia ao horário local de Brasília (BRT, UTC-3), equivalente a `23:45 UTC`. O cabeçalho foi corrigido para evitar inconsistências temporais.
2. **Declaração Honesta de Capturas de Tela Ausentes:**
   - O relatório anterior alegava a existência de dois arquivos PNG (`docs/.../plan-settings-polish/01_plan_1280x577_above_fold.png` e `02_settings_validation_error.png`).
   - A inspeção do sistema de arquivos comprovou que **ambos os arquivos estavam ausentes**. A ferramenta de automação do trabalhador gravou capturas repetidamente no buffer temporário global `/home/eliezer/.config/browser-harness/tmp/shot.png`, sendo sucessivamente sobrescrito e não arquivado no repositório.
   - As seções 3.3, 3.4 e 4 do referido relatório foram corrigidas para declarar explicitamente o status de **não arquivado**, recusando qualquer tentativa de fabricar retroativamente imagens ou copiar o buffer temporário desatualizado.
3. **Escopo Real dos Testes Automatizados Anteriores:**
   - Os 7 testes de `plan-settings-polish.test.ts` foram executados via SSR (`renderToString`) em Node.js. Eles comprovam a sintaxe, unicidade do botão no DOM e marcação acessível, mas **não** comprovam geometria real de pixels de viewport, renderização visual nem confirmação de foco interativo/cliques ao vivo no navegador.
   - A comprovação visual e de interação física acima da dobra fica canonicamente atribuída à suíte Cucumber Playwright autorizada pós-auditoria.

---

## 2. Estrutura da Suíte de Aceitação e Fechamento de Lacunas de Evidência

A suíte Cucumber foi estruturada em 5 funcionalidades consolidadas, totalizando **47 cenários** e **264 passos executáveis**, sem testes redundantes de estilo cosmético e com cobertura integral dos casos críticos:

### 2.1. Funcionalidade 01: Workspace de Investigação e Planejamento Analítico (`01_research_workspace.feature`)
- **Compositor (Shift+Enter vs. Enter):**
  - Digitação real de `Shift+Enter` insere quebra de linha sem disparar requisição POST de plano.
  - Pressionar `Enter` com tema válido dispara exatamente uma requisição POST de criação de plano.
  - Seleção de cards de sugestão preenche o input e transfere o foco (`document.activeElement`) para o editor.
  - Auto-resize dinâmico: expansão vertical com texto multilinha sem corte, adaptação em 375px sem rolagem horizontal e teto de altura máxima de 120px com rolagem vertical intencional para textos longos (>300 caracteres).
- **Painel de Preferências (+):**
  - Verificação geométrica de limites de viewport: `top >= 0` e `isTopClipped === false` sob qualquer estado de rolagem e mobile.
  - Fechamento com tecla `Escape` e retorno de foco para o botão gatilho.
  - Snapshot fidedigno de pontos (1..20) e personas selecionadas, sem contagem legada fixa de 4.
- **Geometria de PlanView em 1280x577 e Mobile:**
  - O botão primário único `Iniciar pesquisa` (`#start-research-btn`) repousa no cabeçalho compacto, posicionado acima da dobra (`isAboveFold === true`, `bottom <= 577px`) no carregamento inicial sem rolagem (`scrollY === 0`).
  - Verificação de acionabilidade física (`isHittable`): o elemento retornado por `document.elementFromPoint(centerX, centerY)` nas coordenadas do viewport coincide com o botão, sem uso de `scrollIntoView` artificial para mascarar problemas de layout.
  - Divulgação progressiva: pontos iniciam recolhidos e expandem individualmente ou via "Expandir todos os detalhes".
  - Proteção contra descarte acidental: clique em "Novo tema" abre `role="alertdialog"` (*"Descartar plano formulado?"*); o clique em "Cancelar" preserva o plano e seus dados intactos.
- **Exportação e Cópia Verificadas:**
  - Clique real em "Baixar .md" aguarda o evento de download (`page.waitForEvent('download')`), lê o stream binário baixado em UTF-8 e inspeciona se o conteúdo é idêntico byte a byte ao dossiê publicado.
  - O hash SHA-256 do arquivo baixado é calculado e comparado com o hash do artefato publicado. Não se considera mera presença de botão como prova de download.
  - Clique em "Copiar Markdown" lê a área de transferência do contexto de teste (`navigator.clipboard.readText()`), nunca lendo o clipboard do SO hospedeiro, e valida igualdade com o dossiê, com feedback visual transitório.
- **Acessibilidade e Responsividade:**
  - Viewports: 375px (mobile), 837px (tablet/narrow) e 916px sem cortes na barra de navegação superior (`isClipped === false`) e sem rolagem horizontal no body (`scrollWidth <= clientWidth + 2`).
  - Suporte a `prefers-reduced-motion: reduce`: painel visível imediatamente sem transições GSAP prolongadas.

### 2.2. Funcionalidade 02: Controle de Auditoria e Tratamento de Falhas (`02_audit_gating_and_failures.feature`)
- **Gating Estrito do Redator (11/12 Critérios):**
  - Parecer reprovado com 10/12 critérios bloqueia rigorosamente a chamada ao endpoint `/writer` (`writerCalled === false`).
  - Dossiê retornado pelo redator com 200 mas status `incompleto` ou sem texto é marcado como falha com diagnóstico visível, nunca como sucesso.
- **Rotulagem Temporal do Ciclo e Diagnósticos Estruturados:**
  - No Ciclo 2 com busca ativa após reprovação no Ciclo 1, o cabeçalho demarca honestamente: `"Auditoria do ciclo 1 — revisão em andamento no ciclo 2"`.
  - Banner explicativo esclarece que a busca em andamento visa enriquecer evidências e superar os apontamentos anteriores.
  - Diagnóstico estruturado com nomes canônicos dos critérios reprovados (`CANONICAL_CRITERIA_NAMES`), lacunas apontadas e ações recomendadas.
  - Registro técnico bruto integral (com IDs de alegações, chunks e fontes) preservado sob disclosure colapsável acessível (`.audit-technical-details`).
- **Retentativa Sensível ao Estágio (Stage-Aware Retry):**
  - Falha de timeout ou 504 na busca web oferece retentativa de busca e auditoria.
  - Busca concluída com sucesso seguida de erro 504 na auditoria: preserva o resultado da busca e oferece "Tentar auditoria novamente", executando a auditoria sem repetir a varredura web.
  - Auditoria aprovada seguida de erro 500 no redator: oferece "Tentar redigir dossiê novamente", chamando exclusivamente o endpoint do redator.
- **Prevenção de Concorrência:** Duplo clique rápido no botão de execução envia apenas uma requisição inicial de busca.

### 2.3. Funcionalidade 03: Configurações, Sessão Integrada e Parâmetros Cifrados (`03_settings_and_credentials.feature`)
- **Validação com Foco Acessível:**
  - Submissão com campos inválidos dispara `aria-invalid="true"` e `aria-describedby`.
  - O foco ativo do navegador (`document.activeElement`) é transferido automaticamente para o primeiro controle inválido (`#llm-base-url`), sem disparar requisições de gravação e sem `.focus()` manual injetado no teste.
- **Alinhamento Normativo Adendo 002 (RN-10):**
  - Explicação visível da regra: Banco de Dados Relacional Cifrado possui prioridade sobre variáveis de ambiente (`.env`).
  - Tabela de credenciais distingue expressamente a coluna de origem ativa entre `"Banco Cifrado"` e `"Ambiente (.env)"`.
  - Chave-mestra `CREDENTIALS_MASTER_KEY` explicada como restrita ao ambiente para bootstrap seguro.
  - Mascaramento client-side e sanitização estrita para `OPENAI_API_KEY`, `JINA_API_KEY` e `WEBHOOK_HMAC_SECRET`.
  - Nenhuma credencial real de produção é modificada pelos testes (isolamento via porta 8011 e chaves temporárias).
- **Preservação de Rascunho em Memória:**
  - Rascunho digitado preservado na navegação interna por hash (`#settings` -> `#research` -> `#settings`), sem gravação em storage persistente. Botão de descarte limpa o formulário com segurança.

### 2.4. Funcionalidade 04: Histórico Local de Pesquisas (`04_history_and_persistence.feature`)
- **Abertura de Relatório Somente de Redação (Sem Plano):**
  - Registro histórico legado contendo apenas `writerResponse` (sem `planResponse`) abre diretamente o relatório do dossiê no workspace.
  - Nenhum plano fictício ou contagem inventada de pontos é fabricada.
  - O `ContextSidebar` órfão não é renderizado quando não há plano associado.
- **Alternância Segura de Registros:**
  - Abrir uma pesquisa que possui plano formulado renderiza o plano e a barra lateral de contexto.
  - Retornar ao histórico e abrir uma pesquisa somente de redação limpa imediatamente os metadados do plano anterior (`currentPlan === null`), exibindo o dossiê em layout unicolunar limpo.
- **Preservação de Snapshots e Sanitização:**
  - Pesquisa com 2 pontos e personas `historiador,cetico` restaura o snapshot exato sem sofrer contaminação pelas seleções ativas do compositor.
  - Projeção segura descarta campos internos de reasoning, envelopes de inferência ou telemetria privada.
  - Tolerância contra registros corrompidos no `localStorage` sem quebrar o componente.

### 2.5. Funcionalidade 05: Separação Contábil de Fontes (`05_sources_accounting.feature`)
- **Contabilidade Tripartite de Fontes:**
  - Substituição definitiva do rótulo enganoso anterior `Fontes Bibliográficas Verificadas` pelo painel acessível `Fontes da Investigação` (`SourceBreakdown`).
  - Três contadores coesos em linha: total consultadas (`read_ok`), utilizadas no dossiê (citadas) e consultadas mas não citadas (contexto investigativo, com nota factual de que não constituem fontes rejeitadas).
  - Grupos expansíveis nativos com `<details>` e `<summary>`. Grupo de utilizadas aberto por padrão; não citadas e total consultadas acessíveis sob demanda.
- **Tratamento Fidedigno de Registros Legados e Desconhecidos:**
  - Relatório legado com status `indisponivel` exibe contadores de consultadas e não citadas como traço (`—`), nunca como zero (`0`) fictício.
  - Badge `Legado / Indisponível` e notificação honesta de que evidências brutas de leitura não foram gravadas.
  - Citações conhecidas extraídas do texto permanecem visíveis no grupo de utilizadas.
- **Rejeição Estrita de Divergência de Hash de Artefato (`artifact_hash`):**
  - Divergência de hash SHA-256 do texto publicado ou de ID rejeita a vinculação de fontes de outra versão.
  - Exibe aviso conciso: *"As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado."*
  - O texto Markdown publicado, a cópia e o download permanecem 100% íntegros.
  - O histórico local não persiste fontes com hash divergente.
- **Registro Legado Apenas com Resumo:** Rejeita vinculação de fontes de artigo completo quando o registro possui apenas `dossier_resumo`, marcando totais como indisponíveis.
- **Tratamento de Falha de Rede:** Erro em `/sources` exibe alerta com botão "Tentar novamente" sem ocultar o dossiê nem prejudicar cópia e download.
- **Cenário de Replay Live Somente-Leitura (`SOURCE_LIVE_REPLAY_PATH`):**
  - Executado exclusivamente se a variável de ambiente `SOURCE_LIVE_REPLAY_PATH` estiver definida com o arquivo de replay temporário (modo 0600) fornecido pelo Root.
  - Inicializa contexto de navegador headless secundário e estritamente isolado (`initIsolatedLiveContext`).
  - Carrega registro histórico real do usuário no storage do contexto isolado e navega para `SOURCE_LIVE_BASE_URL` (`http://127.0.0.1:3002`).
  - Abre a pesquisa, executa bootstrap e consulta `/api/v1/pipeline/{id}/sources` via `GET`.
  - Valida a contabilidade real: **11 consultadas, 9 utilizadas e 2 não citadas** (status `completo`).
  - Expande os grupos de 2 fontes não citadas e de todas as 11 fontes consultadas.
  - Valida a correspondência exata do hash SHA-256 do dossiê exibido com o artefato publicado.
  - Captura screenshot canônico `live-replay-source-breakdown.png` para arquivo de evidências.
  - **Barreira de Segurança Ativa:** O manipulador do contexto isolado intercepta e bloqueia qualquer tentativa de `POST` em `/plan`, `/search`, `/audit` ou `/writer`, garantindo **ZERO re-execuções de modelos pagos**.
  - Se a variável não estiver definida, o teste falha com instrução clara, em vez de pular silenciosamente.

---

## 3. Evidências de Inspeção e Validação Técnica do Harness

### 3.1. Inspeção Estática de Step Definitions e Conformidade Gherkin
Comando executado:
```bash
npx tsx src/tests/cucumber-static-inspection.ts
```
Saída da verificação:
```text
=== Inspeção Estática de Conformidade Cucumber / Gherkin ===

[Definições] Total de step definitions identificadas em steps.ts: 219
  ✓ Nenhuma step definition duplicada encontrada.

[Features] Arquivos .feature encontrados: 5
  • 01_research_workspace.feature: 16 cenários, 101 passos
  • 02_audit_gating_and_failures.feature: 10 cenários, 50 passos
  • 03_settings_and_credentials.feature: 8 cenários, 40 passos
  • 04_history_and_persistence.feature: 7 cenários, 34 passos
  • 05_sources_accounting.feature: 6 cenários, 39 passos

=== Resumo da Inspeção Estática ===
Total de Arquivos Feature: 5
Total de Cenários Gherkin: 47
Total de Passos Executáveis: 264
Total de Step Definitions: 219
Passos Não Atendidos: 0
Duplicatas em steps.ts: 0

✓ TODAS AS STEP DEFINITIONS ESTÃO ÍNTEGRAS, SEM DUPLICATAS OU PASSOS INDEFINIDOS!
```
**Exit Code:** `0`

### 3.2. Checagem Estrita de Tipagem TypeScript dos Steps e World
Comando executado:
```bash
npx tsc --noEmit --target ES2022 --module NodeNext --moduleResolution NodeNext --skipLibCheck features/support/*.ts features/step_definitions/*.ts
```
**Resultado:** Compilação concluída com sucesso sem nenhum erro ou aviso de tipo (`Exit Code: 0`).

### 3.3. Compilação Completa do Projeto Frontend
Comando executado:
```bash
npm run build
```
Saída da compilação:
```text
> deep-research-frontend@1.0.0 build
> tsc && vite build

vite v6.4.5 building for production...
transforming...
✓ 2221 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.97 kB │ gzip:   0.60 kB
dist/assets/index-Wmy6xx4v.css   85.15 kB │ gzip:  25.45 kB
dist/assets/index-DJ1sYgkX.js   510.95 kB │ gzip: 157.42 kB
✓ built in 12.50s
```
**Exit Code:** `0`

### 3.4. Regressão Completa das Suítes Unitárias e Focadas
Comandos executados:
```bash
npx tsx src/tests/defects-regression.ts
npx tsx src/tests/plan-settings-polish.test.ts
npx tsx src/tests/sources-accounting.test.ts
npx tsx src/tests/execution-view-regression.ts
npx tsx src/tests/docs-history-remediation.test.ts
```
**Resultado:** Todos os 38 testes de regressão de componentes reais, regras de sanitização, contratos de API e SSR passaram com sucesso (0 falhas).

---

## 4. Comandos Exatos para Execução da Suíte Final de Aceitação

A execução dos testes Cucumber deve ocorrer **exclusivamente após a aprovação formal do Auditor Independente de todo o projeto**.

### 4.1. Execução da Suíte Padrão de Aceitação (Localhost 8011)
Certifique-se de que o backend de fixture e os serviços simulados estejam ativos na porta `8011`:
```bash
cd /home/eliezer/Escritorio/deep-research/Deep-Research/frontend
BASE_URL=http://localhost:8011 npm run test:e2e
```

### 4.2. Execução com o Ensaio de Replay Live Somente-Leitura (127.0.0.1:3002)
Quando o Root fornecer o arquivo temporário `0600` com os dados do relatório publicado (`dee9fa33-1205-4323-8715-ab388deb8747`):
```bash
cd /home/eliezer/Escritorio/deep-research/Deep-Research/frontend
SOURCE_LIVE_REPLAY_PATH=/path/to/temporary_replay.json \
SOURCE_LIVE_BASE_URL=http://127.0.0.1:3002 \
BASE_URL=http://localhost:8011 \
npm run test:e2e
```

---

## 5. Limitações e Riscos Residuais Honestos

1. **Ausência de Execução Antecipada:**
   - Em conformidade irrestrita com a instrução do usuário (*"DO NOT RUN ANY CUCUMBER until root independent WHOLE-PROJECT final auditor approves"*), o runner `npm run test:e2e` **não foi executado nesta etapa**.
   - Não se reivindica aprovação prévia de testes E2E antes da autorização formal do Root.
2. **Dependência de Servidores Ativos para a Rodada Final:**
   - A execução da suíte requer que o processo de fixture na porta `8011` e (para o cenário de replay live) o servidor live na porta `3002` estejam ativos e acessíveis.
3. **Isolamento de Ambiente e Provedores Pagos:**
   - A suíte padrão em `8011` opera com provedores externos simulados via mock autorizado pelo acceptance-protocol.
   - O ensaio live em `3002` possui barreira de software em nível de navegador que rejeita requisições POST para endpoints de geração, eliminando qualquer risco de custos adicionais com modelos pagos.
