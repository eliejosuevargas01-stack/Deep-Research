# Relatório de Correção de Tipografia: Geist Sans (`tokens.css`)

## 1. Contexto e Diagnóstico

- **Problema Identificado:** Em `frontend/src/styles/tokens.css`, o token `--font-sans` declarava `'Geist', system-ui, ...`. No entanto, os pacotes instalados `@fontsource/geist-sans` (400, 500, 600) registram suas regras `@font-face` sob o nome de família exato `'Geist Sans'`. Como resultado, os navegadores não associavam o token à fonte self-hosted declarada em `main.css`, caindo silenciosamente no fallback do sistema.
- **Referência Aplicada:** Diretriz do Craft Floor (`impeccable/reference/craft-floor.md`), que prescreve o uso estrito de fontes self-hosted para preservar a identidade visual aprovada sem depender de fallbacks acidentais.
- **Princípio de Intervenção Bounded:** Nenhuma outra alteração de código ou topologia foi realizada. Os relatórios prévios (como `docs/frontend/worker-fix-r1.md`) e os arquivos de estado do detector foram rigorosamente preservados.

---

## 2. Correção Implementada

- **Arquivo Modificado:** `frontend/src/styles/tokens.css` (linha 58).
- **Alteração:**
```diff
--- a/frontend/src/styles/tokens.css
+++ b/frontend/src/styles/tokens.css
@@ -58,3 +58,3 @@
   /* Tipografia */
-  --font-sans: 'Geist', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
+  --font-sans: 'Geist Sans', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
   --font-mono: 'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
```

---

## 3. Comandos Executados e Resultados

### 3.1. Compilação TypeScript e Build de Produção
- **Comando:** `npm run build`
- **Diretório:** `frontend/`
- **Código de Saída:** 0
- **Resultado:**
  - TypeScript compilation (`tsc`) concluída com 0 erros.
  - Bundling Vite concluído em 3.2s.
  - Artefatos de fonte empacotados com sucesso no build:
    - `dist/assets/geist-sans-latin-400-normal-gapTbOY8.woff2` (33.40 kB)
    - `dist/assets/geist-sans-latin-500-normal-uokXdC-Q.woff2` (34.72 kB)
    - `dist/assets/geist-sans-latin-600-normal-DFOURf8L.woff2` (35.29 kB)

### 3.2. Testes de Aceitação E2E (Cucumber / Playwright)
- **Comando:** `BASE_URL=http://127.0.0.1:3001 npm run test:e2e`
- **Diretório:** `frontend/`
- **Código de Saída:** 0
- **Resultado:**
  - 21 cenários executados: 21 aprovados (100%).
  - 100 passos Gherkin executados: 100 aprovados (100%).
  - Tempo de execução: ~33 segundos.
  - Todas as capturas de tela em `docs/frontend/evidence/` atualizadas com sucesso sob a nova tipografia.

---

## 4. Evidência Técnica de Carregamento no Navegador (Chromium)

Testado através do Playwright em sessão headless Chromium autorizada contra a pré-visualização isolada (`http://127.0.0.1:3001`):

1. **Requisições de Rede (Font Assets):**
   - `http://127.0.0.1:3001/node_modules/@fontsource/geist-sans/files/geist-sans-latin-400-normal.woff2`: HTTP 200 (`font/woff2`).
   - `http://127.0.0.1:3001/node_modules/@fontsource/geist-sans/files/geist-sans-latin-500-normal.woff2`: HTTP 200 (`font/woff2`).
   - `http://127.0.0.1:3001/node_modules/@fontsource/geist-sans/files/geist-sans-latin-600-normal.woff2`: HTTP 200 (`font/woff2`).
   - `http://127.0.0.1:3001/node_modules/@fontsource/geist-mono/files/geist-mono-latin-400-normal.woff2`: HTTP 200 (`font/woff2`).

2. **Estilo Computado no DOM:**
   - `window.getComputedStyle(document.body).fontFamily`:
     `"Geist Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
   - `window.getComputedStyle(document.documentElement).fontFamily`:
     `"Geist Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`

3. **Status do Conjunto de Fontes (`document.fonts`):**
   - `document.fonts.status`: `"loaded"`
   - `document.fonts.check('15px "Geist Sans"')`: `true`
   - `document.fonts.check('400 15px "Geist Sans"')`: `true`
   - `document.fonts.check('500 15px "Geist Sans"')`: `true`
   - `document.fonts.check('600 15px "Geist Sans"')`: `true`
   - Entradas no `FontFaceSet`:
     - Família `Geist Sans`, peso `400`: `status: "loaded"`
     - Família `Geist Sans`, peso `500`: `status: "loaded"`
     - Família `Geist Sans`, peso `600`: `status: "loaded"`

4. **Medição Física de Glifos (Canvas Metrics):**
   - Texto de amostra: `"The quick brown fox jumps over the lazy dog 1234567890"`
   - Largura renderizada com `'Geist Sans'`: `433.00px`
   - Largura renderizada com fallback `sans-serif` do sistema: `410.03px`
   - Divergência métrica confirmada (`isGeistSansMetricDivergentFromSystemFallback: true`), comprovando que o motor de renderização do Chromium está desenhando os glifos físicos da fonte self-hosted `Geist Sans`.

---

## 5. Arquivo de Evidência Estruturada

O registro estruturado em JSON com a telemetria completa da execução encontra-se persistido em:
`docs/frontend/evidence/font-verification.json`
