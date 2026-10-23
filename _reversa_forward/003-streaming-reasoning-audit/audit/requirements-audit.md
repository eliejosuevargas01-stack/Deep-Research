# Requirements Audit

> Identificador da feature: `003-streaming-reasoning-audit`
> Data: `2026-10-22`
> Documento auditado: `_reversa_forward/003-streaming-reasoning-audit/requirements.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de itens | 20 |
| Aprovados | 10 |
| Reprovados | 10 |
| Veredito | Reprovado |

## Itens por categoria

### Clareza

- [X] Q-001 | Clareza | O objetivo principal da funcionalidade está delimitado de forma compreensível e direta na visão geral
- [X] Q-002 | Clareza | As responsabilidades de streaming entre as quatro etapas do pipeline (planejador, busca, auditoria e redação) estão explicitadas
- [ ] Q-003 | Clareza | O requisito RF-06 define critérios objetivos e verificáveis para "aprimorar a rastreabilidade metodológica"
  > motivo: O texto de RF-06 ("aprimorar a rastreabilidade metodológica") é vago e abstrato, sem definir como o acesso ao reasoning pelo Auditor deve ser operacionalizado ou testado.
  > sugestão: Especificar exatamente como o Auditor consome o reasoning (ex.: "O prompt do Auditor deve receber o campo reasoning_coleta das evidências para validar a pertinência do raciocínio das personas").

### Completude

- [X] Q-004 | Completude | O documento contém as seções estruturais essenciais (Visão Geral, Requisitos Funcionais, Requisitos Não-Funcionais e Cenários)
- [ ] Q-005 | Completude | Existem cenários de aceitação em formato Gherkin cobrindo fluxos de erro ou falhas (casos tristes)
  > motivo: Todos os 3 cenários Gherkin contemplam exclusivamente caminhos felizes; não há nenhum cenário de falha de conexão SSE, erro de parsing ou timeout.
  > sugestão: Adicionar cenários Gherkin para falha de streaming intermediário (ex.: desconexão SSE) e para respostas com JSON/chunks truncados.
- [ ] Q-006 | Completude | O documento define o comportamento do sistema quando um modelo não emite cadeia de raciocínio (reasoning ausente/nulo)
  > motivo: Não está especificado se modelos sem suporte a reasoning devem resultar em valor nulo, string vazia ou exceção nos payloads e colunas do banco.
  > sugestão: Adicionar regra de fallback explícita: "Quando o modelo não emitir reasoning_content, os campos correspondentes na API e banco de dados devem ser persistidos como NULL".

### Consistência

- [ ] Q-007 | Consistência | Os nomes das propriedades expostas na API (RF-04) coincidem com os nomes das colunas de banco (RF-03) ou possuem mapeamento unívoco documentado
  > motivo: Em RF-03 a coluna é definida como `reasoning_planejamento`, enquanto em RF-04 o campo de resposta é denominado apenas `reasoning`, gerando ambiguidade de nomenclatura entre API e banco.
  > sugestão: Padronizar o nome do campo nos payloads da API para manter simetria ou explicitar o mapeamento de serialização (ex.: `reasoning_planejamento` em `PlanResponse`).
- [ ] Q-008 | Consistência | O cenário Gherkin de entrega de webhook reflete fielmente todos os campos estipulados no requisito RF-05
  > motivo: RF-05 determina que o webhook deve incluir `reasoning_dossier` e `reasoning_auditoria`, mas o cenário Gherkin correspondente menciona apenas `dossier_final` e `reasoning_dossier`, omitindo `reasoning_auditoria`.
  > sugestão: Atualizar o passo "Então" do cenário do webhook para: "E o payload assinado contém dossier_final, reasoning_dossier e reasoning_auditoria".
- [X] Q-009 | Consistência | As entidades de dados citadas (tabelas pesquisa, pontos e conteudo_coletado) são coerentes com o modelo relacional existente do projeto

### Cobertura

- [ ] Q-010 | Cobertura | Todos os Requisitos Funcionais (RF-01 a RF-06) possuem ao menos um cenário de aceitação Gherkin dedicado
  > motivo: Os RF-01 (comportamento de tool_calls em stream), RF-04 (respostas de planejamento e auditoria na API) e RF-06 não possuem cenários de aceitação em Gherkin.
  > sugestão: Criar cenários de aceitação para o streaming de chamadas estruturadas/tool_calls e para as respostas de auditoria e planejamento.
- [X] Q-011 | Cobertura | A persistência dos metadados de reasoning cobre todas as etapas que geram deliberação analítica

### EdgeCases

- [ ] Q-012 | EdgeCases | O comportamento perante desconexões e timeouts durante a transmissão SSE está especificado
  > motivo: O documento não estabelece política de retentativa, timeout de leitura de stream ou tratamento para buffers interrompidos antes do `[DONE]`.
  > sugestão: Incluir requisito de tratamento de interrupção: definir se a operação faz retry exponencial ou levanta `StreamInterruptedError` com descarte do buffer parcial.
- [X] Q-013 | EdgeCases | O tratamento de marcadores de fim de transmissão (`data: [DONE]`) e variações de payloads delta entre provedores foi previsto
- [ ] Q-014 | EdgeCases | O limite de tamanho ou impacto em memória para cadeias de raciocínio extensas possui limites operacionais definidos
  > motivo: Não há estipulação de limite máximo de caracteres/tokens ou proteção contra esgotamento de memória em streams de reasoning muito longos.
  > sugestão: Definir um teto operacional razoável para acúmulo de reasoning por chamada (ex.: truncamento defensivo ou limite máximo de buffer).

### Jargão

- [X] Q-015 | Jargão | A terminologia técnica empregada é adequada ao contexto de integrações com LLMs
- [ ] Q-016 | Jargão | As siglas técnicas (ex.: SSE) são expandidas na primeira ocorrência para facilitar o entendimento de novos integrantes
  > motivo: A sigla "SSE" é usada em RF-01 sem expansão prévia (Server-Sent Events).
  > sugestão: Escrever "Server-Sent Events (SSE)" na primeira menção em RF-01.

### SoluçãoImplícita

- [X] Q-017 | SoluçãoImplícita | Os requisitos funcionais focam no comportamento esperado do sistema e nas propriedades de dados a serem preservadas
- [ ] Q-018 | SoluçãoImplícita | Os requisitos não-funcionais evitam prescrever código ou bibliotecas internas desnecessárias
  > motivo: O RNF-03 prescreve implementação específica de código Python (`"".join(...)`) e RNF-02 acopla o requisito à biblioteca `httpx.MockTransport`, misturando design de implementação com especificação de requisitos.
  > sugestão: Reformular RNF-03 para "O consumo de streams deve manter complexidade de memória O(N) e alocação eficiente de buffers" e RNF-02 para "A camada de transporte HTTP em testes unitários deve suportar streaming sem chamadas de rede externas".

### Princípios

- [X] Q-019 | Princípios | A arquitetura monolítica modular e a autonomia de cada endpoint do pipeline são respeitadas
- [X] Q-020 | Princípios | A separação de responsabilidades entre agentes e persistência auditável é mantida

## Itens reprovados, detalhe

### Q-003
> motivo: O texto de RF-06 ("aprimorar a rastreabilidade metodológica") é vago e abstrato, sem definir como o acesso ao reasoning pelo Auditor deve ser operacionalizado ou testado.
> sugestão: Especificar exatamente como o Auditor consome o reasoning (ex.: "O prompt do Auditor deve receber o campo reasoning_coleta das evidências para validar a pertinência do raciocínio das personas").

### Q-005
> motivo: Todos os 3 cenários Gherkin contemplam exclusivamente caminhos felizes; não há nenhum cenário de falha de conexão SSE, erro de parsing ou timeout.
> sugestão: Adicionar cenários Gherkin para falha de streaming intermediário (ex.: desconexão SSE) e para respostas com JSON/chunks truncados.

### Q-006
> motivo: Não está especificado se modelos sem suporte a reasoning devem resultar em valor nulo, string vazia ou exceção nos payloads e colunas do banco.
> sugestão: Adicionar regra de fallback explícita: "Quando o modelo não emitir reasoning_content, os campos correspondentes na API e banco de dados devem ser persistidos como NULL".

### Q-007
> motivo: Em RF-03 a coluna é definida como `reasoning_planejamento`, enquanto em RF-04 o campo de resposta é denominado apenas `reasoning`, gerando ambiguidade de nomenclatura entre API e banco.
> sugestão: Padronizar o nome do campo nos payloads da API para manter simetria ou explicitar o mapeamento de serialização (ex.: `reasoning_planejamento` em `PlanResponse`).

### Q-008
> motivo: RF-05 determina que o webhook deve incluir `reasoning_dossier` e `reasoning_auditoria`, mas o cenário Gherkin correspondente menciona apenas `dossier_final` e `reasoning_dossier`, omitindo `reasoning_auditoria`.
> sugestão: Atualizar o passo "Então" do cenário do webhook para: "E o payload assinado contém dossier_final, reasoning_dossier e reasoning_auditoria".

### Q-010
> motivo: Os RF-01 (comportamento de tool_calls em stream), RF-04 (respostas de planejamento e auditoria na API) e RF-06 não possuem cenários de aceitação em Gherkin.
> sugestão: Criar cenários de aceitação para o streaming de chamadas estruturadas/tool_calls e para as respostas de auditoria e planejamento.

### Q-012
> motivo: O documento não estabelece política de retentativa, timeout de leitura de stream ou tratamento para buffers interrompidos antes do `[DONE]`.
> sugestão: Incluir requisito de tratamento de interrupção: definir se a operação faz retry exponencial ou levanta `StreamInterruptedError` com descarte do buffer parcial.

### Q-014
> motivo: Não há estipulação de limite máximo de caracteres/tokens ou proteção contra esgotamento de memória em streams de reasoning muito longos.
> sugestão: Definir um teto operacional razoável para acúmulo de reasoning por chamada (ex.: truncamento defensivo ou limite máximo de buffer).

### Q-016
> motivo: A sigla "SSE" é usada em RF-01 sem expansão prévia (Server-Sent Events).
> sugestão: Escrever "Server-Sent Events (SSE)" na primeira menção em RF-01.

### Q-018
> motivo: O RNF-03 prescreve implementação específica de código Python (`"".join(...)`) e RNF-02 acopla o requisito à biblioteca `httpx.MockTransport`, misturando design de implementação com especificação de requisitos.
> sugestão: Reformular RNF-03 para "O consumo de streams deve manter complexidade de memória O(N) e alocação eficiente de buffers" e RNF-02 para "A camada de transporte HTTP em testes unitários deve suportar streaming sem chamadas de rede externas".

## Veredito

**Reprovado**

> Justificativa: Foram reprovados 10 de 20 itens avaliados, incluindo múltiplos itens com classificação CRITICAL:
> 1. Ausência completa de cenários de aceitação para casos negativos/falhas (Q-005).
> 2. Cobertura de cenários Gherkin insuficiente para metade dos requisitos funcionais (Q-010).
> 3. Contradições internas de nomenclatura e especificação de payload entre requisitos e cenários (Q-007 e Q-008).

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-22 | Auditoria gerada por `/reversa-quality` | reversa-quality |
