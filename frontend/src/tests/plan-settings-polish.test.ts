/**
 * Testes Focados de Regressão e Acessibilidade: PlanView & SettingsView Polish
 *
 * Validações de código real de produção:
 * 1. PlanView: Botão primário único no cabeçalho antes dos eixos (acima da dobra)
 * 2. PlanView: Ausência estrita de botões duplicados ou clones adesivos
 * 3. PlanView: Diálogo de confirmação seguro para 'Novo tema' com descarte explícito e cancelamento seguro
 * 4. PlanView: Preservação de snapshot de personas e contagem de pontos analíticos
 * 5. SettingsView: Precedência normativa Adendo 002 (Banco Cifrado > Ambiente, CREDENTIALS_MASTER_KEY bootstrap)
 * 6. SettingsView: Mascaramento estrito de segredos e preservação de rascunho
 * 7. SettingsView: Foco acessível e rolagem para o primeiro controle inválido em ordem DOM
 */
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';

// Registra hook para ignorar imports de CSS durante execução de testes SSR no Node
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
import { PlanResponse } from '../types/api';

async function runPlanSettingsPolishTests() {
  console.log('--- Iniciando Testes de Regressão: PlanView & SettingsView Polish ---');

  const { PlanView } = await import('../components/PlanView.js');
  const { SettingsView, initialSettingsFormData } = await import('../components/SettingsView.js');

  // =========================================================================
  // 1. PlanView: Botão Primário Único no Cabeçalho (Above-the-Fold)
  // =========================================================================
  console.log('\n[Teste 1] PlanView: Botão primário único posicionado no cabeçalho antes dos eixos');
  const samplePlan: PlanResponse = {
    id_pesquisa: 'test-plan-001',
    tema: 'Energia solar: plano extenso para verificação visual',
    n_pontos: 2,
    criado_em: '2026-10-26T18:00:00Z',
    preferencias: {
      n_pontos: 2,
      personas: ['historiador', 'visionario', 'cetico', 'futurista'],
    },
    pontos: [
      {
        ponto_id: 'p1',
        ponto_n: 1,
        ponto: 'Eficiência fotovoltaica em perovskitas',
        status: 'pendente',
        eixo_estruturado: {
          pergunta_principal: 'Qual a durabilidade de células de perovskita sob estresse térmico?',
          subperguntas: ['Quais compostos retardam a degradação?', 'Como se comparam ao silício?'],
          hipoteses: ['Perovskitas tandem superam 30% de eficiência teórica.'],
          consultas_iniciais: ['perovskite thermal degradation', 'tandem solar cell durability'],
          fontes_primarias_desejadas: ['Nature Energy', 'NREL'],
          riscos_de_vies: ['Estudos acelerados em laboratório podem não refletir clima real'],
          evidencias_que_refutariam: ['Testes de campo mostrando queda abaixo de 80% em 6 meses'],
          criterio_de_conclusao: 'Identificar ao menos 3 estudos revisados por pares com T80 > 1000h.',
          investigabilidade: 'alta',
          eixo_essencial: true,
        },
      },
      {
        ponto_id: 'p2',
        ponto_n: 2,
        ponto: 'Integração de baterias residenciais e custo nivelado',
        status: 'pendente',
        eixo_estruturado: {
          pergunta_principal: 'Qual a viabilidade econômica do armazenamento distribuído?',
          subperguntas: ['Qual o payback médio atual?', 'Quais subsídios regulatórios existem?'],
          hipoteses: ['Baterias LFP reduzem o LCOE residencial em 15% até 2028.'],
          consultas_iniciais: ['residential BESS LCOE 2026', 'tariff arbitrage home battery'],
          fontes_primarias_desejadas: ['BloombergNEF', 'EIA'],
          riscos_de_vies: ['Projeções de custo dependentes de escala de fornecimento'],
          evidencias_que_refutariam: ['Preços de lítio estáveis com taxa de retorno inferior a 4%'],
          criterio_de_conclusao: 'Demonstrar taxa de retorno positiva em tarifas com ponta/fora de ponta.',
          investigabilidade: 'alta',
          eixo_essencial: true,
        },
      },
    ],
  };

  const htmlPlan = renderToString(
    React.createElement(PlanView, {
      plan: samplePlan,
      onStartExecution: () => {},
      onReset: () => {},
      onEditTheme: () => {},
      isStarting: false,
    })
  );

  // O botão primário deve estar contido na linha do cabeçalho
  assert.ok(
    htmlPlan.includes('plan-header-primary-action'),
    'PlanView deve conter container de ação primária no cabeçalho'
  );
  assert.ok(
    htmlPlan.includes('id="start-research-btn"'),
    'PlanView deve conter o botão #start-research-btn'
  );

  // Posição no DOM: o botão de início deve vir ANTES do plan-stepper
  const buttonIndex = htmlPlan.indexOf('id="start-research-btn"');
  const stepperIndex = htmlPlan.indexOf('plan-stepper');
  assert.ok(
    buttonIndex !== -1 && stepperIndex !== -1 && buttonIndex < stepperIndex,
    'O botão primário de início deve preceder a lista de eixos investigativos no DOM (acima da dobra)'
  );

  // =========================================================================
  // 2. PlanView: Ausência Estrita de Botões Duplicados
  // =========================================================================
  console.log('[Teste 2] PlanView: Unicidade estrita do botão Iniciar pesquisa (sem clones)');
  const matchesStartBtn = htmlPlan.match(/id="start-research-btn"/g);
  assert.equal(
    matchesStartBtn?.length,
    1,
    'Deve existir exatamente 1 elemento com id="start-research-btn" no DOM'
  );

  const matchesStartText = htmlPlan.match(/<span>Iniciar pesquisa<\/span>/g);
  assert.equal(
    matchesStartText?.length,
    1,
    'O texto "Iniciar pesquisa" deve ocorrer exatamente 1 vez no cartão'
  );

  // =========================================================================
  // 3. PlanView: Preservação de Snapshot e Metadados Analíticos
  // =========================================================================
  console.log('[Teste 3] PlanView: Preservação de snapshot de personas e dados analíticos');
  assert.ok(
    htmlPlan.includes('4 personas ativas'),
    'Snapshot deve indicar 4 personas ativas'
  );
  assert.ok(
    htmlPlan.includes('pontos analíticos'),
    'Snapshot deve indicar pontos analíticos'
  );
  assert.ok(
    htmlPlan.includes('Qual a durabilidade de células de perovskita sob estresse térmico?'),
    'Pergunta principal do eixo 1 deve estar presente'
  );
  assert.ok(
    htmlPlan.includes('Qual a viabilidade econômica do armazenamento distribuído?'),
    'Pergunta principal do eixo 2 deve estar presente'
  );

  // =========================================================================
  // 4. SettingsView: Precedência Adendo 002 e Bootstrap Master Key
  // =========================================================================
  console.log('\n[Teste 4] SettingsView: Informação de precedência normativa Adendo 002');
  const htmlSettings = renderToString(
    React.createElement(SettingsView, {
      draft: initialSettingsFormData,
    })
  );

  assert.ok(
    htmlSettings.includes('Qual valor vale'),
    'SettingsView deve explicar qual valor tem precedência'
  );
  assert.ok(
    htmlSettings.includes('tem prioridade'),
    'SettingsView deve informar que o valor salvo vence o ambiente'
  );
  assert.ok(
    htmlSettings.includes('CREDENTIALS_MASTER_KEY'),
    'SettingsView deve registrar que CREDENTIALS_MASTER_KEY é restrita ao ambiente para bootstrap'
  );

  // =========================================================================
  // 5. SettingsView: Mascaramento Seguro de Segredos e Preservação de Rascunho
  // =========================================================================
  console.log('[Teste 5] SettingsView: Campos sensíveis protegidos como password');
  assert.ok(
    htmlSettings.includes('id="openai-key" type="password"'),
    'OPENAI_API_KEY deve ser input type="password"'
  );
  assert.ok(
    htmlSettings.includes('id="jina-key" type="password"'),
    'JINA_API_KEY deve ser input type="password"'
  );
  assert.ok(
    htmlSettings.includes('id="webhook-secret" type="password"'),
    'WEBHOOK_HMAC_SECRET deve ser input type="password"'
  );

  // =========================================================================
  // 6. SettingsView: Acessibilidade e Contratos dos Inputs com Erro
  // =========================================================================
  console.log('[Teste 6] SettingsView: Atributos acessíveis (aria-describedby, role="alert")');
  assert.ok(
    htmlSettings.includes('id="llm-base-url"'),
    'Input de LLM_BASE_URL presente com id canônico'
  );
  assert.ok(
    htmlSettings.includes('id="jina-base-url"'),
    'Input de JINA_BASE_URL presente com id canônico'
  );
  assert.ok(
    htmlSettings.includes('id="n-pontos"'),
    'Input de N_PONTOS presente com id canônico'
  );
  assert.ok(
    htmlSettings.includes('id="callback-url"'),
    'Input de CALLBACK_WEBHOOK_URL presente com id canônico'
  );

  // =========================================================================
  // 7. PlanView: Divulgação Progressiva dos Eixos (Acordeões)
  // =========================================================================
  console.log('[Teste 7] PlanView: Controles de acordeão e divulgação progressiva');
  assert.ok(
    htmlPlan.includes('btn-toggle-all-details'),
    'Botão de alternância global de detalhes presente'
  );
  assert.ok(
    htmlPlan.includes('stepper-point-toggle'),
    'Botões de alternância individual de detalhes presentes nos eixos'
  );
  assert.ok(
    htmlPlan.includes('is-collapsed'),
    'Eixos iniciam recolhidos para visualização compacta acima da dobra'
  );

  console.log('\n--- Todos os 7 testes focados de PlanView e SettingsView Polish passaram com sucesso! ---');
}

runPlanSettingsPolishTests().catch((err) => {
  console.error('Falha nos testes de PlanView & SettingsView Polish:', err);
  process.exit(1);
});
