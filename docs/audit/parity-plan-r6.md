# Plano r6: correções de estado, escala visual e polimento

Base: `feature/gdr-parity` em `8c75c50`. Backend 8010 no ar.
Evidência visual: `frontend/problems/*.png` (8 capturas, 1920×1080).

## Worktrees

| Worktree | Branch | Escopo |
| --- | --- | --- |
| `../wt-backend-telemetry-state` | `feature/r6-backend-telemetry` | tokens no banco + todos os agentes, status vivo, contador de auditoria |
| `../wt-layout-scroll-scale` | `feature/r6-layout-scale` | 100vh sem scroll global, +50% central, limite e auto-scroll do reasoning, pills na home |
| `../wt-icons-personas-planner` | `feature/r6-icons` | SVG +50% e animação forte, ícone próprio por persona, ícone do planejador |
| `../wt-theme-contrast-cursor-bg` | `feature/r6-theme` | background com cursor, contraste, tema claro mais confortável |

## Propriedade de arquivos (sem colisão)

- **W1:** `app/**`, `frontend/src/App.tsx`, `components/Sidebar.tsx`,
  `components/ContextSidebar.tsx`, `components/TokenUsageMeter.tsx`,
  `hooks/usePipelineStream.ts`, `services/api.ts`, `types/api.ts`.
- **W2:** `styles/clean-theme.css`, `styles/main.css`, `styles/composer-parity.css`,
  `styles/reasoning-feed.css`, `components/EmptyState.tsx`, `components/Composer.tsx`,
  `components/ReasoningCardItem.tsx`.
- **W3:** `components/ResearchIcons.tsx`, `components/PlanningView.tsx`,
  `styles/planning-view.css`, novo `styles/icons-scale.css`.
- **W4:** `components/HorizonBackground.tsx`, novos `styles/ambient-cursor.css` e
  `styles/theme-contrast.css`, `src/main.tsx` (só a lista de imports).

Nenhum worker toca arquivo de outro. `App.tsx` é só do W1.

## Achados confirmados nas capturas

1. Reasoning ocupa a largura toda, mas a coluna central é cercada por espaço morto; o
   texto sai pequeno e a página inteira rola.
2. Todos os cards de persona em execução usam o mesmo ícone genérico; o planejador
   não tem ícone nenhum.
3. Painel direito: `telemetria indisponível` durante a busca e `Auditoria:
   Aguardando` mesmo com pontos já auditados/reprovados.
4. Barra de conversas mostra `Planejado` enquanto o pipeline roda.
5. Tema claro estoura branco; reasoning e divisórias com pouco contraste.

## Aceite por frente

- **W1:** colunas `tokens_prompt/tokens_completion/tokens_total` em `pesquisa`
  (migração aditiva em `init_db`), incremento a cada `generation_attempt` de
  qualquer etapa; `/api/v1/pipeline/{id}/status` e SSE devolvem o acumulado;
  evento `audit.result` alimenta `ContextSidebar` na hora; `Sidebar` mostra
  `Em pesquisa` durante busca/auditoria/redação; teste de backend cobrindo soma
  de tokens e transição de status; doc `docs/architecture/planner-flow.md`.
- **W2:** `html, body, #root { height: 100%; overflow: hidden }`, scroll só em
  `.workspace-main`; coluna central mais larga; escala +50% nos blocos de
  reasoning (fontes, títulos, badges, gaps); `max-height` + `overflow-y: auto` em
  aberto e fechado; auto-scroll durante streaming; sugestões viram pills abaixo
  do compositor com o topo livre.
- **W3:** `PersonaIcon` recebe e respeita cada persona em execução e concluída;
  `PlanningView` renderiza o ícone do planejador; tamanho +50%, `stroke-width`,
  opacidade e keyframes visivelmente maiores; nada de cor fora da paleta.
- **W4:** spotlight radial seguindo o cursor com interpolação, só cores da paleta;
  reasoning com contraste maior; tema claro com off-white suave; contraste AA
  mantido nos dois temas.

## Verificação (todos)

```
cd frontend && npx tsc --noEmit && npm run build
node --import tsx src/tests/<suite>.test.ts
npx vite --port 30XX --strictPort   # porta própria por worker
```

Depois do merge: `impeccable detect` nas 9 rotas, `impeccable critique` visual,
comparação com `frontend/problems/*.png`, capturas novas em
`docs/audit/r6-shots/`. Loop até 0 achados.
