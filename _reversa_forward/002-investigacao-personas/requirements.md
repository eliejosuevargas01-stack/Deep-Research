# Requirements: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`  
> Data: 2026-10-12 (revisão consolidada pós-auditoria)  
> Pasta da feature: `_reversa_forward/002-investigacao-personas`  
> Fonte de verdade: decisões do operador registradas nas sessões de 2026-10-12. Zero pontos abertos.

---

## 1. Resumo

Depois que o operador aprova o briefing (Feature 001), o sistema investiga cada ponto de pesquisa com 4 workers (personas cognitivas) concorrentes: **historian**, **skeptic**, **pragmatist**, **futurist**. Para N pontos (3 a 7) são N × 4 execuções simultâneas (ex.: 5 pontos = 20 workers; 7 pontos = 28 workers).

O serviço despachante (`InvestigationService`) instancia cada worker passando a tupla `(research_id, step_id, step_title, persona)`. Cada worker roda um loop autônomo de tool calling (LiteLLM nativo com formato de ferramentas OpenAI, mantendo histórico de mensagens exclusivamente em RAM) consumindo uma ferramenta de busca Jina Search. A ferramenta recebe a query e devolve o texto limpo com o scraping já realizado pela Jina. O modelo pode realizar até 3 buscas por ponto e possui autonomia para parar antes se considerar as evidências suficientes. Cada worker grava seu resultado final individualmente em `research_step_results` e a Feature 002 encerra aí. Auditoria, redação e relatório final pertencem às features subsequentes.

---

## 2. Identificador único `research_id`

- O `research_id` (UUID aleatório) é gerado ANTES da elaboração do briefing, no momento em que a query/tema do usuário é submetida. A linha em `research` é persistida com `id` igual ao `research_id` e com o tema fornecido.
- O briefing NÃO gera identificador próprio: adota o mesmo `research_id` (`briefings.id == research.id`). Todas as tabelas do pipeline compartilham esse identificador único.
- Os pontos de pesquisa só passam a existir na tabela `research_points` quando o rascunho for expressamente aprovado; antes disso, residem unicamente no versionamento do briefing.
- Ao aprovar o briefing, os pontos aprovados são persistidos em `research_points`, todos vinculados ao `research_id` e nascendo com status `SCRAPER_PENDING`.
- Para editar o briefing ou solicitar novo rascunho com feedback, o usuário faz referência sempre ao `research_id`.
- O mesmo `research_id` governa o disparo da investigação, as fases posteriores de auditoria e síntese, e todas as consultas de telemetria.
- Nome canônico público do campo em todas as APIs e schemas: `research_id`.

### 2.1 Impacto e ajustes na Feature 001 (aprovado)
- `POST /briefings` instancia primeiro o registro em `research` (`id` aleatório + tema) e utiliza esse mesmo UUID como identificador da linha em `briefings`.
- Ao aprovar (`POST /briefings/{research_id}/approve`), os pontos são salvos em `research_points` com status `SCRAPER_PENDING` e a pesquisa passa de imediato para `SCRAPER`.
- As tabelas `briefings` e `briefing_versions` continuam como histórico canônico auditável de versões do rascunho.
- **Quebra de contrato da Feature 001 aprovada:** as respostas públicas da API de briefing substituem a chave `id` por `research_id`. Consumidores externos e documentação (`docs/api/briefing-scout.md`) são ajustados.
- Briefing aprovado não retorna para rascunho: chamadas a `POST /briefings/{research_id}/reopen` em briefing com status `approved` retornam HTTP 409 Conflict. Os testes da 001 que exerciam reabertura pós-aprovação são readequados.
- **Edição por feedback (`PATCH /briefings/{research_id}`):** o PATCH antigo por lista manual de pontos é extinto. O endpoint passa a aceitar corpo JSON `{"note": "texto do feedback"}` (mínimo 3 e máximo 4000 caracteres, correspondente ao padrão do frontend). O Scout opera com tool calling Jina: recebe o tema original, o rascunho anterior e o feedback do usuário como mensagem de chat, decide de forma autônoma a consulta de busca na tool Jina, obtém os resultados e gera uma nova versão de pontos em `briefing_versions`. A pesquisa permanece em `BRIEFING` durante a geração e conclui em `PENDING_APPROVAL`. A resposta é síncrona HTTP 200 contendo o novo rascunho. Se o Scout falhar durante o PATCH, a pesquisa transita para `FAILED`, o briefing fica com status `failed`, e nova tentativa exige submeter novo briefing.
- A suíte de 184 testes da Feature 001 é atualizada para esse novo contrato (`research_id`, bloqueio 409 no reopen e novo PATCH por feedback) mantendo 100% de aprovação.

---

## 3. Modelo de dados

### 3.1 Entidade `research` (pesquisa)
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

### 3.2 Entidade `research_points` (pontos de pesquisa)
- Registros existem apenas a partir da aprovação do briefing.
- Status permitidos do ponto: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`, `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`. O status legado `SEARCH_SUCCESS` é expurgado do enum; legados existentes migram para `AUDIT_PENDING`.
- `attempt_count`: contador inteiro atômico de falhas definitivas acumuladas de workers associados àquele ponto.

### 3.3 Entidade `research_step_results` (resultados analíticos da investigação)
Tabela append-only para auditoria e rastreabilidade total.

| Coluna | Tipo SQLAlchemy / DB | Origem | Descrição |
|---|---|---|---|
| `id` | `sa.Uuid` (PK) | banco | UUID primário do resultado |
| `research_id` | `sa.Uuid` (FK `research.id`, index=True) | código | Identificador universal da pesquisa |
| `step_id` | `sa.Uuid` (FK `research_points.id`, index=True) | código | Identificador do ponto correspondente |
| `step_title` | `sa.Text` | código | Enunciado textual do ponto investigado |
| `result` | `sa.Text` | modelo / erro | Texto analítico em caso de sucesso; mensagem sanitizada (máx 500 chars) em falha |
| `used_urls` | `sa.JSON` | modelo | Array JSON com URLs expressamente aproveitadas pelo modelo |
| `read_urls` | `sa.JSON` | harness | Array JSON com a totalidade das URLs retornadas pelo provedor Jina |
| `worker` | `sa.String(32)` | código | Persona designada: `historian`, `skeptic`, `pragmatist`, `futurist` |
| `status` | `sa.String(32)` | código | Status do resultado: `AUDIT_PENDING`, `APPROVED`, `REJECTED`, `FAILED` |
| `created_at` | `sa.DateTime(timezone=True)` | banco | Timestamp UTC de inserção |

---

## 4. Máquina de estados consolidada

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

---

## 5. Regras de negócio

- **RN-01 Disparo da Investigação.** O endpoint `POST /briefings/{research_id}/investigate` exige autenticação de administrador (`require_admin`), valida que `research.status == 'SCRAPER'` e que todos os pontos vinculados estejam em `SCRAPER_PENDING`. Atualiza atomicamente os pontos para `SCRAPER_IN_PROGRESS`, responde HTTP 202 com `{"research_id": "...", "status": "SCRAPER"}` e despacha a execução em background via FastAPI `BackgroundTasks`. Se os pontos já estiverem em `SCRAPER_IN_PROGRESS`, `AUDIT_PENDING` ou `SCRAPER_FAILED`, rejeita imediatamente com HTTP 409 Conflict.
- **RN-02 Concorrência Concorrente Irrestrita.** Para N pontos, o serviço instancia N × 4 corrotinas executadas sob `asyncio.gather(..., return_exceptions=True)`. As chamadas não são enfileiradas pelo semáforo legado de 4 slots de `app/services/llm.py`, operando conforme a Emenda de Concorrência ao Princípio IV de `.reversa/principles.md`.
- **RN-03 Parâmetros de Despacho dos Workers.** O orquestrador assíncrono repassa explicitamente para cada função worker a tupla `(research_id, step_id, step_title, persona)`. O worker carrega do banco apenas as chaves de API e configurações de modelo.
- **RN-04 Tool Calling e Memória Volátil.** A execução com o LLM utiliza a API nativa de ferramentas do LiteLLM (`tools` padrão OpenAI). O histórico conversacional (`messages`) é retido unicamente em memória RAM pelo tempo de vida do worker e descartado ao final, sem persistência intermediária em banco de dados.
- **RN-05 Ferramenta Jina Search.** A tool de busca realiza requisição HTTP POST para `https://s.jina.ai/` enviando JSON `{"q": query}` com cabeçalhos `Authorization: Bearer <token>`, `Accept: application/json` e `X-Engine: direct`. Se as chaves `jina_proxy_url` e `jina_proxy_auth_key` estiverem configuradas em `app_settings`, a requisição é direcionada ao proxy respeitando estritamente o mesmo contrato e cabeçalhos.
- **RN-06 Orçamento de Pesquisa.** Cada worker pode disparar no máximo 3 consultas de busca Jina por ponto. O modelo encerra voluntariamente o loop retornando o JSON de resultado quando julgar as fontes suficientes. Repetições técnicas de uma mesma busca motivadas por falhas de rede NÃO descontam do teto de 3 pesquisas.
- **RN-07 Retries Técnicos e Timeouts.** Chamadas externas à Jina e ao LiteLLM executam até 3 tentativas em caso de erro transitório de rede ou HTTP 429/5xx. Se o cabeçalho `Retry-After` for fornecido, a espera respeita o valor indicado; caso contrário, aplica backoff exponencial de 2s e 4s. O timeout limite por chamada individual é de 90s para o LLM e 90s para a Jina. O timeout global máximo por execução completa de um worker é fixado em 600s.
- **RN-08 Rastreabilidade Total de URLs Lidas.** O harness intercepta todas as URLs retornadas pela API da Jina durante as buscas realizadas pelo worker e as persiste no campo `read_urls`, independentemente de terem sido citadas pelo modelo.
- **RN-09 Resiliência e Isolamento de Falhas.** A falha definitiva ou estouro de timeout de um worker não aborta nem interrompe as demais corrotinas concorrentes.
- **RN-10 Seleção de Modelos por Persona.** O modelo utilizado por cada persona é extraído de `app_settings.models.<persona>` (`historian`, `skeptic`, `pragmatist`, `futurist`). Se o valor correspondente estiver ausente ou vazio, adota automaticamente como fallback o modelo configurado para o `scout`.
- **RN-11 Retomada Pós-Reinício do Servidor.** Um hook no ciclo de inicialização do FastAPI inspeciona pesquisas em `SCRAPER` cujos pontos estejam em `SCRAPER_IN_PROGRESS` e reagenda exclusivamente os workers que ainda não possuem linha correspondente em `research_step_results`.
- **RN-12 Isolamento Modular.** Toda a lógica da Feature 002 reside no pacote autônomo `app/investigation/` (schemas, prompts, tools, worker, storage, service, router).
- **RN-13 Validação de Formato e Autocorreção de JSON.** O modelo deve entregar seu resultado analítico final no formato JSON `{"result": "...", "used_urls": [...]}`. Caso o payload retornado seja sintaticamente inválido ou não obedeça às chaves exigidas, o harness executa até 3 correções dedicadas instruindo o modelo a formatar o JSON, sem consumir as tentativas de rede.
- **RN-14 Prompts Base das Personas.** Os prompts das personas são derivados de `app/prompts/personas.json`, adicionando instrução de sistema que exige citação factual das fontes lidas e a entrega do JSON final.

---

## 6. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF-01 | Gerar `research_id` previamente e registrar linha em `research` antes do briefing, vinculando o mesmo UUID a `briefings.id` |
| RF-02 | Ao aprovar o briefing via `POST /briefings/{research_id}/approve`, instanciar os pontos em `research_points` em `SCRAPER_PENDING` e mudar a pesquisa para `SCRAPER` |
| RF-03 | Expor `POST /briefings/{research_id}/investigate` assíncrono (HTTP 202), transitando pontos para `SCRAPER_IN_PROGRESS` e bloqueando re-disparos com HTTP 409 |
| RF-04 | Despachar N × 4 workers concorrentes sob `asyncio.gather`, repassando a cada um `(research_id, step_id, step_title, persona)` |
| RF-05 | Executar loop de tool calling LiteLLM com busca Jina, teto estrito de 3 buscas e parada voluntária |
| RF-06 | Integrar busca Jina direta ou via proxy sob contrato unificado POST `{"q": query}` com timeout de 90s |
| RF-07 | Interceptar e salvar a integridade das URLs retornadas pelo provedor em `read_urls` |
| RF-08 | Aplicar até 3 retries técnicos (com suporte a `Retry-After` e backoff 2s/4s) e até 3 chamadas de reparo de JSON |
| RF-09 | Persistir linha append-only em `research_step_results` para cada worker finalizado (`AUDIT_PENDING` ou `FAILED`) |
| RF-10 | Atualizar o status dos pontos (`AUDIT_PENDING` ou `SCRAPER_FAILED`) e a pesquisa (`AUDIT` ou `FAILED` se 100% falharem) ao término do gather |
| RF-11 | Fornecer migração Alembic 0007 criando `research_step_results`, unificando enums de status, removendo `SEARCH_SUCCESS` e executando backfill de briefings legados |
| RF-12 | Readequar endpoints da 001: adotar `research_id`, bloquear `POST /briefings/{research_id}/reopen` em aprovado (HTTP 409) e implementar `PATCH /briefings/{research_id}` por feedback `{"note"}` com novo rascunho Scout |
| RF-13 | Reatar execuções de workers incompletos no startup do servidor |

---

## 7. Requisitos não funcionais

- **Segurança de Segredos:** Nenhuma chave de API, token Bearer, URL com credenciais ou stack trace é exposto em logs ou gravado no banco. Mensagens de erro salvas na coluna `result` em falha definitiva são sanitizadas e truncadas a 500 caracteres.
- **Desempenho e Não-Bloqueio:** A orquestração assíncrona de até 28 workers simultâneos não bloqueia o event loop principal da aplicação.
- **Auditabilidade e Preservação:** Todos os resultados e URLs pesquisadas são preservados de maneira imutável (append-only) para consumo da Feature 003 (Auditoria).
- **Conformidade Normativa:** Operação alinhada ao Princípio IV de concorrência com emenda específica registrada em `.reversa/principles.md`.

---

## 8. Critérios de aceitação (Gherkin)

```gherkin
Cenário: Disparo bem-sucedido da investigação
  Dado uma pesquisa com briefing aprovado em status SCRAPER
  E 5 pontos de pesquisa persistidos em status SCRAPER_PENDING
  Quando o cliente envia POST /briefings/{research_id}/investigate autenticado como admin
  Então a API responde HTTP 202 com {"research_id": "...", "status": "SCRAPER"}
  E os 5 pontos passam atomicamente para status SCRAPER_IN_PROGRESS
  E 20 workers assíncronos são despachados concorrentemente

Cenário: Re-disparo rejeitado por conflito
  Dado uma pesquisa cujos pontos já se encontram em SCRAPER_IN_PROGRESS
  Quando o cliente envia POST /briefings/{research_id}/investigate
  Então a API rejeita com HTTP 409 Conflict

Cenário: Parada voluntária antecipada do worker
  Dado um worker investigando um ponto com persona skeptic
  Quando o modelo atinge síntese suficiente após 1 consulta à ferramenta de busca
  Então o modelo não emite nova tool call
  E encerra o loop entregando o JSON final
  E o resultado é registrado em research_step_results com status AUDIT_PENDING

Cenário: Bloqueio no teto de 3 pesquisas
  Dado um worker que já executou 3 buscas com sucesso
  Quando o modelo emite uma 4ª tool call de pesquisa
  Então o harness recusa a execução da ferramenta e exige a entrega do JSON final

Cenário: Repetição técnica de busca não consome cota
  Dado um worker executando sua primeira pesquisa
  Quando a chamada à Jina falha por timeout de rede e obtém sucesso no retry
  Então o consumo de cota contabilizado perante o modelo permanece em 1 de 3 pesquisas

Cenário: Interceptação e separação de URLs lidas e aproveitadas
  Dado uma consulta Jina que retornou 8 fontes externas no corpo da resposta
  E o modelo citou 3 fontes na chave used_urls do seu resultado final
  Quando o resultado é persistido
  Então a coluna read_urls registra as 8 URLs retornadas
  E a coluna used_urls registra exatamente as 3 URLs citadas

Cenário: Resiliência em falha individual de worker
  Dado um lote de 20 workers em execução
  Quando 1 worker atinge o timeout global de 600s ou esgota as 3 tentativas externas
  Então esse worker grava linha em research_step_results com status FAILED e erro sanitizado
  E o contador attempt_count do respectivo ponto é incrementado em 1
  E os demais 19 workers prosseguem sua execução sem interrupção

Cenário: Conclusão bem-sucedida da investigação global
  Dado uma pesquisa com 5 pontos em investigação
  Quando todos os 20 workers concluem e pelo menos 1 ponto obteve sucesso analítico
  Então os pontos com >= 1 sucesso transitam para AUDIT_PENDING
  E a pesquisa transita para o status AUDIT

Cenário: Falha global de 100% dos pontos investigados
  Dado uma pesquisa onde todos os workers de todos os pontos falharam definitivamente
  Quando o asyncio.gather encerra
  Então todos os pontos ficam em status SCRAPER_FAILED
  E a pesquisa transita atomicamente para o status FAILED

Cenário: Reabertura pós-aprovação rejeitada
  Dado um briefing que já atingiu o status approved
  Quando é feita requisição POST /briefings/{research_id}/reopen
  Então a API responde HTTP 409 Conflict com mensagem explicativa

Cenário: Edição de briefing por feedback textual
  Dado um briefing em status draft aguardando aprovação
  Quando o usuário envia PATCH /briefings/{research_id} com {"note": "Aprofundar riscos regulatórios"}
  Então o Scout é acionado novamente com o tema original somado ao feedback
  E um novo rascunho é persistido em briefing_versions
  E a API responde síncrona HTTP 200 com a nova versão gerada

Cenário: Falha do Scout durante PATCH de feedback
  Dado um briefing em status draft
  Quando o Scout falha irremediavelmente durante o PATCH
  Então a API responde com código de erro HTTP 500/502
  E a pesquisa transita para status FAILED
  E o briefing transita para status failed

Cenário: Retomada automática após reinicialização do servidor
  Dado que o servidor foi reiniciado enquanto uma pesquisa tinha pontos em SCRAPER_IN_PROGRESS
  Quando a aplicação executa o hook de startup do FastAPI
  Então o sistema detecta os pontos incompletos
  E reinsere em background apenas as personas que ainda não possuem registro em research_step_results
```

---

## 9. Pontos Abertos

Nenhum. Todas as decisões de produto, arquitetura, tolerância a falhas e contratos foram deliberadas pelo operador.
