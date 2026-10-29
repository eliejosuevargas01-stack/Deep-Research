# Auditoria de paridade GDR — rodada 0

Data: 2026-10-29. Alvo: `frontend/` do repositório Deep-Research.
Método: build viva em `http://127.0.0.1:3002` (Vite, API 8010), varredura
`impeccable detect` sobre 4 rotas + sonda Playwright própria medindo contraste
contra o primeiro ancestral opaco, piso tipográfico, alvos de toque, rolagem e
overflow por elemento (`scripts/audit/parity-probe.mjs`).
Estados congelados usados: `#harness`, `#execution-search`, `#execution-audit`,
`#execution-rejected` (harnesses de DEV, dados mock — nenhuma chamada paga).

## Passo 1 — Análise de desvio visual (app atual × referências)

Referências do gabarito: `frontend/references/Captura desde 2026-10-29 13-2*.png`
e `14-56/14-57` (Gemini Deep Research). Capturas `14-56`, `14-57` e `15-01` são
do próprio app (estado anterior), não do gabarito.

| Zona | Gabarito (Gemini) | App na rodada 0 | Desvio |
|---|---|---|---|
| Cabeçalho do bloco central | logo da fase + título do run + contagem de páginas em uma linha | `h1` "Investigação em andamento" + badge de estágio + barra de progresso; sem logo de fase | Ícone de convergência ausente |
| Passo de reasoning | marcador abstrato de 24px + header em negrito + corpo em 1 parágrafo, accordion por passo | cartão com borda/fundo, chip de persona colorido, ícone lucide, timestamp 10.5px | Caixa dentro de caixa; ícone errado; texto abaixo do piso |
| Fontes por passo | grade de chips com favicon + domínio truncado, agrupadas por cluster | só `1 página lida` em texto; chips existem apenas no rail | Chips de fonte ausentes no passo |
| Right rail | painel com "Fuentes exploradas" (dropdown) e lista densa | rail de 360px com 5 cards: tokens (vazio), status, fontes (vazio), escopo, meta | Estrutura certa, densidade e estados vazios errados |
| Tokens | contador sempre visível | "Telemetria de tokens indisponível" ocupa um card inteiro | Estado vazio inflado; sem total/entrada/saída quando não há telemetria |
| Prompt bar | barra única com chips de modo e ações abaixo | composer com toolbar de 4 gatilhos + contador + 3 linhas de helper | Denso, mas sem hierarquia; helper redundante |
| Tipografia | 13-14px corpo, 11px meta, mono em números | Inter em 58-83% do texto, 19 nós funcionais a 10.2-10.5px | Piso violado; face gasta |
| Hierarquia | aberturas por hairline, sem sombra | cards brancos com sombra suave sobre canvas | "Box-in-box" parcial |

## Passo 2 — Auditoria Impeccable (rodada 0)

### Placar

| # | Dimensão | Nota | Achado-chave |
|---|---|---|---|
| 1 | Acessibilidade | 2 | 6 nós de texto com contraste 1.86:1–3.84:1 e 19 nós funcionais a 10.2–10.5px |
| 2 | Performance | 3 | Chunks separados corretamente; `gsap` mapeado no Vite mas nunca importado (config morta) |
| 3 | Theming | 3 | Tokens completos e tema escuro definido; 4 literais de persona fora dos tokens |
| 4 | Responsivo | 2 | Zero overflow horizontal, mas dupla rolagem em ≤640px e prefers-color-scheme ignorado (correto) |
| 5 | Integridade de implementação | 2 | 1 anti-pattern + 4 advisories do detector; ícones de persona não são os do contrato |
| **Total** | | **12/20** | Aceitável — trabalho significativo necessário |

### Achados

**P1-01 · Contraste das pills de persona (3.84 / 2.72 / 1.86 / 2.69 : 1)**
- Local: `frontend/src/styles/linear-timeline.css:262-288`
- Categorias: Acessibilidade, Theming. WCAG 1.4.3 (AA).
- Medido: Historiador `#a855f7` sobre `#f1e8f9` = 3.84:1; Cético `#f97316`/`#fbecde`
  = 2.72:1; Auditor `#eab308`/`#f9f3dc` = 1.86:1; Visionário `#0ea5e9`/`#dff2f7` = 2.69:1.
- Impacto: rótulo de agente ilegível em tela de brilho baixo e para baixa visão.
- Correção: escurecer o texto da pill (manter o tint), não clarear o fundo.

**P1-02 · Texto funcional abaixo de 11px**
- Local: `linear-timeline.css` (timecodes 10.5px, rótulos de persona 10.2px);
  19 nós por rota de execução.
- Categoria: Acessibilidade. Impacto: meta ilegível em alta densidade e alvo de
  leitura prejudicado.
- Correção: piso 11px para timecode, label e meta; mono 11px nos números.

**P1-03 · Ícones de pessoa/passo em desacordo com o contrato**
- Local: `ReasoningCardItem.tsx:13` (lucide), `ReasoningFeed.tsx:2` (`Brain`),
  cabeçalho de `ExecutionView.tsx` sem logo de fase.
- Categoria: Integridade de implementação. O contrato exige `PersonaIcon` e
  `ConvergenceLogo` de `/home/eliezer/Descargas/DeepResearchExecution.tsx`.
- Impacto: a interface não tem assinatura própria no bloco que é o produto.

**P2-01 · Card dentro de card no reasoning**
- Local: `ReasoningCardItem.tsx` + `reasoning-feed.css` (cartão com borda, raio
  e fundo dentro do painel do feed).
- Categoria: Integridade. Impacto: densidade e leitura piores que o gabarito.

**P2-02 · `[side-tab]` — barra colorida de 2px**
- Local: `frontend/src/styles/gdr-refit.css:277` (`border-left: 2px solid var(--color-primary)`).
- Detector: anti-pattern contado. Correção: hairline neutra + peso/tamanho.

**P2-03 · `[bounce-easing]` em 3 transições**
- Local: `gdr-refit.css:468`, `:536`, `:583` (`cubic-bezier(.34,1.56,.64,1)`).
- Correção: `cubic-bezier(.22,1,.36,1)`, 150-220ms.

**P2-04 · `[overused-font]` Inter em 58-83% do texto**
- Local: `frontend/src/styles/tokens.css:109` (`--sans: "Inter"`).
- Correção: `--sans: "Outfit"` (já é dependência e já carrega 600/700/800),
  importando 400/500 em `main.css`.

**P2-05 · Favicon externo falha e some sem fallback**
- Local: `SourcesExplorer.tsx:83` — `https://www.google.com/s2/favicons?...`.
- Medido: `404 t1.gstatic.com/faviconV2?...bcb.gov.br...` na rota
  `#execution-search`; o `onError` esconde o `<img>` e o chip fica sem marcador.
- Correção: tile com a inicial do domínio como fallback, sem tingir o favicon real.

**P2-06 · Dupla rolagem em ≤640px**
- Medido: em `#harness` 390×844 a página rola (`scrollHeight` 1241) e o
  `.reasoning-feed-stream` mantém rolagem própria (1598 em 506px).
- Correção: um único scroller por tela; feed sem `max-height` quando a página já rola.

**P2-07 · Estado vazio do medidor de tokens ocupa um card**
- Local: `TokenUsageMeter.tsx:33-43`.
- Impacto: o elemento mais importante do rail (tokens) aparece como ausência.
- Correção: linha honesta + estrutura de 3 linhas mesmo sem telemetria de modelo.

**P3-01 · `gsap` no `manualChunks` sem import no código**
- Local: `frontend/vite.config.ts:31`. Categoria: Performance/manutenção.

**P3-02 · Helper do composer repete o contrato de teclado em 3 linhas**
- Local: `Composer.tsx` (helper "Enter planeja, Shift+Enter nova linha" + contador
  + dica de 5-500 caracteres). Categoria: Clareza.

### O que está certo (manter)
- Um único `<main>` com `h1` correto por rota; `nav` com rótulo; skip link presente.
- Tema padrão é o desenhado: com `prefers-color-scheme: dark` e sem `data-theme`,
  o app continua claro (`body` `rgb(251,252,249)`) — não herda o SO.
- Zero overflow horizontal em 1440 e 390 nas 4 rotas.
- Chunks separados para markdown/ícones/react; nenhum canvas animando em RAF.
- Tokens completos e `:root[data-theme='dark']` cobrindo o conjunto usado.

## Plano de execução (4 pacotes independentes)

| Worker | Branch | Posse | Entrega |
|---|---|---|---|
| 1 | `feature/worker-1-reasoning` | `ResearchIcons.tsx` novo, `ReasoningFeed`, `ReasoningCardItem`, `LinearTimeline`, `ExecutionView`, `linear-timeline.css`, `reasoning-feed.css`, `reasoning-step.css` | Ícones do contrato, timeline aberta, accordion, chips de fonte no passo, P1-01/02/03, P2-01 |
| 2 | `feature/worker-2-rightrail` | `TokenUsageMeter`, `SourcesExplorer`, `ContextSidebar`, `right-rail.css` novo | Medidor real, chips com favicon + fallback, seções por hairline, P2-05/07 |
| 3 | `feature/worker-3-forms-plan` | `Composer`, `PlanView`, `ResearchPreferences`, `QuickSheet`, `BottomDock`, `forms-parity.css` novo | Prompt bar, pré-voo, modais sólidos, P3-02, alvo de toque |
| 4 | `feature/worker-4-polish-ui` | `tokens.css`, `main.css`, `components.css`, `gdr-refit.css`, `open-canvas.css`, `clean-theme.css`, `world.css`, `App.tsx`, `index.html` | P2-02/03/04/06, a11y do shell, tema escuro, movimento |

Regra de merge: cada worker só escreve nos arquivos da sua coluna; CSS novo entra
por import local do componente, sem tocar `main.tsx` — nenhum conflito previsto
além de linhas de import.
