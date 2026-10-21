# Inspeção Profunda: Entrypoints, Fixtures, Callers e Integração Total (T028 / S28)

Data: 2026-10-21  
Feature: `005-convergencia-pipeline`  
Ação: T028 / S28  
Lentes aplicadas: Ciclo real de execução (sem mocks de serviço de domínio), Segurança outbound e SSRF, Integridade dos contratos HTTP (interfaces/pipeline-http.md), Ausência de modificações em arquivos protegidos e Ausência de dependências/frontend novos.

---

## 1. Escopo Inspecionado

Arquivos de produto e serviços integrados:
- `app/briefing/router.py` (entrypoint modular POST /briefings, PATCH /briefings/{id}, POST /briefings/{id}/investigate)
- `app/briefing/service.py` (geração síncrona, revisão com autoaprovação, decisão única)
- `app/routers/research.py` (entrypoint `/api/research`, `/api/research/{id}/resume`, `/api/reports/{id}`, `/api/reports/{id}/retry-callback`)
- `app/services/research.py` (adaptador modular `run_research` -> `InvestigationService`, eventos SSE, scheduler)
- `app/investigation/service.py` (ciclo reativo por lotes topológicos, barreira de merge committed, CAS para WRITE)
- `app/services/pipeline/writer.py` (agregação de bundles Evidence e InvestigationMerge, guardrails de limitação e proposta didática)
- `app/services/webhook.py` e `app/tools/outbound.py` (validação anti-SSRF de callback B2B e outbound guard)

Arquivos de teste e suítes de validação:
- `tests/integration/test_pipeline_convergence_http.py` (novo: prova real de ponta a ponta sem mock de serviços de domínio)
- `tests/integration/test_full_pipeline.py` (adaptado: ciclo completo do pipeline legado/modular)
- `tests/investigation/test_investigation_e2e.py` (resiliência parcial, esgotamento e ciclo de personas)
- `tests/test_briefing_api.py`, `tests/test_briefing_generation_boundaries_qa.py`, `tests/test_briefing_lifecycle_qa.py` (briefing síncrono e decisão única)

Contratos de referência:
- `_reversa_forward/005-convergencia-pipeline/requirements.md` (RF-508, RF-509, RN-509, RN-510)
- `_reversa_forward/005-convergencia-pipeline/interfaces/pipeline-http.md`

---

## 2. Veredito Global

**Status: 🟢 APROVADO**

A integração total do ciclo de vida da pesquisa foi verificada em profundidade. O pipeline executa de ponta a ponta através dos entrypoints reais, preservando o modelo transacional, os contratos de segurança outbound e a integridade estrita das bibliotecas e arquivos protegidos.

---

## 3. Avaliação por Lente

### 3.1. Exercício do Ciclo Real (Sem mock de serviços centrais)
- **Não-violação de mocks de domínio**: `run_research` e `run_investigation` são executados diretamente sem mocks funcionais. Apenas I/O de rede externa (chamadas LLM LiteLLM, Search Jina e dispatch HTTP de webhook) é interceptado por fakes pontuais em nível de transporte/cliente.
- **Topologia e Batches**: Os testes exercitam a ordenação topológica de dependências entre pontos (`Fundamentos de Consenso` -> `Métricas de Acurácia`), disparando as personas em lotes paralelos seguros conforme a precedência DAG.
- **Merge Snapshot e Auditoria**: O snapshot de `InvestigationMerge` é verificado como committed antes da invocação do `AuditService`, garantindo que a auditoria nunca receba dados transitórios ou parciais de personas individuais.
- **Sessão Fechada e CAS**: A transição para `WRITE` ocorre via CAS atômico. A sessão SQLAlchemy é fechada antes da chamada de síntese ao Writer, prevenindo que locks de conexão ou transações de banco fiquem suspensos durante a inferência.

### 3.2. Segurança Outbound e SSRF (RN-510)
- Em conformidade com o contrato de segurança:
  - Sessões de navegador proíbem `callback_url` no payload com HTTP 422.
  - Endpoints B2B validam `callback_url` via `is_safe_url` e `outbound_guard` (`app/tools/outbound.py`), bloqueando IPs de loopback (127.0.0.1/8), redes privadas (RFC 1918), link-local e metadados de nuvem.
  - O endpoint `/api/reports/{id}/retry-callback` dispara webhook sem recriar, recalcular ou sobrescrever o registro `Report` existente no banco.
  - Pesquisas com falha de entrega de callback mantêm o status `DONE` e o relatório consultável via GET `/api/reports/{id}` com HTTP 200.

### 3.3. Briefing Síncrono e Decisão Única (RF-509 / RN-509)
- POST `/briefings` retorna 201 com o briefing completamente gerado e persistido (sem polling ou status assíncrono).
- PATCH `/briefings/{id}` revisa o briefing de forma síncrona, promove autoaprovação e agenda a investigação.
- Segunda revisão ou chamada conflitante de investigate resulta em HTTP 409 (conflito de estado).
- Nenhuma nova rota de aprovação (`/briefings/{id}/approve`) foi introduzida.

### 3.4. Integridade de Dependências e Arquivos Protegidos
- **Zero novas dependências**: Nenhuma alteração em `requirements.txt`, `package.json` ou manifests do projeto.
- **Zero alterações de frontend**: O diretório `frontend/` permaneceu intocado durante todo o ciclo de integração da feature 005.
- **Arquivos protegidos intactos**:
  - `app/routers/research.py`: SHA-256 `5584c7f46d8fcaad5266f063a0d837b0002cf887a68e653ff2dd38e49b980ea9` (inalterado)
  - `frontend/src/api.ts`: SHA-256 `400ceeabe7a681cecffa2f39d05cff325b458395e05c18f50ea0f35a4ed77702` (inalterado)
  - `frontend/src/main.tsx`: SHA-256 `78a243b73d604f505c8c92c9de9f3f5e29638f3edc0801d349da7d36064b754f` (inalterado)
  - `frontend/src/research-utils.ts`: SHA-256 `1a6454e1f5e5a706b64de163668a09b3796fdeb7e15c3dd6f7f300267df0f650` (inalterado)

---

## 4. Findings e Apontamentos

| ID | Severidade | Localização | Descrição | Recomendação |
|---|---|---|---|---|
| F-003 | Baixa (informativa) | `tests/integration/test_full_pipeline.py` | Teste adaptado com monkeypatch explícito nas classes `PersonaWorker` e `AuditService`, mantendo retrocompatibilidade com o harness legado. | Mantido conforme preconizado em T026. |
| F-004 | Baixa (informativa) | `app/investigation/service.py:365` | Persistência de `InvestigationMerge` isolada em transação atômica logo após superação da barreira das 4 personas. | Padrão robusto de commit antes da etapa de auditoria. |

---

## 5. Conclusão da Inspeção

O conjunto de código, adaptadores e suítes de teste de integração cumpre rigorosamente as especificações do Reversa Framework. Aprovado para avanço ao QA Geral e Final (T029).
