# Rodada r7 — impeccable audit + critique

Alvo: as 7 capturas de `frontend/problems` e as telas que elas representam.
Loop executado: detect → sweep → correção → re-auditoria, até zero achado.

## Como as telas foram congeladas

- `#research-sim` (novo): plano pré-gerado + pipeline simulado que avança
  busca → auditoria → redação → concluído, com tokens e status subindo.
- `#execution-failed` (novo): estado terminal de falha de redação.
- `#execution-rejected`, `#execution-search`, `#plan`, `#harness`: já existiam.

## Achados e correções

| Evidência | Achado | Correção | Prova |
|---|---|---|---|
| Imagen 3 | Ícones dos buscadores sem cor; painel preso em "Auditoria Aguardando" | Cores por persona (só quando ativa) + `auditAoVivo` no painel | 10 ícones, 4 ativos; 2 detect achados → 0 |
| Imagen 4 | Banner do card de falha translúcido, texto da timeline aparecendo por trás | Card opaco (`rgb(247,245,241)` / `rgb(26,25,26)`), `z-index: 2`, coluna | `scrollWidth == clientWidth` em 1440/768/390 |
| Imagen 5 | Botões do card de erro colidindo/borda sumindo | `execution-banner-actions` com wrap, botões `flex: 0 0 auto` | botões terminam em 537/691 com card até 1032 |
| Imagen 6 | Scrollbar nativa e notação "2.185,3k" | Scrollbar na paleta (`thin`, 22% do texto) e `formatCompactTokens` em mil/mi | `2,19 mi`, `19,1 mil` |
| Imagen 7 | Ícones monocromáticos; cabeçalho rolava junto | `data-persona` + cor ativa; header `flex: 0 0 auto`, `.tl-linear` como único scroller | header y=28 h=115 fixo; timeline sh 563 / ch 501 |
| Imagen 8 / base | JSON cru do planejador e banner de 500 | `raciocinioLegivel` (parcial incluso) e `ErrorNotice` único | 3 amostras sem `{`/`"`; 0 overflow |
| Home | Área vazia sem identidade | Hero das 7 personas + fundo que reage ao ponteiro | hero 880×248; `--cursor-px` 0.41→0.46 alterando as duas camadas |

## Auditoria final

- `impeccable detect` — 0 achados em `/`, `#research`, `#research-sim`, `#plan`,
  `#execution-failed`, `#execution-search`, `#execution-rejected`, `#settings`,
  `#history`, `#docs`, `#harness`.
- `neutral-sweep` (7 rotas × 3 larguras) — 0 achados de nome acessível, alvo,
  heading, overflow de página; 1 scroll container nas telas de trabalho.
- `zero-gate` — ZERO FINDINGS (inclui contraste nos dois temas e 390px).
- `tsc` 0, build ok, 5 suítes de frontend ok.

## Artefatos aceitos (não são defeito)

- `scrollWidth > clientWidth` em elementos com `text-overflow: ellipsis`
  (título da rail, tema inline, ações da timeline) e em `<text>` de SVG:
  o conteúdo é cortado de propósito e não gera rolagem horizontal
  (`documentElement.scrollWidth == clientWidth`).
- `#plan` mantém 1 h1 e as amostras em h2; nenhum salto de heading.
