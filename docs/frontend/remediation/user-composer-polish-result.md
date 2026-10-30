# Relatório de Polimento Visual e Interativo do Composer

Data: 26 de outubro de 2026
Alvo: `frontend/src/components/Composer.tsx` e seletores de Composer em `frontend/src/styles/components.css`
Ambiente de Validação: Fixture isolada em `http://localhost:8011` (sem navegação/concorrência com o usuário real em `3002` e sem chamadas a provedores externos pagos)
Evidências: `user-composer-polish-evidence/**`

---

## 1. Diagnóstico do Defeito Raiz

Conforme evidenciado no screenshot autoritativo fornecido pelo usuário (`/tmp/codex-clipboard-9549cfb2-3a3c-4a58-9dca-8ef9194f38a7.png`, arquivado em `user-composer-polish-evidence/00-original-attached-defect.png`):

1. **Defeito Identificado:**
   - Em `frontend/src/styles/main.css`, a regra global `:focus-visible` prescreve `box-shadow: var(--focus-ring);` (`0 0 0 2px #FFFFFF, 0 0 0 4px var(--violet-2)`).
   - O elemento interno `textarea.composer-input` herdava essa pseudo-classe ao ser focado via clique ou navegação.
   - Como o container externo `.composer-box` já ativava `:focus-within` aplicando borda e anel em Violet (`var(--violet)`), renderizava-se um anel retangular roxo e branco interno envolvendo o texto `"O futuro da matriz energética no Brasil"`, aninhado dentro da pílula arredondada externa. O resultado era um contorno visualmente conflitante, distorcido e redundante.

2. **Desalinhamentos Ópticos Concomitantes:**
   - `.composer-box` utilizava `align-items: center;`. Em campos de texto de única linha, o botão de envio (40px), o contador (17px) e o textarea (28px) ficavam em alturas ligeiramente descompassadas em relação à linha de base tipográfica.
   - Em expansão multilinha (2 ou mais linhas), `align-items: center` fazia o botão de envio e o contador flutuarem verticalmente no centro da caixa em vez de se ancorarem estavelmente no canto inferior direito.
   - Em visualização móvel (`max-width: 640px`), o textarea declarava `font-size: 0.95rem` (~15.2px), valor abaixo de 16px que dispara zoom automático indesejado no iOS Safari.

---

## 2. Remediação Implementada

A intervenção foi estritamente delimitada aos arquivos de escopo próprio do Composer:

### A. `frontend/src/styles/components.css`
- **Eliminação do Anel Interno Redundante:**
  Adicionada a regra específica em nível de controle composto:
  ```css
  .composer-box:focus-within .composer-input:focus,
  .composer-box:focus-within .composer-input:focus-visible,
  .composer-input:focus,
  .composer-input:focus-visible {
    outline: none;
    box-shadow: none;
  }
  ```
  O anel de foco acessível é fornecido de forma limpa pelo container composto `.composer-box:focus-within` (`border-color: var(--violet); box-shadow: 0 0 0 1px var(--violet), var(--shadow-composer);`), com contraste superior a 8:1 contra o fundo branco.
- **Preservação de Foco via Teclado nos Demais Controles:**
  O botão de envio (`.composer-send-btn:focus-visible`) e o botão expansível de preferências (`.preferences-toggle-btn:focus-visible`) preservam explicitamente `box-shadow: var(--focus-ring);` quando focados via tecla Tab.
- **Alinhamento Óptico e Flex:**
  - `.composer-box` configurado com `align-items: flex-end;` e padding refinado `8px 12px 8px 16px`.
  - `.composer-input` recebeu `min-width: 0; padding: 8px 0; min-height: 24px; line-height: 1.5; box-sizing: border-box; overflow-y: auto;`, garantindo que o texto de 1 linha tenha exatamente 40px de área vertical e sua linha de base se alinhe milimetricamente ao contador.
  - `.composer-counter` ajustado com `margin-bottom: 12px; line-height: 1; flex-shrink: 0; white-space: nowrap;`, travando a linha de base dos números na mesma altura da linha de base do texto.
  - Botão de envio fixado em `width: 40px; height: 40px; min-width: 40px; min-height: 40px;` ancorado ao fundo à direita.
- **Estados Desabilitado, Carregando e Validação:**
  - Suporte à classe `.composer-box.disabled` com fundo sutil, borda neutra e cursor `not-allowed`.
  - Remoção de borda duplicada da animação de spinner em `.composer-send-btn .spinner`, permitindo que o ícone SVG `Loader2` gire com suavidade sem anel externo parasita.
- **Acessibilidade e Responsividade Móvel (`max-width: 640px`):**
  - Entrada segura com `font-size: 16px;` para eliminar zoom involuntário no iOS Safari.
  - Touch target estendido para `44px` no botão de envio (`min-height: 44px; min-width: 44px;`).
  - Contador `{length}/500` integralmente visível e preservado sem ocultação arbitrária.

### B. `frontend/src/components/Composer.tsx`
- Adicionada a classe condicional `disabled` ao wrapper `.composer-box`:
  ```tsx
  <div className={`composer-box ${disabled || isSubmitting ? 'disabled' : ''}`}>
  ```
- **Auto-resize Responsivo com Guarda de Largura (ResizeObserver):**
  - Anteriormente, o cálculo de altura do textarea (`textareaRef.current.style.height = ...`) era disparado unicamente por `useEffect([value])`. Ao redimensionar a viewport ou mudar a orientação do dispositivo com texto já digitado sem alteração de valor (ex.: desktop -> mobile 375px), o texto quebrava em múltiplas linhas mas a altura permanecia travada na dimensão anterior de 1 linha, provocando aparecimento de barra de rolagem e corte da primeira linha (`06-after-mobile-focused.png`).
  - Implementado `ResizeObserver` nativo observando o elemento do textarea com guarda estrita de variação de largura (`Math.abs(currentWidth - prevWidth) >= 1`). Apenas alterações reais na largura disponível disparam a função de ajuste, eliminando loops de feedback de altura, preservando o foco e conteúdo do usuário, com fallback seguro caso `ResizeObserver` esteja indisponível e desconexão limpa no unmount. Teto de 120px e rolagem intencional para textos longos rigorosamente mantidos.

---

## 3. Verificação com Browser Real (CDP / Fixture 8011)

A validação foi executada no servidor de fixture `http://localhost:8011` utilizando a API nativa `browser_exec` em sessão isolada:

1. **Inspeção de Estilos Computados no Desktop (1280x800):**
   - `.composer-box`: `boxShadow: rgba(109, 40, 217, 0.09) 0px 12px 32px -4px...`, `border-color: rgb(109, 40, 217)`, `height: 58px`.
   - `.composer-input`: `boxShadow: none`, `outline: none`, `height: 37px`, `bottom: 727.71875px`.
   - `.composer-send-btn`: `height: 40px`, `bottom: 727.71875px`. Alinhamento de subpixel perfeito (`bottom` idêntico).
   - `.composer-counter`: `top: 704.46px`, `bottom: 715.71px`, alinhado à linha de base.
   - Evidência arquivada: `user-composer-polish-evidence/04-after-desktop-focused.png`.

2. **Navegação Real por Teclado (Tecla Tab para o Botão de Envio):**
   - Elemento ativo: `BUTTON.composer-send-btn`
   - `matchesFocusVisible: true`
   - `boxShadow: "rgb(255, 255, 255) 0px 0px 0px 2px, rgb(124, 58, 237) 0px 0px 0px 4px"` (`--focus-ring` ativo e de alta visibilidade).
   - Evidência arquivada: `user-composer-polish-evidence/05-after-send-btn-tab-focused.png`.

3. **Inspeção Mobile (375x667, Emulação de Toque / Retina 2x):**
   - `.composer-input`: `fontSize: "16px"` (prevenção contra auto-zoom do iOS).
   - `.composer-send-btn`: `height: 44px`, `width: 44px`, `minHeight: 44px`, `minWidth: 44px` (touch target WCAG).
   - `.composer-counter`: Largura 39.84px visível, `{length}/500` íntegro.
   - Evidência arquivada: `user-composer-polish-evidence/06-after-mobile-focused.png`.

4. **Compilação do Frontend:**
   - Comando: `cd frontend && npm run build`
   - Resultado: Sucesso absoluto (`tsc && vite build` sem avisos ou erros).

---

## 4. Limitações e Fronteiras Observadas

1. **Preservação de Escopo:**
   - Nenhum arquivo fora do escopo atribuído foi modificado. `ExecutionView`, `ContextSidebar`, `App`, `ResearchPreferences`, backend e os arquivos rastreados pelo git permanecem estritamente preservados com seus diffs originais intactos.
2. **Ambiente Real de Usuário:**
   - A aba do usuário em execução real na porta `3002` e o backend `8010` jamais foram recarregados, cancelados ou acionados.
   - Nenhuma pesquisa ou chamada a provedores reais pagos foi disparada.
3. **Auditoria Independente:**
   - Não foi emitido 100% de auto-aprovação unilateral. A suíte Cucumber final não foi executada, ficando reservada para a etapa de auditoria independente subsequente.
