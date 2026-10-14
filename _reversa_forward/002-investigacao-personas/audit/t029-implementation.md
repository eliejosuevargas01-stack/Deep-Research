# Relatório de Implementação T029: Compatibilização dos Testes Async com AnyIO

> **Natureza do Artefato:** Relatório de implementação técnica do desenvolvedor executor (não constitui auditoria de aceitação independente nem encerra a Feature 002).

## 1. Escopo e Responsabilidade Única

Ação T029 da Feature 002 (`002-investigacao-personas`): compatibilizar os quatro testes assíncronos legados distribuídos entre `tests/integration/test_full_pipeline.py` e `tests/unit/workers/test_workers_and_auditor.py` para execução com o runner nativo do AnyIO já instalado no ambiente, sem adicionar novas dependências nem enfraquecer verificações comportamentais existentes.

## 2. Arquivos Modificados e Linhas

### 2.1. `tests/unit/workers/test_workers_and_auditor.py`
- **Linhas 10-13:** Adicionada fixture local `anyio_backend() -> str: return "asyncio"` para vincular o runner do AnyIO sem depender de conftest global.
- **Linhas 27, 40, 54:** Substituído `@pytest.mark.asyncio` por `@pytest.mark.anyio` nas três funções de teste async (`test_scout_worker`, `test_persona_workers`, `test_writer_agent`). O teste síncrono `test_auditor_agent_verdict` foi mantido inalterado.

### 2.2. `tests/integration/test_full_pipeline.py`
- **Linhas 37-43:** Adicionada fixture local `anyio_backend() -> str: return "asyncio"` e atualizado o decorador da função `test_full_pipeline_e2e_integration` de `@pytest.mark.asyncio` para `@pytest.mark.anyio`.
- **Linhas 91-98:** Atualizada expectativa de estado pós-scouting de `pending_approval` para `PENDING_APPROVAL` (normativa T023).
- **Linhas 102-109:** Atualizada expectativa de status retornado pela aprovação do briefing de `approved` para `SCRAPER` (normativa T023).
- **Linhas 188-193:** Mantido monkeypatch dos estágios do pipeline e adicionado patch explícito em `app.routers.research.dispatch_callback` além de `app.services.webhook.dispatch_callback` para garantir cobertura de chamadas locais e importações diretas sem vazamento de rede.
- **Linhas 192-194:** Disparo explícito de `run_research` via `client.portal.call(run_research, rid)`, refletindo a mudança normativa de T017 / Q1-D12 (a aprovação do briefing não agenda mais o pipeline automaticamente).
- **Linhas 198-208:** Atualizada condição de término do loop e asserção final de banco de `completed` para `DONE` (normativa T023).

## 3. Comandos Executados e Resultados

### 3.1. Baseline Inicial (Preflight)
- **Comando:** `python3 -B -m pytest tests/integration/test_full_pipeline.py tests/unit/workers/test_workers_and_auditor.py -q -p no:cacheprovider --tb=short`
- **Exit Code:** `1`
- **Resultado:** 4 failed, 1 passed, 5 warnings (erros `async def functions are not natively supported` e marcas `asyncio` desconhecidas).

### 3.2. Verificação Principal T029
- **Comando:** `python3 -B -m pytest tests/integration/test_full_pipeline.py tests/unit/workers/test_workers_and_auditor.py -q -p no:cacheprovider --tb=short`
- **Exit Code:** `0`
- **Resultado:** 5 passed, 1 warning (Starlette testclient deprecation warning upstream) em ~4.2s.

### 3.3. Verificação de Não-Regressão com C5
- **Comando:** `python3 -B -m pytest tests/integration/test_full_pipeline.py tests/unit/workers/test_workers_and_auditor.py tests/test_backend.py::test_full_pipeline_with_controlled_sources_and_models -q -p no:cacheprovider --tb=short`
- **Exit Code:** `0`
- **Resultado:** 6 passed, 1 warning em ~5.5s.

### 3.4. Verificação de Whitespace e Higiene Git
- **Comando:** `git diff --check`
- **Exit Code:** `0` (limpo, sem trailing whitespace ou conflitos).

## 4. Hashes Criptográficos dos Artefatos de Teste

| Arquivo | Algoritmo | Hash SHA-256 |
|---|---|---|
| `/root/projects/deep-research/tests/integration/test_full_pipeline.py` | SHA-256 | `b30cc1772af8254f09179f3038b339665d75972763a6d7330614077ffd156e0f` |
| `/root/projects/deep-research/tests/unit/workers/test_workers_and_auditor.py` | SHA-256 | `613d19ebbb0f132f841cc516f064500a0f8c6faadcd801272690282be7ffbb93` |

## 5. Limites e Ações Restantes da Feature 002

1. **T029 Concluída:** Testes assíncronos legados agora rodam 100% verdes com AnyIO nativo e respeitam os estados canônicos de T023 (`PENDING_APPROVAL`, `SCRAPER`, `DONE`) e o agendamento explícito de T017.
2. **Ações Pendentes:**
   - **T035:** Ações de persistência e validação pendentes de integração.
   - **T019:** Auditoria formal e fechamento de requisitos da Feature.
   - **T030:** Registro final e consolidação de rastros pelo parent agent.
3. Não houve alteração em arquivos proibidos (`actions.md`, `progress.jsonl`, `app/**`, `requirements.txt`).
