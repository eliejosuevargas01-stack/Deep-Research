# Legacy Impact — Feature 002: Investigação de Personas

| Arquivo | Tipo de Mudança | Impacto | Motivo | Evidência |
|---------|----------------|---------|--------|-----------|
| app/models/domain_models.py | alteração | alto | ResearchStatus unificado (SCRAPER, BRIEFING, PENDING_APPROVAL, DONE, FAILED); novo ResearchStepResult | `git diff HEAD -- app/models/domain_models.py` linhas 45-62, 89-98 |
| app/routers/research.py | alteração | alto | Endpoint GET /research/{id} aceita status SCRAPER/BRIEFING/PENDING_APPROVAL; validação de transição | `git diff HEAD -- app/routers/research.py` linhas 34-58, 112-135 |
| app/services/research.py | alteração | alto | run_research aceita SCRAPER como entrada; grava FAILED em exceção; step_results persistido | `git diff HEAD -- app/services/research.py` linhas 28-42, 67-89, 156-178 |
| app/services/pipeline/writer.py | alteração | médio | Estados DONE/FAILED no writer; grava step_results final | `git diff HEAD -- app/services/pipeline/writer.py` linhas 18-35, 72-85 |
| app/services/webhook.py | alteração | médio | Normaliza status DONE vindo do webhook externo para ResearchStatus.DONE | `git diff HEAD -- app/services/webhook.py` linhas 41-55 |
| app/briefing/domain.py | alteração | alto | Ajuste de validações: PATCH de briefing por feedback {"note": str} e alinhamento de research_id | `git diff HEAD -- app/briefing/domain.py` |
| app/briefing/router.py | alteração | alto | Rotas /briefings: reopen 409 em briefing aprovado, PATCH por feedback note (3..4000) com Scout | `git diff HEAD -- app/briefing/router.py` |
| app/briefing/schemas.py | alteração | alto | FeedbackUpdateSchema com note obrigatória; campos canônicos | `git diff HEAD -- app/briefing/schemas.py` |
| app/briefing/service.py | alteração | alto | Reopen bloqueado com 409 em aprovado; revisão Scout via feedback note | `git diff HEAD -- app/briefing/service.py` |
| app/briefing/storage.py | alteração | médio | Persistência com chave research_id e suporte aos novos status | `git diff HEAD -- app/briefing/storage.py` |
| app/main.py | alteração | alto | Router investigation incluído; recovery RN-11 (retry briefing falho) | `git diff HEAD -- app/main.py` linhas 18-25, 42-58 |
| tests/test_backend.py | alteração | médio | Testes novos para status SCRAPER/BRIEFING/PENDING_APPROVAL; mock step_results | `git diff HEAD -- tests/test_backend.py` linhas 142-189, 234-267 |
| tests/test_e2e_criteria.py | alteração | médio | Cenários E2E investigation→briefing→approval; valida step_results | `git diff HEAD -- tests/test_e2e_criteria.py` linhas 67-112 |
| tests/test_briefing_acceptance.py | adição | médio | Testes aceitação briefing: create, reopen 409, feedback PATCH | `git diff HEAD -- tests/test_briefing_acceptance.py` (arquivo novo) |
| tests/test_briefing_api.py | adição | médio | Testes API briefing: valida schemas, 409, 422 | `git diff HEAD -- tests/test_briefing_api.py` (arquivo novo) |
| tests/test_briefing_domain.py | adição | médio | Testes domínio briefing: validações RN-07, RN-09, RN-11 | `git diff HEAD -- tests/test_briefing_domain.py` (arquivo novo) |
| tests/test_briefing_lifecycle.py | adição | médio | Testes ciclo de vida: approve, reject, reopen | `git diff HEAD -- tests/test_briefing_lifecycle.py` (arquivo novo) |
| tests/test_briefing_lifecycle_qa.py | adição | baixo | QA extra: edge cases briefing | `git diff HEAD -- tests/test_briefing_lifecycle_qa.py` (arquivo novo) |
| tests/test_briefing_schemas.py | adição | baixo | Validação schemas BriefingCreate/Update/Response | `git diff HEAD -- tests/test_briefing_schemas.py` (arquivo novo) |
| tests/test_briefing_storage_qa.py | adição | baixo | QA storage: índice research_id, concorrência | `git diff HEAD -- tests/test_briefing_storage_qa.py` (arquivo novo) |
| alembic/versions/0007_investigation_step_results_and_status.py | adição | alto | Migração: tabela research_step_results; enum ResearchStatus expandido; FK briefing.research_id | `cat alembic/versions/0007_investigation_step_results_and_status.py` linhas 1-194 |

---

## Riscos Residuais

| Risco | Estado | Detalhe |
|-------|--------|---------|
| T001 — SEARCH_SUCCESS não migrado | aberto | Aguarda correção por T024; enum ResearchStatus ainda contém valor legado não usado |
| T012/T022 — Credenciais LLM no service | aberto | Variáveis de ambiente LLM_API_KEY, LLM_MODEL lidas direto em app/services/research.py; não injetadas via config |
| Retomada sem duplicar step_results | aberto | Lógica de resume em app/services/research.py (linha 67-89) não verifica step_results existentes antes de append |
| app/investigation/* | **estado em correção** | Sibling ativo edita pipeline investigation; legado-impact pode divergir |
| app/main.py | **estado em correção** | Sibling ativo ajusta recovery RN-11 e routers; diff pode mudar |
| alembic/versions/0007_investigation_step_results_and_status.py | **estado em correção** | Sibling ativo pode revisar migração (down, índices, constraints) |