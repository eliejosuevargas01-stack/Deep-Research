# r6: resultado da execução

Base inicial `8c75c50` → HEAD final desta rodada `c4d2651` em `feature/gdr-parity`.

## Worktrees e merge

| Worktree | Commit na branch | Como entrou |
| --- | --- | --- |
| `wt-backend-telemetry-state` | `6570084` | arquivos copiados à mão (branch nasceu de um HEAD antigo do backend, com 12k linhas ainda não commitadas) |
| `wt-layout-scroll-scale` | `fe469b8`, `a7b1dad`, `0983632` | merge `01b7b8f` |
| `wt-icons-personas-planner` | `0f9cc4d`, `8de20a2` | merge `5495450` |
| `wt-theme-contrast-cursor-bg` | `a640ab6` | merge `4a4a1a8` |

Conflito real: `ReasoningCardItem.tsx` (auto-scroll do W2 + ícones do W3) e `main.tsx`
(imports dos dois). Resolvidos à mão; `theme-contrast.css` ficou por último na ordem
dos CSS, senão `gdr-refit.css` sobrescrevia.

Worktrees removidas depois do merge. Branch `feature/r6-backend-telemetry-state`
mantida (não mergeada, conteúdo aplicado por cópia).

## O que foi corrigido

1. **Tokens persistidos por pesquisa.** Colunas `tokens_prompt`,
   `tokens_completion`, `tokens_total` em `pesquisa`, migração aditiva idempotente
   em `app/db/init_db.py`, acúmulo a cada `GenerationAttempt` (planejador,
   buscadores, auditor, redator) e devolução no `GET /pipeline/{id}/status`.
   Provado: pesquisa `c537f85c…` com 3000/12345/15345 devolve os três campos.
2. **Telemetria ao vivo na rail.** `App.tsx` consulta o status a cada 3 s durante a
   execução e uma vez ao abrir o registro; `TokenUsageMeter` prefere o valor ao vivo
   ao `metadados_modelo`.
3. **Status vivo na lista.** `buscando`, `auditando` e `redigindo` viram `Em pesquisa`
   em `Sidebar.tsx`, e o registro da lista é atualizado pelo evento de estágio.
4. **Contador de auditoria.** `audit.result` no SSE já chamava `onAuditResult`; o
   `auditSummary` passou a refletir aprovados/total na hora, inclusive reprovado.
5. **Layout.** `html/body/#root` com 100% e `overflow: hidden`; scroll só no
   `.workspace-main`; tetos duplicados de 1280/1500 px removidos; grade central
   1596 px em 1920 (era 1280); home com compositor ancorado na base e 4 pílulas
   abaixo dele.
6. **Reasoning.** `max-height` + `overflow-y: auto` em aberto e fechado com
   auto-scroll durante streaming (pausa se o usuário subir), corpo em 15 px,
   título em 20 px, badge 13 px, ícone 24 px.
7. **Ícones.** Cada persona com o próprio SVG (historiador, visionário, cético,
   futurista, auditor, redator) ao vivo e depois; planejador com ícone no cabeçalho.
   Traço neutro em `currentColor`, 2.2-2.4 px, animações com amplitude maior.
8. **Tema e fundo.** Spotlight radial seguindo o cursor com `rAF` + lerp, só tokens
   da paleta, desligado em touch e `prefers-reduced-motion`; tema claro em
   `#fbfaf7`; título 11,68:1, corpo 11,68:1, preview 11,86:1, título escuro 16,37:1.

## Evidência

- `node scripts/audit/zero-gate.mjs` → `ZERO FINDINGS` (9 rotas × 3 viewports,
  overflow 0, tipo mínimo ok, sem cursor piscando, sem clipping; pior contraste
  escuro 7,66:1).
- `impeccable detect` em `/#settings` caiu de 10 achados para 0 depois do
  placeholder `#5c5c5c`.
- `npx tsc --noEmit` 0; build 193,58 kB / gzip 54,28.
- 9 suítes de teste do frontend passando; `tests/unit/test_token_accumulation_w1.py`
  passando.
- `docs/audit/r6-shots/` com 30 capturas (home, harness, execução, histórico,
  configurações × 1920/1440/390 × claro/escuro) e as três `final-*`.

## Pendências conscientes

- `gdr-refit` e `app-concurrency` continuam falhando por motivo pré-existente,
  igual em `HEAD` limpo.
- O fluxo do planejador foi só documentado (`docs/architecture/planner-flow.md`):
  o harness roda o SERP antes e manda o contexto pronto; o modelo não faz tool
  calling própria.
- 53 arquivos de backend seguem não commitados na árvore de trabalho (trabalho
  anterior a esta rodada).
