# Pendências rodada 4 (pós-merge r3)

Árvore: `feature/gdr-parity` @ merge r3. Medido em `:3002` com API `:8010`.
`impeccable detect --json` por rota + `structural-gate` + `probe-details`.

## Estrutura r3 — aprovada

| Alvo | Antes | Depois | Veredito |
|---|---|---|---|
| Abas no painel | 0 | 2 (`Raciocínio`, `Fontes·6`), 1 painel visível | ok |
| Faixa de tokens | 0 px | 74 px, nos dois modos | ok |
| Linha fechada | 28–187 px, 11 com hora, 9 com chip | 44–45 px, 0 hora, 0 chip | ok |
| Composer | 1 dock fora, faixa de status, sem nota legal | 0 dock fora, slot presente, nota legal, 0 faixa | ok |
| Sidebar | 0 conversas, rodapé "dados ficam…" | 3 conversas (seed), sem rodapé | ok |
| Probe 10 combinações | 11 overflow a 390 | 0 overflow, 0 tiny, 0 contraste, 0 alvo | ok |

## Achados abertos (zero-findings policy)

| # | Rota | Achado | Medida | Dono |
|---|---|---|---|---|
| F1 | todas | `p.sidebar-conversations-empty` texto 11,5px | 11,5px < 12 | sidebar |
| F2 | exec | `span.tl-grupo-tema` 11px (x3) | 11px < 12 | timeline |
| F3 | exec | `span.tl-cursor` cursor piscante decorativo (2 por rota) | animação `tl-pisca` | timeline |
| F8 | exec | `span.tl-grupo-tema` estoura o container | scrollWidth 708–715 × clientWidth 619, sem ellipsis | timeline |
| F4 | settings | `section.card p` ~107 chars, `.alert-banner div` ~108 | > 80 | polish |
| F5 | settings | `#creds-list-heading` desbalanceado (advisory) | última linha 16% | polish |
| F6 | settings | hierarquia tipográfica plana (advisory) | body 12,8 / h2 15,8 / h1 17,3 → passo 1,23 | polish |
| F7 | docs | `span.arch-metric` 10,5px; 5 blocos com ~96–105 chars; 3 stragglers | < 12px; > 80 | polish |

Contraste no escuro dos componentes novos (abas, tokens, fontes, conversas,
linha): **0 abaixo de 4,5:1** — sem achado.

## Regra de fechamento

Cada dono corrige seu item, mede antes/depois, commita e o merge é reauditado.
Rodada só fecha com `detect` = `[]` em todas as rotas e probe estrutural verde.
