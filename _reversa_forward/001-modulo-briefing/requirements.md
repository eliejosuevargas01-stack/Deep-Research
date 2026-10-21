# Requirements: Módulo de briefing

> Identificador: `001-modulo-briefing`
> Data: `2026-10-10`
> Pasta da extração reversa: `_reversa_sdd/` (vazia; documentação antiga eliminada)
> Confidência: 100% 🟢 CONFIRMADO (auditado e aprovado pelo operador em 2026-10-16)
>
> **Nota de vigência (2026-10-19):** Este requirements está sujeito ao adendo normativo aprovado [`../../_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md`](../../_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md), que possui precedência sobre trechos conflitantes. Em particular: a criação e a revisão de briefing operam na mesma requisição HTTP de forma estritamente síncrona (retornando 200/201 com o rascunho completo, sem HTTP 202 nem polling) e usam exclusivamente busca SERP via Jina (SERP-only, sem leitura de páginas integrais, cuja regra de 10 corpos limpos integrais aplica-se unicamente aos workers da Feature 002).
>
> **Aviso de vigência documental:** Este documento registra a especificação original da Feature 001 (Módulo de Briefing). Conforme os requisitos vigentes da Feature 002 (`_reversa_forward/002-investigacao-personas/requirements.md:134-137,231`), decisões de produto sucessoras superdimensionaram e ajustaram fluxos: (1) a reabertura de briefing aprovado foi descontinuada (retornando HTTP 409 em `POST /briefings/{research_id}/reopen` com status aprovado definitivo); (2) o endpoint de edição manual direta de lista de pontos foi substituído por revisão única assistida via `PATCH /briefings/{research_id}` com nota de feedback (`note`). A extinção do endpoint `/approve` e a aprovação implícita via `/investigate` estão planejadas na Sprint C8 da Feature 002 (`_reversa_forward/002-investigacao-personas/actions.md:114-118,196-198`, T036–T040) e permanecem futuras em relação a este documento. As especificações originais da Feature 001 são preservadas abaixo como histórico com notas de vigência.

## 1. Resumo executivo

A feature cria o módulo de briefing do backend. O módulo recebe um tema de pesquisa, consulta resultados SERP via Jina para mapear o assunto, com uma chamada por vez e repetição somente em falha e produz um rascunho dos pontos importantes que a pesquisa deverá investigar. O operador pode editar e aprovar esse rascunho. Execução da pesquisa fica fora deste módulo.

## 2. Contexto a partir do legado

Documentação Reversa anterior e regras implícitas no código atual não são fonte de requisitos desta feature, por decisão do usuário em 2026-10-10.

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| Decisão do usuário, 2026-10-10 | Projeto será separado em módulos; primeira feature cobre somente backend do briefing | 🟢 |
| Decisão do usuário, 2026-10-10 | Agente de inteligência artificial recebe tema, faz uma única busca e gera rascunho de pontos de foco, sem responder à pesquisa | 🟢 |
| Decisão do usuário, 2026-10-10 | Instrução de sistema do agente vem diretamente da pasta de prompts | 🟢 |
| Decisão do usuário, 2026-10-10 | Escopo inclui geração, edição e aprovação; execução da pesquisa fica fora | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Operador da pesquisa | Definir foco antes de iniciar investigação | Informa tema, revisa rascunho gerado, ajusta pontos e aprova briefing |
| Módulo de pesquisa, consumidor futuro | Receber foco aprovado | Lê somente briefing aprovado para iniciar etapa posterior, fora desta feature |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Briefing nasce de tema informado pelo operador, normalizado por strip; válido somente com 3 a 300 caracteres após strip. Contagem em caracteres Unicode (code points, `len` Python) sobre o tema já normalizado; strip remove caracteres de espaço em branco (whitespace: espaços, tabulações, quebras de linha) das extremidades, preservando espaços internos. Fronteiras explícitas: 2 caracteres rejeitado com 422; 3 caracteres válido; 300 caracteres válido; 301 caracteres rejeitado com 422. Tema nulo, vazio ou somente espaços é rejeitado com 422 antes de qualquer chamada externa (SERP/LLM). 🟢
  - Tipo: nova
2. **RN-02:** Agente dispõe de uma única tool de pesquisa: SERP via Jina. Uma chamada por vez obtém resultados SERP via Jina (sem garantia de motor Google exclusivo); novas chamadas de busca são permitidas somente quando a anterior falhar. Agente analisa somente esses resultados. Não há leitura de páginas, Reader, scraping adicional ou outra ferramenta de pesquisa. 🟢
   - Tipo: nova
3. **RN-03:** Busca serve para identificar pontos importantes, não para responder à pesquisa. Briefing contém no mínimo 3 e no máximo 7 pontos de foco na geração, após edição e na aprovação, não conclusões. Alvo habitual de geração: 5 pontos; usar outra quantidade dentro desse intervalo quando necessário ao tema. 🟢
   - Tipo: nova
   - Validade de ponto (RN-03a): ponto é válido somente quando `title` e `description` são texto não-vazio após strip; ponto nulo, com campo ausente, vazio ou somente espaços é rejeitado. Contagem 3–7 vale para a geração, a edição salva e a aprovação. 🟢
4. **RN-04:** Instrução de sistema usada pelo agente vem de arquivo da pasta de prompts, sem texto equivalente definido diretamente na lógica do módulo. 🟢
   - Tipo: nova
5. **RN-05:** Operador pode refinar o rascunho através de feedback conversacional antes da aprovação definitiva em etapa única; versão salva mantém entre 3 e 7 pontos. 🟢 *(Nota de vigência: Requisito original da Feature 001 supersedido pelos requisitos vigentes de `_reversa_forward/002-investigacao-personas/requirements.md:136,231`, que extinguiram a edição manual de lista em favor de revisão única assistida via `PATCH /briefings/{research_id}` com campo `note`.)*
   - Tipo: nova
6. **RN-06:** Aprovação torna briefing disponível para etapa posterior. Operador pode reabri-lo, retornando ao estado de rascunho e permitindo edição. Edição direta enquanto aprovado é recusada. 🟢 *(Nota de vigência: A reabertura de briefing aprovado foi supersedida pela Feature 002 em `_reversa_forward/002-investigacao-personas/requirements.md:135,231`, tornando a aprovação definitiva e retornando HTTP 409 em tentativas de reabertura; a extinção de `/approve` de C8 permanece futura.)*
   - Tipo: nova
   - Contrato de consumo (RN-06a): o endpoint de consumo do briefing aprovado (`GET /briefings/approved/{id}`) responde 409 enquanto o briefing estiver em `draft` após reabertura, até nova aprovação. 🟢 *(Nota de vigência: Reabertura pós-aprovação supersedida por HTTP 409 na Feature 002:135,231.)*
   - Impacto da reabertura (RN-06b): reabertura limpa `approved_at` e retorna o registro a `draft`; histórico de versões permanece consultável e monotônico. 🟢 *(Nota de vigência: Reabertura pós-aprovação supersedida por HTTP 409 na Feature 002:135,231.)*
7. **RN-07:** Módulo não inicia investigação nem gera relatório. 🟢
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Receber tema de pesquisa e criar briefing em geração | Must | Tema entre 3 e 300 caracteres gera registro identificável; fora do intervalo é rejeitado antes de chamadas externas | 🟢 |
| RF-02 | Oferecer somente tool SERP via Jina ao agente | Must | Uma chamada por vez obtém resultados SERP via Jina; nenhuma página é lida e nenhuma segunda tool de pesquisa é disponibilizada; sucesso não dispara buscas adicionais | 🟢 |
| RF-03 | Gerar rascunho com pontos importantes da pesquisa | Must | Rascunho gerado contém 3 a 7 pontos de foco com título e descrição, visando habitualmente 5 e adaptando quantidade ao tema quando necessário, sem resposta conclusiva | 🟢 |
| RF-04 | Carregar instrução de sistema da pasta de prompts | Must | Alteração no arquivo de prompt muda instrução usada na próxima geração sem alteração de lógica | 🟢 |
| RF-05 | Permitir edição do rascunho antes da aprovação | Must | Operador altera, adiciona, remove ou reordena pontos; versão salva contém 3 a 7 pontos e fica consultável; fora desse intervalo, edição é rejeitada sem substituir versão anterior | 🟢 *(Nota de vigência: Requisito original supersedido por `_reversa_forward/002-investigacao-personas/requirements.md:136,231` em favor de PATCH com `note`.)* |
| RF-06 | Permitir aprovação do briefing | Must | Briefing com 3 a 7 pontos válidos muda para aprovado; edição é recusada até reabertura | 🟢 *(Nota de vigência: Extinção de `/approve` planejada na Sprint C8 da Feature 002; rota ativa em `app/briefing/router.py:289-305`.)* |
| RF-07 | Expor briefing aprovado para etapa posterior | Must | Consumidor obtém conteúdo aprovado sem iniciar investigação | 🟢 |
| RF-08 | Informar falhas de busca, geração ou prompt | Must | Falha impede rascunho inválido e retorna motivo seguro, sem segredos | 🟢 |
| RF-09 | Reabrir briefing aprovado | Must | Reabertura muda estado para rascunho e permite novas edições | 🟢 *(Nota de vigência: Supersedido por `_reversa_forward/002-investigacao-personas/requirements.md:135,231`, que bloqueia reabertura de aprovado com HTTP 409.)* |
| RF-10 | Retentar automaticamente falhas no mesmo registro | Must | Mantém mesmo registro; cada operação externa que falhar recebe até 4 tentativas totais (inicial e 3 retentativas), sequenciais; falha do agente reutiliza resultado SERP já obtido | 🟢 |

### 5.1 Regras de nulidade e campos obrigatórios SERP (Q-014)
- Tema: nulo, vazio ou somente espaços após strip → rejeição 422 antes de qualquer chamada externa; válido somente 3–300 chars Unicode após strip (fronteiras: 2 rejeitado, 3 e 300 válidos, 301 rejeitado).
- Ponto: nulo, com `title`/`description` ausente, nulo, vazio ou somente espaços após strip → `InvalidContent`; geração, edição salva e aprovação exigem 3–7 pontos válidos.
- Item SERP: obrigatório `title`, `url` e `description` presentes e não-vazios após strip; campos adicionais ignorados silenciosamente; item sem qualquer campo obrigatório é inválido para parser.
- SERP com zero resultados: resposta cujo `data[]` está vazio, ausente ou não deixa nenhum item válido após filtragem é falha de busca externa (erro seguro) — consome tentativa de busca, e esgotado o teto de 4 tentativas encerra o registro em `FAILED` sem chamar o modelo (LLM) nem gerar rascunho.
- Arquivo de prompt inválido: ausente, vazio (0 bytes), somente espaços, ilegível (erro de leitura) ou com codificação não-UTF-8 é rejeitado com erro interno seguro 500 (`PromptUnavailable`, mensagem fixa sem detalhes locais), antes de qualquer chamada SERP ou LLM; registro existente persiste `FAILED` com erro seguro.

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Modularidade | Lógica, regras, prompts e contratos do briefing permanecem dentro dos limites do módulo | Separação do projeto em módulos | 🟢 |
| Segurança | Credenciais e dados sensíveis nunca aparecem em resposta, erro ou registro do briefing | Proteção de dados operacionais | 🟢 |
| Rastreabilidade | Cada briefing registra tema, busca única, referência de prompt usado (metadado: caminho relativo ou hash, nunca texto integral), edições e aprovação | Auditoria do foco aprovado | 🟢 |
| Confiabilidade | Falha externa não gera rascunho parcial como válido | Evitar briefing incorreto | 🟢 |
| Testabilidade | Busca, agente e prompt podem ser substituídos em testes sem acesso externo | Verificação do módulo isolado | 🟢 |

### Princípios operacionais explícitos

- **Princípio II — Isolamento de prompt:** instrução de sistema vem exclusivamente de arquivo em disco em runtime (pasta de prompts); nunca é persistida em banco nem vazada em respostas ou logs. Tema informado pelo operador e resultados SERP são dados não confiáveis: nunca interpolados na instrução de sistema, apenas no payload `user`.
- **Princípio III — Falha terminal audível:** o timeout é por tentativa (30s configuráveis) e sua expiração consome 1 das até 4 tentativas totais da operação externa; não existe deadline global sobre a operação completa. Saída estruturalmente inválida do modelo (JSON inválido, shape fora do esquema ou contagem fora de 3–7) consome tentativa com erro seguro, reusando o resultado SERP já obtido, sem nova busca. Esgotamento das 4 tentativas ou falha não retentável (configuração/programação/cancelamento) encerra o registro de forma segura: para falhas retentáveis esgota o orçamento e persiste `failed` com tentativa best-effort (erro fixo, sem segredo/payload bruto); best-effort significa sem garantia contra queda catastrófica de processo ou banco — crash pode impedir a persistência. Sem travamento silencioso em caminho normal.
- **Princípio IV — Concorrência segura:** CAS (compare-and-swap) protege somente concorrência de atualização de versões: transições usam comparação otimista sobre `version`, e colisão (versão concorrente) responde 409 sem sobrescrever estado concorrente. Histórico de versões é monotônico (append a partir de v2), jamais reescrito. Aprovação/reabertura repetida no estado já atingido responde 409 (contrato de transição aprovado), sem no-op silencioso. Não há deduplicação global por tema na criação: cada POST cria um briefing independente com seu próprio identificador UUID; concorrência de criação não é bloqueada nem deduplicada por este princípio. "Uma chamada por vez" qualifica-se como por operação/invocação (lock por instância de cliente SERP), não como limite global.

## 7. Critérios de Aceitação

```gherkin
Cenário: Gerar rascunho de briefing
  Dado tema de pesquisa válido e prompt disponível
  Quando operador solicita briefing
  Então sistema obtém resultados SERP via Jina em uma chamada bem-sucedida
  E não executa buscas adicionais após sucesso
  E agente usa instrução da pasta de prompts
  E sistema retorna rascunho com 3 a 7 pontos de foco, sem resposta final
  E prompt orienta 5 pontos como alvo habitual, adaptando quantidade ao tema quando necessário

Cenário: Editar rascunho
  # Nota de vigência: Cenário histórico da Feature 001 supersedido pela Feature 002:136,231 (edição manual de lista extinta em favor de PATCH com note)
  Dado briefing em rascunho
  Quando operador altera pontos de foco
  Então sistema salva nova versão do rascunho com 3 a 7 pontos

Cenário: Rejeitar tema inválido antes de chamadas externas
  Dado tema nulo, vazio ou somente espaços, ou fora de 3 a 300 caracteres Unicode após strip
  Quando operador solicita briefing
  Então sistema rejeita com 422
  E não chama SERP nem LLM

Cenário: Fronteiras de tema
  Dado tema normalizado por strip (extremidades removidas, espaços internos preservados)
  Quando tema tem 2 caracteres
  Então sistema rejeita com 422
  Quando tema tem 3 ou 300 caracteres
  Então sistema aceita e cria registro
  Quando tema tem 301 caracteres
  Então sistema rejeita com 422

Cenário: Criar briefing sem deduplicação por tema
  Dado dois pedidos com o mesmo tema válido
  Quando operador solicita briefing duas vezes
  Então cada POST cria um briefing independente com UUID próprio

Cenário: Consultar briefing aprovado pelo consumidor
  Dado briefing aprovado
  Quando consumidor consulta endpoint de briefing aprovado
  Então sistema retorna conteúdo aprovado
  E não dispara nova busca nem nova geração

Cenário: Esgotamento das tentativas do agente
  Dado busca SERP concluída e agente com falha nas 4 tentativas totais
  Quando sistema esgota tentativas do agente
  Então sistema encerra com estado terminal FAILED no mesmo registro
  E tenta persistir FAILED de forma best-effort, sem garantia contra queda catastrófica de processo ou banco
  E informa erro seguro sem segredos

Cenário: Timeout por tentativa consome orçamento
  Dado busca SERP concluída e timeout de 30 segundos por tentativa
  Quando uma tentativa do agente expira por timeout
  Então tentativa conta no orçamento de 4 tentativas totais
  E sistema retenta reusando o mesmo resultado SERP
  E esgotamento encerra com FAILED e erro seguro

Cenário: Saída inválida do modelo consome tentativa
  Dado busca SERP concluída
  Quando modelo retorna JSON inválido ou lista com menos de 3 ou mais de 7 pontos
  Então tentativa conta como falha com erro seguro
  E sistema retenta reusando o mesmo resultado SERP
  E esgotamento encerra com FAILED sem rascunho válido

Cenário: Rejeitar quantidade inválida
  Dado briefing em rascunho
  Quando operador tenta salvar ou aprovar conteúdo com menos de 3 ou mais de 7 pontos
  Então operação é recusada
  E versão anterior permanece intacta

Cenário: Aprovar briefing
  Dado briefing em rascunho válido com 3 a 7 pontos
  Quando operador aprova
  Então briefing fica aprovado
  E edição direta é recusada enquanto aprovado

Cenário: Reabrir briefing
  # Nota de vigência: Cenário histórico da Feature 001 supersedido pela Feature 002:135,231 (reabertura de aprovado descontinuada; responde HTTP 409)
  Dado briefing aprovado
  Quando operador solicita reabertura
  Então briefing retorna ao estado de rascunho
  E operador pode editar pontos

Cenário: Falha na busca
  Dado tema de pesquisa válido
  Quando busca SERP falha nas 4 tentativas totais
  Então sistema marca falha no mesmo registro e não cria rascunho válido
  E informa motivo seguro

Cenário: Retentar operação sem repetir sucesso
  Dado busca SERP concluída e chamada do agente com falha
  Quando sistema retenta chamada do agente
  Então reutiliza resultado da busca e mantém mesmo registro
  E faz no máximo 4 tentativas totais da operação que falhou

Cenário: Prompt ausente ou inválido
  Dado arquivo de prompt ausente ou inválido
  Quando operador solicita briefing
  Então sistema não chama agente
  E informa falha de configuração sem expor conteúdo sensível
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 a RF-10 | Must | Formam ciclo mínimo de briefing, da geração à aprovação |
| Rastreabilidade | Should | Facilita auditoria sem bloquear geração mínima |
| Testabilidade isolada | Must | Necessária para validar módulo sem serviços externos |

## 9. Esclarecimentos

### Sessão 2026-10-10

- **Q:** Quais limites aplicar?
  **R:** Tema com 3 a 300 caracteres; rascunho gerado com 3 a 7 pontos.
- **Q:** Briefing aprovado pode ser reaberto?
  **R:** Sim. Retorna ao estado de rascunho para edição. *(Nota de vigência: Resposta histórica de 2026-10-10 supersedida pelas decisões de 2026-10-14 da Feature 002:135,231, que fixaram resposta HTTP 409 na reabertura de aprovado.)*
- **Q:** Qual recuperação após falha?
  **R:** Retentar automaticamente no mesmo registro: 1 tentativa inicial mais até 3 retentativas, total de 4 tentativas por operação externa que falhar.
- **Q:** Qual ferramenta de pesquisa usar?
  **R:** Uma única tool SERP via Jina para busca Google. Analisar somente resultados; sem leitura de páginas. Uma chamada por vez; se houver falha, pode chamar novamente.

- **Q:** Retentativas podem repetir a busca?
  **R:** Sim, em falhas. Uma única chamada por vez; nenhuma busca extra após sucesso.
- **Q:** Qual limite total?
  **R:** 4 tentativas totais: inicial mais 3 retentativas.

- **Q:** Qual quantidade de pontos permitir após edição e para aprovação?
  **R:** Mínimo 3, máximo 7; quantidade habitual de 5 pontos, variando quando necessário. Limites valem para geração, edição salva e aprovação. A média de 5 é orientação para o agente, não exigência de exatamente 5 em cada briefing.

### Sessão 2026-10-11

- **Q:** T003: fontes oficiais não provam Google como motor do `s.jina.ai` (Elastic: 'Google ou outro'; código OSS aceita google e bing). Como tratar RF-02?
  **R:** Aceitar SERP Jina sem garantia de Google exclusivo; RF-02 passa a exigir busca SERP via Jina sem leitura de páginas.
- **Q:** Schema da resposta Jina no modo `no-content` não tem exemplo oficial. Como congelar o parser?
  **R:** Parser tolerante: somente `title`, `url` e `description` são obrigatórios em cada item de `data[]`; campos adicionais são ignorados silenciosamente.
- **Q:** Timeout de cliente para Jina e LLM (sem SLA público)?
  **R:** 30 segundos por tentativa, configurável; cada operação mantém limite de até 4 tentativas totais sequenciais em falha.

## 10. Lacunas

Nenhum marcador pendente nesta sessão. Decisões técnicas de T003 integradas: SERP via Jina aceita sem exclusividade Google; parser tolerante com `title`, `url`, `description` obrigatórios; timeout de cliente 30s por tentativa.

## 11. Glossário de termos e siglas (Q-015)

| Termo | Significado |
|-------|-------------|
| SERP | Search Engine Results Page — lista de resultados retornada pela busca, consumida como `title`/`url`/`description` |
| Jina | Provedor Jina AI; endpoint `https://s.jina.ai/` usado como única tool de pesquisa (SERP) |
| LLM | Large Language Model — agente que gera rascunho de pontos a partir de instrução de sistema + resultados SERP |
| CAS | Compare-And-Swap — atualização condicional: grava somente se a `version` lida ainda for a corrente; versão concorrente responde 409 sem sobrescrever |
| monotonicidade de versão | Histórico de versões somente cresce por append (v2 em diante); nenhuma versão passada é reescrita ou removida |
| snapshot imutável | Cópia congelada do briefing numa versão; edição posterior cria nova versão sem alterar snapshots anteriores |
| status do briefing | Estado do ciclo: `generating` (criado, aguardando geração); `draft` (rascunho editável); `approved` (aprovado, disponível para consumo); `failed` (falha terminal segura) |
| GENERATING | Estado inicial após criação válida; aguarda prompt→SERP→LLM |
| DRAFT | Estado de rascunho editável; permite edição, aprovação e consumo parcial |
| APPROVED | Estado aprovado; bloqueia edição direta até reabertura; habilita consumo aprovado |
| FAILED | Estado terminal de falha segura; não gera rascunho válido; erro fixo sem segredos |
| Prompt | Instrução de sistema lida de arquivo em disco em runtime; nunca persistida em banco nem vazada em resposta/log |
| Tx1/Tx2 | Transação 1 (reserva do registro `generating`) / Transação 2 (persistência CAS do resultado) |
| 422/409/404/503 | Erro HTTP: conteúdo inválido / conflito de versão ou estado / ausente / falha externa |

## 12. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-10 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-10-10 | `/reversa-clarify`: limites, reabertura, tool SERP via Jina sem leitura de páginas e 4 tentativas sequenciais | reversa |
| 2026-10-10 | Confirmação posterior do usuário: 3–7 pontos também após edição e para aprovação; alvo habitual de 5 pontos | reversa |
| 2026-10-11 | `/reversa-clarify`: RF-02 ajustado para SERP via Jina (sem exclusividade Google comprovada); parser tolerante (`title`, `url`, `description`); timeout 30s configurável | reversa |
| 2026-10-11 | T038 saneamento textual: Q-010 (Gherkin timeout por tentativa e saída inválida), Q-011 (contagem Unicode, strip, fronteiras 2/3/300/301), Q-014 (SERP vazio e prompt inválido), Q-015 (glossário CAS/monotonicidade/snapshot/status), Q-019 (best-effort e timeout por tentativa), Q-020 (CAS vs deduplicação de criação) | reversa |

## 13. Emendas

### E001, 2026-10-11

O que muda: Permitir que o cliente SERP Jina opere sem chave de API (omitindo o cabeçalho Authorization quando nenhuma chave for fornecida) para compatibilidade com o modo sem chave/padrão, mantendo validação estrita de caracteres em chaves fornecidas; atualizar o modelo padrão da role scout para `gemini/gemini-3.8-flash`.
Motivo: Solicitação explícita do operador para utilizar modo sem chave como default do Jina e adotar o modelo Gemini 3.8 Flash como padrão do scout/briefing.
Arquivos previstos: `app/services/settings.py`, `app/briefing/serp_client.py`, `app/briefing/router.py`, `tests/test_briefing_serp_client.py`, `tests/test_briefing_api.py`.

Atualização de escopo, 2026-10-11: o operador retirou a mudança do Jina: “me enganei, para serp jina precisa de chave, mantenha como esta”. O modo anônimo acima não será implementado; cliente SERP e exigência de chave permanecem intactos. Testes HTTP reais de GET e POST em `s.jina.ai` sem Authorization retornaram 401 `AuthenticationRequiredError`.

Escopo vigente de E001: somente modelo padrão do scout/briefing, `gemini/gemini-3.8-flash`. A resolução deve preservar a precedência modelo explícito no banco, depois `SCOUT_MODEL`, depois esse padrão quando ambos ausentes. Não migrar configurações existentes nem alterar modelos de outras roles. Alterar apenas a tabela `DEFAULT_ROLE_MODELS` não satisfaz a emenda: `runtime_settings()` também deve aplicar esse fallback ao scout.
Arquivos previstos no escopo vigente: `app/services/settings.py`, `tests/test_briefing_llm_binding.py` (ou teste isolado `tests/test_briefing_settings.py` se necessário). Integração com provedor LLM real continua um gate separado; modelo documentado não prova chamada autenticada.

