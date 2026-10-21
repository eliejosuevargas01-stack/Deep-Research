# Relatório de QA Independente: Coleta, Worker e Dados (S09-S12)

Data: 2026-10-21  
Feature: `005-convergencia-pipeline`  
Ação: T015 / S15  
Perfil: `qa-specialist`  
Veredicto: **APROVADO** 🟢

---

## 1. Resumo Executivo

Este relatório atesta a verificação independente de qualidade das entregas do recorte **Coleta, Worker e Dados** (tarefas S09 a S12), cobrindo:
1. `S05` / `S09`: Ferramenta Jina Search (`app/services/search.py`, `app/investigation/tools.py`).
2. `S07` / `S10`: Persona Worker e validação de citações verbatim (`app/investigation/schemas.py`, `app/investigation/worker.py`).
3. `S08` / `S11`: Modelo de dados, persistência por rodada e barreira de 4 análises (`app/models/domain_models.py`, `app/investigation/storage.py`, `app/investigation/service.py`).
4. `S12`: Ciclo de vida da migração Alembic 0008 em SQLite e PostgreSQL efêmero 16 (`alembic/versions/0008_investigation_rounds_and_merges.py`, `tests/investigation/test_round_migration.py`).

Todas as 4 suítes executaram com 100% de sucesso (84/84 testes aprovados), sem erros de regressão ou vazamento de estado.

---

## 2. Matriz de Execução de Testes Automatizados

Ambiente de execução: Python 3.14.7, pytest 9.1.1, isolamento com `aiosqlite:///:memory:` e container Docker efêmero `postgres:16-alpine`.

| Suíte de Testes | Frente | Total Testes | Pass | Fail | Duração | Exit Code |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `tests/investigation/test_jina_tool.py` | Coleta Jina 10 resultados, HTMLParser stdlib, SSRF guard | 31 | 31 | 0 | 1.169s | `0` |
| `tests/investigation/test_persona_worker.py` | Busca prévia obrigatória, teto 3 queries, citação verbatim | 38 | 38 | 0 | 13.968s | `0` |
| `tests/investigation/test_round_storage.py` | Barreira 4 personas, persistência atômica de merge e rodada | 11 | 11 | 0 | 1.033s | `0` |
| `tests/investigation/test_round_migration.py` | Alembic 0008 clean/populated/downgrade/reupgrade (SQLite + PG16) | 4 | 4 | 0 | 6.170s | `0` |
| **TOTAL GERAL** | **Recorte Coleta-Worker-Dados (S09–S12)** | **84** | **84** | **0** | **22.340s** | **`0`** |

---

## 3. Verificação Factual dos Critérios de Aceite

### 3.1 Coleta Jina (RF-501 / RN-501)
- **10 páginas por busca**: Comprovado em `app/investigation/tools.py:135` (`"num": 10`) e `tools.py:249`. Testado em `test_tool_requests_10_results_by_default`.
- **Limpeza HTML conservadora**: Implementada via `_JinaHTMLCleaner` (`html.parser.HTMLParser` nativo da stdlib), removendo estritamente tags de ruído estrutural (`header`, `nav`, `script`, `style`, `footer`, `aside`) e preservando integralmente o corpo textual.
- **Proteção anti-SSRF**: Validação estrita de IP em `tools.py:45-70` contra faixas privadas (`is_private`, loopback, multicast, link-local) com cache LRU (`@lru_cache(maxsize=1024)`) para evitar gargalos de latência DNS.
- **Sem corte silencioso**: O conteúdo capturado é retornado na íntegra no campo `body` sem truncamentos arbitrários (`tools.py:159`).

### 3.2 Persona Worker e Citações (RF-502 / RF-503 / RN-502 / RN-503)
- **Busca prévia mandatória**: Comprovado em `worker.py:468`. Qualquer tentativa do modelo LLM de entregar JSON de síntese sem ter disparado previamente a ferramenta `jina_search` é rejeitada com mensagem de erro explícita e reorientação de fluxo.
- **Teto estrito de queries**: Comprovado em `worker.py:364-370`. O worker permite no máximo 3 consultas de busca por turno de persona. Consultas repetidas são deduplicadas automaticamente via `_url_key`.
- **Verificação verbatim estrita**: Implementada em `worker.py:480-488` (`_quote_supported`). As citações (`exact_quote`) informadas no payload devem ser substrings exatas e comprovadas nos corpos dos documentos efetivamente entregues pelas buscas da rodada. Citações forjadas ou aproximadas são sumariamente rejeitadas.
- **Tipagem de Citação**: Schema `CitationItem` em `app/investigation/schemas.py:40-83` garante strings não vazias e sanitizadas para `claim`, `exact_quote`, `source_url` e `source_title`.

### 3.3 Modelo de Dados, Storage e Barreira (RF-504 / RN-504 / RN-508)
- **Barreira de 4 personas por rodada**: Em `app/investigation/storage.py:97-116` (`check_merge_barrier`), o ponto de pesquisa só avança para status `AUDIT_PENDING` quando todas as 4 personas configuradas tiverem persistido suas análises na rodada corrente.
- **Persistência de Merge Atômica**: `InvestigationMerge` gravado via `save_investigation_merge` (`storage.py:118-144`) com constraint única em `(research_id, step_id, round)`.
- **Incremento de rodada**: `current_round` é gerenciado e propagado no fluxo de investigação (`service.py:120-145`), incrementando em novos ciclos de investigação.

### 3.4 Migração Alembic 0008 (D e data-delta §5)
- **Compatibilidade DDL**: Colunas `investigation_round` em `research_points` e `round` em `research_step_results` criadas como `nullable=True`, preservando integridade de dados pré-existentes.
- **Reversibilidade Provada**: Downgrade para `0007` e re-upgrade para `0008` testados e confirmados sem perda de registros em tabelas pai (`research`, `research_points`, `reports`, `evidences`).
- **Validação em PostgreSQL Real**: Teste `test_postgres_ephemeral_clean_and_populated_lifecycle` validou clean install e base populada contra instância real `postgres:16-alpine`, confirmando unique constraints, integridade referencial e retenção de registros legados.

---

## 4. Veredicto Final

**APROVADO** 🟢

O recorte S09–S12 cumpre integralmente os contratos de engenharia e os requisitos da Feature 005. O pipeline está apto a prosseguir para a sprint S16 (implementação de auditoria por merge e rodada T016).
