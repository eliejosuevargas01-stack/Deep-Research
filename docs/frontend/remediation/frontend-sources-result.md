# Relatório de Implementação Frontend: Separação Contábil e Rastreabilidade de Fontes

**Data**: 2026-10-26  
**Componente**: Frontend (`frontend/src/**`, `frontend/features/**`, `docs/frontend/remediation/**`)  
**Modelo de Execução**: `ag/gemini-3.8-flash-high` via Render Router (Reasoning High)  

---

## 1. Resumo Executivo

Em conformidade com a solicitação do usuário e os contratos técnicos (`.impeccable/remediation-20261026/sources-contract.md` e `docs/frontend/remediation/sources-api-contract.md`), foi implementada no frontend a separação contábil fidedigna de fontes de pesquisa em três categorias canônicas:
1. **Fontes Consultadas (`consultadas`)**: URLs HTTP(S) com leitura confirmada pelo Reader (`read_ok` e corpus textual material registrado nas coletas).
2. **Fontes Utilizadas no Dossiê (`utilizadas`)**: URLs citadas no texto publicado do dossiê final e rastreáveis às evidências.
3. **Fontes Consultadas mas Não Citadas (`nao_utilizadas`)**: Referências e leituras investigadas com sucesso que serviram de apoio e contexto, sem citação explícita no relatório final (com explicação factual clara de que não constituem fontes rejeitadas).

O rótulo enganoso anterior `Fontes Bibliográficas Verificadas` (que apenas extraía URLs por regex sem comprovação de leitura) foi completamente removido e substituído pelo componente acessível `SourceBreakdown`, dotado de folha de estilos própria e escopada, contadores coesos em linha (recusando o padrão lazy de três cards métricos decorados), blocos nativos expansíveis `<details>` / `<summary>`, sanitização estrita de URLs e vinculação rigorosa de integridade de versão por `artifact_hash` (SHA-256 do texto publicado).

---

## 2. Resolução das Não-Conformidades Apontadas pelo Root (Revisões 1, 2 e 3)

### 2.1. Revisão 1

1. **Rejeição Estrita de Divergência de Hash/Versão**:
   - Em caso de divergência de `artifact_hash` ou de `id_pesquisa`, os dados de fontes são estritamente rejeitados: `verifiedSources` é mantido nulo e nenhum dado incompatível é passado ao estado de exibição ou ao `historyService`.
   - Exibe aviso conciso e em linguagem natural: *"As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado."* sem expor hashes criptográficos técnicos ao usuário.
   - O texto Markdown publicado, as ações de copiar e baixar o relatório permanecem 100% íntegras e preservadas byte-a-byte.

2. **Diferenciação Fidedigna de Estados: Carregando, Erro, Mismatch e Legado**:
   - `loading`, `error` e `isMismatch` são tratados como estados mutuamente exclusivos do status confirmado `indisponivel`.
   - Durante o carregamento inicial, exibe o indicador honesto *"Carregando fontes..."* e contadores como traço (`—`), sem badges falsos de legado.
   - O badge e o banner de relatório legado só são ativados quando `status === 'indisponivel'` for confirmado pelo backend, sem carregamento ou erro pendente.
   - Quando a contagem for desconhecida (`null`), a lista vazia não afirma falsamente "Nenhuma fonte...", mas sim *"Contabilidade não registrada ou indisponível para esta categoria."*

3. **Parser AST de Citações Markdown sem Falsos Positivos**:
   - A função de extração `extractSourcesFromMarkdown` utiliza a árvore sintática real (AST) fornecida por `unified`, `remark-parse` e `remark-gfm`.
   - Blocos de código (`code`) e código em linha (`inlineCode`) são ignorados.
   - URLs com parênteses e parâmetros complexos são extraídas integralmente sem truncamento.
   - Definições de links (`[id]: url`) só são coletadas se houver `linkReference` no corpo do documento; definições não citadas são descartadas.

4. **Sanitização Rigorosa de Histórico e Expurgo de Segredos**:
   - Retém exclusivamente URLs públicas com protocolo `http:` ou `https:`; descarta completamente esquemas perigosos ou internos (`javascript:`, `ftp:`, `file:`, etc.).
   - Remove dados de autenticação embutidos na autoridade da URL (`user:pass@`).
   - Remove parâmetros de consulta de credenciais/tokens (`token`, `api_key`, `apikey`, `key`, `secret`, `password`, `auth`, `access_token`), preservando rotas e queries de navegação legítimas.
   - Garante que totais numéricos sejam inteiros finitos não-negativos (`Number.isInteger(val) && val >= 0`), mantendo contagens indefinidas estritamente como `null`.

### 2.2. Revisão 2 (Vinculação Estrita de Versão e Digest Criptográfico)

5. **Identidade Exata Síncrona de Versão (`reportId` E `publishedText`)**:
   - A estrutura `VerifiedSourcesState` armazena expressamente `reportId`, `publishedText`, `publishedHash` e `data`.
   - A derivação de `activeSources` e o indicador de correspondência (`isExactIdentityMatched`) exigem que **AMBOS** o `reportId` e o `publishedText` batam com os valores correntes da propriedade `report`.
   - Caso o texto publicado seja alterado em um re-render com o mesmo ID, o estado visível de fontes é imediatamente anulado de forma síncrona, prevenindo vazamento de dados ou contadores defasados da versão anterior antes que o `useEffect` conclua o recálculo.
   - Todos os contadores e a listagem de fontes reutilizam uniformemente o mesmo estado amarrado (`activeSources`), eliminando qualquer discrepância entre resumo textual e lista.

6. **Validador Puro de Produção `verifySourcesBinding`**:
   - Implementada a função pura exportada `verifySourcesBinding(currentReportId, publishedText, localHash, sources)`.
   - Exige que o digest local (`localHash`) seja gerado com sucesso (rejeita como não verificado caso o hash local retorne vazio por falha de crypto).
   - Para qualquer relatório com texto publicado não-vazio, exige que o backend retorne obrigatoriamente um `artifact_hash` não-vazio (inclusive quando o status for `indisponivel`), rejeitando resumos sem amarração criptográfica.
   - Exige igualdade exata (case-insensitive) entre `sources.artifact_hash` e `localHash`.
   - Garante que qualquer falha de verificação ou erro de rede resulte em aviso de preservação do texto sem disparar requisições ou mutações desnecessárias.

### 2.3. Revisão 3 (Caso de Borda: Registro Legado Apenas com Resumo)

7. **Rejeição de Resumo de Fontes sem Texto Completo Publicado**:
   - *Cenário reproduzido*: Registros legados no histórico que possuem apenas `dossier_resumo` (sem `dossier_final`) não possuem texto publicado completo para cálculo do hash do artefato. Uma consulta por ID com texto vazio não pode aceitar o resumo de fontes autoritativo de outro artigo publicado.
   - *Correção implementada*:
     - Em `verifySourcesBinding`, se `publishedText` estiver ausente ou em branco (`(publishedText || '').trim().length === 0`), a vinculação é estritamente rejeitada com a mensagem honesta: *"Este registro contém apenas um resumo; não é possível confirmar os totais de fontes do relatório completo."*
     - A exibição do resumo textual visível (`dossier_resumo`), as ações de cópia e o download do Markdown são totalmente preservados e intactos.
     - As contagens de fontes são marcadas como indisponíveis (`—`), evitando atribuir fontes e totais alheios ao registro legado.
     - Relatórios legados completos com texto real (`dossier_final`) e hash correspondente continuam hidratando normalmente (incluindo o relatório ativo do usuário 11/9/2).
     - Adicionado o campo `report.dossier_resumo` ao array de dependências do `useEffect` em `ReportView`, garantindo que alterações no resumo em registros sem texto final disparem o ciclo de limpeza e revalidação.

### 2.4. Refinamento de Divulgação Progressiva Inicial (Round 4)

8. **Recolhimento Inicial dos 3 Grupos de Fontes (Painel Inicial Compacto)**:
   - *Motivação*: Em relatórios com muitas fontes citadas (ex: 9 fontes citadas pelo usuário), manter o Grupo 1 expandido por padrão deslocava excessivamente a visualização vertical e afastava os outros dois grupos da leitura inicial.
   - *Ajuste aplicado*:
     - Removido o atributo fixo `open` do Grupo 1 (`Fontes Utilizadas no Dossiê`) em `SourceBreakdown.tsx`.
     - Todos os três grupos de fontes iniciam recolhidos por padrão, apresentando uma visão compacta, limpa e balanceada das três categorias com seus contadores e badges numéricos imediatamente visíveis no cabeçalho.
     - Cada elemento `<details>` nativo permanece individualmente expansível via clique ou teclado (Enter/Espaço), com preservação do suporte completo a leitores de tela.
     - Não foram introduzidos controles artificiais ou intrusivos (sem "ExpandAll", filtros adicionais ou tabelas de conteúdo).
     - Quando expandidas, listas longas de fontes rolam naturalmente dentro da página, sem falsa asserção de que todas caibam sem rolagem.
     - Modificação estritamente apresentacional e reversível, sem impacto em contratos de API, schemas, persistência ou estilos CSS.

---

## 3. Arquivos Modificados e Criados (Escopo Estrito de Titularidade)

| Arquivo | Natureza | Descrição das Modificações |
|---|---|---|
| `frontend/src/types/api.ts` | Modificado | Adição dos tipos canônicos `FontesStatus`, `FonteItem`, `FontesResumo` e extensão aditiva de `WriterResponse.fontes`. |
| `frontend/src/services/api.ts` | Modificado | Adição do método somente-leitura `getSources(id_pesquisa, signal)` apontando para `GET /api/v1/pipeline/{id}/sources` com `credentials: 'same-origin'`. |
| `frontend/src/services/history.ts` | Modificado | Projeção e sanitização estrita de fontes públicas no histórico local, expurgo de credenciais e preservação de contagens `null`. |
| `frontend/src/components/SourceBreakdown.tsx` | Criado/Refinado | Componente visual tripartite de fontes, detalhes nativos `<details>/<summary>` (todos os 3 grupos recolhidos inicialmente), proteção contra contagens zero inventadas e estados de erro/mismatch. |
| `frontend/src/components/SourceBreakdown.css` | Criado | Folha de estilos escopada alinhada ao identity DominusLabs/Docs (sem dependência de alteração em arquivos comuns). |
| `frontend/src/components/ReportView.tsx` | Modificado | Substituição do rótulo legado enganoso por `SourceBreakdown`, cálculo de `artifact_hash`, função `verifySourcesBinding` com guarda para registros resumo-only, amarra de identidade síncrona e parser AST de citações. |
| `frontend/src/tests/sources-accounting.test.ts` | Criado | Bateria de 13 testes focados cobrindo componentes, serviços reais, sanitização, casos limites de integridade, versão e registros resumo-only. |
| `frontend/features/05_sources_accounting.feature` | Criado | Especificação Gherkin BDD da funcionalidade de separação contábil de fontes. |
| `frontend/features/step_definitions/steps.ts` | Modificado | Definições de passos Cucumber correspondentes à nova funcionalidade (sem execução antecipada da suite E2E). |

---

## 4. Evidências de Validação Técnica

### 4.1. Testes Focados de Contabilidade e Vinculação de Fontes (13 testes)
Comando executado:
```bash
npx tsx src/tests/sources-accounting.test.ts
```
Saída:
```text
--- Iniciando Testes Focados de Produção: Contabilidade de Fontes ---

[Teste 1] extractSourcesFromMarkdown: extração via AST sem falsos positivos de código ou truncamentos
[Teste 2] computeArtifactHash: conformidade com SHA-256 padrão
[Teste 3] SourceBreakdown: Estado carregando não deve exibir badge de legado
[Teste 4] SourceBreakdown: Estado completo (status: completo)
[Teste 5] SourceBreakdown: Relatório legado confirmado (status: indisponivel)
[Teste 6] SourceBreakdown: isMismatch suprime listas de fontes e contagens alheias
[Teste 7] SourceBreakdown: Exibição de erro com botão de nova tentativa
[Teste 8] ReportView: Integração com SourceBreakdown e preservação byte-a-byte
[Teste 9] historyService: Sanitização estrita de HTTP(S), expurgo de userinfo e queries de segredo
[Teste 10] api.getSources: Contrato de rede e AbortSignal
[Teste 11] verifySourcesBinding: validação de digest local, hash idêntico e ID
[Teste 12] ReportView: Derivação síncrona sem fuga de estado defasado ao alterar texto
[Teste 13] ReportView: Relatório legado resumo-only preserva texto e marca totais como indisponíveis

--- Todos os 13 testes focados de contabilidade de fontes passaram com sucesso! ---
```

### 4.2. Testes de Regressão de Produção Concorrentes
Comando executado:
```bash
npx tsx src/tests/defects-regression.ts && npx tsx src/tests/execution-view-regression.ts
```
Saída:
```text
--- Executando Testes com Código Real de Produção ---
[Teste 1] PlanView real (SSR): Plano legado sem preferências
[Teste 2] PlanView real (SSR): Plano com snapshot exato de 2 personas
[Teste 3] historyService real: Sanitização de plano legado sem preferências
[Teste 4] historyService real: Preservação de snapshot e descarte de dados privados
[Teste 5] SettingsView real (SSR): Estado inicial limpo
[Teste 6] SettingsView real (SSR): Rascunho ativo em memória
--- Todos os 6 testes de componentes e serviços reais passaram com sucesso! ---

=== Iniciando Testes de Regressão de Produção (ExecutionView & ContextSidebar) ===
[Teste 1] Auditoria do Ciclo 1 em andamento de busca no Ciclo 2
[Teste 2] Auditoria do mesmo ciclo durante a redação (Writing)
[Teste 3] Ciclo de auditoria desconhecido/legado (fallback seguro)
[Teste 4] Tracker de busca em falha no estágio searching
[Teste 5] Diagnóstico estruturado canônico e detalhes técnicos preservados
[Teste 6] Acessibilidade: aria-live restrito a status sucinto
[Teste 7] Tema da pesquisa visível e título em linguagem de produto
[Teste 8] Concordância gramatical singular ("1 ponto")
[Teste 9] Lógica determinística dos helpers puros
--- TODOS OS 9 TESTES DE REGRESSÃO PASSARAM COM SUCESSO! ---
```

### 4.3. Verificação de Compilação e Build de Produção
Comando executado:
```bash
npm run build
```
Saída:
```text
> deep-research-frontend@1.0.0 build
> tsc && vite build

vite v6.4.5 building for production...
transforming...
✓ 2221 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                                   0.97 kB │ gzip:   0.60 kB
dist/assets/index-rmpwtDhS.css                                   85.05 kB │ gzip:  25.43 kB
dist/assets/index-CZn23IAs.js                                   507.41 kB │ gzip: 156.41 kB
✓ built in 22.51s
```

---

## 5. Limitações e Riscos Residuais (Sem Autoaprovação 100%)

1. **Limites da Prova por SSR (`renderToString`)**:
   - Os testes focados unitários e de regressão executados via SSR com `renderToString` provam a estrutura estática dos componentes, a ausência de rótulos incorretos, a sanitização rigorosa do histórico, o contrato da API e a lógica determinística da função de produção `verifySourcesBinding` para relatórios completos e resumo-only. No entanto, como `renderToString` no Node não executa ciclos de vida assíncronos de `useEffect`, a comprovação do ciclo completo de montagem, cancelamento e hidratação dinâmica no navegador depende do teste de integração com o DOM ativo (Cucumber/Playwright montado).
2. **Dependência de Recarga da Fixture pelo Root**:
   - A fixture na porta 8011 executa um processo estático isolado previamente iniciado. Qualquer verificação em navegador ativo só refletirá o novo backend e a hidratação completa após o Root reiniciar a fixture quando os serviços de backend estiverem estáveis.
3. **Execução Final do Cucumber E2E**:
   - Conforme instrução estrita, a execução final do Cucumber não foi realizada nesta etapa e está reservada para o auditor independente final.
