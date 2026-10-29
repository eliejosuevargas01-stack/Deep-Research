# Delta estrutural vs. referência — rodada 3

Data: 2026-10-29 · Branch: `feature/gdr-parity` · Base: `b0e3b96`
Contrato: `DESIGN.md` §2 (grade + sidebar), §6 (linha do passo), §7 (painel de
contexto), §8 (composer).

A rodada 2 fechou o que era mensurável por sonda e listou quatro divergências
**estruturais** (D1–D4). A rodada 3 implementa exatamente esses quatro itens em
quatro worktrees disjuntas. Este documento guarda o antes medido e o alvo.

## Antes (medido em `:3002`, `scripts/audit/structural-gate.mjs`)

| Métrica | 1440×900 | 390×844 | Alvo |
|---|---|---|---|
| Abas no painel direito | 0 | 0 | 2 (`Raciocínio`, `Fontes`) |
| Painéis (`[role=tabpanel]`) visíveis | 0 | 0 | 1 |
| Faixa de tokens (altura) | 0 px | 0 px | > 0 nos dois modos |
| Largura do rail | 360 px | 358 px | 360 / 320 (≤1280) |
| Linhas de passo fechadas | 11 | 11 | 11 |
| Altura das linhas fechadas | 28–187 px | 45–331 px | 40–56 px |
| Linhas fechadas com `<time>` visível | 11/11 | 11/11 | 0 |
| Linhas fechadas com chip de persona | 9/11 | 9/11 | 0 |
| Barras de ferramentas (`.dock-bar`) | 1 (fora do composer) | 0 | 1, dentro do composer |
| Slot `[data-composer-tools]` | ausente | ausente | presente |
| Faixa de status com contagens | 1 | 1 | 0 |
| Observação legal do composer | ausente | ausente | presente |
| Conversas na sidebar | 0 (3 semeadas) | 0 | 3 |
| Rodapé "dados ficam neste navegador" | 1 | 0 | 0 |
| Overflow de documento | 0 | 0 | 0 |

## Alvos da rodada

- **D1** — painel único com cabeçalho, abas `Raciocínio`/`Fontes · N`, faixa de
  tokens sempre visível, recolhível para trilho de 44px.
- **D2** — linha fechada com um único rótulo denso (persona inline), hora/chips
  só no corpo expandido, 40–56 px.
- **D3** — composer único, acessórios na própria barra, `BottomDock` portado
  para `[data-composer-tools]`, painel de ferramenta em fluxo abaixo da barra.
- **D4** — grupo `Conversas` na sidebar com item ativo e link para o histórico.

## Portões

`npx tsc --noEmit`; `npm run build`; `impeccable detect --json` = `[]` por rota;
`parity-probe` sem achado novo; `structural-gate` nos alvos acima. O veredito da
rodada só sai com a árvore mesclada reauditada — não por worktree.
