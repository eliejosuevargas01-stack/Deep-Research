# Roadmap: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`
> Data: `2026-10-13`
> Requirements: `_reversa_forward/002-investigacao-personas/requirements.md`
> Confidência: 🟢 decisões de produto confirmadas Q1–Q10; 🟡 interpretação arquitetural explicitada onde requirements não fixa implementação.

---

## 1. Resumo da abordagem

> **Estado:** proposta documental; feature está em `coding`. Itens registrados em `progress.jsonl` não substituem aceite: falhas baseline e teste sensível a ordem/DNS seguem gates obrigatórios (Q2).

A Feature 002 implementa a investigação concorrente dos pontos aprovados no briefing através de 4 personas canônicas (**historian**, **skeptic**, **pragmatist**, **futurist**). Para $N$ pontos aprovados (3 a 7), são instanciadas exatamente $N 	imes 4$ execuções simultâneas em background (`asyncio.gather` irrestrito).
Cada worker executa um loop de reflexão com LiteLLM nativo e memória conversacional em RAM, invocando a ferramenta Jina Search (via POST direto ou proxy customizado). O modelo tem teto rígido de até 3 consultas de busca por ponto, podendo encerrar antecipadamente. O harness registra em `read_urls` as URLs retornadas pela Jina; isso não prova leitura integral nem citação verbatim. O modelo fornece `result` e `used_urls`. Os resultados são salvos em `research_step_results` com status `AUDIT_PENDING` (ou `FAILED`), atualizando o ponto para `AUDIT_PENDING` quando pelo menos uma persona conclui, ou `SCRAPER_FAILED` quando todas falham; a pesquisa vai a `AUDIT` se houver algum ponto bem-sucedido e a `FAILED` se todos falharem.

---

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| **I. Rastreabilidade Factual Estrita (Verbatim Citation)** | O harness registra todas as URLs retornadas pela Jina (`read_urls`), sem afirmar leitura integral ou prova verbatim e o modelo referencia explicitamente as URLs utilizadas (`used_urls`), preparando os dados para a auditoria factual futura (Feature 003). | Respeita |
| **II. Defesa de Privacidade e Isolamento de Prompts** | Prompts/CoT ficam somente em RAM; `result` persiste síntese final ou erro sanitizado, sem segredos. 🟢 decisão confirmada; execução permanece sujeita a verificação de aceite. | Respeita |
| **III. Resiliência por Degradação Graciosa e Limites Rígidos** | Falha de uma persona isolada não interrompe os outros workers (`return_exceptions=True`). Timeout de 90s por chamada I/O, 600s por worker e 3 tentativas totais (1 inicial + 2 retries, backoff 2s/4s; aplicar `Retry-After` quando presente). Se todos os workers de um ponto falharem, o ponto fica `SCRAPER_FAILED`; a pesquisa segue para `AUDIT` se ao menos um ponto tiver sucesso, e vai a `FAILED` somente se todos os pontos falharem. | Respeita |
| **IV. Concorrência Segura e Idempotência** | O princípio estabelece semáforo `Semaphore(20)`. No entanto, por decisão deliberada do operador, o módulo `app/investigation/` opera com **concorrência irrestrita** via `asyncio.gather` (até 28 workers simultâneos), ignorando semáforos legados. A idempotência é garantida com HTTP 409 em re-disparos. | Respeita (Princípio IV emendado formalmente em `.reversa/principles.md`: concorrência irrestrita na 002, governada por timeouts e retries) |

---

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| **D-01** | Identificador unificado `research_id` gerado antes do briefing | Briefing, passos, investigação e auditoria compartilham o mesmo UUID canônico da pesquisa | Criar IDs desconectados ou tabela de mapeamento intermediária | 🟢 |
| **D-02** | Módulo isolado em `app/investigation/` | Mantém separação limpa de responsabilidades e desacoplamento do código legado monolítico | Misturar workers dentro de `app/services/research.py` | 🟢 |
| **D-03** | Tabela dedicada `research_step_results` append-only | Permite auditoria histórica e repesquisa futura sem conflitar com constraints legadas de `Evidence` | Reutilizar `Evidence` ou salvar em coluna JSON nos passos | 🟢 |
| **D-04** | Concorrência irrestrita via `asyncio.gather` | Executar simultaneamente todos os pontos x 4 personas (até 28 workers) sem gargalos de semáforo | Usar semáforo 4 do `llm.py` ou semáforo 20 | 🟢 |
| **D-05** | Tool Calling nativo LiteLLM com mensagens em RAM | Padrão robusto da OpenAI, sem frameworks pesados; histórico descartado da RAM ao fim da execução | LangChain, LlamaIndex, ou salvar histórico de tool calls no banco | 🟢 |
| **D-06** | Jina Search via POST com suporte a proxy | POST `https://s.jina.ai/` com payload JSON `{"q": query}` e headers `Accept: application/json` / `X-Engine: direct`; ou proxy se configurado | GET com query string na URL | 🟢 |
| **D-07** | Teto de 3 buscas com parada antecipada | O modelo reflete se tem dados suficientes e para; se atingir 3 queries, o harness encerra e exige o JSON final | Busca infinita ou número fixo obrigatório de 3 queries | 🟢 |
| **D-08** | Retries e backoff para chamadas externas | Até 3 tentativas totais; respeita `Retry-After` ou espera exponencial de 2s e 4s; retries não consomem o teto de 3 buscas | Sem retries ou retry imediato sem backoff | 🟢 |
| **D-09** | Até 3 correções de JSON final do modelo | Se a resposta não parsear no schema esperado, faz até 3 chamadas corretivas dedicadas sem descontar das buscas | Descartar imediatamente ou aceitar texto não estruturado | 🟢 |
| **D-10** | Disparo assíncrono com HTTP 202 e re-disparo com HTTP 409 | Chamador recebe `research_id` imediatamente; se já disparado, rejeita com 409 Conflict | Execução síncrona com timeout HTTP longo | 🟢 |
| **D-11** | Retomada automática pós-reinício | Servidor retoma apenas personas sem linha em `research_step_results`; `SCRAPER_IN_PROGRESS` é estado de ponto, não de pesquisa | Perder execuções em andamento ou marcar tudo como falha | 🟢 decisão / 🟡 mecanismo derivado |
| **D-12** | Aprovação não agenda pipeline legado | Aprovação/revisão mantém pesquisa em `SCRAPER`; somente `POST /briefings/{research_id}/investigate` dispara workers | Manter `schedule(run_research)` no fluxo legado | 🟢 Q1 |
| **D-13** | Títulos ilimitados (Q11) + tema 3–300 (Q13) | `step_title` e `research_points.title` passam a `sa.Text` (migração 007); títulos gerados pelo Scout NÃO têm teto de 500; tema do usuário 3–300 com HTTP 422 e erro explícito | Truncar título ou aplicar 500 ao tema | 🟢 Q4/Q6 (superadas por Q11/Q13) |
| **D-14** | Falhas baseline são gate de aceite | Corrigir 9 falhas herdadas e 1 sensível a ordem/DNS antes do aceite; não dispensar como dívida prévia | Excluir testes do gate | 🟢 Q2 |
| **D-15** | Exaustão de reparos de JSON produz FAILED | Inicial + até 3 correções; ao esgotar, grava FAILED, result="Invalid JSON response after 3 corrections" e used_urls=[] | Descartar sem persistir ou salvar JSON quebrado | 🟢 Q7 |
| **D-16** | Contador de falhas definitivo | `attempt_count` nasce em 0 e incrementa +1 atomicamente por falha de worker; retomada ignora personas já persistidas | Contar falhas transitórias ou duplicar incremento na retomada | 🟢 Q8 |
| **D-17** | Isolamento de prompts e CoT | Apenas RAM; `result` contém análise final ou erro sanitizado de até 500 caracteres, sem prompts ou segredos | Persistir histórico bruto de mensagens | 🟢 Q9 |
| **D-18** | Modelo e credenciais por persona | `app_settings.models.<persona>` com fallback scout; resolver chave e base URL do provedor correspondente para cada execução | Reutilizar chave scout para provedores diferentes | 🟢 RN-10 / 🟡 resolução técnica |
| **D-19** | Fronteira de acesso e reserva | Admin obrigatório; inexistente 404, não admin 401/403, estado inválido ou zero pontos 409; reserva atômica antes de 202 | Disparo duplicado ou retorno 202 sem pontos | 🟢 Q5/Q10 |
| **D-20** | Discriminação de erros HTTP no PATCH | HTTP 500 para erro interno/configuração, HTTP 502 para geração pelo modelo indisponível e HTTP 503 para busca Jina indisponível; pesquisa FAILED e briefing failed | Agrupar erros ou mascarar causa externa | 🟢 Q12 |

---

## 4. Premissas

Nenhuma premissa de produto permanece em aberto após Q1–Q10. Escolhas de tradução técnica marcadas 🟡 são interpretações arquiteturais, não deliberações adicionais.

---

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `InvestigationService` | `app/investigation/service.py` | componente-novo | Orquestrador de investigação assíncrona, fan-out de workers e transições de estado |
| `PersonaWorker` | `app/investigation/worker.py` | componente-novo | Executa o loop de tool calling com LiteLLM, limite de 3 queries e extração de fontes |
| `JinaToolAdapter` | `app/investigation/tools.py` | componente-novo | Cliente HTTP para Jina Search (POST direto ou proxy) com timeouts e retries |
| `InvestigationRouter` | `app/investigation/router.py` | componente-novo / contrato-novo | Expõe somente `POST /briefings/{research_id}/investigate` (consulta de status fica fora desta feature) |
| `BriefingRouter` | `app/briefing/router.py` | regra-alterada / contrato-alterado | Troca `id` por `research_id`, instancia `Research` antes do briefing, bloqueia reopen pós-aprovação e troca PATCH por feedback `{"note"}` |
| `ResearchService` | `app/services/research.py` | regra-alterada | Adaptação para o novo enum de status `ResearchStatus` unificado |

### Âncoras reais e recorte

`architecture.md`, `domain.md`, `c4-context.md`, `state-machines.md`, `dependencies.md` e `code-analysis.md` estão ausentes na extração. Não representam regras herdadas verificadas. Âncoras físicas: `_reversa_sdd/prd.md`, componente **Módulo backend de briefing** em `_reversa_sdd/sdd/briefing.md` e **Módulo de Briefing (Backend)** em `_reversa_sdd/addenda/001-modulo-briefing.md`. O adendo da 001 registra contratos anteriores; §2.1 e Q1 da 002 autorizam substituição de edição manual, reabertura e identificador público. A tabela acima aponta arquivos reais de código, não componentes inventados de uma extração inexistente.

Arquivos afetados adicionais: `app/briefing/schemas.py`, `app/briefing/storage.py`, `app/briefing/domain.py`, `app/briefing/service.py`, `app/routers/research.py`, `app/main.py`, `app/services/pipeline/writer.py`, `app/services/webhook.py`, migração `0007`, testes de briefing/investigação e três suítes de regressão do baseline. Alvos exatos e sprints constam de `actions.md`. Templates locais e hooks ausentes; fallback canônico apenas lido, conforme `investigation.md`.

---

## 6. Delta no modelo de dados

- **Nova tabela `research_step_results`**: armazena os resultados das personas (`id`, `research_id`, `step_id`, `step_title`, `result`, `used_urls`, `read_urls`, `worker`, `status`, `created_at`).
- **Novo enum de status em `Research.status`**: `PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`.
- **Novos status em `ResearchPoint.status`**: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`, `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`.
- **Backfill em migração Alembic**: instancia linhas em `research` para briefings existentes e copia pontos de briefings aprovados para `research_points`.
- Detalhe completo em: `_reversa_forward/002-investigacao-personas/data-delta.md`.

---

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `POST /briefings/{research_id}/investigate` | HTTP | `_reversa_forward/002-investigacao-personas/interfaces/investigate.md` |
| `Briefings API (Contrato Atualizado)` | HTTP | `_reversa_forward/002-investigacao-personas/interfaces/briefings.md` |

---

## 8. Plano de migração

1. **Alembic Migration (versão `0007_investigation_step_results_and_status`)**:
   - Criação da tabela `research_step_results` com FKs para `research.id` e `research_points.id`.
   - Atualização da coluna `research.status` (conversão segura de tipos/strings).
   - Migração de dados legados de `research.status` para o novo enum.
   - Backfill: para cada registro existente em `briefings`, criar registro correspondente em `research` com o mesmo UUID; para briefings com status `approved`, instanciar os pontos em `research_points` como `SCRAPER_PENDING`.
2. **Atualização da Feature 001**:
   - Atualizar `POST /briefings` para criar `Research` antes de gerar o rascunho.
   - Atualizar schemas para retornar `research_id` no lugar de `id`.
   - Atualizar `POST /briefings/{research_id}/approve` para instanciar pontos em `research_points`.
   - Substituir `PATCH /briefings/{research_id}` (lista de pontos) por feedback `{"note"}` (3 a 4000 caracteres): Scout roda Jina de novo com tema + feedback e gera nova versão; resposta síncrona 200.
   - `POST /briefings/{research_id}/reopen` em briefing aprovado passa a retornar 409; ajustar `tests/test_briefing_lifecycle.py`, `tests/test_briefing_lifecycle_qa.py` e `tests/test_briefing_acceptance.py`.
   - Ajustar os 184 testes unitários da 001 para validar o novo contrato e manter 100% de aprovação.
3. **Implementação do Módulo `app/investigation/`**:
   - Schemas, Tools, Worker, Service e Router.
   - Registro do router no `app/main.py`.
   - Registro de hook de inicialização do FastAPI para retomar workers em `SCRAPER_IN_PROGRESS`.

---

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Rate limit (HTTP 429) no gateway LLM pelo disparo de 20-28 conexões | Alto | Média | Tratamento nativo com backoff exponencial (2s, 4s) e respeito estrito ao header `Retry-After`. Resiliência parcial evita derrubar o lote. |
| Timeout na API da Jina Search | Médio | Média | Timeout de 90s por chamada, timeout global de 600s por worker, 3 tentativas totais (1 inicial + 2 retries, backoff 2s/4s) e isolamento por worker. |
| Modelo emite JSON final com sintaxe inválida | Médio | Média | Harness realiza até 3 chamadas corretivas dedicadas instruindo o modelo a corrigir o JSON. |
| Reinício do container interrompe workers em andamento | Médio | Baixa | Startup inspeciona pesquisa em `SCRAPER` com pontos `SCRAPER_IN_PROGRESS` e retoma somente personas sem linha gravada. |

---

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Nove falhas baseline de `8bfd529` e um teste sensível a ordem/DNS corrigidos, sem dispensa (Q2)
- [ ] Aprovação/revisão legada não agenda `schedule(run_research)`; disparo ocorre exclusivamente por `/briefings/{research_id}/investigate` (Q1)
- [ ] Migração Alembic `0007` executada com sucesso
- [ ] 184 testes da Feature 001 adaptados ao novo contrato e 100% passando
- [ ] Testes de unidade e integração do módulo `app/investigation/` implementados e verdes
- [ ] Teste E2E de disparo assíncrono e paralelismo das 4 personas aprovado
- [ ] Auditoria Reversa (`/reversa-audit` e `/reversa-quality`) sem inconformidades

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-12 | Versão inicial gerada por `/reversa-plan` | reversa |
| 2026-10-13 | Delta reconciliado com esclarecimentos Q1–Q10; plano futuro separado do estado de coding e dos gates abertos | reversa-plan |
