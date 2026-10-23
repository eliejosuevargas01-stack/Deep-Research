# Requisitos: Suporte a Streaming Universal e Captura de Reasoning para Auditoria

> Identificador: `003-streaming-reasoning-audit`
> Data de Início: `2026-10-22`
> Status: `requirements`
> Origem: Solicitação do usuário para streaming nativo em todos os modelos (`stream: true`) e coleta do `reasoning` dos modelos para auditoria e entrega ao cliente.

## 1. Visão Geral e Objetivo

Esta feature introduz streaming nativo obrigatório (`stream: true`) para todas as chamadas aos modelos de linguagem (`LLMClient`), cobrindo Planejador, Searcher (as 4 personas), Auditor e Redator Final.
Adicionalmente, captura de forma segregada a cadeia de pensamento (`reasoning` / `reasoning_content`) emitida pelos modelos analíticos (`step-5-preview`, `gemini-3.5-flash-lite`, etc.), persistindo-a em novas colunas no banco de dados SQLite permanente para fins de auditoria profunda e devolvendo-a nos payloads JSON de resposta e webhook de entrega final.

## 2. Requisitos Funcionais (RF)

- **RF-01 (Streaming Nativo Obrigatório):** Todas as inferências enviadas a roteadores ou provedores LLM (`/chat/completions`) devem operar com `stream: true`, inclusive chamadas de `tool_calls` e `generate_json`, processando chunks SSE incrementais (`delta.content`, `delta.reasoning_content`, `delta.tool_calls`) de ponta a ponta.
- **RF-02 (Captura e Segregação de Reasoning):** O `LLMClient` deve desacoplar e retornar tanto o `content` quanto o `reasoning_content` (ou `thinking`) gerado pelo modelo em todas as chamadas.
- **RF-03 (Persistência de Reasoning na Base de Dados):**
  - Tabela `pesquisa`: Adicionar coluna `reasoning_dossier TEXT` (raciocínio analítico gerado pelo Redator Final durante a elaboração do dossiê).
  - Tabela `pontos`: Adicionar coluna `reasoning_auditoria TEXT` (cadeia de raciocínio lógico gerada pelo Auditor durante a avaliação dos 12 critérios) e `reasoning_planejamento TEXT` (raciocínio da decomposição dos pontos).
  - Tabela `conteudo_coletado`: Adicionar coluna `reasoning_coleta TEXT` (raciocínios e decisões de busca gerados pelas 4 personas durante a fase de pesquisa).
- **RF-04 (Exposição de Reasoning nas Respostas da API):**
  - `PlanResponse` e `PlanAsyncResponse`: Devolver `reasoning` do planejamento.
  - `SearchResponse`: Devolver `reasoning` em cada persona coletada (`PersonaColetaItem`).
  - `AuditResponse`: Devolver `reasoning` do parecer do auditor em cada item avaliado.
  - `WriterResponse`: Devolver `reasoning_dossier` junto ao dossiê final.
- **RF-05 (Entrega de Reasoning no Webhook de Callback):**
  - O payload despachado para `CALLBACK_WEBHOOK_URL` no evento `research.completed` deve incluir o campo `reasoning_dossier` e `reasoning_auditoria`, permitindo auditoria externa total pelo cliente receptor.
- **RF-06 (Auditoria e Inspeção Baseada em Reasoning):** O módulo `Auditor` e as ferramentas de inspeção do sistema devem ter acesso ao reasoning gerado pelas etapas anteriores para aprimorar a rastreabilidade metodológica.

## 3. Requisitos Não-Funcionais (RNF)

- **RNF-01 (Resiliência do Streaming com Proxies e Roteadores):** A leitura via stream deve tratar sufixos `data: [DONE]`, linhas em branco e formatos delta de múltiplos provedores (OpenAI, DeepSeek/StepFun reasoning, Gemini thinking).
- **RNF-02 (Compatibilidade Retroativa de Testes):** Transportes mockados (`httpx.MockTransport`) devem continuar funcionando perfeitamente em modo de teste, serializando chunks em stream ou aceitando fallback limpo.
- **RNF-03 (Desempenho e Não Esgotamento de Memória):** Os acumuladores de chunks de stream devem utilizar listas de buffers de strings (`"".join(...)`) de forma eficiente.

## 4. Cenários de Aceitação (Gherkin)

```gherkin
Cenário: Captura de reasoning e conteúdo via streaming na redação final
  Dado um conjunto de evidências aprovadas para a pesquisa
  Quando o Redator Final processa a solicitação com stream=true
  Então o conteúdo gerado é estruturado em Markdown nas 4 seções
  E o reasoning_content emitido pelo modelo é capturado integralmente
  E o reasoning_dossier é salvo na tabela pesquisa
  E a resposta do endpoint /api/v1/writer inclui o campo reasoning_dossier

Cenário: Captura de reasoning na busca agêntica pelas personas
  Dado um ponto focal de investigação
  Quando as 4 personas executam suas queries em stream=true
  Então cada persona armazena suas deliberações e seu reasoning de busca
  E os dados são persistidos na tabela conteudo_coletado com reasoning_coleta

Cenário: Entrega de reasoning no webhook assinado de callback
  Dado que uma pesquisa assíncrona foi concluída pelo PipelineRunner
  Quando o evento research.completed é despachado para o webhook
  Então o payload assinado contém dossier_final e reasoning_dossier
```
