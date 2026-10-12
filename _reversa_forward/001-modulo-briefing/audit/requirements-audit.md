# Requirements Audit

> Identificador da feature: `001-modulo-briefing`
> Data: `2026-10-11`
> Documento auditado: `_reversa_forward/001-modulo-briefing/requirements.md`
> Escopo: clareza textual, completude e alinhamento com princípios. Não avalia código nem testes de implementação.

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de itens | 20 |
| Aprovados | 20 |
| Reprovados | 0 |
| Veredito | Aprovado |

Confronto item a item do requirements vigente após saneamento textual T038. Todos os 20 itens avaliados foram aprovados. As 6 pendências da rodada anterior (Q-010, Q-011, Q-014, Q-015, Q-019, Q-020) foram completamente sanadas no texto através de especificações explícitas e cenários Gherkin correspondentes, sem introdução de decisões técnicas não autorizadas.

## Itens por categoria

### Clareza

- [X] Q-001 | Clareza | O resumo distingue geração de briefing de investigação e relatório final?
  Evidência: §1 (linhas 10–11) afirma que o módulo produz rascunho dos pontos de foco e que a execução da pesquisa fica fora deste módulo; §4 (RN-03, linha 36) reforça que a busca identifica pontos e não conclusões; §4 (RN-07, linha 47) veda expressamente início de investigação ou geração de relatório; §5 (RF-03, linha 56 e RF-07, linha 60) delimita o consumo futuro sem disparo de pesquisa.
- [X] Q-002 | Clareza | A expressão “pontos válidos” tem definição única e verificável?
  Evidência: §4 (RN-03a, linha 38): "ponto é válido somente quando `title` e `description` são texto não-vazio após strip; ponto nulo, com campo ausente, vazio ou somente espaços é rejeitado. Contagem 3–7 vale para a geração, a edição salva e a aprovação"; §5.1 (linha 67) reitera a rejeição de campos vazios/nulos com `InvalidContent`.

### Completude

- [X] Q-003 | Completude | As seções identificáveis do documento estão presentes e preenchidas sem placeholders?
  Evidência: Seções 1 a 12 presentes e estruturadas. §10 (linhas 227–230) registra zero lacunas pendentes e a incorporação das decisões técnicas de T003. §11 (linhas 231–249) traz glossário formal e §12 (linhas 250–258) o histórico de alterações. Nenhum marcador `TODO` ou `TBD` permanece.
- [X] Q-004 | Completude | O contrato de consumo define o que ocorre quando briefing aprovado é reaberto?
  Evidência: §4 (RN-06a, linha 45): "o endpoint de consumo do briefing aprovado (`GET /briefings/approved/{id}`) responde 409 enquanto o briefing estiver em `draft` após reabertura, até nova aprovação"; §4 (RN-06b, linha 46) define que a reabertura limpa `approved_at`, retorna o estado a `draft` e preserva histórico monotônico de versões.

### Consistência

- [X] Q-005 | Consistência | “Tema”, “rascunho”, “pontos”, “aprovado” e reabertura preservam significado ao longo do documento?
  Evidência: Vocabulário consistente em todo o texto: tema normalizado em RN-01/RF-01/§5.1; rascunho (`draft`) em RN-05/RF-03/RF-05; pontos válidos em RN-03/RN-03a/§5.1; aprovado (`approved`) e reabertura em RN-06/RN-06a/RN-06b/RF-06/RF-09; estados alinhados às entradas formais do glossário (§11).
- [X] Q-006 | Consistência | Os limites de tema e pontos são uniformes entre regras, requisitos e esclarecimentos?
  Evidência: Limites numéricos estritamente consistentes: tema entre 3 e 300 caracteres após strip em RN-01 (linha 32), RF-01 (linha 54), §5.1 (linha 66), Gherkin (linhas 106, 111–118) e Esclarecimentos §9 (linha 202); contagem de 3 a 7 pontos de foco em RN-03 (linha 36), RN-03a (linha 38), RN-05 (linha 41), RF-03 (linha 56), RF-05 (linha 58), RF-06 (linha 59), §5.1 (linha 67), Gherkin (linhas 97, 103, 147, 154, 159) e Esclarecimentos §9 (linhas 202, 215–217), com meta de 5 pontos como orientação e alvo habitual.
- [X] Q-007 | Consistência | A decisão mais recente sobre Jina prevalece sobre o histórico que menciona Google?
  Evidência: §1 (linha 10), RN-02 (linha 34: "sem garantia de motor Google exclusivo"), RF-02 (linha 55) e Esclarecimentos §9 (linhas 220–221) documentam a aceitação de SERP Jina sem motor Google exclusivo após a decisão de T003, superando o registro histórico anterior de 2026-10-10.

### Cobertura de cenários

- [X] Q-008 | Cobertura de cenários | Há cenários Gherkin para casos felizes e negativos do ciclo principal?
  Evidência: §7 (linhas 90–187) documenta 14 cenários cobrindo casos felizes (geração, edição, aprovação, consulta por consumidor, reabertura, criação sem deduplicação) e casos negativos (rejeição de tema fora de 3–300 antes de chamadas externas, fronteiras 2/3/300/301, rejeição de pontos fora de 3–7, falha na busca SERP, esgotamento do agente em 4 tentativas, timeout por tentativa, saída inválida do modelo, prompt ausente ou inválido e retentativa isolada).
- [X] Q-009 | Cobertura de cenários | Rejeição de tema e consumo aprovado possuem cenários Gherkin próprios e verificáveis?
  Evidência: §7 traz cenários dedicados: "Rejeitar tema inválido antes de chamadas externas" (linhas 105–110: tema nulo, vazio, espaços ou fora de 3–300 caracteres gera 422 sem chamadas SERP/LLM) e "Consultar briefing aprovado pelo consumidor" (linhas 125–130: endpoint retorna briefing aprovado sem novas chamadas externas ou geração).
- [X] Q-010 | Cobertura de cenários | Timeout, saída inválida e esgotamento do agente possuem resultados terminais em Gherkin?
  Evidência: Sanado por T038. §7 traz agora três cenários dedicados e encadeados:
  - "Cenário: Esgotamento das tentativas do agente" (linhas 131–137): esgotamento das 4 tentativas encerra com estado terminal `FAILED` no mesmo registro, persiste `FAILED` de forma best-effort e informa erro seguro sem segredos.
  - "Cenário: Timeout por tentativa consome orçamento" (linhas 138–144): timeout individual de 30s por tentativa consome 1 tentativa do orçamento de 4 totais, retenta reusando mesmo resultado SERP, e esgotamento encerra com `FAILED` e erro seguro.
  - "Cenário: Saída inválida do modelo consome tentativa" (linhas 145–151): saída com JSON inválido ou pontos fora de 3–7 conta como falha, consome tentativa com erro seguro, retenta reusando SERP, e esgotamento encerra com `FAILED`.

### Edge cases

- [X] Q-011 | Edge cases | O intervalo 3–300 caracteres define contagem, tratamento de espaços e fronteiras em Gherkin?
  Evidência: Sanado por T038. §4 (RN-01, linha 32) explicita unidade e normalização: "Contagem em caracteres Unicode (code points, `len` Python) sobre o tema já normalizado; strip remove caracteres de espaço em branco (whitespace: espaços, tabulações, quebras de linha) das extremidades, preservando espaços internos. Fronteiras explícitas: 2 caracteres rejeitado com 422; 3 caracteres válido; 300 caracteres válido; 301 caracteres rejeitado com 422".
  §5.1 (linha 66) reitera as regras e fronteiras.
  §7 (linhas 111–119) traz cenário Gherkin dedicado "Fronteiras de tema" testando explicitamente: 2 caracteres rejeitado com 422; 3 ou 300 caracteres aceitos; 301 caracteres rejeitado com 422.
- [X] Q-012 | Edge cases | O intervalo 3–7 pontos é exigido na geração, edição salva e aprovação, preservando versão anterior em rejeição?
  Evidência: RN-03 (linha 36), RN-03a (linha 38), RN-05 (linha 41), RF-05 (linha 58) e RF-06 (linha 59) aplicam a faixa de 3 a 7 pontos em todas as fases. Cenário Gherkin "Rejeitar quantidade inválida" (linhas 152–157) garante que operação com menos de 3 ou mais de 7 pontos é recusada e versão anterior permanece intacta.
- [X] Q-013 | Edge cases | As quatro tentativas incluem a inicial e evitam repetir uma busca bem-sucedida?
  Evidência: RN-02 (linha 34), RF-10 (linha 63: "cada operação externa que falhar recebe até 4 tentativas totais (inicial e 3 retentativas), sequenciais; falha do agente reutiliza resultado SERP já obtido"), §9 (linhas 206, 211, 213) e cenário Gherkin "Retentar operação sem repetir sucesso" (linhas 176–181) garantem que a busca SERP bem-sucedida é reutilizada sem repetição e que o total de tentativas por operação é limitado a 4.
- [X] Q-014 | Edge cases | Entradas nulas, SERP vazio e prompt inválido possuem regras de tratamento inequívocas?
  Evidência: Sanado por T038. §5.1 e regras de negócio definem cada caso de forma inequívoca:
  - Tema nulo/vazio: RN-01 (linha 32), §5.1 (linha 66) e Gherkin (linhas 105–110) determinam rejeição com 422 antes de qualquer chamada externa.
  - Ponto nulo/vazio: RN-03a (linha 38) e §5.1 (linha 67) definem `InvalidContent` para campos ausentes/vazios/nulos após strip.
  - Item SERP: §5.1 (linha 68) exige `title`, `url` e `description` preenchidos e não-vazios após strip.
  - SERP vazio: §5.1 (linha 69) explicita que resposta com `data[]` vazio, ausente ou sem itens válidos após filtragem é falha de busca externa (erro seguro), consome tentativa de busca e, se esgotado o teto de 4 tentativas, encerra o registro em `FAILED` sem chamar o modelo LLM nem gerar rascunho.
  - Prompt inválido: §5.1 (linha 70) explicita que arquivo ausente, vazio (0 bytes), somente espaços, ilegível ou não-UTF-8 é rejeitado com erro interno seguro 500 (`PromptUnavailable`, mensagem fixa sem detalhes locais) antes de qualquer chamada SERP ou LLM, persistindo `FAILED` seguro em registro existente. Cenário Gherkin correspondente nas linhas 182–187.

### Ausência de jargão

- [X] Q-015 | Ausência de jargão | Siglas e termos técnicos são explicados para pessoa nova no time?
  Evidência: Sanado por T038. §11 (linhas 231–249) expandiu o glossário e definiu formalmente em português claro:
  SERP, Jina, LLM, CAS (Compare-And-Swap), monotonicidade de versão, snapshot imutável, status do briefing (`generating`, `draft`, `approved`, `failed`), GENERATING, DRAFT, APPROVED, FAILED, Prompt, Tx1/Tx2 e códigos HTTP 422/409/404/503.
  Termos operacionais contextuais também encontram definição textual clara no corpo: strip e caracteres Unicode em RN-01 (linha 32); payload e dados não confiáveis em §6 (linha 84); `InvalidContent` como erro de domínio em §5.1 (linha 67); best-effort qualificado como ausência de garantia contra queda catastrófica em §6 (linha 85) e Gherkin (linha 135); MoSCoW (Must/Should) tabulado em §8 (linhas 189–196).

### Ausência de solução implícita

- [X] Q-016 | Ausência de solução implícita | As restrições Jina e arquivo de prompt são decisões explícitas, e não escolhas técnicas ocultas?
  Evidência: §2 (linhas 12–21) documenta decisões formais do usuário de 2026-10-10 para uso exclusivo de tool SERP Jina e instrução via arquivo na pasta de prompts; Esclarecimentos em §9 (linhas 207–208, 220–226) detalham as razões das escolhas, sem frameworks ou bibliotecas desnecessárias impostas no requirements.

### Alinhamento com princípios

- [X] Q-017 | Alinhamento com princípios | O princípio I é respeitado sem exigir citações de relatório final em módulo que não produz conclusões?
  Evidência: RN-03 (linha 36) e RN-07 (linha 47) delimitam o briefing à geração de tópicos preliminares de foco, sem emissão de conclusões ou relatório de pesquisa. O Princípio I (Verbatim Citation de fatos em relatório) permanece preservado para as fases de pipeline e escrita subsequentes, sem imposição distorcida em módulo que não emite conclusões.
- [X] Q-018 | Alinhamento com princípios | A rastreabilidade protege o prompt de sistema e explicita tratamento de entradas não confiáveis?
  Evidência: §6 detalha o Princípio II (linha 84): "instrução de sistema vem exclusivamente de arquivo em disco em runtime (pasta de prompts); nunca é persistida em banco nem vazada em respostas ou logs. Tema informado pelo operador e resultados SERP são dados não confiáveis: nunca interpolados na instrução de sistema, apenas no payload `user`". Em §6 (linha 78), a rastreabilidade armazena apenas referência de prompt (metadado: caminho relativo ou hash, nunca texto integral). Em §8 (linha 194), Rastreabilidade é classificada com prioridade MoSCoW `Should` (orientação de auditoria que não bloqueia a entrega mínima nem promete capacidade persistida obrigatória nesta etapa). A fronteira de proteção de segredos resguarda as interfaces públicas (respostas HTTP, registros persistidos e logs).
- [X] Q-019 | Alinhamento com princípios | O princípio III tem resultado terminal explícito para toda operação externa e saída inválida?
  Evidência: Sanado por T038. §6 (linha 85) removeu a ambiguidade de "timeout persistido":
  "o timeout é por tentativa (30s configuráveis) e sua expiração consome 1 das até 4 tentativas totais da operação externa; não existe deadline global sobre a operação completa. Saída estruturalmente inválida do modelo (JSON inválido, shape fora do esquema ou contagem fora de 3–7) consome tentativa com erro seguro, reusando o resultado SERP já obtido, sem nova busca. Esgotamento das 4 tentativas ou falha não retentável (configuração/programação/cancelamento) encerra o registro de forma segura: para falhas retentáveis esgota o orçamento e persiste `failed` com tentativa best-effort (erro fixo, sem segredo/payload bruto); best-effort significa sem garantia contra queda catastrófica de processo ou banco — crash pode impedir a persistência. Sem travamento silencioso em caminho normal". Cenários Gherkin correspondentes (linhas 131–151).
- [X] Q-020 | Alinhamento com princípios | O texto garante concorrência segura e idempotência conforme princípio IV?
  Evidência: Sanado por T038. §6 (linha 86) delimita o escopo de concorrência com precisão:
  "CAS (compare-and-swap) protege somente concorrência de atualização de versões: transições usam comparação otimista sobre `version`, e colisão (versão concorrente) responde 409 sem sobrescrever estado concorrente. Histórico de versões é monotônico (append a partir de v2), jamais reescrito. Aprovação/reabertura repetida no estado já atingido responde 409 (contrato de transição aprovado), sem no-op silencioso. Não há deduplicação global por tema na criação: cada POST cria um briefing independente com seu próprio identificador UUID; concorrência de criação não é bloqueada nem deduplicada por este princípio. 'Uma chamada por vez' qualifica-se como por operação/invocação (lock por instância de cliente SERP), não como limite global". Cenário Gherkin "Criar briefing sem deduplicação por tema" nas linhas 120–124.

## Veredito

**Aprovado.** 20/20 itens aprovados; 0 reprovados. Todos os pontos das rodadas anteriores foram sanados com texto inequívoco, definições formais e cenários Gherkin completos. A clareza textual e o alinhamento com os princípios arquiteturais atendem integralmente ao padrão de qualidade do Reversa.

## Limitações e conformidade operacional

- `.reversa/active-requirements.json` verificado para feature `001-modulo-briefing`.
- Auditoria leitora estrita sobre `_reversa_forward/001-modulo-briefing/requirements.md`.
- **`requirements.md` NÃO foi modificado.**
- **Nenhum arquivo de código, teste, ação, roadmap ou progress foi modificado nesta execução.**
- Manifesto congelado L104 de `progress.jsonl` verificado: 230 arquivos de baseline preservados intactos.
- **Este relatório avalia exclusivamente clareza textual e aderência formal de requisitos; NÃO aprova código, QA executável ou execução em runtime; a feature NÃO está DONE.**
- Único arquivo gravado: `_reversa_forward/001-modulo-briefing/audit/requirements-audit.md`.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-11 | Primeira auditoria textual gerada por `/reversa-quality` (Reprovado, 10/20) | reversa-quality |
| 2026-10-11 | Reauditoria textual preliminar de rascunho anterior (Aprovado, 20/20) | reversa-quality |
| 2026-10-11 | Reauditoria textual estrita pós-T037 com confronto item a item (Reprovado, 14/20; findings Q-010, Q-011, Q-014, Q-015, Q-019, Q-020) | reversa-quality |
| 2026-10-11 | Reauditoria textual completa pós-T038 (Aprovado, 20/20; saneamento integral de Q-010, Q-011, Q-014, Q-015, Q-019, Q-020 comprovado) | reversa-quality |

## Proveniência documental e checks

- SHA-256 requirements vigente auditado: `964cd5d70511a968f123620b186ba82908740a51ae8caa38d0ceb5ec5cb68653`.
- SHA-256 principles: `ff769546e4d360809b04a55d93e696b9aac3b4ba8f856720c7f592eba049612b`.
- Relatório anterior substituído: SHA-256 `1812093abd5b54f14a8fe614049be992fc301749ce02700c40f6fef48e0e2db6`; preservados veredictos históricos Reprovado 10/20, Aprovado 20/20 e Reprovado 14/20.
- Checks exclusivamente documentais: vinte IDs únicos, contagens, evidências e tabelas; sem execução de teste, código ou provedor. Progress/actions preservados.
