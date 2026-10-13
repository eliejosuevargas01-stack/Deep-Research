# Relatório de Auditoria Cruzada (Cross-Check): Feature 002 (Rodada 2)

> Identificador da feature: `002-investigacao-personas`  
> Data: `2026-10-12` (auditoria pós-saneamento)  
> Artefatos analisados:
> - [`requirements.md`](../requirements.md)
> - [`roadmap.md`](../roadmap.md)
> - [`actions.md`](../actions.md)
> - [`data-delta.md`](../data-delta.md)
> - [`interfaces/briefings.md`](../interfaces/briefings.md)
> - [`interfaces/investigate.md`](../interfaces/investigate.md)
> - [`onboarding.md`](../onboarding.md)
> - [`investigation.md`](../investigation.md)
> - Princípios: `.reversa/principles.md` (Princípio IV emendado)
> - Código real: `app/models/domain_models.py`, `app/briefing/*`, `app/routers/research.py`, `app/main.py`, `app/services/*`, `alembic/versions/*`, `tests/*`, `frontend/src/*`

---

## 1. Resumo Executivo e Contagem de Achados

| Severidade | Quantidade |
|------------|------------|
| **CRITICAL** | 0 |
| **HIGH** | 0 |
| **MEDIUM** | 0 |
| **LOW** | 1 |
| **TOTAL** | **1** |

**Veredito:** **APROVADO**  
Todos os 10 apontamentos da Rodada 1 (`A001` a `A010`) foram plenamente saneados. Não existem bloqueios conceituais, ciclos de dependência, quebras de regras ativas ou incongruências de dados. O único achado remanescente é uma contagem cosmética no resumo de ações (LOW), sem impacto operacional. O plano está liberado para execução via `/reversa-coding`.

---

## 2. Revalidação dos Achados da Rodada 1

| ID Anterior | Severidade | Eixo | Status Rodada 2 | Evidência de Resolução |
|---|---|---|---|---|
| `A001` | CRITICAL | Sanidade do actions | **SANADO** | Cadeia de dependências recalculada para 9 passos sequenciais (`T001 -> T002 -> T008 -> T010 -> T011 -> T012 -> T013 -> T018 -> T020`). Aresta falsa `T012 -> T014` eliminada (`T014` agora depende diretamente de `T002`). |
| `A002` | HIGH | Cobertura | **SANADO** | `app/briefing/schemas.py` e `app/briefing/storage.py` foram expressamente contemplados no escopo de `T014`, cobrindo o retorno de `research_id`, criação da pesquisa e persistência de pontos aprovados. |
| `A003` | HIGH | Sanidade do actions | **SANADO** | Separação estrita dos arquivos alvo de Briefing: `T015` altera exclusivamente `app/briefing/router.py` (paths `{research_id}` e bloqueio 409) e `T016` altera `app/briefing/service.py` (lógica de geração síncrona do novo PATCH). |
| `A004` | HIGH | Sanidade do actions | **SANADO** | Conflito sobre `app/main.py` eliminado: `T017` atua estritamente em `app/routers/research.py` e `app/services/pipeline/`, sem tocar no lifespan. Toda a alteração de lifespan e registro de rotas foi centralizada em `T018`. |
| `A005` | HIGH | Cobertura / Sanidade | **SANADO** | Escopo dos 184 testes detalhado em `T019`: especificados os 20 arquivos em `tests/test_briefing*.py` e os arquivos de regressão legados afetados pelo enum (`tests/test_backend.py`, `tests/test_e2e_criteria.py`). |
| `A006` | HIGH | Coerência com legado | **SANADO** | Frontend web formalmente excluído do escopo da Feature 002 em `actions.md:6` e `actions.md:87`, postergado para sprint dedicada. |
| `A007` | MEDIUM | Consistência | **SANADO** | Regra de resolução de modelos com fallback para `scout` (RN-10) foi expressamente incluída nas especificações de `T004` e `T010`. |
| `A008` | MEDIUM | Artefatos desatualizados | **SANADO** | `investigation.md:1` recebeu nota formal de contexto histórico esclarecendo que o documento é preliminar e foi superado pelas deliberações de `requirements.md`. |
| `A009` | LOW | Consistência | **SANADO** | Parâmetro de rota em `interfaces/briefings.md` padronizado para `{research_id}` em todos os endpoints (`GET`, `PATCH`, `POST /approve`, `POST /reopen`). |
| `A010` | LOW | Consistência | **SANADO** | `onboarding.md:107` corrigido para utilizar a função SQL compatível `json_array_length(used_urls::json)`. |

---

## 3. Tabela de Achados Atuais (Rodada 2)

| ID | Severidade | Eixo | Descrição | Onde está | Recomendação |
|---|---|---|---|---|---|
| `A001` | **LOW** | Sanidade do actions | Divergência cosmética no resumo de métricas: a tabela informa 7 ações paralelizáveis (`[//]`), mas existem 8 ações com a marcação no corpo do documento (`T003`, `T004`, `T005`, `T006`, `T009`, `T014`, `T017`, `T021`). | `actions.md:13` | Ajustar o valor da métrica na tabela de resumo de 7 para 8. Não bloqueia execução. |

---

## 4. Detalhamento de Achados Críticos e Altos

*Nenhum achado de severidade CRITICAL ou HIGH detectado nesta rodada.*

---

## 5. Itens Verificados e Aprovados (Tabela de Conformidade)

### 5.1 Eixo 1: Cobertura
- [x] **Requisitos Funcionais no Roadmap (13/13)**:
  - RF-01 (Unificação `research_id`) coberto em D-01 e Roadmap Seção 8.
  - RF-02 (Instanciação de pontos em `research_points` em aprovação) coberto em Roadmap Seção 8.
  - RF-03 (Endpoint `POST /investigate` HTTP 202) coberto em D-10 e Roadmap Seção 7.
  - RF-04 (Fan-out de N × 4 workers sob `asyncio.gather`) coberto em D-04.
  - RF-05 (Loop LiteLLM RAM com teto de 3 buscas e parada voluntária) coberto em D-05 e D-07.
  - RF-06 (Adaptador Jina POST direto/proxy com timeout 90s) coberto em D-06.
  - RF-07 (Interceptação de todas as URLs em `read_urls`) coberto em D-03 e Roadmap Seção 6.
  - RF-08 (Até 3 retries técnicos e até 3 chamadas de reparo de JSON) coberto em D-08 e D-09.
  - RF-09 (Persistência append-only em `research_step_results`) coberto em D-03 e Roadmap Seção 6.
  - RF-10 (Atualização de status dos passos e da pesquisa) coberto em Roadmap Seção 1 e 8.
  - RF-11 (Migração Alembic 0007, limpeza de `SEARCH_SUCCESS` e backfill) coberto em Roadmap Seção 6 e 8.
  - RF-12 (Readequação dos contratos da 001: `research_id`, 409 reopen e novo PATCH por feedback) coberto em Roadmap Seção 5 e 8.
  - RF-13 (Retomada automática no startup do FastAPI) coberto em D-11 e Roadmap Seção 8.
- [x] **Decisões Técnicas no Actions (11/11)**:
  - D-01 mapeado em T001, T002, T014.
  - D-02 mapeado no pacote `app/investigation/` (T003, T004, T008..T013).
  - D-03 mapeado em T001, T002, T011.
  - D-04 mapeado em T012.
  - D-05 mapeado em T009, T010.
  - D-06 mapeado em T006, T008.
  - D-07 mapeado em T007, T010.
  - D-08 mapeado em T006, T008, T010.
  - D-09 mapeado em T007, T010.
  - D-10 mapeado em T003, T013.
  - D-11 mapeado em T018.
- [x] **Cenários Gherkin Cobertos (13/13)**:
  - Disparo da investigação e validação de 20 workers: T013, T020.
  - Rejeição de re-disparo com HTTP 409: T013, T020.
  - Parada voluntária antecipada do worker: T007, T010.
  - Bloqueio de 4ª busca no teto de 3: T007, T010.
  - Retentativas técnicas sem desconto de cota: T006, T007, T008, T010.
  - Separação estrita de `read_urls` e `used_urls`: T006, T008, T010, T011.
  - Resiliência em falha de worker isolado e incremento de `attempt_count`: T007, T010, T011, T012.
  - Conclusão global bem-sucedida (>= 1 sucesso -> `AUDIT`): T012, T020.
  - Falha global de 100% dos pontos (`FAILED`): T012, T020.
  - Bloqueio de reabertura pós-aprovação (HTTP 409): T015, T019.
  - Edição de briefing por feedback textual com novo rascunho Scout: T016, T019.
  - Falha do Scout durante PATCH (HTTP 500/502 e status `FAILED`): T016, T019.
  - Retomada de workers incompletos no startup: T018, T020.

### 5.2 Eixo 2: Consistência
- [x] **Terminologia e Nomenclatura**: Uniformidade absoluta em nomes de entidades, tabelas e enums (`research_step_results`, `ResearchStatus`, `ResearchPoint.status`, personas `historian`, `skeptic`, `pragmatist`, `futurist`, campos `used_urls` e `read_urls`).
- [x] **Valores de Status**:
  - `Research.status`: `PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED` (idêntico em requirements, roadmap, data-delta, actions).
  - `ResearchPoint.status`: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING` (status `SEARCH_SUCCESS` eliminado de todos os documentos).
- [x] **Parâmetros de Rota**: Padronização completa em `{research_id}` em `interfaces/briefings.md`, `interfaces/investigate.md` e `onboarding.md`.
- [x] **Existência de Identificadores**: Todos os identificadores referenciados (RF-01..RF-13, RN-01..RN-14, D-01..D-11, T001..T021) existem e estão documentados.

### 5.3 Eixo 3: Coerência com o Legado e Princípios
- [x] **Princípio IV (.reversa/principles.md)**: Emenda registrada formalmente em `.reversa/principles.md:33`, documentando a concorrência irrestrita com `asyncio.gather` para até 28 workers governada por timeouts rígidos e retries.
- [x] **Princípios I, II e III**: Respeito estrito à rastreabilidade de citações em fontes lidas, sanitização de erros sem vazamento de chaves ou prompts em banco/logs e degradação graciosa com tolerância a falhas parciais.
- [x] **Compatibilidade de Banco**: Uso de tipos portáteis (`sa.Uuid`, `sa.JSON`, `sa.DateTime(timezone=True)`) mantendo paridade entre testes em SQLite e produção em PostgreSQL.
- [x] **Isolamento de Escopo do Frontend**: Frontend formalmente postergado, evitando quebras acidentais de build na execução do backend da Feature 002.

### 5.4 Eixo 4: Sanidade do Actions
- [x] **Grafo de Dependências Acíclico (DAG)**: Verificação topológica confirma ausência de ciclos. Todas as dependências apontam estritamente para ações anteriores no pipeline.
- [x] **Isolamento de Arquivos Alvo**: Todas as 21 ações possuem arquivos alvo únicos e bem definidos. Tarefas marcadas como paralelizáveis (`[//]`) operam em arquivos completamente distintos, sem sobreposição de escrita simultânea.
- [x] **Maior Cadeia Crítica**: 9 passos sequenciais de código (`T001 -> T002 -> T008 -> T010 -> T011 -> T012 -> T013 -> T018 -> T020`).

---

## 6. Escopo Fora do Recorte da Auditoria

1. Nenhuma execução de migrações ou gravações em banco de dados ativo.
2. Nenhuma alteração efetuada em código-fonte, testes ou nos documentos de especificação analisados.
3. Não foram lidos arquivos `.env` nem credenciais secretas.
4. Nenhuma chamada externa a provedores de rede (Jina Search, LiteLLM).

---

## 7. Conclusão e Recomendação

O ciclo de saneamento foi concluído com sucesso. Todos os impedimentos da Rodada 1 foram eliminados com precisão técnica. A Feature 002 está aprovada pelo auditor leitor e apta para a fase de implementação de código.

**Próximo passo recomendado:** Executar `/reversa-coding`.
