> **Nota de Contexto Histórico (Reversa SDD):** Este documento registra o levantamento exploratório inicial pré-plano de LiteLLM e Jina. Todas as 6 perguntas e lacunas levantadas foram integralmente respondidas e deliberadas pelo operador nas sessões de 2026-10-12, estando consolidadas de forma canônica e normativa em `requirements.md` e `roadmap.md`.

---

# Investigação pré-plano — 002-investigacao-personas

**Escopo:** fatos de fronteira no código atual e documentação oficial LiteLLM/Jina. Este arquivo não aprova contratos, política de retry, modelo de dados final nem decisões adicionais. As alegações 🟢 do `requirements.md` são tratadas como texto a esclarecer, não como prova de implementação.

## Achados verificáveis

| Tema | Observação e evidência |
|---|---|
| Identidade e briefing | `app/briefing/domain.py:16-20, 149-167` define estados `generating`, `draft`, `failed`, `approved`; só `draft → approved` e leitura aprovada são permitidas. `app/briefing/router.py:196-213` expõe leitura aprovada em `/briefings/approved/{briefing_id}`; `app/briefing/router.py:135-193` gera briefing de forma síncrona. Não há rota `investigate` no router inspecionado (`app/briefing/router.py:135-302`). `BriefingRecord` (`app/models/domain_models.py:131-141`) é entidade separada de `Research` (`:31-42`); não foi observado vínculo entre os dois. |
| Concorrência e orçamento | `app/services/llm.py:174` define `_LLM_SEMAPHORE = asyncio.Semaphore(4)`; `complete()` adquire o semáforo em `:305-307`. Isto é limite existente para esse helper, não prova de limite global nem de aplicabilidade ao módulo novo. `requirements.txt:13` declara `litellm>=1.77.0`; `app/briefing/llm_binding.py:101-166` demonstra `litellm.acompletion`, timeout e uma tentativa para Scout, mas sem tool loop. |
| Mensagens e memória | O binding Scout envia somente `system` e `user` (`app/briefing/llm_binding.py:136-153`). Não há neste binding ciclo de tool call nem persistência de histórico; `app/briefing/service.py` e `app/briefing/storage.py` tratam geração/versionamento do briefing. Logo, mensagens por worker e durabilidade além da execução não ficam estabelecidas por esse precedente. |
| Jina | `app/briefing/serp_client.py:11, 38-56, 60-74, 76-109` usa `POST https://s.jina.ai/`, JSON `{q}`, Bearer, `Accept: application/json`, `X-Respond-With: no-content`, timeout injetado e quatro tentativas sem espera declarada (`:14-15`). `app/tools/search_pipeline.py:163-184` usa Jina Search com GET em `https://s.jina.ai/{query}` e parse Markdown; leitura de URL passa por `r.jina.ai` em `:198-224`. São adaptadores existentes diferentes; nenhum confirma contrato de proxy para investigação. `AppSettings` armazena `jina_base_url`, `jina_proxy_url`, `jina_proxy_timeout_seconds` (`app/models/domain_models.py:118-128`); `runtime_jina_proxy()` retorna URL, chave proxy descriptografada e timeout default 20s (`app/services/settings.py:310-321`). |
| Forma dos resultados | `app/models/domain_models.py:60-74` já tem `Evidence` por ponto/persona/URL, com chave única `(research_point_id, persona, source_url)` e versionamento otimista; `ResearchPoint` tem `attempt_count`, status e `audit` JSON (`:45-57`). Não existe no recorte inspecionado classe `research_step_results` nem campo `sources_read` em `ResearchPoint`. `Evidence` não equivale ao registro de resultado/histórico descrito no requisito. `alembic/versions/0006_briefing_storage.py:16-74` cria `briefings` e `briefing_versions`, sem tabelas de investigação. |
| Estados e configuração de personas | `app/services/settings.py:12-20` declara defaults de modelo para as quatro roles e Scout; `runtime_settings()` em `:290-301` preserva role configurada ou usa fallback, e força fallback default só para `scout`. `app/prompts/personas.json:2-8` contém prompts para quatro personas, Scout, Auditor e Writer. Isso confirma conteúdo e configuração, não que o executor proposto exista. |

## Documentação oficial consultada

- LiteLLM Function Calling: https://docs.litellm.ai/docs/completion/function_call — descreve envio de `messages` + `tools`, leitura de tool calls, execução no aplicativo e retorno do resultado como mensagem para nova chamada. A documentação inclui verificações de suporte por modelo (`supports_function_calling`, `supports_parallel_function_calling`). Não garante suporte homogêneo a cada modelo configurado.
- LiteLLM JSON mode / Structured Outputs: https://docs.litellm.ai/docs/completion/json_mode — documenta `response_format`, incluindo JSON Schema e classe Pydantic em modelos/provedores compatíveis, e recomenda verificar suporte. Não prova que todo modelo atualmente configurável aceite schema estrito.
- Jina Reader: https://jina.ai/reader/ — distingue `s.jina.ai` (busca/SERP) de `r.jina.ai` (leitura de URL); descreve `X-Engine: direct` como modo de fetch HTTP direto, rápido, contrastado com engine browser default. Página cita Search como top cinco resultados com URLs/conteúdo em fluxo compatível com Reader; não estabelece formato de proxy customizado.
- Jina API docs: https://docs.jina.ai/api/ — descreve Search em `https://s.jina.ai/`, método POST e Bearer; lista `Accept: application/json`. `X-Engine` documentado como seleção de engine de fetch, em contexto de Reader. Não encontrei confirmação documental que `X-Engine: direct` seja aplicável à busca Search ou que `GET /?q=...` seja o contrato de Search recomendado.

## Lacunas materiais: perguntas bloqueantes ao operador

1. **Vínculo de identidade:** `briefing_id` é ID de `BriefingRecord`, enquanto `research_id` é outra entidade. Como briefing aprovado vira ou aponta para `Research`, e qual identidade/cópia aprovada alimenta cada `ResearchPoint`? O código atual não mostra essa relação.
2. **Limite efetivo de concorrência:** o requisito pede fan-out sem semáforo, mas helper LLM atual tem semáforo 4. A execução nova deve evitar `complete()` ou remover/alterar esse limite? O limite declarado é apenas por chamada LLM ou há limite operacional externo que deve ser respeitado? Não presumir capacidade de provedor para 28 requests simultâneos.
3. **Semântica de memória:** mensagens isoladas valem apenas durante uma execução; resultado final é durável. Deve persistir também histórico intermediário/tool messages? Em caso positivo, qual conteúdo deve ser retido e por quanto tempo? Não salvar raciocínio interno/COT; definir se mensagens de tool serão mantidas.
4. **Contrato Jina e proxy:** confirmar método, URL e codificação de query, formato/parse de resposta, headers de Search, uso/escopo de `X-Engine: direct`, e como proxy recebe query e responde. Configuração existente `jina_proxy_url`/credencial usa `jina_proxy_auth` e timeout; os nomes `JINA_PROXY_BASE_URL`/`JINA_PROXY_KEY` do requisito não correspondem à API observada. Também confirmar precedência entre configuração DB, variáveis de ambiente e endpoint direto. Não reutilizar formato do briefing nem inventar contrato de proxy.
5. **Persistência e constraints:** requisito alterna `step_results` e `research_step_results`, exige três entidades e histórico append-only, mas existe `Evidence` com unicidade por URL/ponto/persona. Confirmar identidade/FKs, granularidade do resultado, campos/tipos efetivamente requeridos, relação persona/tentativa, se tentativas com falha geram linha, política de repetição e quais constraints impedem duplicação. Confirmar se `sources_read` é necessária além de `all_collected_sources` por resultado; evitar duplicação de fontes sem finalidade acordada.
6. **Shape e significado do status:** confirmar schema exato do JSON final e dos objetos fonte, associação de fonte usada vs retornada, e se status `auditar` é valor literal persistido ou estado de processo. Requisito também descreve erro `failed`, pontos `in_progress/completed/blocked` e execução assíncrona HTTP 202, sem definir transições/recuperação após reinício do processo.

## Detalhes que podem ser definidos depois (não bloqueiam entendimento do recorte)

- Nome exato de funções, classes internas e ordem de módulos dentro de `app/investigation/` — desde que fronteiras e políticas bloqueantes acima sejam decididas.
- Formatação textual dos prompts/personas, desde que mantenha os prompts existentes quando isso for requisito.
- Texto de erro interno e organização de logs, sem alterar semântica HTTP, privacidade de segredos ou auditoria requerida.

## Escopo não realizado

Sem chamadas pagas ou credenciais, sem requisição de investigação/produção, sem teste de modelo/Jina, sem migração, alteração de código ou requirements. Nenhuma preferência operacional foi inferida a partir de comportamento de fallback existente.
