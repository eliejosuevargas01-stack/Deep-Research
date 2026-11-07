/**
 * Testes Focados de Produção (Sem código espelhado / Sem simulação fictícia de pipeline)
 * Importa e executa exclusivamente componentes e serviços reais de produção:
 * - historyService (sanitização real e persistência defensiva)
 * - PlanView (renderização real SSR via renderToString para planos legados vs com snapshot)
 * - SettingsView (renderização real SSR com rascunho controlado em memória)
 * - initialSettingsFormData (contrato de inicialização limpa sem segredos)
 */
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';

const cssHook = `
export async function load(url, context, nextLoad) {
  if (url.endsWith('.css')) {
    return { format: 'module', shortCircuit: true, source: 'export default {};' };
  }
  return nextLoad(url, context);
}
`;
register('data:text/javascript,' + encodeURIComponent(cssHook), pathToFileURL('./'));

import assert from 'node:assert/strict';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { historyService } from '../services/history';
import { PlanResponse, ResearchHistoryRecord } from '../types/api';

// Armazenamento em memória isolado para os testes de historyService
const memoryStorage: Record<string, string> = {};
global.localStorage = {
  getItem: (k: string) => memoryStorage[k] ?? null,
  setItem: (k: string, v: string) => { memoryStorage[k] = String(v); },
  removeItem: (k: string) => { delete memoryStorage[k]; },
  clear: () => { for (const k in memoryStorage) delete memoryStorage[k]; },
  length: 0,
  key: () => null,
} as unknown as Storage;

async function runProductionTests() {
  console.log('--- Executando Testes com Código Real de Produção ---');

  const { PlanView } = await import('../components/PlanView.js');
  const { SettingsView, initialSettingsFormData } = await import('../components/SettingsView.js');

  // =========================================================================
  // 1. PlanView Real: Plano Legado sem Preferências vs Snapshot
  // =========================================================================
  console.log('\n[Teste 1] PlanView real (SSR): Plano legado sem preferências');
  const legacyPlan: PlanResponse = {
    id_pesquisa: 'legacy-prod-001',
    tema: 'História da Energia no Brasil',
    n_pontos: 2,
    criado_em: '2026-10-26T12:00:00Z',
    pontos: [
      { ponto_id: 'p1', ponto_n: 1, ponto: 'Ponto 1', status: 'pendente' },
      { ponto_id: 'p2', ponto_n: 2, ponto: 'Ponto 2', status: 'pendente' },
    ],
    // preferencias ausente
  };

  const htmlLegacy = renderToString(
    React.createElement(PlanView, {
      plan: legacyPlan,
      onStartExecution: () => {},
      onReset: () => {},
      isStarting: false,
    })
  );

  assert.ok(
    htmlLegacy.includes('Personas analíticas'),
    'PlanView real deve exibir "Personas analíticas" quando o snapshot for desconhecido'
  );
  assert.ok(
    !htmlLegacy.includes('4 personas ativas') && !htmlLegacy.includes('4 persona ativa'),
    'PlanView real NUNCA deve adivinhar 4 personas quando o snapshot for desconhecido'
  );

  console.log('[Teste 2] PlanView real (SSR): Plano com snapshot exato de 2 personas');
  const snapshotPlan: PlanResponse = {
    ...legacyPlan,
    id_pesquisa: 'snap-prod-002',
    preferencias: {
      n_pontos: 2,
      personas: ['historiador', 'cetico'],
    },
  };

  const htmlSnap = renderToString(
    React.createElement(PlanView, {
      plan: snapshotPlan,
      onStartExecution: () => {},
      onReset: () => {},
      isStarting: false,
    })
  );

  assert.ok(
    htmlSnap.includes('2 personas ativas'),
    'PlanView real deve refletir a contagem real "2 personas ativas"'
  );
  assert.ok(
    htmlSnap.includes('Historiador, Cetico'),
    'PlanView real deve incluir os nomes das personas configuradas no title'
  );

  // =========================================================================
  // 2. historyService Real: Preservação e Sanitização
  // =========================================================================
  console.log('\n[Teste 3] historyService real: Sanitização de plano legado sem preferências');
  const legacyRecord: ResearchHistoryRecord = {
    id_pesquisa: 'rec-legacy-prod',
    tema: 'Pesquisa Legada',
    criado_em: '2026-10-26T12:00:00Z',
    status: 'planejado',
    total_pontos: 2,
    planResponse: legacyPlan,
  };
  historyService.save(legacyRecord);
  const retrievedLegacy = historyService.get('rec-legacy-prod');
  assert.equal(
    retrievedLegacy?.planResponse?.preferencias,
    undefined,
    'historyService real não deve criar objeto preferencias com array vazio'
  );

  console.log('[Teste 4] historyService real: Preservação de snapshot e descarte de dados privados');
  const snapRecordWithLeak: any = {
    id_pesquisa: 'rec-snap-prod',
    tema: 'Pesquisa com Snapshot',
    criado_em: '2026-10-26T12:00:00Z',
    status: 'planejado',
    total_pontos: 2,
    planResponse: snapshotPlan,
    __internal_reasoning_leak: 'DADOS_PRIVADOS_QUE_DEVEM_SER_REMOVIDOS',
  };
  historyService.save(snapRecordWithLeak);
  const retrievedSnap = historyService.get('rec-snap-prod');
  assert.deepEqual(
    retrievedSnap?.planResponse?.preferencias?.personas,
    ['historiador', 'cetico'],
    'Snapshot exato preservado no histórico'
  );
  assert.equal(
    (retrievedSnap as any).__internal_reasoning_leak,
    undefined,
    'Campos de telemetria ou raciocínio privado descartados pelo sanitizador real'
  );

  // =========================================================================
  // 3. SettingsView Real: Estado Vazio vs Rascunho em Memória
  // =========================================================================
  console.log('\n[Teste 5] SettingsView real (SSR): Estado inicial limpo');
  const htmlSettingsEmpty = renderToString(
    React.createElement(SettingsView, {
      draft: initialSettingsFormData,
    })
  );
  assert.ok(
    !htmlSettingsEmpty.includes('Você possui alterações não salvas'),
    'SettingsView limpo não deve exibir banner de rascunho não salvo'
  );
  assert.ok(
    !htmlSettingsEmpty.includes('Descartar rascunho'),
    'SettingsView limpo não deve exibir botão de descartar rascunho'
  );

  console.log('[Teste 6] SettingsView real (SSR): Rascunho ativo em memória');
  const draftWithUrl = {
    ...initialSettingsFormData,
    LLM_BASE_URL: 'https://api.openai.com/v1',
  };
  const htmlSettingsDraft = renderToString(
    React.createElement(SettingsView, {
      draft: draftWithUrl,
      onDiscardDraft: () => {},
    })
  );
  assert.ok(
    htmlSettingsDraft.includes('Você possui alterações não salvas no formulário (preservadas em memória nesta sessão)'),
    'SettingsView com rascunho deve exibir alerta descritivo de preservação em memória'
  );
  assert.ok(
    htmlSettingsDraft.includes('Descartar rascunho'),
    'SettingsView com rascunho deve renderizar ação explícita de descarte'
  );
  assert.ok(
    htmlSettingsDraft.includes('https://api.openai.com/v1'),
    'Valor do rascunho deve estar presente no input correspondente'
  );

  console.log('\n--- Todos os 6 testes de componentes e serviços reais passaram com sucesso! ---');
}

runProductionTests().catch((err) => {
  console.error('Falha nos testes de produção:', err);
  process.exit(1);
});
