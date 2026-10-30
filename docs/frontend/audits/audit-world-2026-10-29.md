# Auditoria de mundo visual — 2026-10-29

Escopo: frontend do Deep Research (`frontend/`), servidor Vite em
`http://127.0.0.1:3001`, API em `127.0.0.1:8010` com SQLite scratch. Nenhuma
chamada a provedor pago foi feita.

## O que mudou (entregáveis)

| # | Entregável | Implementação | Evidência |
|---|---|---|---|
| 1 | Listas e layouts refinados | Lista de temas virou `ul` com numeral mono, título/descrição em duas linhas, hover que desloca 4px, foco com outline de 2px; histórico virou linha com fio de 1px e ações que aparecem no hover/focus-within | `EmptyState.tsx`, `HistoryView.tsx`, `.sample-topic-*`/`.history-container` em `world.css`; screenshots `final-light`, `final-history` |
| 2 | Fundo dinâmico | Três auroras em gradiente radial, animadas só por `transform` (46/58/64s), grão de 4,5%, força 26% no claro e 17% no escuro, desligável em Aparência e congelada em `prefers-reduced-motion` | `HorizonBackground.tsx`, `.ambient-*`; perf abaixo |
| 3 | Toolbar e popups abaixo do chat | Dock com Parâmetros, Aparência, Atalhos e Sessão; painel abre **em fluxo** sob a barra (não cobre o input); `aria-expanded`, `Esc` fecha e devolve foco, clique fora fecha | `BottomDock.tsx`; teste funcional: `panel:true → Esc → false`, foco `dock-btn`, stepper `1→2` |
| 4 | UX writing e poda | "Modo local" removido de todo o `src` (`grep` = 0); hero reescrito ("Investigue a fundo. Audite cada ponto." / "Plano, evidência auditada, dossiê: cada frase com sua fonte."); histórico sem jargão de cookie; títulos de sessão em linguagem de usuário | `grep -rn "Modo local" src` → 0; `EmptyState.tsx`, `HistoryView.tsx`, `Navbar.tsx` |
| 5 | Logo SVG real | Marca = três estratos que convergem para um ponto dentro de um arco de auditoria; componente inline (`currentColor` + acento) e asset `public/logo.svg`/`favicon.svg` | `BrandMark.tsx`, `public/logo.svg`; aplicado em sidebar e navbar |
| 6 | Grafo interativo na documentação | SVG de 720×316, cinco estágios em linha, loop `auditoria → busca` tracejado, nó focável (`role=button`, `aria-pressed`), detalhe abaixo que troca por clique ou `Enter`; loop só anima no nó ativo | `ArchitectureGraph.tsx`; teste: foco + `Enter` → detalhe "Plano"; screenshot `final-docs` |
| 7 | App mobile dedicado + Android | Tab bar fixa (48px), FAB 46px, quick sheet com puxador/arrasto/`Esc`/scroll lock, composer sticky acima da barra, 236px de respiro no fim do conteúdo; Capacitor com `appId online.dominuslabs.deepresearch` | `MobileTabBar.tsx`, `QuickSheet.tsx`, `capacitor.config.ts`, `android/`; APK `app-debug.apk` 4,6 MB, `minSdk 24`, `targetSdk 36` |

## Números medidos

### Sweep neutro (7 rotas × 3 viewports = 21 combinações)

```
overflow 6 · contrast 0 · unnamed 0 · small 0 · headingJumps 0
```

Os 6 "overflow" são **apenas** `<text>` do SVG do grafo em `#docs`:
`scrollWidth` 72 vs `clientWidth` 67 (5px). O bbox real do glifo é 66px dentro
de um nó de 120px — não há clipping. O Chromium reporta `scrollWidth` de
`<text>` de forma que não corresponde ao layout; `document.scrollWidth −
clientWidth = 0` em 320, 390, 720, 1440 e 844×390 (paisagem).

### Zoom de texto 200%

```
#research, #settings, #execution-audit → único item: .ambient-field
document.documentElement.scrollWidth − clientWidth = 0
```

`.ambient-field` é `position: fixed; inset: 0; contain: strict; overflow:
hidden` com filhos decorativos maiores que a viewport (necessário para a
aurora). O `scrollWidth` do container mede o conteúdo clipado; a página não
rola na horizontal.

### Tema escuro

```
#research   lightSurfaces 0 · body rgb(15,15,15)
#settings   lightSurfaces 0 · body rgb(15,15,15)
#execution-audit lightSurfaces 0 · body rgb(15,15,15)
```

Contraste de texto no escuro (contra o primeiro ancestral opaco):
título 16,37:1; corpo 11,86:1; muted 6,13–7,15:1; input 14,97:1;
rótulos do dock 10,85:1; chip ativo 10,65:1.

### Detector (`impeccable detect`)

```
1440x800 → [overused-font (advice)]
 390x844 → [overused-font (advice)]
```

`overused-font` é advisory aceito: Inter é a face de corpo declarada no
`DESIGN.md`; trocar a face seria mudar o mundo visual. O `ai-color-palette`
("purple/violet gradient") foi eliminado ao trocar a aurora violeta por
teal/sage/âmbar — restou 0 ocorrência.

### Performance de ambientação (CDP, 3s, 1440×900)

| Estado | TaskDuration | Script | Layout | LCP | CLS |
|---|---|---|---|---|---|
| auroras ligadas | **0,1%** | 0% | 0% | 632 ms | 0 |
| auroras desligadas | 0% | 0% | 0% | 396 ms | 0 |

A primeira versão em canvas 2D media **97,8%** de main thread — foi descartada,
não otimizada.

### Build

```
index-DxjmXjV1.js   147,40 kB │ gzip 40,40 kB
index-Ch7Pxd1H.css  115,95 kB │ gzip 18,97 kB
DocsView            15,27 kB │ gzip  5,55 kB
vendor-react        142,94 kB │ gzip 45,79 kB
vendor-markdown     120,40 kB │ gzip 34,95 kB  (lazy)
built in 5,69s
```

`tsc --noEmit`: exit 0. `cap sync` + `gradlew assembleDebug`: exit 0.
APK: `online.dominuslabs.deepresearch`, versionName 1.0, compileSdk 36,
minSdk 24, targetSdk 36, 4,6 MB.

## Ciclo auditoria → correção → regressão

| Achado medido | Correção | Regressão |
|---|---|---|
| Skip-link com `position: relative` criava 117px de coluna e comprimia o composer para **209px** | Removido do seletor de empilhamento | Composer **326×169** em 390×844; `doc overflow 0` |
| Painel do dock abria para cima e cobria o input | Painel passou a abrir em fluxo, sob a barra | `panel true → composer não sobreposto`; screenshot `research-light-dock` |
| Canvas 2D: **97,8%** de TaskDuration | Trocado por CSS transform-only | **0,1%**; LCP 632 ms; CLS 0 |
| Aurora violeta disparava `ai-color-palette` | Teal (`info`) + sage (`success`) + âmbar (`warning`), violeta só em ação | Detector: 0 `ai-color-palette` |
| Escuro com aurora 0,30 e sem grão (banding) | 0,17 + grão 4,5% + borda de 1px na sidebar | Screenshot aprovado; contraste 6,13–16,37:1 |
| Grafo com nós escalonados e sem grade | Linha única, 5×120px, loop com dip 74 | Sem texto fora do nó; legível em 390 e 1440 |
| Texto funcional 10,8px/9,9px | 11,25px (sessão) e 11,1px (tab bar) | `undersized-ui-text` 0 |
| Zoom 200%: marca da sidebar 233px em 165px | `font-size: min(1.08rem, 22px)` + marca isolada ≤820px | Zoom: só o artefato do `.ambient-field` |
| Alvos móveis: fechar 36px, segmento 26px | 44px e 40px; tabs 48px; FAB 46px | Todos ≥40px (WCAG 2.5.8 mínimo 24) |
| Ícone de marca genérico (Compass) em navbar/sidebar | `BrandMark` + favicon SVG | Asset 489 B; contraste herdado |

## Auditoria visual (o que o olho pegou)

- Primeira versão do dock: painel flutuante sobre o composer → rejeitado.
- Primeira versão da aurora clara: mancha roxa cobrindo o topo → força 26% e
  três matizes distintos.
- Primeira versão do escuro: halo saturado e faixas → 0,17 + grão.
- Grafo em "S": aresta de reprovação cruzando o fluxo → linha única com retorno
  abaixo.
- Marca pequena na sidebar (1,02rem) → 1,08rem com limite em px.

## Dívida declarada (não é pendência de UI)

- Ciclo real de execução com provedor (streaming, erro, dossiê, reload no meio)
  não foi exercitado: exige chamada paga, fora de escopo por decisão.
- `overused-font` permanece como advisory consciente.
- Os dois artefatos de medição (SVG `<text>` e `.ambient-field`) estão provados
  acima com o número que importa: overflow horizontal do documento = 0.

## Checklist final

- [x] 10 referências Awwwards verificadas com tier/data e URL
- [x] Listas redesenhadas (temas + histórico) com hover/foco
- [x] Fundo dinâmico performático e desligável
- [x] Dock de ferramentas abaixo do chat, com popups em fluxo e teclado
- [x] "Modo local" removido; copy podada
- [x] Logo SVG autoral na paleta, em componente e asset
- [x] Grafo interativo de arquitetura/loops na documentação
- [x] Mobile nativo (tab bar, FAB, sheet com gesto) + APK Android compilado
- [x] `tsc`, build, sweep, detector, zoom e tema escuro medidos
- [x] Nenhum `TODO`/`FIXME`/mock novo introduzido
