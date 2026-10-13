# Requirements: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`
> Data: 2026-10-13 (revisão consolidada pós-auditoria — Rodada 3)
> Pasta da feature: `_reversa_forward/002-investigacao-personas`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA
> Fonte de verdade: decisões do operador registradas nas sessões de 2026-10-12 e esclarecimentos de 2026-10-13 (Q1–Q13).

---

## 1. Resumo executivo

Após a aprovação do briefing (Feature 001), o sistema investiga cada ponto de pesquisa aprovado disparando concorrentemente quatro workers com personas cognitivas distintas: **historian**, **skeptic**, **pragmatist** e **futurist**. Cada worker executa tool calling com a ferramenta de busca Jina Search em memória volátil (RAM), persistindo seus resultados analíticos e URLs de forma imutável (append-only) em `research_step_results` para posterior auditoria (Feature 003) e redação (Feature 004).

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
| Operador de pesquisa (Admin) | Iniciar investigação aprofundada sobre briefing previamente aprovado | Aciona `POST /briefings/{research_id}/investigate` autenticado como admin e acompanha o avanço |
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

1. **RN-01 Disparo da Investigação.** O endpoint `POST /briefings/{research_id}/investigate` exige autenticação de administrador (`require_admin`; ausência ou invalidade retorna HTTP 401/403). Se o `research_id` não existir em `research`, responde HTTP 404 Not Found. Valida que `research.status == 'SCRAPER'`, que existam pontos e que todos os pontos vinculados estejam em `SCRAPER_PENDING`. Se a pesquisa não possuir pontos ou já possuir pontos em `SCRAPER_IN_PROGRESS`, `AUDIT_PENDING` ou `SCRAPER_FAILED`, rejeita atomicamente com HTTP 409 Conflict. Atualiza atomicamente os pontos para `SCRAPER_IN_PROGRESS`, responde HTTP 202 com `{"research_id": "...", "status": "SCRAPER", "message": "Investigação iniciada em background"}` e despacha a execução em background via FastAPI `BackgroundTasks`. 🟢
   - Tipo: nova

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
- Os pontos de pesquisa só passam a existir na tabela `research_points` quando o rascunho for expressamente aprovado; antes disso, residem unicamente no versionamento do briefing.
- Ao aprovar o briefing, os pontos aprovados são persistidos em `research_points`, todos vinculados ao `research_id` e nascendo com status `SCRAPER_PENDING`.
- Para editar o briefing ou solicitar novo rascunho com feedback, o usuário faz referência sempre ao `research_id`.
- O mesmo `research_id` governa o disparo da investigação, as fases posteriores de auditoria e síntese, e todas as consultas de telemetria.
- Nome canônico público do campo em todas as APIs e schemas: `research_id`.

**Impacto e ajustes na Feature 001 (aprovado):**
- `POST /briefings` instancia primeiro o registro em `research` (`id` aleatório + tema) e utiliza esse mesmo UUID como identificador da linha em `briefings`. O tema tem tamanho de 3 a 300 caracteres após strip; se o usuário enviar tema com mais de 300 caracteres, a API rejeita com HTTP 422 Unprocessable Entity e mensagem de erro explícita sobre o limite de 300 (Q13).
- Os títulos e descrições de pontos de briefing gerados pelo Scout devem ser texto não-vazio e NÃO possuem comprimento máximo fixo (Q11; regra anterior Q6 revogada). O sistema aceita e persiste o título integral. A mensagem de erro sanitizada em falha terminal mantém limite de 500 caracteres; a análise final de sucesso não possui teto de 500.
- Ao aprovar (`POST /briefings/{research_id}/approve`), os pontos são salvos em `research_points` com status `SCRAPER_PENDING` e a pesquisa passa de imediato para `SCRAPER`.
- As tabelas `briefings` e `briefing_versions` continuam como histórico canônico auditável de versões do rascunho.
- **Quebra de contrato da Feature 001 aprovada:** as respostas públicas da API de briefing substituem a chave `id` por `research_id`. Consumidores externos e documentação (`docs/api/briefing-scout.md`) são ajustados.
- Briefing aprovado não retorna para rascunho: chamadas a `POST /briefings/{research_id}/reopen` em briefing com status `approved` retornam HTTP 409 Conflict. Os testes da 001 que exerciam reabertura pós-aprovação são readequados.
- **Edição por feedback (`PATCH /briefings/{research_id}`):** o PATCH antigo por lista manual de pontos é extinto. O endpoint passa a aceitar corpo JSON `{"note": "texto do feedback"}` (mínimo 3 e máximo 4000 caracteres, correspondente ao padrão do frontend). O Scout opera com tool calling Jina: recebe o tema original, o rascunho anterior e o feedback do usuário como mensagem de chat, decide de forma autônoma a consulta de busca na tool Jina, obtém os resultados e gera uma nova versão de pontos em `briefing_versions`. A pesquisa permanece em `BRIEFING` durante a geração e conclui em `PENDING_APPROVAL`. A resposta é síncrona HTTP 200 contendo o novo rascunho. Se o Scout falhar de forma terminal durante o PATCH, a API responde HTTP 500 para erro interno de configuração, HTTP 502 para geração de modelo indisponível ou HTTP 503 para busca Jina indisponível (Q12); a pesquisa transita para `FAILED`, o briefing fica com status `failed`, e nova tentativa exige submeter novo briefing.
- A suíte de 184 testes da Feature 001 é atualizada para esse novo contrato (`research_id`, bloqueio 409 no reopen e novo PATCH por feedback) mantendo 100% de aprovação.

### 4.2 Modelo de dados

#### 4.2.1 Entidade `research` (pesquisa)
Status permitidos (`research.status`): `PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`.

- `PENDING`: reservado exclusivamente para futura fila global de pesquisas simultâneas (sem limite nesta feature).
- `BRIEFING`: enquanto o scout gera o rascunho inicial ou processa nova versão após feedback.
- `PENDING_APPROVAL`: rascunho gerado aguardando revisão e aprovação do usuário.
- `SCRAPER`: briefing aprovado, indicando prontidão para disparo ou investigação em andamento pelos workers.
- `AUDIT`: todos os workers de todos os pontos concluíram a investigação.
- `WRITE`: reservado para a fase de redação final do relatório (Feature 004).
- `DONE`: pesquisa concluída com relatório final publicado.
- `FAILED`: falha irremediável na geração do briefing, falha no PATCH por feedback, ou esgotamento em falha de 100% dos pontos da investigação.

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
| Scout conclui rascunho com sucesso | `PENDING_APPROVAL` | (não existem) | Nenhuma |
| `PATCH /briefings/{research_id}` por feedback | `BRIEFING` -> `PENDING_APPROVAL` | (não existem) | Nova versão em `briefing_versions` |
| Falha do Scout no POST ou PATCH | `FAILED` | (não existem) | Briefing vai para `failed` |
| `POST /briefings/{research_id}/approve` | `SCRAPER` | Inseridos como `SCRAPER_PENDING` | Nenhuma |
| `POST /briefings/{research_id}/investigate` | `SCRAPER` | Transitam para `SCRAPER_IN_PROGRESS` | Nenhuma |
| Worker individual conclui com sucesso | `SCRAPER` | Mantém `SCRAPER_IN_PROGRESS` | Linha salva com `AUDIT_PENDING` |
| Worker individual esgota retries em falha | `SCRAPER` | Incrementa `attempt_count` | Linha salva com `FAILED` e erro sanitizado |
| Ponto com >= 1 worker concluído com sucesso | `SCRAPER` | Transita para `AUDIT_PENDING` | — |
| Ponto com todos os 4 workers falhos | `SCRAPER` | Transita para `SCRAPER_FAILED` | — |
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
| RF-02 | Ao aprovar o briefing via `POST /briefings/{research_id}/approve`, instanciar os pontos em `research_points` em `SCRAPER_PENDING` e mudar a pesquisa para `SCRAPER`, aceitando títulos gerados pelo Scout sem teto de 500 caracteres (Q11) | Must | Pontos persistem em `research_points` vinculados ao `research_id`; títulos acima de 500 caracteres são aceitos e gravados integralmente em coluna Text | 🟢 |
| RF-03 | Expor `POST /briefings/{research_id}/investigate` assíncrono (HTTP 202), transitando pontos para `SCRAPER_IN_PROGRESS` e bloqueando re-disparos com HTTP 409 | Must | Responde HTTP 202 com status SCRAPER; pontos transitam para SCRAPER_IN_PROGRESS; re-disparo em andamento retorna HTTP 409 Conflict | 🟢 |
| RF-04 | Despachar N × 4 workers concorrentes sob `asyncio.gather`, repassando a cada um `(research_id, step_id, step_title, persona)` | Must | Para N pontos (3 a 7), despacha exatamente N × 4 corrotinas com a tupla completa de argumentos | 🟢 |
| RF-05 | Executar loop de tool calling LiteLLM com busca Jina, teto estrito de 3 buscas e parada voluntária | Must | Worker realiza até 3 buscas Jina por ponto; para voluntariamente quando dados bastam; 4ª chamada é bloqueada pelo harness | 🟢 |
| RF-06 | Integrar busca Jina direta ou via proxy sob contrato unificado POST `{"q": query}` com timeout de 90s | Must | Executa POST na API direta ou proxy configurado com timeout 90s; payloads e cabeçalhos preservados | 🟢 |
| RF-07 | Interceptar e salvar a integridade das URLs retornadas pelo provedor em `read_urls` | Must | Harness captura 100% das URLs retornadas no payload Jina e grava em `read_urls` no banco | 🟢 |
| RF-08 | Aplicar até 3 tentativas totais (1 chamada inicial + até 2 retries técnicos com suporte a `Retry-After` e backoff 2s/4s) e até 3 chamadas de reparo de JSON | Must | Erros transitórios de rede/429/5xx recebem até 2 retries; formato JSON inválido recebe até 3 correções dedicadas separadas | 🟢 |
| RF-09 | Persistir linha append-only em `research_step_results` para cada worker finalizado (`AUDIT_PENDING` ou `FAILED`) | Must | Cada worker finalizado insere exatamente uma linha com persona, resultado analítico ou erro sanitizado e URLs | 🟢 |
| RF-10 | Atualizar o status dos pontos (`AUDIT_PENDING` ou `SCRAPER_FAILED`) e a pesquisa (`AUDIT` ou `FAILED` se 100% falharem) ao término do gather | Must | Pontos com >=1 sucesso passam a AUDIT_PENDING e pesquisa a AUDIT; se 100% falharem, pontos ficam SCRAPER_FAILED e pesquisa FAILED | 🟢 |
| RF-11 | Fornecer migração Alembic 0007 criando `research_step_results`, unificando enums de status, removendo `SEARCH_SUCCESS` e executando backfill de briefings legados | Must | Tabela criada com tipos portáteis; SEARCH_SUCCESS migra para AUDIT_PENDING; briefings órfãos ganham linha em research | 🟢 |
| RF-12 | Readequar endpoints da 001: adotar `research_id`, bloquear `POST /briefings/{research_id}/reopen` em aprovado (HTTP 409) e implementar `PATCH /briefings/{research_id}` por feedback `{"note"}` com novo rascunho Scout, discriminando falhas em 500/502/503 (Q12) | Must | Reopen de aprovado retorna 409; PATCH aceita note e gera novo rascunho; falha terminal retorna 500 (config), 502 (modelo) ou 503 (Jina) | 🟢 |
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

Cenário: Instanciação de pontos de pesquisa na aprovação do briefing (RF-02)
  Dado um briefing em status draft com 5 pontos válidos
  Quando o operador envia POST /briefings/{research_id}/approve autenticado como admin
  Então a API responde HTTP 200 com status approved
  E os 5 pontos são persistidos na tabela research_points vinculados ao research_id com status SCRAPER_PENDING
  E a pesquisa transita para status SCRAPER

Cenário: Título longo gerado pelo Scout aceito e persistido sem limite (RF-02, Q11)
  Dado um rascunho de briefing gerado pelo Scout contendo um ponto com título de 520 caracteres
  Quando o operador aprova o briefing
  Então o sistema aceita o ponto sem aplicar teto de 500 caracteres
  E persiste o título integralmente na coluna Text de research_points

Cenário: Disparo bem-sucedido da investigação (RF-03, RF-04)
  Dado uma pesquisa com briefing aprovado em status SCRAPER
  E 5 pontos de pesquisa persistidos em status SCRAPER_PENDING
  Quando o cliente envia POST /briefings/{research_id}/investigate autenticado como admin
  Então a API responde HTTP 202 com {"research_id": "...", "status": "SCRAPER"}
  E os 5 pontos passam atomicamente para status SCRAPER_IN_PROGRESS
  E 20 workers assíncronos são despachados concorrentemente

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
  Dado um briefing que já atingiu o status approved
  Quando é feita requisição POST /briefings/{research_id}/reopen
  Então a API responde HTTP 409 Conflict com mensagem explicativa

Cenário: Edição de briefing por feedback textual (RF-12)
  Dado um briefing em status draft aguardando aprovação
  Quando o usuário envia PATCH /briefings/{research_id} com {"note": "Aprofundar riscos regulatórios"}
  Então o Scout é acionado novamente com o tema original somado ao feedback
  E um novo rascunho é persistido em briefing_versions
  E a API responde síncrona HTTP 200 com a nova versão gerada

Cenário: Falha do Scout durante PATCH de feedback (RF-12, Q12)
  Dado um briefing em status draft
  Quando o Scout falha irremediavelmente durante o PATCH
  Então a API responde com código HTTP 500 (configuração), HTTP 502 (modelo indisponível) ou HTTP 503 (busca Jina indisponível) conforme a causa
  E a pesquisa transita para status FAILED
  E o briefing transita para status failed

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
| RF-02 | Must | Essencial: instanciação de pontos aprovados em `research_points` com títulos sem teto (Text) |
| RF-03 | Must | Essencial: endpoint seguro `/investigate` com HTTP 202 assíncrono e bloqueio 409 de re-disparos |
| RF-04 | Must | Essencial: paralelismo concorrente dos 4 workers por ponto via `asyncio.gather` irrestrito |
| RF-05 | Must | Essencial: loop de tool calling Jina Search com teto de 3 buscas e parada voluntária |
| RF-06 | Must | Essencial: suporte à ferramenta Jina direta ou via proxy configurado |
| RF-07 | Must | Essencial: rastreabilidade total de URLs lidas pelo harness em `read_urls` |
| RF-08 | Must | Essencial: tolerância a falhas transitórias (retries 2s/4s) e autocorreção de JSON (até 3 tentativas) |
| RF-09 | Must | Essencial: persistência imutável append-only dos resultados das personas |
| RF-10 | Must | Essencial: transição de estado da pesquisa e dos pontos ao término da investigação |
| RF-11 | Must | Essencial: migração de banco 0007 unificando enums e executando backfill histórico |
| RF-12 | Must | Essencial: quebra de contrato controlada (adotar `research_id`, bloquear reopen 409 e PATCH feedback 500/502/503) |
| RF-13 | Must | Essencial: resiliência a crashes do servidor com retomada idempotente no startup |
| RNF de Segurança | Must | Proteção de credenciais, isolamento rigoroso de prompts/CoT em RAM e sanitização de erros |
| RNF de Desempenho | Should | Execução assíncrona não bloqueante de até 28 workers simultâneos |
| RNF de Auditabilidade | Must | Preservação append-only de evidências para o pipeline de auditoria posterior |
| RNF de Conformidade | Must | Alinhamento obrigatório à Emenda de Concorrência ao Princípio IV |

---

## 9. Esclarecimentos

### Sessão 2026-10-13 (Rodada 1)
- **Q1 (Agendamento legado):** Ao aprovar briefing pelo endpoint legado `POST /api/research/{research_id}/briefing/approve` ou na revisão automática, o pipeline legado (`schedule(run_research)`) deve ser desativado. A pesquisa permanece em `SCRAPER` aguardando disparo exclusivo por `POST /briefings/{research_id}/investigate`.
- **Q2 (Falhas herdadas de teste):** Todas as 9 falhas herdadas do baseline `8bfd529` (5 em `tests/test_backend.py` e 4 em `tests/integration`/`tests/unit` por ausência de `pytest-asyncio`), além de 1 teste sensível a DNS/ordem, devem ser corrigidas dentro do escopo da Feature 002 antes do aceite final.
- **Q3 (Contagem de tentativas):** Limite estrito de 3 tentativas totais por chamada externa (1 chamada inicial + até 2 retries técnicos com backoff exponencial 2s/4s). RF-08 e RN-07 unificados nessa regra.
- **Q4 (Limite de `step_title`):** A coluna `step_title` é persistida como `sa.String(500)` para alinhamento estrito ao banco de dados e à entidade upstream `research_points.title`. **SUPERADA em Rodada 3 (Q11):** títulos de pontos gerados pelo Scout NÃO possuem teto de 500; a migração da 007 deve ampliar `research_points.title` e `research_step_results.step_title` para `sa.Text`.
- **Q5 (Casos de borda em `/investigate`):** O endpoint `POST /briefings/{research_id}/investigate` retorna formalmente: HTTP 404 quando o `research_id` não existe; HTTP 401/403 quando não autenticado como administrador; e HTTP 409 Conflict quando a pesquisa não possui pontos ou já possui pontos em execução/finalizados.

### Sessão 2026-10-13 (Rodada 2)
- **Q6 (L-01 Comprimento do título):** Títulos de pontos de briefing com mais de 500 caracteres são rejeitados na validação de entrada com HTTP 422 Unprocessable Entity. **SUPERADA em Rodada 3 (Q11):** títulos de pontos gerados pelo Scout NÃO têm teto de 500; a restrição se aplica apenas ao campo `theme` do body de criação (3–300, Q13), não aos títulos de pontos.
- **Q7 (L-02 Exaustão de reparos JSON):** Se o modelo não entregar JSON válido após as 3 correções dedicadas, o worker encerra com `success=False`, grava linha em `research_step_results` com status `FAILED`, `result="Invalid JSON response after 3 corrections"`, `used_urls=[]`, e incrementa `attempt_count`.
- **Q8 (L-03 Ciclo de vida de `attempt_count`):** `attempt_count` inicia em 0 na persistência pós-aprovação e incrementa atomicamente em +1 para cada falha definitiva de worker. Na retomada, o sistema despacha apenas personas sem linha gravada no banco, garantindo idempotência.
- **Q9 (L-04 Isolamento de prompts e chain-of-thought):** Prompts de sistema e raciocínio bruto (*chain-of-thought*) residem estritamente em RAM e são proibidos em banco, logs públicos e respostas de API. A coluna `result` armazena exclusivamente a síntese analítica final ou o erro sanitizado.
- **Q10 (L-05 Cenários Gherkin):** Formalizados no Gherkin os cenários para HTTP 404 (pesquisa inexistente), HTTP 401/403 (não admin), HTTP 409 (pesquisa sem pontos) e exaustão de reparos de JSON.

### Sessão 2026-10-13 (Rodada 3)
- **Q11 (Título gerado pelo Scout):** Se o Scout gerar um ponto do briefing com título maior que 500 caracteres, NÃO limitar — o sistema deve aceitar e persistir o título inteiro. Títulos e descrições de pontos devem permanecer texto não-vazio. A mensagem de erro de falha sanitizada mantém limite de 500 caracteres; a análise final de sucesso NÃO tem esse teto. A validação de entrada de `title` com `max_length=500` (Q6 anterior) é revogada; os títulos são gerados pelo modelo, não recebidos pelo cliente.
- **Q12 (Códigos HTTP de falha do Scout no PATCH):** Ao revisar briefing por feedback, se o Scout falhar de forma terminal: **HTTP 500** para erro interno de configuração (`ProviderConfigurationError`, autenticação/autorização inválida do LLM); **HTTP 502** para geração pelo modelo indisponível (`LLMAttemptError` após exaustão de 3 tentativas); **HTTP 503** para busca Jina indisponível (`SerpSearchError`). Em qualquer falha terminal, a pesquisa transita para `FAILED` e o briefing para `failed`.
- **Q13 (Limite do tema do usuário):** O tema informado pelo operador deve ter entre 3 e 300 caracteres após normalização (`strip`). Acima de 300, o sistema rejeita com HTTP 422 e mensagem de erro explícita sobre o limite de 300 caracteres (não usar erro genérico). O campo `theme` no body de criação mantém validação 3–300 conforme Feature 001; acima de 300 é rejeitado com erro explícito "Tema deve ter entre 3 e 300 caracteres" antes de qualquer I/O.

---

## 10. Lacunas

- 🔴 Implementação: a migração da 007 deve ampliar `research_points.title` e `research_step_results.step_title` de `sa.String(500)` para `sa.Text` (Q11); código atual ainda usa `String(500)`.
- 🔴 Implementação: a validação de entrada de `title` com `max_length=500` (Q6 revogada) deve ser removida do schema de briefing; a regra vigente permite título ilimitado gerado pelo Scout.
- 🔴 Contratos e plano: `interfaces/briefings.md`, `data-delta.md`, `roadmap.md` e `actions.md` foram reconciliados com as decisões Q11–Q13; coding pendente nas sprints C1 a C7.

Nenhuma decisão de produto pendente neste recorte. Todos os pontos de produto foram integralmente decididos pelo operador.

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-10-12 | Elaboração inicial dos requisitos pós-auditoria de planejamento | reversa-requirements |
| 2026-10-13 | Consolidação dos esclarecimentos Q1 a Q10 (desativação de agendamento legado, falhas baseline, retries, limites e Gherkin) | reversa-clarify |
| 2026-10-13 | Incorporação das deliberações Q11 a Q13 (títulos sem teto de 500, discriminação HTTP 500/502/503 no PATCH e tema 3–300 com HTTP 422 explícito); harmonização com template canônico | reversa-clarify |
