# Deep Research — Relatório de Correções do Frontend (Round 1)

## 1. Identificação do Ciclo de Correção
- **Ciclo:** Worker Correction Round 1 (Pós-Auditoria Independente `disposition: fix`).
- **Auditor Independente:** Profile `Auditor` (`ag/gemini-3.8-flash-high`, reasoning high).
- **Repositório:** `/home/eliezer/Escritorio/deep-research/Deep-Research`.
- **Status do Build:** Compilação TypeScript (`tsc && vite build`) com 0 erros.
- **Status dos Testes de Aceitação:** 21 cenários Cucumber (100 passos Gherkin) aprovados com 100% de sucesso.

---

## 2. Matriz de Resolução dos Achados da Auditoria Independente

| ID do Achado | Gravidade | Descrição / Requisito | Ações de Correção Implementadas | Evidência Comprovada |
| :--- | :---: | :--- | :--- | :--- |
| **FINDING-R1-01** | **P0** | Truncamento e estouro de texto e botões no relatório mobile ($\le 375\text{px}$). | Reduzido padding de `.report-card` para 16px no mobile; aplicado `flex-wrap: wrap` e largura responsiva de 50%/100% aos botões `.btn-secondary`; adicionado `overflow-wrap: break-word` e `word-break: break-word` ao `.markdown-body`; ativado wrapping de URLs longas em `.source-item`. | `docs/frontend/evidence/mobile-finished.png` (inspecionado via `vision_analyze`: botões e textos 100% contidos e legíveis). |
| **FINDING-R1-02** | **P0** | Ausência de capturas de tela para estados mobile (planejado, configurações, falha). | Implementados cenários específicos no Playwright/Cucumber para captura móvel em viewport 375x812 dos estados: plano estruturado, configurações com tabela de parâmetros e alerta de bloqueio de auditoria. | `docs/frontend/evidence/mobile-planned.png`<br>`docs/frontend/evidence/mobile-settings.png`<br>`docs/frontend/evidence/mobile-failure.png`. |
| **FINDING-R1-03** | **P1** | Vazamento de enums internos em inglês no status da barra lateral (`searching`, `completed`, etc.). | Implementadas funções auxiliares `getStatusLabel` e `getStatusBadgeClass` em `ContextSidebar.tsx` traduzindo integralmente todos os estados de `PipelineStage` para português com fallback neutro `"Em processamento"`. | Verificado visualmente em `mobile-finished.png` e `mobile-failure.png`: chips exibem `"Dossiê concluído"` e `"Reprovado na auditoria"`. |
| **FINDING-R1-04** | **P1** | Destruição indiscriminada de transições por regra global `0.001ms` em `prefers-reduced-motion`. | Substituída a regra destrutiva em `main.css` por transições suaves de opacidade (`0.15s ease-out`) sem deslocamentos físicos (`transform: none`). Adicionada limpeza formal de tweens GSAP no desmontar do componente (`gsap.killTweensOf`). | `frontend/src/styles/main.css` e `frontend/src/App.tsx`. |
| **FINDING-R1-05** | **P1** | Promessa inflada de "segurança total" nas configurações e texto ambíguo "(Aberto)" na navbar. | Substituída a cópia em `SettingsView.tsx` por descrição honesta e precisa da volatilidade em memória da aba do navegador. Na `Navbar.tsx`, o badge quando ausente agora exibe `"Sem Chave em Memória"` (removida a alegação de backend aberto). | `docs/frontend/evidence/desktop-settings.png` e `docs/frontend/evidence/mobile-settings.png`. |
| **FINDING-R1-06** | **P1** | Denominador enganoso no badge de auditoria de pontos (exibia `10/11` com 12 avaliados). | Corrigida a interpolação em `ExecutionView.tsx` para o padrão explícito: `${item.criterios_aprovados}/${item.criterios?.length || 12} critérios • mín. ${item.criterios_minimos}`. | `docs/frontend/evidence/desktop-failure.png` e `docs/frontend/evidence/mobile-failure.png`: exibe com precisão `Reprovado (10/12 critérios • mín. 11)`. |
| **FINDING-R1-07** | **P2** | Ausência de reatividade imediata no badge de chave da navbar ao salvar em memória. | Implementado disparo de evento nativo `apikeychange` em `setApiKey` e `clearApiKey` no `api.ts`, ouvido reativamente pelo `App.tsx`, atualizando o badge superior imediatamente sem recarregar ou navegar. | Cenário automatizado em `features/03_settings_and_credentials.feature`. |
| **FINDING-R1-08** | **P2** | Oclusão de conteúdo por compositor sticky flutuando sobre cards longos durante a rolagem. | Ajustado `.composer-anchor` em `components.css` para encaixe no fluxo inferior com `position: sticky; bottom: max(var(--space-4), env(safe-area-inset-bottom, 16px));`, permitindo rolagem livre sem sobreposição de nós. | Inspecionado e validado via `vision_analyze` em `desktop-planned.png` e `mobile-planned.png`. |

---

## 3. Resolução da Advertência do Detector Mecânico (Impeccable Detect)
- **Advertência:** `border-left: 3px solid var(--color-primary)` em `.markdown-body blockquote` (linha 891 do `components.css`).
- **Remediação Aplicada:** Borda substituída por divisor sutil de 1px (`border-left: 1px solid var(--color-border-strong)`), respeitando o teto de espessura de 1px para divisores e alertas prescrito no Craft Floor.
- **Evidência:** `frontend/src/styles/components.css` verificado sem advertências de estilo.

---

## 4. Mitigação dos Riscos de Contrato e Robustez Adicional

1. **Tratamento de Objetos de Detalhe FastAPI (Erro 422):**
   - Função `parseApiError` em `api.ts` estendida para extrair com precisão objetos estruturados contendo `mensagem`, `pergunta_de_esclarecimento` e `diagnostico`, concatenando-os amigavelmente em vez de exibir `[object Object]`.
   - Testado pelo cenário `Tratamento de erro 422 com objeto de detalhe estruturado`.

2. **Exigência de Dossiê Textual não Vazio para Conclusão:**
   - Em `App.tsx`, a transição para `completed` exige estritamente que `wRes.status === 'concluido'` E que `wRes.dossier_final` contenha texto válido maior que zero. Respostas com status `incompleto`, `falha` ou corpo vazio são direcionadas para o estado `failed` com alerta descritivo.
   - Testado pelo cenário `Redator retornando 200 com status incompleto ou dossiê vazio não é considerado sucesso`.

3. **Isolamento de Requisições Concorrentes por ID de Pesquisa:**
   - Adicionada referência de controle `activeResearchIdRef` em `App.tsx`. Respostas tardias de requisições anteriores são descartadas imediatamente se o usuário tiver iniciado ou carregado outra investigação.

4. **Projeção Segura e Bounded do Histórico Local:**
   - Em `historyService.save` (`history.ts`), foi implementada a sanitização defensiva que projeta exclusivamente atributos públicos (`id_pesquisa`, `tema`, `criado_em`, `pontos`, `dossier_final`), descartando telemetria interna, envelopes de chamadas LLM e tokens.
   - Testado pelos cenários `Projeção segura de histórico descartando raciocínio interno e envelopes` e `Resiliência contra registros corrompidos no armazenamento local`.

5. **Proteção Client-Side de Segredos (`WEBHOOK_HMAC_SECRET`):**
   - Função `safeClientMask` em `SettingsView.tsx` força mascaramento client-side para chaves sensíveis (`WEBHOOK_HMAC_SECRET`, `OPENAI_API_KEY`, etc.), mesmo quando o backend retornar texto em claro (ex: `tipo === 'webhook'`).
   - Testado pelo cenário `Proteção client-side contra vazamento de segredo HMAC desmascarado`.

6. **Salvamento Parcial e Granular de Credenciais:**
   - O loop de persistência em `SettingsView.tsx` agora registra sucessos e falhas por parâmetro, limpando da tela estritamente os campos sensíveis salvos com êxito e mantendo os campos com erro visíveis com mensagem detalhada para correção.

7. **Validação Estrita de URL e Inteiros Positivos:**
   - Validador `isPositiveInteger` rejeita estritamente números decimais (ex: `3.5`), strings não numéricas, zero ou negativos. URLs são validadas através do construtor nativo `URL` exigindo protocolo `http/https` e hostname válido.

---

## 5. Resultados dos Testes de Aceitação E2E (Cucumber)

Comando executado:
```bash
npm run test:e2e
```

**Resultado:**
- **Total de Cenários:** 21 cenários executados.
- **Aprovados:** 21 cenários (100% pass rate).
- **Total de Passos Gherkin:** 100 passos executados.
- **Aprovados:** 100 passos (100% pass rate).
- **Tempo:** 25.69 segundos em Chromium headless.

---

## 6. Catálogo Completo de Evidências em `docs/frontend/evidence/`

1. `desktop-empty.png`: Tela inicial vazia em 1440x900 com sugestões temáticas.
2. `mobile-empty.png`: Tela inicial vazia responsiva em viewport 375x812.
3. `desktop-planned.png`: Plano de 5 pontos com stepper conectado e ação única `[▶ Iniciar pesquisa]`.
4. `mobile-planned.png`: Plano adaptado em coluna única para mobile, cards secundários empilhados e botão touchable.
5. `desktop-finished.png`: Dossiê analítico concluído com status, botões de ação e lista de 3 fontes canônicas.
6. `mobile-finished.png`: Dossiê em viewport mobile com quebra de linha de botões e texto sem corte lateral.
7. `desktop-failure.png`: Bloqueio estrito da auditoria com badge `10/12 critérios • mín. 11`.
8. `mobile-failure.png`: Tela de falha em mobile perfeitamente contida sem transbordamento horizontal.
9. `desktop-settings.png`: Configurações em desktop com chave em memória ativa, teste de conexão e tabela RN-10.
10. `mobile-settings.png`: Configurações em mobile com grid colapsado em coluna única e inputs sem truncamento.
11. `desktop-history.png`: Histórico local devidamente rotulado com pesquisas concluídas.
12. `real-fastapi-http.json`: Registro de execução dos endpoints síncronos contra a API real isolada.
13. `impeccable-detect.json`: Relatório original do detector mecânico (preservado).

---

## 7. Limitações Residuais
- **Modo Síncrono Estrito:** O sistema aguarda o encerramento determinístico de cada fase (Search -> Audit -> Writer). Streaming via SSE permanece como escopo exclusivo do Checkpoint 2.
- **Volatilidade de Chave:** A chave `X-API-Key` reside apenas na memória da aba. O recarregamento da página (F5) limpa a chave por design de segurança.
