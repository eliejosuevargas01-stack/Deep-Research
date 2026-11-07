# Revisão cruzada independente — rodada 2 (pós D-09..D-12)

## Método

Inventário: 7 unidades × 4 arquivos + `ingestao-e-api/routes.json` (9 rotas) + `verification/` (5 arquivos: `comandos.md`, `pytest.txt` 78 passed, `api-smoke.md`, `db-inventory.md`, `runner-e2e.md`) + frontend 51 passed + build OK.
Citações: referências `arquivo:linha` reconferidas abrindo a linha (distribuídas nas 7 unidades + todos os pontos contestados dos audits). Critério: linha existe, conteúdo sustenta a afirmação, teste citado existe com o nome dado.
Testes: `.venv/bin/python -m pytest tests -q` → **78 passed** (colado em `verification/pytest.txt`). Frontend: `npm test -- --run` → **14 arquivos / 51 testes**; `npm run build` → OK (14.38s).

## Achados e disposição

| ID | Achado | Disposição |
|---|---|---|
| Y-01 | `src/api.py:23-42` auth com `GET /health` aberto (`:33-34`) contradiz audit-backend §7 ("health exige chave") | aplicado — código corrigido pós-audit; `tests/test_api_key.py:44-46` (200 com chave errada) + smoke manual 200 sem chave; audit §7 obsoleto registrado em `gaps.md` removidas |
| Y-02 | `src/webhook.py:14-50` 5 tentativas contradiz `_reversa_sdd` antiga ("2 tentativas") e audit-backend D-01 (descrevia alvo) | aplicado — D-01 implementado; `tests/test_webhook.py` (2×500→sucesso; 5 falhas→raise); docs atualizadas |
| Y-03 | `config/hermes_config.yaml` sem `delegation:` (14 linhas) contradiz docs antigas (espelho morto) | aplicado — D-06 removido; docs atualizadas, `gaps.md` removidas |
| Y-04 | `src/evidencias.py:1-123` + `hydrator.py:90-101,115-128` compactação vs docs antigas ("integral sem truncamento") | aplicado — D-11: DB integral (`hidratar` `:354-389`) × prompt compactado + `compactacao{}`; `tests/test_evidencias.py:18-103`; RF03/PRD atualizados |
| Y-05 | `hermes_home/.../config.yaml:1-21` 7 papéis forte/leve + `provider: env` sem segredo contradiz audit-backend §2/§6 (segredo `sk-c1f...`, todos `ag/gemini`) | aplicado — repo corrigido pós-audit; `src/settings.py:31-55`; script confirma 3 forte + 4 lite; `gaps.md` removidas |
| Y-06 | `src/settings.py:93-98,141-144,209-212` env-only + 422 contradiz docs antigas (`api_key` gravável) e audit-frontend F4/F6 | aplicado — D-10; smoke `PUT api_key=x` 422; `SettingsV12.tsx:169-171` mostra `base_url` só-leitura "definido por ambiente"; F4 mitigado no backend (UI ainda exibe campo — ver Y-11) |
| Y-07 | `src/orchestrator.py:150-159` `run.concluido` com `avaliacao_pontos[]` + `src/api.py:154-156` GET boletim contradiz docs antigas (sem chamador) | aplicado — D-08 plugado; docstring `planner.py:51-58` atual; `gaps.md` removidas |
| Y-08 | `src/db/repository.py:257-287` `obter_auditorias` + `src/api.py:136-153` contradiz docs antigas (só última) | aplicado — D-04; smoke `auditorias: 1`; teste 2 rodadas→2 itens |
| Y-09 | `engine/Dockerfile:2-5` `latest` + compose 2 serviços; `DR_HERMES_STATE_DB` `:ro` (`telemetria.py:97`, compose `:14,:18`) | aplicado — D-12; SDD registra aceite |
| Y-10 | `src/api.py:76-125` SSE (`/eventos`+`/events`, snapshot/replay/heartbeat/at-least-once `:88-92`) + `research_events` nos dois DDLs | aplicado — docs e `traceability.csv` (SSE/AUTH) + `tests/test_eventos.py:81-107` + `tests/test_api_key.py:66-87` |
| Y-11 | audit-frontend F1–F3/F5/F7–F9 (contagens vs arrays, `run.concluido` sem GET, dupla contagem tokens, SSE 404, reasoning) | **parcial** — backend emite arrays (`fonte.lida :291-301`, `ponto.coletado :303-313`, `tokens.atualizados :659-669` com `tokens_execucao` delta + totais); `run.concluido` carrega `avaliacao_pontos` mas não relatório (cliente deve refazer `GET`); F4/F6 mitigados no backend; F7/F8/F10 seguem como **LACUNA** de UI (fora do escopo backend; `gaps.md` G-07/G-08) |
| Y-12 | `src/orchestrator.py:363-401` auditor ausente → 12 false (não `PipelineError`) contradiz docs antigas | aplicado — resiliência documentada |

Totais: 12 conferidas, 11 aplicadas, 1 parcial (Y-11 UI, fora do escopo backend).
Citações conferidas nesta rodada (arquivo:linha abertos): `src/api.py:23-42,49-77,88-92,130-157`; `src/settings.py:31-55,93-98,141-144,200-212`; `src/evidencias.py:1-123`; `src/hydrator.py:90-129`; `src/webhook.py:14-50`; `src/orchestrator.py:68-111,137-223,262-322,363-459,150-159,594-669`; `src/planner.py:44-76`; `src/db/repository.py:199-287,289-325,354-510`; `src/telemetria.py:77-167`; `src/contracts.py:58,172-187`; `config/hermes_config.yaml:1-14`; `hermes_home/profiles/deep-research/config.yaml:1-21`; `engine/Dockerfile:2-5`; `docker-compose.yml`; `tests/test_api_key.py:32-87`; `tests/test_evidencias.py:18-103`; `tests/test_eventos.py:81-107`.

## Limites

Sem Hermes real, sem PostgreSQL, mesma família de modelo na extração e na revisão, árvore suja pré-existente fora de `_reversa_sdd/` não tocada por esta revisão (só `_reversa_sdd/` editado; `migration/DECISIONS.md` recebeu D-09..D-12 + Q).
