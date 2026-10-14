# Requirements: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`
> Data: 2026-10-13 (revisão consolidada pós-auditoria — Rodada 3)
> Pasta da feature: `_reversa_forward/002-investigacao-personas`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA
> Fonte de verdade: decisões do operador registradas nas sessões de 2026-10-12, 2026-10-13 (Q1-Q13) e 2026-10-14 (Q14-Q16).

---

## 1. Resumo executivo

O ciclo de pesquisa inicia com `POST /briefings`, que entrega o briefing inicial em rascunho (`draft`) e aguarda a decisão do operador. O operador dispõe de duas vias exclusivas: (a) acionar `POST /briefings/{research_id}/investigate` sobre o primeiro briefing válido ainda em rascunho, o que opera aprovação implícita e início de investigação na mesma operação, instanciando os pontos em `research_points` e disparando os workers em background; ou (b) enviar feedback textual único via `PATCH /briefings/{research_id}`, acionando obrigatoriamente nova busca SERP Jina formulada pela IA com tema original e feedback, gerando o briefing revisado (preservando pontos não afetados e ajustando ou acrescentando foco conforme novas evidências) e aprovando e iniciando a investigação automaticamente em background, sem endpoint `/approve`, sem segunda chamada a `/investigate` e sem confirmação intermediária. Iniciada a investigação, o sistema investiga cada ponto de pesquisa aprovado disparando concorrentemente quatro workers com personas cognitivas distintas: **historian**, **skeptic**, **pragmatist** e **futurist**. Cada worker executa tool calling com a ferramenta de busca Jina Search em memória volátil (RAM), persistindo seus resultados analíticos e URLs de forma imutável (append-only) em `research_step_results` para posterior auditoria (Feature 003) e redação (Feature 004).

---

## 2. Contexto a partir do legado

A Feature 002 ancora-se nos artefatos da extração reversa e adendos vigentes do módulo de briefing:

| Fonte | Trecho relevante | Confidência |
|---|---|---|
| `_reversa_sdd/prd.md#escopo` | Escopo do módulo de pesquisa, separação do briefing e fases autônomas | 🟢 |
| `_reversa_sdd/sdd/briefing.md#modelo` | Modelo de domínio do briefing, geração de pontos e aprovação | 🟢 |
| `_reversa_sdd/addenda/001-modulo-briefing.md#resumo` | Adendo de convergência da Feature 001: briefing em `app/briefing/`, ciclo `generating/draft/approved/failed` | 🟢 |
| `.reversa/principles.md#I` | Princípio I: Rastreabilidade Factual Estrita (Verbatim Citation) | 🟢 |
| `.reversa/principles.md#II` | Princípio II: Defesa de Privacidade e Isolamento de Prompts | 🟢 |
| `.reversa/principles.md#III` | Princípio III: Resiliência por Degradação Graciosa e Limites Rígidos | 🟢 |
| `.reversa/principles.md#IV` | Princípio IV: Concorrência Segura e Emenda da Feature 002 (gather concorrente irrestrito) | 🟢 |

*Nota sobre fontes:* Os documentos `_reversa_sdd/architecture.md` e `_reversa_sdd/domain.md` estão ausentes da raiz e nenhuma informação foi inferida a partir deles.

---

## 3. Personas e cenários de uso

### 3.1 Personas de usuário

| Persona | Objetivo | Cenário-chave |
|---|---|---|
| Operador de pesquisa (Admin) | Iniciar investigação via aprovação implícita no briefing inicial ou solicitar revisão única por feedback com início automático | Aciona `POST /briefings/{research_id}/investigate` sobre rascunho inicial válido para aprovar implicitamente e disparar a investigação, ou envia feedback único via `PATCH /briefings/{research_id}` que revisa pontos e inicia a investigação automaticamente |
| Consumidor de API / Pipeline | Integrar etapas de auditoria e síntese com resultados coletados | Lê resultados de `research_step_results` quando a pesquisa transita para `AUDIT` |

### 3.2 Papéis cognitivos dos workers (Personas)

| Persona cognitiva | Papel analítico | Foco de investigação |
|---|---|---|
| `historian` | Analista de precedentes históricos | Investiga antecedentes, evolução histórica, contextos passados e trajetórias que explicam o estado atual |
| `skeptic` | Crítico metódico e contra-argumentador | Busca contradições, riscos ocultos, falhas metodológicas, limites de validade e fontes discordantes |
| `pragmatist` | Avaliador prático e operacional | Analisa viabilidade técnica, custos, implementação concreta, restrições regulatórias e trade-offs operacionais |
| `futurist` | Projetista de cenários e tendências | Mapeia impactos emergentes, tendências tecnológicas, disrupções de mercado e cenários prospectivos |

### 3.3 Glossário de termos técnicos

- **UUID**: *Universally Unique Identifier* — Identificador universal de 128 bits gerado aleatoriamente (RFC 4122).
- **PK**: *Primary Key* — Chave primária que identifica unicamente o registro na tabela do banco de dados.
- **FK**: *Foreign Key* — Chave estrangeira que referencia a chave primária de outra tabela, garantindo integridade referencial.
- **LLM**: *Large Language Model* — Modelo de linguagem utilizado pelos workers para gerar síntese analítica.
- **Tool Calling**: Mecanismo no qual o modelo invoca funções estruturadas externas (neste caso, a ferramenta Jina Search).
- **Harness**: Camada de controle da aplicação que gerencia o loop de execução do worker, limites de busca e formatação de saída.
- **Backfill**: Povoamento retroativo de dados históricos para adaptar registros legados ao novo esquema unificado.
- **Hook de Startup**: Rotina assíncrona executada na inicialização do servidor FastAPI para detectar e reagendar tarefas incompletas.
- **RAM**: *Random Access Memory* — Memória volátil onde mensagens e raciocínio bruto residem exclusivamente durante a execução.
- **Append-Only**: Estratégia de armazenamento na qual registros são apenas inseridos, sem atualizações destrutivas, assegurando auditabilidade.
- **Verbatim Citation**: Citação textual literal do trecho original coletado, exigida pelo Princípio I.

---

## 4. Regras de negócio novas ou alteradas

1. **RN-01 Disparo da Investigação.** O endpoint `POST /briefings/{research_id}/investigate` exige autenticação de administrador (`require_admin`; ausência ou invalidade retorna HTTP 401/403). Se o `research_id` não existir em `research`, responde HTTP 404 Not Found. Sobre o primeiro briefing válido em `draft`, a chamada aprova implicitamente e inicia a investigação na mesma operação, sem exigir endpoint `/approve`. O status `draft` e a ausência prévia de registros em `research_points` não motivam HTTP 409. O sistema valida os pontos do briefing antes de criar os registros; aprovação, inserção dos pontos diretamente em `SCRAPER_IN_PROGRESS` e transição da pesquisa para `SCRAPER` ocorrem atomicamente. Briefing sem pontos, re-disparo ou operação concorrente recebem HTTP 409 Conflict sem iniciar nova investigação. A resposta é HTTP 202 com `{"research_id": "...", "status": "SCRAPER", "message": "Investigação iniciada em background"}`, e a execução é despachada em background via FastAPI `BackgroundTasks`. Após a revisão única por feedback, a investigação inicia automaticamente na própria operação do PATCH, sem segunda chamada a `/investigate`; nova chamada sobre investigação já iniciada recebe HTTP 409. 🟢
   - Tipo: alterada

2. **RN-02 Concorrência Concorrente Irrestrita.** Para N pontos (3 a 7), o serviço instancia N × 4 corrotinas executadas sob `asyncio.gather(..., return_exceptions=True)`. As chamadas não são enfileiradas pelo semáforo legado de 4 slots de `app/services/llm.py`, operando conforme a Emenda de Concorrência ao Princípio IV de `.reversa/principles.md`. 🟢
   - Tipo: alterada
   - Origem: Princípio IV

3. **RN-03 Parâmetros de Despacho dos Workers.** O orquestrador assíncrono repassa explicitamente para cada função worker a tupla `(research_id, step_id, step_title, persona)`. O worker carrega do banco apenas as chaves de API e configurações de modelo. 🟢
   - Tipo: nova

4. **RN-04 Tool Calling e Memória Volátil.** A execução com o LLM utiliza a API nativa de ferramentas do LiteLLM (`tools` padrão OpenAI). O histórico conversacional (`messages`) é retido unicamente em memória RAM pelo tempo de vida do worker e descartado ao final, sem persistência intermediária em banco de dados. 🟢
   - Tipo: nova
   - Origem: Princípio II

5. **RN-05 Ferramenta Jina Search.** A tool de busca realiza requisição HTTP POST para `https://s.jina.ai/` enviando JSON `{"q": query}` com cabeçalhos `Authorization: Bearer ***`, `Accept: application/json` e `X-Engine: direct`. Se as chaves `jina_proxy_url` e `jina_proxy_auth_key` estiverem configuradas em `app_settings`, a requisição é direcionada ao proxy respeitando estritamente o mesmo contrato e cabeçalhos. 🟢
   - Tipo: nova

6. **RN-06 Orçamento de Pesquisa.** Cada worker pode disparar no máximo 3 consultas de busca Jina por ponto. O modelo encerra voluntariamente o loop retornando o JSON de resultado quando julgar as fontes suficientes. Repetições técnicas de uma mesma busca motivadas por falhas de rede NÃO descontam do teto de 3 pesquisas. 🟢
   - Tipo: nova

7. **RN-07 Retries Técnicos e Timeouts.** Chamadas externas à Jina e ao LiteLLM executam até 3 tentativas totais (1 inicial + até 2 retries técnicos com backoff exponencial 2s/4s) em caso de erro transitório de rede ou HTTP 429/5xx. Se o cabeçalho `Retry-After` for fornecido, a espera respeita o valor indicado; caso contrário, aplica backoff exponencial de 2s e 4s. O timeout limite por chamada individual é de 90s para o LLM e 90s para a Jina. O timeout global máximo por execução completa de um worker é fixado em 600s. 🟢
   - Tipo: nova
   - Origem: Princípio III

8. **RN-08 Rastreabilidade Total de URLs Lidas.** O harness intercepta todas as URLs retornadas pela API da Jina durante as buscas realizadas pelo worker e as persiste no campo `read_urls`, independentemente de terem sido citadas pelo modelo. 🟢
   - Tipo: nova

9. **RN-09 Resiliência e Isolamento de Falhas.** A falha definitiva ou estouro de timeout de um worker não aborta nem interrompe as demais corrotinas concorrentes. 🟢
   - Tipo: nova
   - Origem: Princípio III

10. **RN-10 Seleção de Modelos por Persona.** O modelo utilizado por cada persona é extraído de `app_settings.models.<persona>` (`historian`, `skeptic`, `pragmatist`, `futurist`). Se o valor correspondente estiver ausente ou vazio, adota automaticamente como fallback o modelo configurado para o `scout`. 🟢
    - Tipo: nova

11. **RN-11 Retomada Pós-Reinício do Servidor.** Um hook no ciclo de inicialização do FastAPI inspeciona pesquisas em `SCRAPER` cujos pontos estejam em `SCRAPER_IN_PROGRESS` e reagenda exclusivamente os workers que ainda não possuem linha correspondente em `research_step_results`. 🟢
    - Tipo: nova

12. **RN-12 Isolamento Modular.** Toda a lógica da Feature 002 reside no pacote autônomo `app/investigation/` (schemas, prompts, tools, worker, storage, service, router). 🟢
    - Tipo: nova

13. **RN-13 Validação de Formato e Autocorreção de JSON.** O modelo deve entregar seu resultado analítico final no formato JSON `{"result": "...", "used_urls": [...]}` (`result` é string analítica não-vazia; `used_urls` é array JSON de strings). Caso o payload retornado seja sintaticamente inválido ou não obedeça às chaves exigidas, o harness executa até 3 correções dedicadas instruindo o modelo a formatar o JSON, sem consumir as tentativas de rede. Se após as 3 correções o JSON permanecer inválido, o worker encerra com falha definitiva (`success=False`), grava linha em `research_step_results` com status `FAILED`, `result="Invalid JSON response after 3 corrections"`, `used_urls=[]`, e incrementa `attempt_count` do ponto correspondente. 🟢
    - Tipo: nova

14. **RN-14 Prompts Base das Personas e Rastreabilidade Factual (Princípio I).** Os prompts das personas são derivados de `app/prompts/personas.json`, adicionando instrução de sistema que exige citação factual estrita (*verbatim*, trecho exato reproduzido da fonte original conforme o Princípio I) acompanhada das URLs correspondentes em `used_urls` e a entrega do JSON final estruturado. Conforme o Princípio I, links representam acessibilidade e apenas a citação literal comprova veracidade. A validação e auditoria profunda dessas citações ocorrem nas fases subsequentes (Feature 003). 🟢
    - Tipo: nova
    - Origem: Princípio I

### 4.1 Identificador único `research_id` e ajustes na Feature 001

- O `research_id` (UUID aleatório) é gerado ANTES da elaboração do briefing, no momento em que o tema do usuário é submetido. A linha em `research` é persistida com `id` igual ao `research_id` e com o tema fornecido.
- O briefing NÃO gera identificador próprio: adota o mesmo `research_id` (`briefings.id == research.id`). Todas as tabelas do pipeline compartilham esse identificador único.
- Os pontos de pesquisa só passam a existir na tabela `research_points` no momento da aprovação implícita (via `POST /briefings/{research_id}/investigate` sobre o primeiro briefing válido) ou automática (ao concluir a revisão única via `PATCH /briefings/{research_id}`); antes disso, residem unicamente no versionamento do briefing (`briefing_versions`).
- Na aprovação (implícita ou automática pós-revisão), os pontos aprovados são persistidos em `research_points` vinculados ao `research_id` com status `SCRAPER_IN_PROGRESS`, e a pesquisa passa de imediato para `SCRAPER`.
- Para solicitar novo rascunho com feedback único, o usuário faz referência sempre ao `research_id`.
- O mesmo `research_id` governa o disparo da investigação, as fases posteriores de auditoria e síntese, e todas as consultas de telemetria.
- Nome canônico público do campo em todas as APIs e schemas: `research_id`.

**Impacto e ajustes na Feature 001 (aprovado):**
- `POST /briefings` instancia primeiro o registro em `research` (`id` aleatório + tema) e utiliza esse mesmo UUID como identificador da linha em `briefings`. O tema tem tamanho de 3 a 300 caracteres após strip; se o usuário enviar tema com mais de 300 caracteres, a API rejeita com HTTP 422 Unprocessable Entity e mensagem de erro explícita sobre o limite de 300 (Q13). O briefing inicial é entregue em status `draft` (`PENDING_APPROVAL` em `research`) e aguarda a escolha do operador.
- Os títulos e descrições de pontos de briefing gerados pelo Scout devem ser texto não-vazio e NÃO possuem comprimento máximo fixo (Q11; regra anterior Q6 revogada). O sistema aceita e persiste o título integral. A mensagem de erro sanitizada em falha terminal mantém limite de 500 caracteres; a análise final de sucesso não possui teto de 500.
- Extinção do endpoint `/approve`: o endpoint `POST /briefings/{research_id}/approve` não deve existir no sistema e nenhum endpoint substituto é criado. A aprovação ocorre exclusivamente de forma implícita (ao chamar `POST /briefings/{research_id}/investigate` sobre o primeiro briefing em rascunho) ou automática (ao concluir a revisão única via `PATCH /briefings/{research_id}`). Ao aprovar, os pontos são salvos em `research_points` em `SCRAPER_IN_PROGRESS` e a pesquisa passa de imediato para `SCRAPER`.
- As tabelas `briefings` e `briefing_versions` continuam como histórico canônico auditável de versões do rascunho.
- **Quebra de contrato da Feature 001 aprovada:** as respostas públicas da API de briefing substituem a chave `id` por `research_id`. Consumidores externos e documentação (`docs/api/briefing-scout.md`) são ajustados.
- Briefing aprovado não retorna para rascunho: chamadas a `POST /briefings/{research_id}/reopen` em briefing com status `approved` ou pesquisa em `SCRAPER` retornam HTTP 409 Conflict. Os testes da 001 que exerciam reabertura pós-aprovação são readequados.
- **Edição e revisão única por feedback (`PATCH /briefings/{research_id}`):** o PATCH antigo por lista manual de pontos é extinto. O endpoint passa a aceitar corpo JSON `{"note": "texto do feedback"}` (mínimo 3 e máximo 4000 caracteres, correspondente ao padrão do frontend). O usuário só pode editar, refazer ou dar feedback uma única vez para a mesma pesquisa; o segundo briefing representa pontos ajustados e foco adicional sobre o mesmo tema e `research_id`, não outro POST independente. O PATCH aciona obrigatoriamente nova pesquisa SERP Jina formulada pela IA a partir do tema original e do feedback (não consulta apenas o tema, não utiliza Reader nem scraping de corpo nem reutilização de buscas anteriores para substituir a nova busca). O Scout executa exatamente uma nova consulta SERP Jina (retries técnicos da mesma consulta por erro transitório de rede ou HTTP 429/5xx não contam como novas consultas). Com base nos novos resultados, a IA revisa os pontos preservando os pontos não afetados e ajustando ou acrescentando foco conforme o feedback e as novas evidências. Ao gerar a versão revisada em `briefing_versions`, o sistema aprova e inicia a investigação automaticamente em background na mesma operação, persistindo os pontos em `research_points` (`SCRAPER_IN_PROGRESS`) e transitando a pesquisa para `SCRAPER`, sem segunda chamada a `/investigate` e sem confirmação intermediária do usuário. A resposta do PATCH é síncrona HTTP 200 contendo o briefing revisado. Qualquer tentativa posterior de nova revisão é bloqueada com HTTP 409 Conflict. Se a busca SERP Jina ou a geração do briefing revisado falhar de forma terminal após esgotar retries: a API responde HTTP 500 para erro interno de configuração, HTTP 502 para geração de modelo indisponível ou HTTP 503 para busca Jina indisponível (Q12); a pesquisa transita para `FAILED`, o briefing fica com status `failed`, nenhuma investigação é iniciada, e nova tentativa exige submeter novo briefing via `POST /briefings`.
- A suíte de testes da Feature 001 é atualizada para esse novo contrato (`research_id`, ausência de `/approve`, aprovação implícita no `/investigate`, revisão única no PATCH com nova busca SERP Jina e início automático da investigação, e bloqueio 409 para segundas revisões) mantendo 100% de aprovação.

### 4.2 Modelo de dados

#### 4.2.1 Entidade `research` (pesquisa)
Status permitidos (`research.status`): `PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`.

- `PENDING`: reservado exclusivamente para futura fila global de pesquisas simultâneas (sem limite nesta feature).
- `BRIEFING`: enquanto o scout gera o rascunho inicial ou processa a revisão única após feedback.
- `PENDING_APPROVAL`: rascunho inicial gerado pelo Scout aguardando escolha do operador (disparo direto com aprovação implícita via `POST /briefings/{research_id}/investigate` ou revisão única com feedback via `PATCH /briefings/{research_id}`). Após a revisão única por feedback, o sistema não retorna a `PENDING_APPROVAL`, transitando diretamente para `SCRAPER` com disparo automático da investigação.
- `SCRAPER`: briefing aprovado (implicitamente via `POST /briefings/{research_id}/investigate` ou automaticamente após revisão única por `PATCH /briefings/{research_id}`), com investigação ativa e em andamento pelos workers concorrentes.
- `AUDIT`: todos os workers de todos os pontos concluíram a investigação.
- `WRITE`: reservado para a fase de redação final do relatório (Feature 004).
- `DONE`: pesquisa concluída com relatório final publicado.
- `FAILED`: falha irremediável na geração do briefing inicial, falha terminal no PATCH por feedback (busca SERP Jina ou geração), ou esgotamento em falha de 100% dos pontos da investigação.

Migração e backfill do enum legado de `research.status`:

| Status Legado | Novo Status Unificado | Justificativa |
|---|---|---|
| `scouting`, `revising` | `BRIEFING` | Fase de concepção ou revisão de briefing |
| `pending_approval` | `PENDING_APPROVAL` | Aguardando ação do usuário |
| `approved` | `SCRAPER` | Briefing aprovado; pronto para workers |
| `in_progress` | `SCRAPER` | Investigação ativa |
| `completed`, `completed_but_callback_failed` | `DONE` | Conclusão definitiva |
| `blocked`, `failed`, `interrupted` | `FAILED` | Estado de erro definitivo |

Backfill de briefings legados sem vínculo: a migração 0007 insere registros correspondentes na tabela `research` para briefings órfãos (`generating` -> `BRIEFING`, `draft` -> `PENDING_APPROVAL`, `approved` -> `SCRAPER` com cópia dos pontos para `research_points` em `SCRAPER_PENDING`, `failed` -> `FAILED`).

#### 4.2.2 Entidade `research_points` (pontos de pesquisa)
- Registros existem apenas a partir da aprovação do briefing.
- Status permitidos do ponto: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`, `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`. O status legado `SEARCH_SUCCESS` é expurgado do enum; legados existentes migram para `AUDIT_PENDING`.
- `title`: `sa.Text` (Q11: sem limite de 500 caracteres; a migração 007 deve ampliar de `String(500)` para `sa.Text`).
- `attempt_count`: contador inteiro atômico de falhas definitivas acumuladas de workers associados àquele ponto (inicia em 0 na criação do ponto pós-aprovação; incrementa atomicamente em +1 para cada worker que esgotar retries ou falhar definitivamente). Na retomada pós-reinício, o sistema reinsere apenas workers sem linha gravada em `research_step_results`, garantindo idempotência sem duplicar incrementos.

#### 4.2.3 Entidade `research_step_results` (resultados analíticos da investigação)
Tabela append-only para auditoria e rastreabilidade total.

| Coluna | Tipo SQLAlchemy / DB | Origem | Descrição |
|---|---|---|---|
| `id` | `sa.Uuid` (PK) | banco | UUID primário do resultado |
| `research_id` | `sa.Uuid` (FK `research.id`, index=True) | código | Identificador universal da pesquisa |
| `step_id` | `sa.Uuid` (FK `research_points.id`, index=True) | código | Identificador do ponto correspondente |
| `step_title` | `sa.Text` | código | Enunciado textual do ponto investigado (sem teto de 500 caracteres; cópia de research_points.title, ampliado para sa.Text na migração 007 conforme Q11) |
| `result` | `sa.Text` | modelo / erro | Texto analítico em caso de sucesso; mensagem sanitizada (máx 500 chars) em falha |
| `used_urls` | `sa.JSON` | modelo | Array JSON com URLs expressamente aproveitadas pelo modelo |
| `read_urls` | `sa.JSON` | harness | Array JSON com a totalidade das URLs retornadas pelo provedor Jina |
| `worker` | `sa.String(32)` | código | Persona designada: `historian`, `skeptic`, `pragmatist`, `futurist` |
| `status` | `sa.String(32)` | código | Status do resultado: `AUDIT_PENDING`, `APPROVED`, `REJECTED`, `FAILED` |
| `created_at` | `sa.DateTime(timezone=True)` | banco | Timestamp UTC de inserção |

### 4.3 Máquina de estados consolidada

| Evento de Ciclo de Vida | `research.status` | `research_points.status` | Ação nos Resultados |
|---|---|---|---|
| `POST /briefings` (criação e geração do Scout) | `BRIEFING` | (não existem) | Nenhuma |
| Scout conclui rascunho inicial com sucesso | `PENDING_APPROVAL` | (não existem) | Briefing inicial em `draft` aguardando escolha do operador |
| `POST /briefings/{research_id}/investigate` sobre rascunho inicial | `SCRAPER` | Inseridos em `SCRAPER_IN_PROGRESS` | Aprovação implícita: inicia investigação e despacha N × 4 workers |
| `PATCH /briefings/{research_id}` por feedback único | `BRIEFING` -> `SCRAPER` | Inseridos em `SCRAPER_IN_PROGRESS` | Nova busca SERP Jina, gera briefing revisado, aprova e inicia investigação automaticamente |
| Tentativa de 2ª revisão via `PATCH /briefings/{research_id}` | Inalterado | Inalterado | Rejeição com HTTP 409 Conflict |
| Falha terminal do Scout no POST ou no PATCH de feedback | `FAILED` | (não existem) | Briefing transita para `failed` sem iniciar investigação |
| Worker individual conclui com sucesso | `SCRAPER` | Mantém `SCRAPER_IN_PROGRESS` | Linha salva com `AUDIT_PENDING` |
| Worker individual esgota retries em falha | `SCRAPER` | Incrementa `attempt_count` | Linha salva com `FAILED` e erro sanitizado |
| Ponto com >= 1 worker concluído com sucesso | `SCRAPER` | Transita para `AUDIT_PENDING` | Nenhuma ação adicional |
| Ponto com todos os 4 workers falhos | `SCRAPER` | Transita para `SCRAPER_FAILED` | Nenhuma ação adicional |
| Todos os pontos finalizam e >= 1 teve sucesso | `AUDIT` | Preservam status final | Pesquisa avança para auditoria |
| Todos os pontos finalizam e 100% falharam | `FAILED` | Todos em `SCRAPER_FAILED` | Pesquisa encerrada em falha total |

### 4.4 Restrições técnicas aprovadas pelo operador

As opções arquiteturais e ferramentas tecnológicas abaixo foram formalmente aprovadas como restrições de projeto pelo operador, distinguindo-se das regras de comportamento puro:
- **Framework Web**: FastAPI (com suporte nativo a `BackgroundTasks` para disparo assíncrono).
- **Provedor e SDK de LLM**: LiteLLM (chamada assíncrona `acompletion` com formato nativo de tool calling OpenAI).
- **Mecanismo de Concorrência**: `asyncio.gather` concorrente irrestrito (autorizado formalmente pela Emenda da Feature 002 ao Princípio IV).
- **ORM e Persistência**: SQLAlchemy assíncrono com migrações gerenciadas via Alembic.
- **Ferramenta de Busca Web**: API Jina Search (direta via POST `https://s.jina.ai/` ou proxy configurado).

---

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|---|---|---|---|---|
| RF-01 | Gerar `research_id` previamente e registrar linha em `research` antes do briefing, vinculando o mesmo UUID a `briefings.id`; validar tema entre 3 e 300 caracteres, rejeitando acima de 300 com HTTP 422 e erro explícito (Q13) | Must | Tema 3–300 gera linha `research` e `briefings` com mesmo UUID; tema >300 recebe HTTP 422 com mensagem explícita do limite 300 antes de qualquer I/O | 🟢 |
| RF-02 | Extinguir endpoint `/approve` e instanciar pontos em `research_points` no momento da aprovação implícita (`/investigate`) ou automática pós-revisão (PATCH), mudando pesquisa para `SCRAPER` e aceitando títulos gerados pelo Scout sem teto de 500 caracteres (Q11) | Must | `/approve` não existe; pontos persistem em `research_points` vinculados ao `research_id` com status inicial `SCRAPER_IN_PROGRESS`; títulos acima de 500 caracteres são gravados integralmente em coluna Text | 🟢 |
| RF-03 | Expor `POST /briefings/{research_id}/investigate` assíncrono (HTTP 202) executando aprovação implícita e início da investigação na mesma operação sobre primeiro briefing válido em draft (sem exigir /approve e sem 409 por draft), bloqueando re-disparos e concorrência com HTTP 409 | Must | Responde HTTP 202 com status SCRAPER sobre draft válido; pontos persistem e iniciam em SCRAPER_IN_PROGRESS; re-disparo ou concorrência retorna HTTP 409 Conflict | 🟢 |
| RF-04 | Despachar N × 4 workers concorrentes sob `asyncio.gather`, repassando a cada um `(research_id, step_id, step_title, persona)` | Must | Para N pontos (3 a 7), despacha exatamente N × 4 corrotinas com a tupla completa de argumentos | 🟢 |
| RF-05 | Executar loop de tool calling LiteLLM com busca Jina, teto estrito de 3 buscas e parada voluntária | Must | Worker realiza até 3 buscas Jina por ponto; para voluntariamente quando dados bastam; 4ª chamada é bloqueada pelo harness | 🟢 |
| RF-06 | Integrar busca Jina direta ou via proxy sob contrato unificado POST `{"q": query}` com timeout de 90s | Must | Executa POST na API direta ou proxy configurado com timeout 90s; payloads e cabeçalhos preservados | 🟢 |
| RF-07 | Interceptar e salvar a integridade das URLs retornadas pelo provedor em `read_urls` | Must | Harness captura 100% das URLs retornadas no payload Jina e grava em `read_urls` no banco | 🟢 |
| RF-08 | Aplicar até 3 tentativas totais (1 chamada inicial + até 2 retries técnicos com suporte a `Retry-After` e backoff 2s/4s) e até 3 chamadas de reparo de JSON | Must | Erros transitórios de rede/429/5xx recebem até 2 retries; formato JSON inválido recebe até 3 correções dedicadas separadas | 🟢 |
| RF-09 | Persistir linha append-only em `research_step_results` para cada worker finalizado (`AUDIT_PENDING` ou `FAILED`) | Must | Cada worker finalizado insere exatamente uma linha com persona, resultado analítico ou erro sanitizado e URLs | 🟢 |
| RF-10 | Atualizar o status dos pontos (`AUDIT_PENDING` ou `SCRAPER_FAILED`) e a pesquisa (`AUDIT` ou `FAILED` se 100% falharem) ao término do gather | Must | Pontos com >=1 sucesso passam a AUDIT_PENDING e pesquisa a AUDIT; se 100% falharem, pontos ficam SCRAPER_FAILED e pesquisa FAILED | 🟢 |
| RF-11 | Fornecer migração Alembic 0007 criando `research_step_results`, unificando enums de status, removendo `SEARCH_SUCCESS` e executando backfill de briefings legados | Must | Tabela criada com tipos portáteis; SEARCH_SUCCESS migra para AUDIT_PENDING; briefings órfãos ganham linha em research | 🟢 |
| RF-12 | Readequar endpoints da 001: adotar `research_id`, bloquear `POST /briefings/{research_id}/reopen` em aprovado (HTTP 409) e implementar revisão única via `PATCH /briefings/{research_id}` por feedback `{"note"}` com nova busca SERP Jina por IA (tema + feedback), aprovação e início automático da investigação em background, bloqueando 2ª revisão com HTTP 409 e discriminando falhas em 500/502/503 (Q12) | Must | Reopen de aprovado retorna 409; PATCH executa nova busca SERP Jina por IA, revisa pontos, aprova e inicia investigação automaticamente; 2ª revisão retorna 409; falha terminal retorna 500, 502 ou 503 | 🟢 |
| RF-13 | Reatar execuções de workers incompletos no startup do servidor | Must | Hook de startup do FastAPI detecta pontos em SCRAPER_IN_PROGRESS e reagenda apenas personas sem linha gravada | 🟢 |

---

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|---|---|---|---|
| Segurança | Nenhuma chave de API, token Bearer, URL com credenciais ou stack trace é exposto em logs ou gravado no banco; prompts de sistema e raciocínio bruto (*chain-of-thought*) residem estritamente em RAM; `result` grava texto analítico ou erro sanitizado de até 500 chars | Princípio II: Defesa de Privacidade e Isolamento de Prompts | 🟢 |
| Desempenho | A orquestração assíncrona de até 28 workers simultâneos não bloqueia o event loop principal da aplicação | Execução assíncrona nativa via FastAPI / asyncio | 🟢 |
| Auditabilidade | Todos os resultados e URLs pesquisadas são preservados de maneira imutável (append-only) para consumo da Feature 003 (Auditoria) | Princípio I: Rastreabilidade Factual Estrita | 🟢 |
| Conformidade | Operação alinhada ao Princípio IV de concorrência com emenda específica de concorrência irrestrita registrada em `.reversa/principles.md` | Emenda da Feature 002 ao Princípio IV | 🟢 |

---

## 7. Critérios de aceitação (Gherkin)

```gherkin
Cenário: Criação de pesquisa e briefing vinculados por research_id (RF-01)
  Dado um operador submetendo tema de pesquisa válido com 50 caracteres
  Quando o operador envia POST /briefings
  Então o sistema persiste a linha em research com UUID aleatório gerado antes do briefing
  E persiste o briefing com o mesmo research_id em briefings.id
  E a API responde HTTP 201 com {"research_id": "...", "status": "draft"}

Cenário: Rejeição de tema excedendo 300 caracteres com HTTP 422 explícito (RF-01, Q13)
  Dado um operador submetendo tema de pesquisa com 301 caracteres após strip
  Quando a requisição POST /briefings é processada
  Então a API rejeita com código HTTP 422 Unprocessable Entity
  E devolve mensagem de erro explícita indicando que o tema deve ter entre 3 e 300 caracteres
  E nenhuma chamada externa de busca ou modelo é realizada

Cenário: Aprovação implícita e instanciação de pontos no disparo direto (RF-02, RF-03)
  Dado um primeiro briefing válido em status draft com 5 pontos
  Quando o operador envia POST /briefings/{research_id}/investigate autenticado como admin
  Então a API responde HTTP 202 com {"research_id": "...", "status": "SCRAPER"}
  E os 5 pontos são persistidos na tabela research_points vinculados ao research_id com status SCRAPER_IN_PROGRESS
  E a pesquisa transita atomicamente para status SCRAPER
  E 20 workers assíncronos são despachados concorrentemente sem exigir endpoint /approve

Cenário: Título longo gerado pelo Scout aceito e persistido sem limite (RF-02, Q11)
  Dado um rascunho de briefing gerado pelo Scout contendo um ponto com título de 520 caracteres
  Quando a investigação é disparada com aprovação implícita ou automática pós-revisão
  Então o sistema aceita o ponto sem aplicar teto de 500 caracteres
  E persiste o título integralmente na coluna Text de research_points

Cenário: Disparo bem-sucedido da investigação sobre briefing draft (RF-03, RF-04)
  Dado uma pesquisa com primeiro briefing válido em status draft
  E pontos definidos no versionamento do briefing
  Quando o cliente envia POST /briefings/{research_id}/investigate autenticado como admin
  Então a chamada não retorna código HTTP 409 motivado pelo status draft
  E a API responde HTTP 202 com {"research_id": "...", "status": "SCRAPER"}
  E os pontos passam a constar em research_points com status SCRAPER_IN_PROGRESS
  E os workers assíncronos de cada ponto são despachados concorrentemente

Cenário: Re-disparo rejeitado por conflito (RF-03)
  Dado uma pesquisa cujos pontos já se encontram em SCRAPER_IN_PROGRESS
  Quando o cliente envia POST /briefings/{research_id}/investigate
  Então a API rejeita com HTTP 409 Conflict

Cenário: Parada voluntária antecipada do worker (RF-05)
  Dado um worker investigando um ponto com persona skeptic
  Quando o modelo atinge síntese suficiente após 1 consulta à ferramenta de busca
  Então o modelo não emite nova tool call
  E encerra o loop entregando o JSON final
  E o resultado é registrado em research_step_results com status AUDIT_PENDING

Cenário: Bloqueio no teto de 3 pesquisas (RF-05)
  Dado um worker que já executou 3 buscas com sucesso
  Quando o modelo emite uma 4ª tool call de pesquisa
  Então o harness recusa a execução da ferramenta e exige a entrega do JSON final

Cenário: Repetição técnica de busca não consome cota (RF-05, RF-08)
  Dado um worker executando sua primeira pesquisa
  Quando a chamada à Jina falha por timeout de rede e obtém sucesso no retry
  Então o consumo de cota contabilizado perante o modelo permanece em 1 de 3 pesquisas

Cenário: Execução de busca Jina via proxy configurado (RF-06)
  Dado que jina_proxy_url e jina_proxy_auth_key estão configurados em app_settings
  Quando um worker dispara consulta de busca
  Então a requisição é direcionada ao proxy configurado mantendo o payload {"q": query} e headers de autenticação

Cenário: Interceptação e separação de URLs lidas e aproveitadas (RF-07)
  Dado uma consulta Jina que retornou 8 fontes externas no corpo da resposta
  E o modelo citou 3 fontes na chave used_urls do seu resultado final
  Quando o resultado é persistido
  Então a coluna read_urls registra as 8 URLs retornadas
  E a coluna used_urls registra exatamente as 3 URLs citadas

Cenário: Resiliência em falha individual de worker (RF-08, RF-09)
  Dado um lote de 20 workers em execução
  Quando 1 worker atinge o timeout global de 600s ou esgota as 3 tentativas externas
  Então esse worker grava linha em research_step_results com status FAILED e erro sanitizado
  E o contador attempt_count do respectivo ponto é incrementado em 1
  E os demais 19 workers prosseguem sua execução sem interrupção

Cenário: Conclusão bem-sucedida da investigação global (RF-10)
  Dado uma pesquisa com 5 pontos em investigação
  Quando todos os 20 workers concluem e pelo menos 1 ponto obteve sucesso analítico
  Então os pontos com >= 1 sucesso transitam para AUDIT_PENDING
  E a pesquisa transita para o status AUDIT

Cenário: Falha global de 100% dos pontos investigados (RF-10)
  Dado uma pesquisa onde todos os workers de todos os pontos falharam definitivamente
  Quando o asyncio.gather encerra
  Então todos os pontos ficam em status SCRAPER_FAILED
  E a pesquisa transita atomicamente para o status FAILED

Cenário: Migração Alembic 0007 e backfill de briefings legados (RF-11)
  Dado um banco de dados com briefings legados da Feature 001 sem registro em research
  Quando a migração 0007 é executada
  Então registros correspondentes são criados em research e research_points
  E pontos legados em status SEARCH_SUCCESS são migrados para AUDIT_PENDING

Cenário: Reabertura pós-aprovação rejeitada (RF-12)
  Dado um briefing que já atingiu o status approved ou uma pesquisa em SCRAPER
  Quando é feita requisição POST /briefings/{research_id}/reopen
  Então a API responde HTTP 409 Conflict com mensagem explicativa

Cenário: Edição de briefing por feedback textual único (RF-12)
  Dado um briefing em status draft aguardando escolha do operador
  Quando o usuário envia PATCH /briefings/{research_id} com {"note": "Aprofundar riscos regulatórios"}
  Então o Scout executa exatamente uma nova consulta de busca SERP Jina formulada pela IA com o tema original e o feedback
  E os pontos não afetados são preservados e os demais ajustados ou acrescidos de foco conforme feedback e novas evidências
  E a nova versão é persistida em briefing_versions
  E o sistema aprova e inicia a investigação automaticamente em background na mesma operação do PATCH
  E a pesquisa transita para SCRAPER com pontos em SCRAPER_IN_PROGRESS sem segunda chamada a /investigate
  E a API responde síncrona HTTP 200 com a versão revisada

Cenário: Segunda revisão por feedback bloqueada (RF-12)
  Dado uma pesquisa cuja revisão única por feedback já foi concluída e a investigação iniciada
  Quando o usuário envia novamente PATCH /briefings/{research_id} com qualquer feedback
  Então a API responde HTTP 409 Conflict sem nova busca Jina e sem alterar a pesquisa

Cenário: Falha do Scout durante PATCH de feedback (RF-12, Q12)
  Dado um briefing em status draft
  Quando a busca SERP Jina ou a geração do briefing revisado falha de forma terminal após esgotar retries
  Então a API responde com código HTTP 500 (configuração), HTTP 502 (modelo indisponível) ou HTTP 503 (busca Jina indisponível) conforme a causa
  E a pesquisa transita para status FAILED
  E o briefing transita para status failed
  E nenhuma investigação é iniciada

Cenário: Retomada automática após reinicialização do servidor (RF-13)
  Dado que o servidor foi reiniciado enquanto uma pesquisa tinha pontos em SCRAPER_IN_PROGRESS
  Quando a aplicação executa o hook de startup do FastAPI
  Então o sistema detecta os pontos incompletos
  E reinsere em background apenas as personas que ainda não possuem registro em research_step_results

Cenário: Disparo rejeitado quando pesquisa não existe (RF-01, RF-03)
  Quando o cliente envia POST /briefings/{research_id}/investigate com um UUID inexistente autenticado como admin
  Então a API rejeita com HTTP 404 Not Found e mensagem "Pesquisa não encontrada"

Cenário: Disparo rejeitado por falta de autenticação administrativa (RF-03)
  Quando o cliente envia POST /briefings/{research_id}/investigate sem credencial de administrador válida
  Então a API rejeita com HTTP 401 Unauthorized ou HTTP 403 Forbidden

Cenário: Disparo rejeitado quando pesquisa não possui pontos aprovados (RF-03)
  Dado uma pesquisa em status SCRAPER sem nenhum ponto associado
  Quando o cliente envia POST /briefings/{research_id}/investigate autenticado como admin
  Então a API rejeita com HTTP 409 Conflict

Cenário: Exaustão de correções de JSON no worker (RF-08, RF-09)
  Dado um worker executando loop de persona
  Quando o modelo retorna JSON inválido por 3 correções consecutivas
  Então o worker encerra com status FAILED
  E grava em research_step_results com result "Invalid JSON response after 3 corrections" e used_urls vazia
  E o attempt_count do ponto é incrementado em 1
```

---

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|---|---|---|
| RF-01 | Must | Essencial: criação prévia do `research_id` vinculando pesquisa e briefing e validação de tema 3–300 |
| RF-02 | Must | Essencial: extinção do `/approve`, instanciação de pontos em `research_points` na aprovação implícita ou automática pós-revisão, com títulos sem teto (Text) |
| RF-03 | Must | Essencial: endpoint seguro `/investigate` com aprovação implícita sobre draft (HTTP 202 assíncrono), sem 409 por draft, e bloqueio 409 de re-disparos/concorrência |
| RF-04 | Must | Essencial: paralelismo concorrente dos 4 workers por ponto via `asyncio.gather` irrestrito |
| RF-05 | Must | Essencial: loop de tool calling Jina Search com teto de 3 buscas e parada voluntária |
| RF-06 | Must | Essencial: suporte à ferramenta Jina direta ou via proxy configurado |
| RF-07 | Must | Essencial: rastreabilidade total de URLs lidas pelo harness em `read_urls` |
| RF-08 | Must | Essencial: tolerância a falhas transitórias (retries 2s/4s) e autocorreção de JSON (até 3 tentativas) |
| RF-09 | Must | Essencial: persistência imutável append-only dos resultados das personas |
| RF-10 | Must | Essencial: transição de estado da pesquisa e dos pontos ao término da investigação |
| RF-11 | Must | Essencial: migração de banco 0007 unificando enums e executando backfill histórico |
| RF-12 | Must | Essencial: quebra de contrato controlada (adotar `research_id`, bloquear reopen 409 e PATCH de revisão única com nova busca SERP Jina e início automático) |
| RF-13 | Must | Essencial: resiliência a crashes do servidor com retomada idempotente no startup |
| RNF de Segurança | Must | Proteção de credenciais, isolamento rigoroso de prompts/CoT em RAM e sanitização de erros |
| RNF de Desempenho | Should | Execução assíncrona não bloqueante de até 28 workers simultâneos |
| RNF de Auditabilidade | Must | Preservação append-only de evidências para o pipeline de auditoria posterior |
| RNF de Conformidade | Must | Alinhamento obrigatório à Emenda de Concorrência ao Princípio IV |

---

## 9. Esclarecimentos

### Sessão 2026-10-13 (Rodada 1)
- **Q1 (Agendamento legado):** Ao aprovar briefing pelo endpoint legado `POST /api/research/{research_id}/briefing/approve` ou na revisão automática, o pipeline legado (`schedule(run_research)`) deve ser desativado. A pesquisa permanece em `SCRAPER` aguardando disparo exclusivo por `POST /briefings/{research_id}/investigate`. **PARCIALMENTE SUPERADA em 2026-10-14:** O endpoint `/approve` deve ser extinto conforme decisão de 2026-10-14. A revisão por feedback deve aprovar e iniciar a investigação automaticamente em background, sem aguardar nova chamada a `/investigate`. Apenas a desativação do agendamento legado `schedule(run_research)` permanece válida. Estas alterações de contrato ainda não estão implementadas nem validadas em produção.
- **Q2 (Falhas herdadas de teste):** Todas as 9 falhas herdadas do baseline `8bfd529` (5 em `tests/test_backend.py` e 4 em `tests/integration`/`tests/unit` por ausência de `pytest-asyncio`), além de 1 teste sensível a DNS/ordem, devem ser corrigidas dentro do escopo da Feature 002 antes do aceite final.
- **Q3 (Contagem de tentativas):** Limite estrito de 3 tentativas totais por chamada externa (1 chamada inicial + até 2 retries técnicos com backoff exponencial 2s/4s). RF-08 e RN-07 unificados nessa regra.
- **Q4 (Limite de `step_title`):** A coluna `step_title` é persistida como `sa.String(500)` para alinhamento estrito ao banco de dados e à entidade upstream `research_points.title`. **SUPERADA em Rodada 3 (Q11):** títulos de pontos gerados pelo Scout NÃO possuem teto de 500; a migração da 007 deve ampliar `research_points.title` e `research_step_results.step_title` para `sa.Text`.
- **Q5 (Casos de borda em `/investigate`):** O endpoint `POST /briefings/{research_id}/investigate` retorna formalmente: HTTP 404 quando o `research_id` não existe; HTTP 401/403 quando não autenticado como administrador; e HTTP 409 Conflict quando a pesquisa não possui pontos ou já possui pontos em execução/finalizados. **PARCIALMENTE SUPERADA em 2026-10-14:** Primeiro briefing válido em `draft` não retorna mais HTTP 409; acionar `/investigate` sobre ele implica aprovação implícita e início imediato da investigação. O bloqueio 409 restringe-se a re-disparos, pesquisas sem pontos ou operações concorrentes.

### Sessão 2026-10-13 (Rodada 2)
- **Q6 (L-01 Comprimento do título):** Títulos de pontos de briefing com mais de 500 caracteres são rejeitados na validação de entrada com HTTP 422 Unprocessable Entity. **SUPERADA em Rodada 3 (Q11):** títulos de pontos gerados pelo Scout NÃO têm teto de 500; a restrição se aplica apenas ao campo `theme` do body de criação (3–300, Q13), não aos títulos de pontos.
- **Q7 (L-02 Exaustão de reparos JSON):** Se o modelo não entregar JSON válido após as 3 correções dedicadas, o worker encerra com `success=False`, grava linha em `research_step_results` com status `FAILED`, `result="Invalid JSON response after 3 corrections"`, `used_urls=[]`, e incrementa `attempt_count`.
- **Q8 (L-03 Ciclo de vida de `attempt_count`):** `attempt_count` inicia em 0 na persistência pós-aprovação e incrementa atomicamente em +1 para cada falha definitiva de worker. Na retomada, o sistema despacha apenas personas sem linha gravada no banco, garantindo idempotência.
- **Q9 (L-04 Isolamento de prompts e chain-of-thought):** Prompts de sistema e raciocínio bruto (*chain-of-thought*) residem estritamente em RAM e são proibidos em banco, logs públicos e respostas de API. A coluna `result` armazena exclusivamente a síntese analítica final ou o erro sanitizado.
- **Q10 (L-05 Cenários Gherkin):** Formalizados no Gherkin os cenários para HTTP 404 (pesquisa inexistente), HTTP 401/403 (não admin), HTTP 409 (pesquisa sem pontos) e exaustão de reparos de JSON. **PARCIALMENTE SUPERADA em 2026-10-14:** Cenários Gherkin foram atualizados para refletir aprovação implícita no `/investigate` direto sobre draft (sem 409 por draft), início automático pós-revisão no PATCH e remoção completa de cenários de `/approve`.

### Sessão 2026-10-13 (Rodada 3)
- **Q11 (Título gerado pelo Scout):** Se o Scout gerar um ponto do briefing com título maior que 500 caracteres, NÃO limitar — o sistema deve aceitar e persistir o título inteiro. Títulos e descrições de pontos devem permanecer texto não-vazio. A mensagem de erro de falha sanitizada mantém limite de 500 caracteres; a análise final de sucesso NÃO tem esse teto. A validação de entrada de `title` com `max_length=500` (Q6 anterior) é revogada; os títulos são gerados pelo modelo, não recebidos pelo cliente.
- **Q12 (Códigos HTTP de falha do Scout no PATCH):** Ao revisar briefing por feedback, se o Scout falhar de forma terminal: **HTTP 500** para erro interno de configuração (`ProviderConfigurationError`, autenticação/autorização inválida do LLM); **HTTP 502** para geração pelo modelo indisponível (`LLMAttemptError` após exaustão de 3 tentativas); **HTTP 503** para busca Jina indisponível (`SerpSearchError`). Em qualquer falha terminal, a pesquisa transita para `FAILED` e o briefing para `failed`.
- **Q13 (Limite do tema do usuário):** O tema informado pelo operador deve ter entre 3 e 300 caracteres após normalização (`strip`). Acima de 300, o sistema rejeita com HTTP 422 e mensagem de erro explícita sobre o limite de 300 caracteres (não usar erro genérico). O campo `theme` no body de criação mantém validação 3–300 conforme Feature 001; acima de 300 é rejeitado com erro explícito "Tema deve ter entre 3 e 300 caracteres" antes de qualquer I/O.

### Sessão 2026-10-14
- **Q14:** Na revisão, como tratar pontos que o usuário não pediu para alterar?
  - **R:** Preservar pontos não afetados; ajustar ou acrescentar foco conforme feedback e novas evidências.
- **Q15:** Quantas consultas SERP distintas à Jina o Scout pode executar nessa revisão? Retries técnicos da mesma consulta não contam como novas consultas.
  - **R:** Uma nova consulta formulada pela IA com tema original e feedback.
- **Q16:** Se busca SERP ou geração do briefing revisado falhar após retries, qual comportamento deve valer? Regra atual encerra pesquisa em FAILED.
  - **R:** Manter FAILED, sem iniciar investigação; nova tentativa exige nova pesquisa.
- **Supersessões explícitas adicionais acordadas pelo operador nesta sessão:**
  - O endpoint `/approve` (`POST /briefings/{research_id}/approve`) não deve existir; não criar endpoint substituto.
  - `POST /briefings/{research_id}/investigate` sobre primeiro briefing válido em `draft` representa aprovação implícita e início da investigação na mesma operação (sem exigir aprovação prévia e sem HTTP 409 por status `draft`).
  - Revisão única por feedback via `PATCH /briefings/{research_id}` executa nova busca SERP Jina formulada pela IA, gera o briefing revisado e aprova/inicia a investigação automaticamente em background, sem exigir segunda chamada a `/investigate` nem confirmação intermediária. Tentativa posterior de nova revisão é bloqueada com HTTP 409 Conflict.

---

## 10. Lacunas

- Entrega anterior: `research_points.title` e `research_step_results.step_title` já usam `Text` em `app/models/domain_models.py:49,65`; `app/briefing/schemas.py:29` não impõe teto de 500 caracteres ao título. As antigas lacunas de Q11 estão resolvidas nesse código.
- Histórico de ações: T001 a T035 estão marcadas `[X]` em `actions.md`. Essas marcações registram a entrega anterior e não comprovam aceite final nem atendimento às decisões de 2026-10-14.
- Contratos e plano pendentes: alinhar `interfaces/briefings.md`, `interfaces/investigate.md`, `data-delta.md`, `roadmap.md` e `actions.md` às decisões de 2026-10-14.
- Implementação pendente: aprovação implícita no `/investigate`, revisão única com nova consulta SERP Jina orientada pelo feedback, início automático após revisão e remoção de `/approve`. Auditoria e testes desses novos comportamentos também permanecem pendentes.

Nenhuma decisão de produto pendente neste recorte. Todos os pontos de produto foram integralmente decididos pelo operador.

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-10-12 | Elaboração inicial dos requisitos pós-auditoria de planejamento | reversa-requirements |
| 2026-10-13 | Consolidação dos esclarecimentos Q1 a Q10 (desativação de agendamento legado, falhas baseline, retries, limites e Gherkin) | reversa-clarify |
| 2026-10-13 | Incorporação das deliberações Q11 a Q13 (títulos sem teto de 500, discriminação HTTP 500/502/503 no PATCH e tema 3–300 com HTTP 422 explícito); harmonização com template canônico | reversa-clarify |
| 2026-10-14 | Atualização de requisitos com decisões Q14 a Q16 (aprovação implícita via /investigate, revisão única por feedback com nova busca SERP Jina, início automático em background e extinção definitiva do /approve) | reversa-clarify |
