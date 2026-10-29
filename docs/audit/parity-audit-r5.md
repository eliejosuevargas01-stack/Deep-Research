# Auditoria de paridade GDR — rodada 5 (medida)

Árvore: `feature/gdr-parity` @ `111e44f`. App em `http://127.0.0.1:3002`,
API `127.0.0.1:8010`. Método: `impeccable detect --json` por rota,
`scripts/audit/probe-details.mjs`, `scripts/audit/structural-gate.mjs`,
capturas 1440×900 e 390×844, leitura das imagens de `frontend/references/`.

## Anatomia de referência (Google Deep Research)

| Zona | Referência | Estado atual |
|---|---|---|
| Nav esquerda | fixa, lista de pesquisas, ação primária no topo | ok |
| Centro | canvas de trabalho + raciocínio por persona, passos expansíveis | ok (timeline única com ícones `ResearchIcons`) |
| Rail direita | tokens (entrada/saída/total) e fontes com favicon | ok em estrutura; aba "Raciocínio" mostra **fatos**, não raciocínio |
| Tipografia | passo claro h1 → h2 → corpo | corrigido em settings (`22/16/14`) |
| Densidade | linha fechada ~44 px, detalhe sob demanda | ok |

## Achados abertos (zero-findings policy)

| # | Rota | Achado | Medida | Dono |
|---|---|---|---|---|
| R5-01 | todas | `p.sidebar-conversations-empty` 11,5px | `font-size: 11.5px` (clean-theme.css:330) | W4 |
| R5-02 | `/` | `p.composer-legal` 11px (advisory) | `font-size: 11px` (composer-parity.css:650) | W3 |
| R5-03 | exec | cabeçalho de grupo corta a pergunta de pesquisa | `.tl-grupo-tema` sw 708 × cw 619, ellipsis em 1440 | W1 |
| R5-04 | exec | aba "Raciocínio" do rail lista estágio/ciclo/ID — nome promete raciocínio que vive no centro | `role=tab` textos `["Raciocínio","Fontes·6"]` | W2 |
| R5-05 | exec | rail abre em "Raciocínio" mesmo com 6 fontes coletadas | `deepResearch.railMode` default | W2 |
| R5-06 | relatório | `.markdown-body` a 720px/15px ≈ 104 caracteres por linha | `max-width: 720px` | W4 |
| R5-07 | exec | corpo expandido ainda tem 11px (`tl-fonte-dominio`, `tl-fonte-paginas`, `tl-callout-score`, `tl-meta`) | 8 seletores a 11px | W1 |
| R5-08 | settings | rótulos/inputs desalinhados e cartões sem respiro vertical | inspeção visual 1440/390 | W3 |
| R5-09 | plano | card pré-voo e modais sem revisão de paridade nesta rodada | `#plan` não capturado no ciclo anterior | W3 |
| R5-10 | exec | favicon externo 404 (`gstatic faviconV2` com `http://bcb.gov.br`) | 2 requests 404 por rota | W2 |

## Fechados nesta rodada (resíduo r4, commit `111e44f`)

- timeline: micro-rótulos 12px, "ao vivo" textual no lugar do cursor piscante (`tl-pisca` removido);
- settings: rampa 22/16/14, medida 560px, `text-wrap: balance`;
- docs: `arch-metric` 12px, markdown com 560px, `text-wrap: pretty`;
- detect em `#execution-search`, `#settings` e `#docs`: só resta R5-01.

## Portão de fechamento

`detect` = `[]` nas 8 rotas (root, history, settings, docs, execution-search,
execution-audit, execution-rejected, harness), 0 overflow de documento em
390/768/1440, 0 texto < 12px, sem cursor piscante, rail com tokens + fontes e
centro com raciocínio expansível usando os ícones de `ResearchIcons.tsx`.

## Fechamento medido (rodada 5)

Varredura final em 9 rotas × 3 viewports (`scripts/audit/zero-gate.mjs`):

```
detect por rota ......... 0 achados em /, #history, #settings, #docs,
                          #execution-search, #execution-audit,
                          #execution-rejected, #harness, #plan
overflow de documento ... 0 em 390, 768 e 1440
texto < 12px ............ 0 (era 22 classes entre 11 e 11,9px)
cursor piscante ......... 0 (tl-pisca removido do CSS e do TSX)
elemento clipado ........ 0 (HTML; <text> de SVG é artefato de instrumento)
rail .................... abas Contexto / Fontes·6, tokens visíveis nos dois
                          modos, 360px, recolhível a ≤56px
centro .................. 20 SVGs de persona na timeline, grupo em 2 linhas
                          com scrollWidth == clientWidth (1440 e 390)
escuro .................. body rgb(15,15,15); pior contraste 6,54:1
tsc --noEmit ............ exit 0
build ................... ok (index 183,94 kB · gzip 51,42 kB)
```

Achados abertos desta rodada: **nenhum**. A aba do rail passou a se chamar
"Contexto" porque lista estágio/ciclo/pontos/ID — o raciocínio é a timeline
central, como na referência.

