# Rodada 5 — execução modular (fecha R5-01..R5-10)

Base: `feature/gdr-parity` @ `111e44f`. Cada frente roda em worktree própria,
porta própria e arquivos disjuntos. Zero achados é o único critério de aceite.

| Frente | Worktree | Branch | Porta | Arquivos permitidos |
|---|---|---|---|---|
| W1 — reasoning central | `../worktree-worker-1` | `feature/worker-1-reasoning` | 3022 | `frontend/src/components/LinearTimeline.tsx`, `frontend/src/components/ResearchIcons.tsx`, `frontend/src/components/ExecutionView.tsx`, `frontend/src/styles/linear-timeline.css`, `frontend/src/styles/execution-view.css` |
| W2 — right rail | `../worktree-worker-2` | `feature/worker-2-rightrail` | 3026 | `frontend/src/components/ContextSidebar.tsx`, `frontend/src/components/SourcesExplorer.tsx`, `frontend/src/components/TokenUsageMeter.tsx`, `frontend/src/components/Favicon.tsx`, `frontend/src/utils/favicon.ts`, `frontend/src/styles/right-rail.css` |
| W3 — formulários/plano/modais | `../worktree-worker-3` | `feature/worker-3-forms-plan` | 3024 | `frontend/src/components/SettingsView.tsx`, `PlanView.tsx`, `PlanningView.tsx`, `Composer.tsx`, `BottomDock.tsx`, `QuickSheet.tsx`, `styles/forms-parity.css`, `styles/composer-parity.css`, `styles/planning-view.css`, `styles/open-canvas.css`, `components/plan-settings-polish.css` |
| W4 — polimento global | `../worktree-worker-4` | `feature/worker-4-polish-ui` | 3025 | `frontend/src/components/Sidebar.tsx`, `ReportView.tsx`, `DocsView.tsx`, `styles/clean-theme.css`, `styles/components.css`, `styles/world.css` |

## Alvos medíveis

W1 — reasoning central (R5-03, R5-07):
- cabeçalho de grupo **não corta** a pergunta: `scrollWidth <= clientWidth + 1`
  em 1440 e 390, ou quebra em duas linhas com `line-clamp` explícito;
- todo texto dentro de `.tl-conteudo` (fechado e expandido) com
  `font-size >= 12px` — inclui `tl-fonte-dominio`, `tl-fonte-paginas`,
  `tl-callout-score`, `tl-callout-status`, `tl-meta`;
- accordion: `aria-expanded` alterna `false→true`, corpo `0→1`, altura cresce;
- cada evento usa `PersonaIcon` de `ResearchIcons.tsx`; o topo da timeline usa
  `ConvergenceLogo` com a fase corrente (stream/audit/synthesis);
- callouts de auditoria (score/status) com hierarquia: número forte, critério
  em texto secundário, ≥12px.

W2 — right rail (R5-04, R5-05, R5-10):
- rail = **tokens + fontes**; a aba que hoje se chama "Raciocínio" passa a
  "Contexto" (fatos: estágio, ciclo, pontos, auditoria, ID, escopo);
- modo inicial: `fontes` quando houver fontes, senão `contexto`; preferência
  persistida continua respeitada quando o usuário troca;
- chips de fonte: favicon válido, título truncado com ellipsis e `title`,
  domínio mono, badge de estado; nenhum 404 de favicon (usar `https://` +
  fallback de inicial quando o provedor falhar);
- medidor: Entrada / Saída / Total visíveis com `height > 0`; barra
  `scaleX`; estado honesto quando não há telemetria;
- recolhido ≤ 56px com `aria-expanded="false"`.

W3 — formulários/plano/modais (R5-02, R5-08, R5-09):
- `composer-legal` 12px; nenhuma linha do composer abaixo de 12px;
- settings: rótulo acima do input, alinhamento à esquerda consistente,
  `gap` vertical uniforme entre campos (medir `getBoundingClientRect().left`
  de label e input = mesmo x), cartões com padding ≥ 20px;
- plano: card pré-voo (pontos, personas, rigor, custo) legível, ações
  primária/secundária com hierarquia e alvo ≥ 40px; modais com foco preso,
  `Esc` fecha e devolve foco.

W4 — polimento global (R5-01, R5-06):
- `sidebar-conversations-empty` 12px (e todo texto da sidebar ≥ 12px);
- relatório e docs: medida de leitura 60–75ch (`max-width` em px), sem
  alterar a medida da home;
- tema escuro: todo par texto/fundo ≥ 4,5:1 nos componentes alterados;
- `prefers-reduced-motion`: nenhuma animação decorativa;
- foco visível em todos os controles alterados (`outline` 2px, offset 2px).

## Portão comum (por worktree)

```bash
cd <worktree>/frontend
npx tsc --noEmit
npm run build
node ../scripts/audit/capture.mjs http://127.0.0.1:<porta> /tmp/w<N>-shots
SK=~/.claude/skills/impeccable/scripts/impeccable
$SK detect --json "http://127.0.0.1:<porta>/#<rota>"
```

Aceite: `tsc` e `build` limpos, `detect` = `[]` nas rotas da frente
(exceção única: `p.sidebar-conversations-empty`, dono W4), screenshots e
medidas antes/depois no relatório, commit só dos arquivos da frente.

## Merge

Ordem: W2 → W3 → W1 → W4 (CSS de tema por último). Reauditoria isenta na
árvore mesclada: detect nas 8 rotas + probe estrutural + capturas 1440/390,
comparação com `frontend/references/`. Qualquer achado reabre rodada 6 com
worktrees novas.
