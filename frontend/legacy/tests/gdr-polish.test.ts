import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
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
const htmlComposer = renderToString(
  React.createElement(Composer, {
    value: 'teste tema',
    onChange: () => {},
    onSubmit: () => {},
    isSubmitting: false,
  })
);
assert.ok(htmlComposer.includes('role="toolbar"'), 'composer meta tem role toolbar');
console.log('gdr-polish ok');
