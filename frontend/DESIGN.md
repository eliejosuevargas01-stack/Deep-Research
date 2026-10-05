# DESIGN.md — Deep Research Engine

Design system extraído e aplicado. Base: Linear (dark-mode-first, precisão de engenharia).
Fonte de referência: skill `popular-web-designs/templates/linear.app.md`.

## Arquitetura do Design System

| Camada | Arquivo | Conteúdo |
|--------|---------|----------|
| Tokens | `src/tokens.css` | Fontes, spacing (8px base), radius, cores, sombras, z-index, tipografia, breakpoints |
| Primitivos CSS | `src/components.css` | .btn-*, .input, .card, .badge-*, .tabs, .drawer, .tooltip, .toast |
| Primitivos React | `src/ui.tsx` | Button, Input, Card, Badge, Tabs, Drawer (a11y: role=tablist, aria-modal) |
| Estilos legados | `src/style.css` | CSS específico do app (não migrado ainda) |

Ordem de import (main.tsx): `style.css` → `tokens.css` → `components.css`.

## Tokens Principais

### Cores (dark-mode-native, Linear)
| Papel | Token | Valor |
|-------|-------|-------|
| Fundo página | `--color-bg-marketing` | `#08090a` |
| Fundo painel | `--color-bg-panel` | `#0f1011` |
| Superfície elevada | `--color-bg-surface` | `#191a1b` |
| Hover | `--color-bg-surface-hover` | `#28282c` |
| Texto primário | `--color-text-primary` | `#f7f8f8` (nunca `#fff`) |
| Texto secundário | `--color-text-secondary` | `#d0d6e0` |
| Texto terciário | `--color-text-tertiary` | `#8a8f98` |
| Texto mínimo | `--color-text-quaternary` | `#62666d` |
| Marca (CTA) | `--color-brand-indigo` | `#5e6ad2` |
| Accent | `--color-accent-violet` | `#7170ff` |
| Accent hover | `--color-accent-hover` | `#828fff` |
| Borda sutil | `--color-border-subtle` | `rgba(255,255,255,0.05)` |
| Borda padrão | `--color-border-standard` | `rgba(255,255,255,0.08)` |
| Status success | `--color-status-success` | `#10b981` |
| Status warning | `--color-status-warning` | `#f59e0b` |
| Status error | `--color-status-error` | `#ef4444` |

### Tipografia
- Primária: Inter (fallback `system-ui`), `font-feature-settings: 'cv01' 1, 'ss03' 1`
- Mono: JetBrains Mono
- Pesos: 400 (leitura), 500 (UI), 590 (ênfase — assinatura Linear)
- Display usa letter-spacing negativo; abaixo de 16px, tracking normal

### Spacing / Radius
- Base 8px; escala de `--space-1` (1px) a `--space-24` (128px)
- Radius: micro 2px · standard 6px (botões/inputs) · card 8px · panel 12px · pill 9999px · círculo 50%

### Z-index
`--z-dropdown:10` → sticky 20 → fixed 30 → modal-backdrop 40 → modal 50 → popover 60 → tooltip 70 → toast 80

## Regras (Do's / Don'ts)

**Faça:**
- Bordas sempre semi-transparentes brancas, nunca cor sólida escura sobre escuro
- Botões com fundo translúcido (`rgba(255,255,255,0.02–0.05)`)
- Indigo da marca apenas em CTA primário e estados interativos
- Elevação por luminância do fundo, não sombra
- `:focus-visible` com ring (`var(--focus-ring)`) — WCAG 2.4.7

**Não faça:**
- `#ffffff` como texto primário (usar `#f7f8f8`)
- Peso 700; máximo é 590
- Letter-spacing positivo em display
- Sombras para elevação em superfície escura
- Cor quente no chrome da UI (paleta é gray + blue-violet)

## Acessibilidade (Sprint 1 — implementado)
- `:focus-visible` ring global
- `prefers-reduced-motion`: transições zero
- Skip link → `#workspace-main`
- `.sr-only` / `.visually-hidden`
- Drawer: `role="dialog"`, `aria-modal`, `aria-labelledby`
- Tabs: `role="tablist"`/`tab`, `aria-selected`
- Skeleton com `role="status"` + `aria-label`

## Bundle (Sprint 4)
`vite.config.ts` manualChunks: vendor-react 212KB / router 79KB / markdown 166KB / lucide 13KB / app 63KB (gzip 18.7KB). Todos < 500KB.

## Dívida conhecida
- `main.tsx` (2597 linhas) ainda usa classes de `style.css`; migração incremental para primitivos de `ui.tsx` pendente
- Tailwind coexiste com tokens custom (remover Tailwind quando migração completar)
- Ícones Lucide sem `aria-hidden` massivo (tratados como decorativos, baixo risco)
