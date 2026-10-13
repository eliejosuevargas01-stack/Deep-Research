# Roadmap: Investigação Paralela por Personas (Workers)

> Identificador: `002-investigacao-personas`
> Data: `2026-10-12`
> Requirements: `_reversa_forward/002-investigacao-personas/requirements.md`
> Confidência: 🟢 CONFIRMADO (todas as decisões deliberadas diretamente pelo operador sem inferências)

---

## 1. Resumo da abordagem

A Feature 002 implementa a investigação concorrente dos pontos aprovados no briefing através de 4 personas canônicas (**historian**, **skeptic**, **pragmatist**, **futurist**). Para $N$ pontos aprovados (3 a 7), são instanciadas exatamente $N 	imes 4$ execuções simultâneas em background (`asyncio.gather` irrestrito).
Cada worker executa um loop de reflexão com LiteLLM nativo e memória conversacional em RAM, invocando a ferramenta Jina Search (via POST direto ou proxy customizado). O modelo tem teto rígido de até 3 consultas de busca por ponto, podendo encerrar antecipadamente. O harness intercepta e persiste todas as URLs retornadas pela Jina em `read_urls`, enquanto o modelo fornece `result` e `used_urls`. Os resultados são salvos em `research_step_results` com status `AUDIT_PENDING` (ou `FAILED`), atualizando os passos para `AUDIT_PENDING` e a pesquisa para `AUDIT`.

---

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| **I. Rastreabilidade Factual Estrita (Verbatim Citation)** | O harness captura a integridade de todas as URLs consultadas na Jina (`read_urls`) e o modelo referencia explicitamente as URLs utilizadas (`used_urls`), preparando os dados para a auditoria factual futura (Feature 003). | Respeita |
| **II. Defesa de Privacidade e Isolamento de Prompts** | Chaves de API e segredos nunca são persistidos em logs, tabelas de resultado ou mensagens do modelo. Mensagens de erro em falhas definitivas são sanitizadas antes de persistidas em `research_step_results`. | Respeita |
| **III. Resiliência por Degradação Graciosa e Limites Rígidos** | Falha de uma persona isolada não interrompe os outros workers (`return_exceptions=True`). Timeout de 90s e 3 tentativas com backoff exponencial ou `Retry-After` para chamadas externas. Se todos os workers de um passo falharem, o passo fica `SCRAPER_FAILED`, mas a pesquisa segue para `AUDIT` se outro passo tiver sucesso. | Respeita |
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
| **D-11** | Retomada automática pós-reinício | Servidor ao subir detecta passos em `SCRAPER_IN_PROGRESS` e retoma apenas os workers sem resultado | Perder execuções em andamento ou marcar tudo como falha | 🟢 |

---

## 4. Premissas

Nenhuma premissa inferida. Todos os pontos materiais, dúvidas e detalhes foram deliberados e respondidos pelo operador nas sessões de esclarecimento.

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
| Timeout na API da Jina Search | Médio | Média | Timeout de 90s por chamada, timeout global de 600s por worker, até 3 retries dedicados e isolamento por worker. |
| Modelo emite JSON final com sintaxe inválida | Médio | Média | Harness realiza até 3 chamadas corretivas dedicadas instruindo o modelo a corrigir o JSON. |
| Reinício do container interrompe workers em andamento | Médio | Baixa | Tarefa de inicialização no FastAPI varre pesquisas em `SCRAPER_IN_PROGRESS` e retoma personas sem resultado gravado. |

---

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
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
