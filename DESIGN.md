# DESIGN.md — DeepResearch

Mode: **Operate** (a UI onde o usuário completa uma investigação).
Build path: código. As decisões abaixo são o contrato; qualquer desvio é
achado de auditoria.

## 1. Híbrido de duas referências (split explícito)

- **Estrutura, densidade e anatomia do reasoning: Google Gemini Deep Research**
  (`frontend/references/*13-2*.png`, `*14-56*`, `*14-57*`). Manda em: divisão de
  zonas, largura do painel direito, anatomia do passo de raciocínio, chips de
  fonte por passo, tipografia compacta e ausência de "caixa dentro de caixa".
- **Casca e cromo: o incumbent do produto** (canvas quente `#FBFCF9`, sidebar
  `#F4F5F2`, superfície branca, hairline `#E4E6E1`, acento violeta `#6D28D9`,
  raio de casca 20px no composer). Não substituir por preto do Gemini: o produto
  tem tema claro por padrão e tema escuro opcional.

Regra de ouro: **nenhum card aninhado**. Separação por hairline de 1px e
espaço em branco; superfície elevada só para camada flutuante (popover, modal,
paleta de atalhos).

## 2. Grade

| Zona | Largura | Conteúdo |
|---|---|---|
| Sidebar de navegação | 244px (rail 64px colapsado, esconde ≤900px) | marca, navegação, rodapé de dados/tema |
| Coluna central | `minmax(0, 1fr)` | plano, timeline de raciocínio, dossiê |
| Right rail (inspetor) | 360px, `border-left: 1px` | tokens, status, fontes, escopo |
| Composer | largura da coluna central, `position: sticky bottom` em ≤640px | input + parâmetros |

`workspace-grid` = `minmax(0,1fr) 360px`, `gap: 0`, separação por hairline. A
coluna central reserva `padding-right: 24px` para não encostar no hairline do
inspetor.
Right rail: `position: sticky; top: 58px + 16px`, rolagem própria quando
exceder a viewport, **nunca** criar segunda barra de rolagem na página.

## 3. Tipografia

- Display: `Outfit` (600/700/800) — títulos de tela e números grandes.
- UI/body: `Outfit` 400/500 — **a face Inter está banida** (detector
  `overused-font` a reprova; a paridade não depende dela).
- Mono: `JetBrains Mono` — queries, domínios, timestamps, IDs, scores.
- Rampa: 11, 12, 13, 14, 16, 18, 22, 28, 34px. **Piso funcional 11px**: link,
  botão, label, célula, meta e timecode nunca abaixo disso. 10px só para
  smallprint legal não interativo.
- Altura de linha: 1.45 corpo, 1.25 título. Peso 600 em rótulo, 500 em corpo
  de destaque, 400 em corpo. Sem `letter-spacing` acima de 0.06em fora de
  micro-label maiúsculo.

## 4. Cor

Tokens são a única fonte (`src/styles/tokens.css`). Nenhum literal novo fora
dos tokens; todo token novo precisa existir em `:root` **e** em
`:root[data-theme='dark']`.

- Acento violeta: ação primária, item ativo, foco. Não é decoração de card.
- Cor por persona (pill do agente) precisa manter **≥4.5:1** sobre o próprio
  fundo tintado. Tints atuais reprovam (3.3:1, 2.4:1, 1.7:1): escurecer o texto
  da pill, não clarear o fundo além do token.
- Semântica de estado: verde aprovado, âmbar atenção/pendência, vermelho
  reprovado, violeta em andamento.
- **Cores originais preservadas**: favicons de domínio, logos e ícones de marca
  não recebem filtro, `opacity` de tint nem dessaturação.

## 5. Ícones (contrato obrigatório)

O bloco central usa **exclusivamente** os ícones abstratos de
`/home/eliezer/Descargas/DeepResearchExecution.tsx`, copiados literalmente para
`src/components/ResearchIcons.tsx`:

- `ConvergenceLogo` — fases `stream` | `audit` | `synthesis`, 24×24 viewBox,
  stroke 1.5, animações SMIL internas. Cabeçalho do bloco de execução e do
  rail de fase.
- `PersonaIcon` — `planejador | futurista | cetico | visionario | historiador |
  auditor | redator`, 24×24 viewBox, stroke 1.5.
- `PersonaIcon` 16px no marcador de cada passo da timeline; 20–24px no rail de
  fases; `ConvergenceLogo` 18px no cabeçalho.
- Proibido: `lucide-react` como marcador de persona/passo. Lucide continua
  válido para affordances (chevron, copiar, link externo, fechar).
- Respeitar `prefers-reduced-motion`: as animações SMIL ficam estáticas
  (congelar via CSS `animation: none` não afeta SMIL — usar
  `<svg>` com parada de tempo por `@media` e classe, ou simplesmente renderizar
  a variante sem `<animate>` nesse modo).

## 6. Anatomia do raciocínio (centro)

Uma linha de rail vertical de 1px percorre a timeline. Cada passo:

```
[ícone 16]  AGENTE · título do passo                    00:42   ▾
            resumo em uma linha, corpo 13px
            └ aberto: queries em mono (prefixo "$ "), reasoning em 13px/1.55,
              chips de fonte (favicon 14px + domínio mono truncado)
```

- Altura da linha de uma linha só: 40–48px. Com título + resumo (o caso real):
  72–96px, porque o conteúdo empilha duas linhas de texto. Altura vem do
  conteúdo, nunca de padding: `padding: 4px 0` na linha.
- Divisor de estágio: micro-label mono 11px maiúsculo + hairline, não uma caixa.
- Callout de chave: fundo `--color-surface-subtle`, `border-left: 0`,
  `padding: 8px 12px`, raio 8px, sem ícone decorativo. Usado para a conclusão do
  ponto (aprovado/reprovado) e para o score do auditor.
- Accordion: `aria-expanded` no botão da linha, corpo com `id` referenciado por
  `aria-controls`; clique em qualquer parte da linha alterna.
- Live: item em streaming mostra o logo da fase (`stream`) e cursor de texto;
  ao concluir, recolhe sozinho e troca o ícone para o da persona.

## 7. Right rail

Ordem fixa, cada seção com hairline inferior e cabeçalho mono 11px maiúsculo:

1. **Tokens da sessão** — total grande (22px, mono), barra entrada/saída com
   `transform: scaleX()`, linhas Entrada/Saída/Total, modelo em mono truncado
   com `title`. Sem telemetria: estado honesto ("telemetria indisponível"),
   nunca zero inventado.
2. **Status** — estágio atual, ciclo `n/4`, pontos coletados, ID curto copiável.
3. **Fontes exploradas (N)** — chips compactos: favicon 14px (cor original),
   título/domínio truncado com `title`, badge de estado. Grupo por ponto quando
   houver `ponto_n`. Vazio: linha única explicando o estado, sem card fantasma.
4. **Escopo** — público, recorte temporal, entregável, em 12px.

Cada seção ≤ 220px de altura antes de rolar internamente; a lista de fontes é o
único bloco com rolagem própria (máx. 40vh).

## 8. Formulários / composer / pré-voo

- Prompt bar: superfície branca, raio 26px (a casca existente), hairline 1px,
  anel de foco violeta via `:focus-within`, altura mínima 52px, `Enter` planeja / `Shift+Enter` nova linha, contador
  `n/500` em mono 11px.
- Card de pré-voo do plano: resumo de 1 linha + 4 chips de fase (Mapeamento,
  Busca, Auditoria, Dossiê) em linha, ações "Editar parâmetros" (outline) e
  "Aprovar e iniciar" (primária). Nada de caixa dentro de caixa.
- Modais/popovers: superfície sólida (nunca `color-mix` transparente), raio 16px,
  sombra `--shadow-lg`, foco preso, `Esc` fecha, retorno de foco ao gatilho.

## 9. Movimento

- Transições 150ms `ease-out` em hover/press, 220ms em abertura de accordion.
- **Banido `cubic-bezier(.34,1.56,.64,1)`** (bounce): usar
  `cubic-bezier(.22,1,.36,1)` (ease-out-quint).
- `prefers-reduced-motion`: remove transforms e animações decorativas, mantém
  mudança de estado legível.

## 10. Piso de qualidade (medido, não opinado)

- Contraste ≥4.5:1 em texto pequeno; ≥3:1 em texto grande; medido contra o
  primeiro ancestral opaco.
- Alvo de toque ≥24×24 CSS px (44×44 no mobile para ações primárias).
- Um único container com rolagem por tela.
- `npx tsc --noEmit` limpo; `npm run build` limpo.
- Detector: `impeccable detect` = **0 anti-patterns** nas rotas reais.
