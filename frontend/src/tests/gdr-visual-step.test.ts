import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const cssHook = `
export async function load(url, context, nextLoad) {
  if (url.endsWith('.css')) {
    return { format: 'module', shortCircuit: true, source: 'export default {};' };
  }
  return nextLoad(url, context);
}`;
register('data:text/javascript,' + encodeURIComponent(cssHook), pathToFileURL('./'));

import assert from 'node:assert/strict';
import React from 'react';
import { renderToString } from 'react-dom/server';

const { Composer } = await import('../components/Composer.js');

/* ---------- 1. Toolbar semântica do Composer (SSR) ---------- */
const html = renderToString(
  React.createElement(Composer, {
    value: 'teste tema',
    onChange: () => {},
    onSubmit: () => {},
    isSubmitting: false,
  })
);

assert.ok(html.includes('role="toolbar"'), 'rodapé do composer expõe role=toolbar');
assert.ok(
  html.includes('aria-label="Ações do tema"'),
  'toolbar tem rótulo acessível próprio (não herdado da região)'
);
assert.ok(html.includes('aria-orientation="horizontal"'), 'toolbar declara orientação horizontal');
assert.ok(
  html.includes('class="composer-meta-group" role="group" aria-label="Parâmetros da pesquisa"'),
  'preferências ficam em grupo rotulado dentro da toolbar'
);

/* Atalho alinhado, decorativo para leitores de tela */
assert.match(
  html,
  /<div class="composer-shortcut" aria-hidden="true">[\s\S]*?<\/div>/,
  'dica de atalho renderiza em bloco próprio'
);
assert.match(
  html,
  /class="composer-shortcut"[\s\S]*?<kbd class="composer-shortcut-key">\s*<svg/,
  'primeira tecla usa ícone lucide (CornerDownLeft)'
);
assert.ok(
  (html.match(/composer-shortcut-key/g) || []).length >= 2,
  'segunda tecla (Shift+Enter) também é um chip kbd'
);
assert.ok(html.includes('composer-shortcut-label'), 'rótulos "planeja"/"nova linha" presentes');
assert.ok(html.includes('Enter'), 'atalho Enter visível');
assert.ok(html.includes('Shift+Enter'), 'atalho Shift+Enter visível');

/* Semântica de teclado e prompt */
assert.ok(html.includes('aria-keyshortcuts="Enter Shift+Enter"'), 'textarea anuncia Enter e Shift+Enter');
assert.ok(html.includes('aria-keyshortcuts="Enter"'), 'botão enviar anuncia Enter');
assert.ok(html.includes('aria-describedby="composer-helper-text"'), 'textarea descreve-se pelo helper');
assert.ok(html.includes('Descreva o tema da pesquisa'), 'placeholder do prompt foi polido');
assert.ok(html.includes('10/500'), 'contador reflete o comprimento do tema');
assert.ok(html.includes('Enter planeja'), 'helper de estado válido cita o atalho de envio');

/* Estado de plano ativo: toolbar superior com ícone lucide */
const htmlPlan = renderToString(
  React.createElement(Composer, {
    value: 'tema já planejado',
    onChange: () => {},
    onSubmit: () => {},
    isSubmitting: false,
    currentPlanActive: true,
  })
);
assert.ok(htmlPlan.includes('role="note"'), 'aviso de plano ativo é uma nota, não um botão');
assert.ok(htmlPlan.includes('composer-plan-indicator'), 'indicador de plano mantém a classe de contrato');
assert.match(
  htmlPlan,
  /lucide-sparkles[^"]*composer-plan-icon"[\s\S]*?Plano formulado/,
  'indicador de plano usa ícone lucide (Sparkles) antes do texto'
);

/* ---------- 2. Regras novas lidas do CSS como texto ---------- */
const cssPath = new URL('../styles/gdr-refit.css', import.meta.url);
const css = readFileSync(cssPath, 'utf8');

/* Nada acima foi removido: blocos antigos continuam no arquivo. */
for (const seletor of [
  '.gdr-token-card',
  '.gdr-sources-card',
  '.reasoning-card-body',
  '.gdr-phase',
  '.exec-error-card',
  '.composer-box',
  '.dock-panel',
]) {
  assert.ok(css.includes(seletor), `seletor pré-existente preservado: ${seletor}`);
}

const marker = css.indexOf('D. Polish final');
assert.ok(marker > 0, 'bloco final de polish existe no CSS');
const tail = css.slice(marker);

/* Spring físico nos chips */
assert.ok(
  tail.includes('cubic-bezier(0.34, 1.56, 0.64, 1)'),
  'spring (curva com overshoot) aplicado às transições de chip'
);
assert.ok(tail.includes('.dock-chip:hover'), 'chips do dock ganham hover com spring');
assert.ok(tail.includes('transform: scale(0.985)'), 'active devolve compressão sutil');

/* Glow de foco por CSS */
assert.ok(tail.includes('.composer-box:focus-within'), 'glow de foco declarado em CSS puro');
assert.ok(tail.includes('0 0 0 8px color-mix'), 'halo difuso usa color-mix sobre o violeta');
assert.ok(tail.includes('.composer-box:focus-within .composer-send-btn:not(:disabled)'), 'botão enviar reage ao foco');

/* Painel flutuante: blur + transição suave */
assert.ok(tail.includes('.preferences-panel'), 'painel de preferências entra no tratamento de vidro');
assert.ok(tail.includes('backdrop-filter: blur(14px) saturate(115%)'), 'blur do painel flutuante declarado');
assert.ok(tail.includes('-webkit-backdrop-filter'), 'prefixo Safari presente');
assert.ok(tail.includes('@supports not'), 'fallback sólido quando backdrop-filter não existe');
assert.ok(tail.includes('transform 0.22s cubic-bezier(0.22, 1, 0.36, 1)'), 'transição suave de entrada');

/* Guarda de reduced motion */
assert.ok(tail.includes('@media (prefers-reduced-motion: reduce)'), 'guarda de movimento reduzido presente');
assert.match(
  tail,
  /@media \(prefers-reduced-motion: reduce\)[\s\S]*transition: none !important/,
  'guarda desliga transições'
);
assert.match(
  tail,
  /@media \(prefers-reduced-motion: reduce\)[\s\S]*transform: none/,
  'guarda neutraliza deslocamentos de hover'
);
assert.match(
  tail,
  /@media \(prefers-reduced-motion: reduce\)[\s\S]*animation: none !important/,
  'guarda neutraliza animações de painel'
);

/* Contraste fixado em token AA */
assert.ok(
  /\.composer-counter,[\s\S]*?color: var\(--color-text-secondary\)/.test(tail),
  'textos secundários fixados em --color-text-secondary'
);
for (const alvo of ['.composer-shortcut', '.composer-helper-text', '.gdr-token-note', '.gdr-phase-meta']) {
  assert.ok(tail.includes(alvo), `contraste cobre ${alvo}`);
}

assert.ok(css.trimEnd().endsWith('}'), 'arquivo CSS termina em bloco fechado');

console.log('gdr-visual-step ok');
