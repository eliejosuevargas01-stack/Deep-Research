# Inspeção documental independente T034 — rastreabilidade pós-QA

## Veredito: CONDITIONAL

Rastreabilidade principal conforme; duas observações LOW no relatório de execução, nenhuma falha de produto confirmada. T034 permanece `[ ]`; este documento não aprova implementação própria nem fecha gates. Todos os achados têm `promoted_to: null`; nenhum bug, registry ou view criado.

## Preflight e recorte

Root `/root/projects/deep-research`, branch `main`, árvore previamente suja/untracked. `AGENTS.md` encontrado somente no root entre ancestrais consultados; nenhum AGENTS descendente nas pastas forward da feature, bugs do contexto ou SDD. Lidos state, active-requirements, config.toml e reversa-config. Estado global `forward-complete` é histórico; active-requirements identifica feature `001-modulo-briefing`, estágio `coding`, fonte vigente para esta feature. Idioma documental pt-BR.

Responsabilidade leaf: somente `legacy-impact.md:166–193`, `regression-watch.md:179–198` e `audit/t034-execution.md:1–72`. Prefixos históricos consultados apenas para qualificação de status/assinaturas e preservação de IDs, não para reauditoria. Não lidos cross-check sibling, roadmap, interfaces nem audit/t025-t026-planning-delta. Nomes desses arquivos presentes nas fontes não autorizam leitura. T030 não reaberta; O-CONTRACT-01 não redescoberta como bug novo. Sem subdelegação, todo, testes, imports de aplicação, rede, DB, .env, instalação, commit, push ou deploy.

## Mapa e readset

Convenção: referências curtas documentais abaixo são relativas a `_reversa_forward/001-modulo-briefing`; caminhos começando em app/, tests/, _reversa_bugs/, _reversa_sdd/ ou .reversa/ são relativos ao root. Linha histórica aponta snapshot narrado, não localização atual de teste necessariamente.

| Área | Fontes efetivamente consultadas | Papel |
|---|---|---|
| Produto | requirements.md:51–70; _reversa_sdd/prd.md:41–47,99–100; _reversa_sdd/sdd/briefing.md:61–63,118 | RF-08 segurança, RF-10 até quatro tentativas por operação, timeout configurável por tentativa; não prova entrega global |
| Contrato congelado | audit/t029-t031-planning-delta.md:9,21–39; audit/t011-integration-decomposition.md:99–120 | D3/D5, F-ERROR-01 e F-CONSISTENCY-01 |
| Entrega | audit/t030-execution.md:7–25; audit/t031-execution.md:8–40 | Mudanças T030/T031 e TDD histórico; assinatura antiga T030 é contexto anterior |
| Inspeção/QA | _reversa_bugs/modulo-briefing/inspections/t030-error-matrix/report.md:3–48; _reversa_bugs/modulo-briefing/inspections/t030-error-matrix-qa/report.md:3–69 | CONDITIONAL na inspeção, produto ordinário PASS, QA PASS_LOCAL; observação não promovida |
| Inspeção/QA | _reversa_bugs/modulo-briefing/inspections/t031-session-factory/report.md:3–76; _reversa_bugs/modulo-briefing/inspections/t031-session-factory-qa/report.md:3–78 | Inspeção PASS, QA PASS_LOCAL, D3 memória e lifecycle citados |
| Código/testes estáticos | app/briefing/llm_binding.py:89–165; AST de tests/test_briefing_llm_binding.py | Assinatura, sequência lexical e contagem de métodos; nenhuma execução funcional |
| Estado/gates | actions.md:85–99; progress.jsonl:L72,L74,L75,L76,L79,L80 | Fechamento T030/T031; T034 e API ainda abertos; correção de overclaims |
| Documentos-alvo | legacy-impact.md:166–193; regression-watch.md:179–198; audit/t034-execution.md:1–72 | Rastreamento após reparo |
| Histórico limitado | legacy-impact.md:6,96,139,162; regression-watch.md:115–117,127,155–175 | Contexto greenfield, assinatura antiga, WIDs e supersessão |

Dados mapeados apenas como evidência citada: AppSettings em SQLite memória, flush transitório não persistido; transporte OpenAI HTTPX MockTransport; settings e LLM simulados. Nenhuma tabela consultada nesta inspeção. Código congelado não alterado.

## Conformidade e proveniência

| Critério | Resultado documental / fonte |
|---|---|
| Factory real session_factory | Conforme: binding:101–105 valida default na factory; :107–113 valida override antes da sessão. Contrato D5:107–108 e entrega T031:12–17 concordam. |
| Close antes de LLM/transporte | Conforme: bloco :113–118 encerra antes de :135 e :153; copia dicionários e scalar openai_base_url. Ordem runtime é evidência anterior QA T031:45–58, não probe novo. |
| D3 flush não persistido | Citado corretamente: QA T031:60–67 descreve SQLite memória, close sem commit, consulta posterior zero AppSettings. Sem alegar DB real/live. |
| Preservação | binding:147–148 zeros; :157–159 matriz; :162–164 guardrail. QA T031:69–72 cita testes preservados. Não generalizar request único OpenAI fake para todos providers. |
| Contagens separadas | AST atual: 24 métodos, 1 sync + 23 async, sem execução. T030: 21 binding / 137 briefing em L72.evidence.parent_replay; T031: 24 / 140 em L74.checks, L75.checks e L76.evidence.parent_replay, QA T031:39–43,72. O report QA T030 não fornece discover137 diretamente: origem desse número é parent L72, não execução QA própria. |
| Vereditos separados | T030 inspeção CONDITIONAL, matriz ordinária/produto PASS (report:3–7); QA PASS_LOCAL (QA:4). T031 inspeção PASS e QA PASS_LOCAL. Fechamento parent L72/L76 não reescreve veredito histórico da inspeção. |
| Binding completed versus API | L76 registra Sprint B binding completed. T025 desbloqueada quanto binding, não API entregue. actions:90–92 mantém T035/D4, T025/T026 `[ ]`; :98–99 T012/T013 `[ ]`; L79 corrige D4 não entregue, L80 mantém coding gate bloqueado. Delta S8 não auditado por este leaf. |
| Histórico e IDs | legacy:181 qualifica assinaturas/status anteriores; regression adendo pós-QA supersede estados :161,173, mantendo W001–W030 (30 IDs distintos, sem W novo no adendo). Sem exigir tabela retrospectiva de mudanças. Preservação contra L80 confirmada, não comparação contra snapshot pré-T034 indisponível. |
| parent_replay | audit/t034-execution.md:52 usa shorthand `parent_replay`; JSON real é `evidence.parent_replay` em L76. Trecho citado existe literalmente. Não é claim de campo top-level nem finding: convenção explicitada aqui. |

O-CONTRACT-01 continua observação MEDIUM histórica com alcance provider não demonstrado (inspeção T030:7,27,38; QA:52–56). Oito callsites instalados examinados anteriormente e OpenAI MockTransport 401/403 não constituem prova global de inalcançabilidade. Não executar nem transformar essa observação em finding novo desta inspeção.

## Achados por lente

| Lente | Achados novos | Confiança alta | Defeitos de produto confirmados | Observações |
|---|---|---|---|---|
| Conformidade documental | 0 | 0 | 0 | 0 |
| Evidência / precisão de vereditos e checks | 2 | 2 | 0 | 2 LOW |
| IDs / histórico / estados | 0 | 0 | 0 | 0 |

### F-EVIDENCE-01 — promoção de observação confundida com veredito

- lens: evidência
- confidence: alta
- suspected_severity: low
- promoted_to: null
- evidence: audit/t034-execution.md:15; inspeção T030:3–7,27; QA T030:4,52–56.
- Texto observado: “observação O-CONTRACT-01 NÃO promovida a overall PASS_LOCAL”. Promoção de finding a bug e atribuição de veredito não são operações intercambiáveis. QA já possui PASS_LOCAL e observação não promovida a bug; inspeção permanece CONDITIONAL. Linha 15 identifica ambos corretamente fora dessa expressão.
- Classificação: imprecisão cosmético-semântica LOW, não falsificação do resultado nem falha runtime. Leitura factual equivocada seria dizer que QA não recebeu PASS_LOCAL; linha 15 termina com QA PASS_LOCAL e fontes refutam essa leitura. Recomenda-se “O-CONTRACT-01 não promovida a bug; inspeção CONDITIONAL; QA PASS_LOCAL”. Sem editar arquivo ou reabrir T030.

### F-EVIDENCE-02 — alcance de git diff check não explicita untracked

- lens: evidência
- confidence: alta
- suspected_severity: low
- promoted_to: null
- evidence: audit/t034-execution.md:3–4,42,51; saída própria de git diff --check e git diff --no-index --check /dev/null no relatório.
- `git diff --check` global retorna exit 0, mas documentos-alvo são untracked. Check direto do relatório untracked retorna exit 3 e reporta trailing whitespace em :3–4, usados como hard breaks Markdown. Portanto “sem trailing whitespace” não está comprovado para todos os arquivos alterados pela verificação citada.
- Classificação: cosmético no Markdown; factual LOW na amplitude declarada do check. Não compromete contratos nem exige remoção de hard breaks. Qualificar check como tracked, ou registrar resultado no-index e decisão de aceitar hard breaks. Nenhuma correção efetuada.

Cluster: precisão de metadados de prova do report T034. Nenhum cluster de falha de software confirmado. Contagens por severidade: critical 0, high 0, medium 0, low 2. Confiança: alta 2, média 0, baixa 0. Bugs promovidos 0.

## Verificações próprias — somente estáticas/documentais

1. `pwd`, `git status --short`, `git branch --show-current`: root e main confirmados; alterações anteriores preservadas.
2. Python stdlib pathlib/json: parse de 80 linhas JSONL; redução de L72/L74/L75/L76/L79/L80 sem executar seus comandos. L76 possui evidence.parent_replay, não binding_unittest/briefing_discover.
3. Python ast: exatamente 24 funções test_* em tests/test_briefing_llm_binding.py, 1 FunctionDef e 23 AsyncFunctionDef. Métodos relevantes atuais: default :344, override :367, lifecycle :512, factory zero :562, SQLite :573, SDK503 :425, retry kwargs :490. Números antigos das fontes mantidos como históricos; não alegar que offsets QA antigos continuam atuais.
4. Delimitadores: legacy 9 tabelas/46 linhas; regression 14/58; execution 1/12. Zero blocos com número de pipes inconsistente. Varredura estrutural dos documentos completos não equivale à auditoria factual do histórico. Nenhum teto de 120 colunas exigido/verificado; claim anterior corrigido em L79.
5. Markdown links explícitos nos adendos/execução: 0. Isso NÃO significa ausência de referências em backticks. Extração encontrou 6 ocorrências concretas em legacy, 3 em regression, 25 em execution. Caminhos root/feature resolvem; três abreviações llm_binding.py:101–103,113–119,108–112 resolvem pelo arquivo plenamente qualificado em execution:11, não pelo diretório audit. Arquivos excluídos nomeados em execution:71 tiveram apenas existência verificada, sem leitura. Todos os demais backticks são símbolos, comandos, texto ou assinatura, não hyperlinks. Referências locais de linhas conferidas contra fontes acima.
6. IDs/grafo: apenas IDs citados T030/T031/T025/T026/T012/T013/T034/T035, D3/D5, F-ERROR-01/F-CONSISTENCY-01/O-CONTRACT-01 confrontados com actions/contratos/reports. Não reconstruído grafo global; cycle_free em L80 é prova parent citada, não verificação nova. Watch IDs contados por regex: 30 distintos W001–W030, preservados no prefixo.
7. `git diff --check`: exit 0 sem saída; não cobre untracked. `git diff --no-index --check /dev/null _reversa_forward/001-modulo-briefing/audit/t034-execution.md`: exit 3, dois trailing-whitespace em :3–4. Primeira tentativa de comando estrutural falhou exit 2 por aspas/backticks no shell, antes de leitura; refeito sem backticks literais, exit 0. Não defeito produto.
8. SHA-256 stdlib: manifesto L80 contém 106 entradas; 102 conferidas, zero mismatches/missing. Quatro excluídas sem ler bytes: cross-check sibling mutável, roadmap, interfaces/briefing-http e audit/t025-t026-planning-delta, fora ownership. Não declarar 106/106. Hash de progress é snapshot próprio fora manifesto; nenhuma escrita nessa fonte.

## Arquivos únicos e hashes do snapshot

Somente novo report desta inspeção é escrita autorizada. Fontes-alvo intactas, hashes coincidem com L80:

| Arquivo (feature-relative) | SHA-256 |
|---|---|
| legacy-impact.md | 2459c0a9d8363f3533cffc67924ac747fdcd0b9cf777b8c8b94e113f4203e375 |
| regression-watch.md | d5bb65a8ede0b44cb880d393388965b1939622fd5331fa3c5c7e20e53265d476 |
| audit/t034-execution.md | 197ea6abc892cde549395e40c1b35a0a8eeb2d65284eca035e6c71b5d44e8b76 |
| actions.md | 934fc0fd92313a0df947a2ca8ea5257afc62321cc4e21a1faf4af96f024ad2bf |
| progress.jsonl | 34f4fe5c6c90ed1e3f631260e7c759562b29fb92a88c65bddb3cd9ea627132be |
| audit/t030-execution.md | 97256a6de008079e9325de30ac5be1b3663ac74b1f95cb8648471b7e5af7e34d |
| audit/t031-execution.md | d1c477d23f70a949836844cd6002771cf8d1fa5d9ca7f25e1c8bcab9602607c1 |

| Arquivo (root-relative) | SHA-256 |
|---|---|
| app/briefing/llm_binding.py | e3f8dff3ef868d3a37a57c52e7ecdce0fe1149b94a23616e9ff7edd668c48233 |
| tests/test_briefing_llm_binding.py | 6436977c90ef1a0f53b4dbf05ed0d24be32a54032f7f731c5829916a5519640b |
| _reversa_bugs/modulo-briefing/inspections/t030-error-matrix/report.md | 6715ec988e728ddf2384cea3e0928031147d8541e6d30c32802cdfd56b2d8be9 |
| _reversa_bugs/modulo-briefing/inspections/t030-error-matrix-qa/report.md | 3e6ef5eeadbbbef62420bd9040df0b107e2b9662916796a250b437e04bd9a1ca |
| _reversa_bugs/modulo-briefing/inspections/t031-session-factory/report.md | 318e6ae1cfd8369c455424415368cab3e4aa6de93ed43a76be8fa450236e2d6a |
| _reversa_bugs/modulo-briefing/inspections/t031-session-factory-qa/report.md | b3e2a4b8454830e24d47f5c34074151a6a6427e1424e4435502faa192687e109 |
| _reversa_sdd/prd.md | d78d05e0bfbd6c937eecf9d0899d4e5d131d780e99a5fbb2dd2ae507584651da |
| _reversa_sdd/sdd/briefing.md | 27c1731e4fb6771957e5ef17b1bfe748f979a3c16331c87c1d2029f666f9c76b |

## Limites e decisão

Veredito documental CONDITIONAL por duas observações LOW, não rejeição do binding previamente aprovado. Sem execução de testes/probes/runtime novo. Cobertura funcional é exclusivamente prova citada anterior; não certifica produção, provider real, PostgreSQL, autenticação/API, D4 ou delta S8. Lentes runtime de fluxo, erros, concorrência, segurança e desempenho não ativadas; este leaf avalia somente representação documental dessas provas. Catálogo/graph não auditados globalmente; nenhum registro de bug criado. Histórico restante explicitamente excluído, sem exigir reescrita, tabela histórica ou fechamento retroativo. T034 segue aberta para decisão parent e gates independentes aplicáveis.
