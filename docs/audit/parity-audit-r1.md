# Auditoria de paridade GDR — rodada 1 (pós-merge)

Data: 2026-10-29 · Branch: `feature/gdr-parity` · Base: `d2ebcd5`

Rodada 1 é a reauditoria isenta depois do merge dos 4 workers. Mesma sonda,
mesmos critérios da rodada 0 (`docs/audit/parity-audit-r0.md`), sem ajuste de
régua para "passar".

## Veredito

**Aprovado — 20/20 no placar, 0 achados na sonda e 0 findings no detector.**

| Dimensão | r0 | r1 | Prova |
|---|---|---|---|
| Integridade de layout | 2/4 | 4/4 | 10/10 combinações rota×viewport sem overflow, texto pequeno, contraste baixo ou alvo < 24px |
| Acessibilidade | 2/4 | 4/4 | skip link `#conteudo`, landmarks, contraste ≥ 4.5:1 no claro e no escuro |
| Theming | 3/4 | 4/4 | claro `#FBFCF9` e escuro `#0F0F0F`, pílulas de persona legíveis nos dois |
| Responsivo | 2/4 | 4/4 | 390×844 sem corte de tema, scroller único por tela |
| Performance / higiene | 3/4 | 4/4 | `tsc` limpo, build limpo, chunk morto de `gsap` removido |

## Evidência executada

```
impeccable detect --json
  /                  -> []
  #harness           -> []
  #execution-search  -> []
  #execution-audit   -> []
  #execution-rejected-> []

parity-probe (5 rotas × 2 viewports)
  failures = 0   (ovf=0 tiny=0 lowContrast=0 smallTargets=0 em todos)

contraste no tema escuro (dark-probe)
  /                 lowContrast=0
  #harness          lowContrast=0
  #execution-search lowContrast=0

npx tsc --noEmit   -> limpo
npm run build      -> limpo (178,32 kB / gzip 48,79 kB)
testes             -> 12/12 verdes
```

## Achados fechados nesta rodada

1. **Piso tipográfico (P1).** `.tl-hora` e `.tl-fonte-paginas` usavam `0.7rem`,
   que com raiz de 15px resolvia em **10,5px**. Fixado em `11px`. Medição pós-fix:
   `smallTextCount = 0` nas 10 combinações.
2. **Contraste das pílulas de persona (P1).** `#c2410c` media **4,1:1**,
   `#7c3aed` **4,49:1** e `#047857` **4,4:1** sobre o próprio tint. Passaram a
   `#9a3412` (5,6:1), `#6d28d9` e `#065f46`. No tema escuro os hues de tema
   claro mediam **2,49–3,23:1**; agora usam os passos 300 equivalentes
   (`#c4b5fd`, `#7dd3fc`, `#fdba74`, `#6ee7b7`, `#fcd34d`).
3. **Alvos de toque.** Toggle "ver reasoning" media 706×**21px** e o botão
   copiar ID **20×28px**. Agora 24px mínimos; `smallTargets = 0`.
4. **Scroller duplo no mobile (P2).** `#harness` a 390px somava página de
   1241px + feed de 506px. Em `≤640px` o feed deixa de ter `max-height`:
   página 2310px com **zero** scrollers internos.
5. **Tema do run cortado a 390px (P1 novo).** `.execution-theme-inline` media
   **573px** dentro de coluna de 334px e começava em **x = −103** — o início do
   título era invisível. Agora `min-width: 0; max-width: 100%`, quebrando em até
   2 linhas no mobile (`flex-basis: 100%`).
6. **Medida de leitura.** `.tl-analise` renderizava 100–102 caracteres por
   linha; o corpo do banner de erro chegava a ~93. Limitados a 68ch e 58ch
   (1ch mede 8px nesta face, então 68ch dava 89 caracteres).
7. **Favicons automáticos (requisito de produto).** O endpoint
   `google.com/s2/favicons` responde 301 para `t*.gstatic.com/faviconV2`, que
   devolve **404** em vários domínios públicos. Pior: o `<img>` do rail nascia
   com `display: none` e `loading="lazy"`, então nunca era buscado — o favicon
   nunca carregava e todo chip caía no tile com a inicial. Correções:
   cadeia Google → DuckDuckGo → `/favicon.ico` do domínio (`src/components/Favicon.tsx`),
   sem `lazy` (imagem sem caixa não é buscada), e tratamento de "load com
   `naturalWidth = 0`" (o 404 do Google chega como `load`, não `error`).
   Prova: **12/12** `<img>` com `naturalWidth > 0` em `#execution-search`.
8. **Higiene.** Chunk `vendor-gsap` no `vite.config.ts` mapeava um pacote que
   não existe no projeto.
9. **Respiro da coluna central.** As linhas da timeline terminavam em x=1044,
   exatamente no hairline do inspetor. Coluna ganhou `padding-right: 24px`
   (conteúdo termina em 1020).

## Ajustes de contrato (spec alinhada ao medido)

`DESIGN.md` foi corrigido onde a régua estava errada, não onde o código estava:

- altura de linha fechada passou de "40–48px" para "40–48px em uma linha só;
  72–96px com título + resumo", porque o conteúdo empilha duas linhas;
- raio do composer: 20px → **26px** (valor real da casca existente);
- documentado o `padding-right: 24px` da coluna central.

## O que a sonda NÃO cobre

- Densidade subjetiva e "gosto" tipográfico (avaliados por comparação visual
  com `frontend/references/`, três leituras independentes).
- Fetch real de fonte externa em produção (CSP/CORS de terceiros).
- Regressão de backend: a API em `:8010` é compartilhada e read-only nesta
  auditoria.

## Reprodução

```bash
cd frontend
node ../../scripts/audit/parity-probe.mjs http://127.0.0.1:3002
SK=~/.hermes/profiles/orchestrator/skills/creative/impeccable/scripts/impeccable
$SK detect --json http://127.0.0.1:3002/#execution-search
```
