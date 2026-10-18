# Audit Report — Feature 002-investigacao-personas, Re-auditoria pós-E001

> Data: 2026-10-16 | Auditor: reversa-audit + reversa-quality (independente)
> Escopo: re-auditoria da Feature 002 após Emenda E001
> Artefatos auditados: `app/briefing/service.py`, `app/briefing/schemas.py`,
> `app/routers/research.py`, `app/main.py`, `tests/test_briefing_api.py`,
> `tests/test_briefing_acceptance.py`,
> `_reversa_forward/002-investigacao-personas/requirements.md` (seção `## Emendas`),
> `_reversa_forward/002-investigacao-personas/actions.md`,
> `_reversa_forward/002-investigacao-personas/progress.jsonl`
> Método: leitura direta dos arquivos (sem execução — sem interpretador no container:
> `python3: not found` confirmado via shell; nenhum teste foi re-executado por este auditor).

## 1. Status Geral

| Trilha | Veredito |
|---|---|
| /reversa-audit (código vs documentação, E001 / A-C8-01 a A-C8-06 + D-01) | **APROVADO** |
| /reversa-quality (clareza, consistência, rastreabilidade) | **APROVADO** (com 2 ressalvas LOW, ver §3) |

## 2. Verificação Item a Item dos Findings Anteriores

| # | Exigência original | Evidência atual | Veredito |
|---|---|---|---|
| A-C8-01 | Query SERP da revisão formulada pela IA (tema+feedback), nunca só tema puro | `app/briefing/service.py:116-152` define `_QUERY_SYSTEM` + `_formulate_serp_query(theme, feedback, llm_complete, timeout)` com fallback combinado `f"{theme} {feedback}"` truncado a 300 chars; `revise_briefing_with_feedback` chama em `service.py:226-228` e usa o resultado em `service.py:230` (`serp_client.search(search_query)`). Guarda anti-eco (`query == theme` → fallback) em `service.py:150-151`. Nenhum `search(briefing.theme)` remanesce no caminho de revisão (só no POST inicial, `service.py:87,308`, correto). | **RESOLVIDO** |
| A-C8-02 | Remover `BriefingEditPointsRequest` e `BriefingApproveRequest` de `schemas.py` | `app/briefing/schemas.py:1-118` contém apenas `BriefingPoint`, `BriefingCreateRequest`, `BriefingFeedbackRequest`, `BriefingReopenRequest`, `BriefingResponse`, `BriefingVersionResponse`, `ApprovedBriefingResponse`. Grep em `app/` por `BriefingEditPoints\|BriefingApproveRequest` retorna 0 ocorrências. | **RESOLVIDO** |
| A-C8-03 | Extinguir rota legada `POST /research/{id}/briefing/approve` | `app/routers/research.py:1-391` não contém nenhuma rota `/approve` nem `/briefing/approve` (rotas vivas: `POST /research`, `GET /research`, `GET /research/{id}`, `POST /research/{id}/briefing/edit`, `GET .../events`, `GET /reports/...`, `POST .../retry-callback`, `POST .../resume`). Grep em `app/` por `briefing/approve` retorna 0 ocorrências em código (só comentários/docstrings em testes e `GET /briefings/approved/` read-only em `app/briefing/router.py:202`, que não é via de aprovação). | **RESOLVIDO** |
| A-C8-04 | Testes cobrindo query SERP + matriz 500/502/503 no PATCH | `tests/test_briefing_api.py:408-476`: `test_patch_revision_serp_uses_ai_formulated_query` (1 busca, query IA), `test_patch_revision_serp_falls_back_to_combined_theme_feedback` (fallback `theme+feedback`, `assertNotEqual` tema puro), `test_patch_revision_errors_map_to_500_502_503` (503 SERP + FAILED sem investigate; 502 LLM + FAILED; 500 prompt + FAILED sem I/O, sem vazamento de segredo). `tests/test_briefing_acceptance.py:269-360`: `test_patch_serp_query_combines_theme_and_feedback` (1 request HTTP real, `q == theme+note`), `test_patch_serp_query_uses_ai_formulation_when_textual`, `test_patch_feedback_terminal_errors` (503/502/500 com FAILED persistido, `inv_mock.await_count==0`, contagem de http_calls/llm.calls). | **RESOLVIDO** |
| A-C8-05 | Transição limpa para SCRAPER em `service.py:264` | `app/briefing/service.py:258-267`: `save_briefing_transition` → `update(Research).where(...).values(status=ResearchStatus.SCRAPER)` + `commit`. Sem escrita transitória de `PENDING_APPROVAL` no caminho de revisão (divergência LOW do relatório anterior eliminada). Status final `SCRAPER` confirmado pelos testes de snapshot (`research.status in ("SCRAPER",)`). Janela de dois commits (storage + flip) persiste por desenho, mitigada por CAS/rowcount — aceito como comportamento documentado, sem valor proibido observável. | **RESOLVIDO** |
| A-C8-06 | Literais legados mortos no `lifespan` de `main.py` | `app/main.py:28-33`: query de retomada usa só `ResearchStatus.BRIEFING`; comentário `E001 (A-C8-06)` registra remoção de `"scouting"`, `"revising"`, `"approved"`, `"in_progress"`; `revising: list = []` e `active: list = []` (sem consultas mortas). Grep em `app/` confirma zero literais legados em código vivo. | **RESOLVIDO** |
| D-01 | Nota de planejamento em `actions.md:198` + seção `## Emendas` com E001 | `actions.md:198` atualizada: "Sprint C8 (T036–T040) implementada em 2026-10-16 e Emenda E001 aplicada na mesma data (query SERP por IA tema+feedback, extinção do /approve legado, schemas limpos, testes PATCH 500/502/503, D-01 corrigido)". Seção `## Emendas` (`actions.md:200-204`) com entrada E001 (arquivos previstos corretos). `requirements.md:485-491` seção `## Emendas / E001` presente. `progress.jsonl:52` registra `action: E001, status: done`. | **RESOLVIDO** |

## 3. Apontamentos Remanescentes (não-bloqueantes, LOW/INFO)

| # | Severidade | Observação |
|---|---|---|
| R-01 | LOW | **Aceite pytest sem exit code.** E001 adiciona cobertura estática comprovada acima, mas nenhum teste foi executado neste ambiente (sem `python3` no container, idêntico ao `blocked-no-interpreter` da C8). Recomenda-se executar `pytest tests/test_briefing_api.py tests/test_briefing_acceptance.py` em ambiente com runtime e registrar exit code antes do fechamento definitivo do gate. Não reprova porque a missão desta re-auditoria é verificação estática de conteúdo, já cumprida. |
| R-02 | LOW/INFO | **Referências à rota extinta em suítes legadas.** `tests/test_backend.py:118,120,327,1149,1287`, `tests/test_e2e_criteria.py:85`, `tests/investigation/test_investigation_runtime_regressions.py:165`, `tests/integration/test_full_pipeline.py:104`, `tests/test_postgres.py:101,103` ainda chamam `POST /api/research/{rid}/briefing/approve` (esperando 200/409 do contrato antigo). Com a extinção correta da rota (A-C8-03), essas chamadas agora retornam 404 — comportamento esperado, mas as suítes legadas precisarão de atualização futura (fora do escopo declarado da E001, que previa só `tests/test_briefing_api.py` + `tests/test_briefing_acceptance.py`). Nenhuma referência remanesce em `app/`. |
| R-03 | INFO | `POST /research/{id}/briefing/edit` (legado, `app/routers/research.py:227`) permanece vivo. Não é via de aprovação (só agenda `run_revision` sobre `BRIEFING`), portanto não viola D-21/Q14–Q16. Mantido sem ação. |

## 4. Veredito Final

- **/reversa-audit: APROVADO.** Todos os findings A-C8-01 a A-C8-06 e D-01 estão resolvidos no código e nos documentos, com evidência linha a linha em §2. Nenhuma não-conformidade HIGH ou MEDIUM remanesce.
- **/reversa-quality: APROVADO.** Contratos, Gherkin (PATCH com 500/502/503 e query IA), `actions.md`, `requirements.md ## Emendas` e `progress.jsonl` estão consistentes e rastreáveis. Ressalvas LOW R-01/R-02 acima são follow-ups, não reprovação.
- **Gate da Sprint C8 + E001: liberado para aceite funcional**, pendente apenas de execução do pytest com exit code em ambiente com runtime (R-01) e futura higienização das suítes legadas que ainda chamam a rota extinta (R-02).
