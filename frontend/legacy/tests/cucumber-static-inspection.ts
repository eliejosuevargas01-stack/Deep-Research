import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootFrontend = path.resolve(__dirname, '../..');
const featuresDir = path.join(rootFrontend, 'features');
const stepsFile = path.join(featuresDir, 'step_definitions/steps.ts');

console.log('=== Inspeção Estática de Conformidade Cucumber / Gherkin ===\n');

// 1. Extração de Step Definitions do steps.ts
const stepsContent = fs.readFileSync(stepsFile, 'utf-8');

interface StepDef {
  pattern: string;
  regex: RegExp;
  line: number;
}

const stepDefs: StepDef[] = [];
const lines = stepsContent.split('\n');

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  const match = /(?:Given|When|Then)\(\s*(['"`])(.*?)\1\s*,/.exec(line);
  if (match) {
    const rawPattern = match[2];
    // Converte parâmetros Cucumber em Regex
    // {string} -> "([^"]*)"
    // {int} -> (-?\d+)
    // {float} -> (-?\d+(?:\.\d+)?)
    // {} -> (.*)
    const normalizedPattern = rawPattern.replace(/\\/g, '');
    const regexPattern = '^' + normalizedPattern
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // escape regex especiais exceto chaves
      .replace(/\\\{string\\\}/g, '"([^"]*)"')
      .replace(/\\\{int\\\}/g, '(-?\\d+)')
      .replace(/\\\{float\\\}/g, '(-?\\d+(?:\\.\\d+)?)')
      .replace(/\\\{word\\\}/g, '([^\\s]+)')
      .replace(/\\\{\\\}/g, '(.*)') + '$';

    stepDefs.push({
      pattern: rawPattern,
      regex: new RegExp(regexPattern),
      line: i + 1,
    });
  }
}

console.log(`[Definições] Total de step definitions identificadas em steps.ts: ${stepDefs.length}`);

// Verificação de duplicatas exatas
const patternCounts = new Map<string, number>();
let duplicateCount = 0;
for (const sd of stepDefs) {
  const current = patternCounts.get(sd.pattern) || 0;
  if (current > 0) {
    console.error(`  ERRO: Step definition duplicada: "${sd.pattern}" (linha ${sd.line})`);
    duplicateCount++;
  }
  patternCounts.set(sd.pattern, current + 1);
}

if (duplicateCount === 0) {
  console.log('  ✓ Nenhuma step definition duplicada encontrada.');
} else {
  console.error(`  ✗ ${duplicateCount} duplicatas encontradas!`);
}

// 2. Leitura de todos os arquivos .feature
const featureFiles = fs.readdirSync(featuresDir)
  .filter((f) => f.endsWith('.feature'))
  .sort();

console.log(`\n[Features] Arquivos .feature encontrados: ${featureFiles.length}`);

let totalScenarios = 0;
let totalSteps = 0;
let unmatchedSteps = 0;

for (const f of featureFiles) {
  const fPath = path.join(featuresDir, f);
  const content = fs.readFileSync(fPath, 'utf-8');
  const fLines = content.split('\n');

  let fileScenarios = 0;
  let fileSteps = 0;

  for (let idx = 0; idx < fLines.length; idx++) {
    const line = fLines[idx].trim();

    if (line.startsWith('Cenário:') || line.startsWith('Cenario:')) {
      fileScenarios++;
      totalScenarios++;
    } else if (
      line.startsWith('Dado ') ||
      line.startsWith('Quando ') ||
      line.startsWith('Então ') ||
      line.startsWith('Entao ') ||
      line.startsWith('E ') ||
      line.startsWith('Mas ')
    ) {
      fileSteps++;
      totalSteps++;

      // Extrai o texto do passo removendo a palavra-chave
      const stepText = line.replace(/^(Dado|Quando|Então|Entao|E|Mas)\s+/, '').trim();

      // Procura correspondência em stepDefs
      const matched = stepDefs.filter((sd) => sd.regex.test(stepText));

      if (matched.length === 0) {
        console.error(`  ✗ Passo NÃO atendido em [${f}:${idx + 1}]: "${line}" (texto: "${stepText}")`);
        unmatchedSteps++;
      } else if (matched.length > 1) {
        console.warn(`  ⚠ Ambiguidade: Passo bate com ${matched.length} definições em [${f}:${idx + 1}]: "${stepText}"`);
      }
    }
  }

  console.log(`  • ${f}: ${fileScenarios} cenários, ${fileSteps} passos`);
}

console.log('\n=== Resumo da Inspeção Estática ===');
console.log(`Total de Arquivos Feature: ${featureFiles.length}`);
console.log(`Total de Cenários Gherkin: ${totalScenarios}`);
console.log(`Total de Passos Executáveis: ${totalSteps}`);
console.log(`Total de Step Definitions: ${stepDefs.length}`);
console.log(`Passos Não Atendidos: ${unmatchedSteps}`);
console.log(`Duplicatas em steps.ts: ${duplicateCount}`);

if (unmatchedSteps > 0 || duplicateCount > 0) {
  console.error('\n✗ FALHA NA INSPEÇÃO ESTÁTICA DO HARNESS!');
  process.exit(1);
} else {
  console.log('\n✓ TODAS AS STEP DEFINITIONS ESTÃO ÍNTEGRAS, SEM DUPLICATAS OU PASSOS INDEFINIDOS!');
  process.exit(0);
}
