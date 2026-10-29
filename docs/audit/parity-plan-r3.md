# Rodada 3 — execução modular (fecha D1–D4 do delta r2)

Contrato: `DESIGN.md` §2, §6, §7, §8. Base: `feature/gdr-parity` em `09867ba`.
Cada frente roda em worktree própria, com portas distintas e arquivos disjuntos.

| Frente | Worktree | Porta | Arquivos permitidos |
|---|---|---|---|
| W6 — painel de contexto (D1) | `../worktree-worker-6` | 3016 | `frontend/src/components/ContextSidebar.tsx`, `frontend/src/components/SourcesExplorer.tsx`, `frontend/src/components/TokenUsageMeter.tsx`, `frontend/src/styles/right-rail.css` |
| W7 — linha do passo (D2) | `../worktree-worker-7` | 3017 | `frontend/src/components/LinearTimeline.tsx`, `frontend/src/components/ResearchIcons.tsx`, `frontend/src/styles/linear-timeline.css`, `frontend/src/styles/execution-view.css` |
| W8 — composer único (D3) | `../worktree-worker-8` | 3018 | `frontend/src/components/Composer.tsx`, `frontend/src/components/BottomDock.tsx`, `frontend/src/styles/forms-parity.css`, `frontend/src/styles/composer-parity.css` |
| W9 — histórico na sidebar (D4) | `../worktree-worker-9` | 3019 | `frontend/src/components/Sidebar.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/clean-theme.css` |

## Alvos mensuráveis (medidos, não opinados)

D1 — painel de contexto:
- cabeçalho com título truncado + alternador `Raciocínio` / `Fontes · N` + recolher;
- exatamente **um** modo renderizado por vez (`[role="tabpanel"]` visível = 1);
- faixa de tokens visível nos dois modos (`getBoundingClientRect().height > 0`);
- recolhido: largura ≤ 56px, `aria-expanded="false"`;

D2 — linha do passo:
- linha fechada com **um** rótulo de texto (persona inline), sem `<time>` visível,
  sem chip de persona; altura entre 40 e 56px;
- expandida: `aria-expanded="true"`, corpo com queries mono + reasoning +
  chips de fonte; uma única `<time>` no DOM visível por linha;
- nenhum par `<button>` + `::after` duplicando chevron;

D3 — composer:
- uma única barra de ferramentas na tela (`[data-composer-tools]`), zero
  `.dock-bar` fixa separada;
- zero faixa de status com `ponto • personas • rigor` fora da caixa;
- `input` do tema com `getBoundingClientRect().y < innerHeight` a 390px;
- painel de ferramenta aberto não cobre o `textarea` (`elementFromPoint` no
  centro do input devolve o próprio textarea ou descendente);

D4 — sidebar:
- grupo `Conversas` com até 6 itens, `aria-current="page"` no ativo, link
  "Ver histórico", estado vazio de uma linha;
- sem o texto "Dados ficam neste navegador" no rodapé.

## Portão comum

```bash
cd <worktree>/frontend
npx tsc --noEmit && npm run build
BACKEND_PORT=8010 npx vite --port <porta> --strictPort   # em background
node ../scripts/audit/parity-probe.mjs http://127.0.0.1:<porta>
node ../scripts/audit/capture.mjs http://127.0.0.1:<porta> /tmp/w<N>-shots
SK=~/.hermes/profiles/orchestrator/skills/creative/impeccable/scripts/impeccable
$SK detect --json "http://127.0.0.1:<porta>/#execution-search"
```

Aceite da frente: `tsc` limpo, build limpo, `detect` = `[]`, probe sem novo
achado (overflow, texto <11px, contraste, alvo <24px), e os números acima
medidos e impressos no relatório. Screenshots em `/tmp/w<N>-shots`.

## Merge

Ordem: W9 (App.tsx) → W6 → W7 → W8. Conflitos esperados só em CSS de tema.
Depois: reauditoria isenta na árvore mesclada e loop até 0 achados.
