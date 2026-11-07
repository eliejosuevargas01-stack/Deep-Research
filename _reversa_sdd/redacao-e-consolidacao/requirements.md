# Redação e consolidação — comportamento observado

Fonte: `src/orchestrator.py` (`_redigir`, `executar`), `src/hydrator.py` (`payload_redator`), `src/contracts.py` (`RedatorSaida`), `src/db/repository.py` (`consolidar`), `src/webhook.py`.

## Entradas

- `_redigir(research_id, encerrados, workspace)` recebe `(ponto, respostas, acumulado, rodada, erro_coleta)`; pontos encerrados (aprovados, limite ou auditor ausente). **CONFIRMADO** (`src/orchestrator.py:452-459,461-465`)
- Payload redator: `research_id, ponto_id, persona="redator", soul, ponto_enunciado, resultado_final_auditor, perguntas_auditoria, perguntas_nao_concluidas, erro_coleta, urls_usadas_acumuladas, informacao_coletada_acumulada_integral` (compactada D-11) + `compactacao{}` (`src/hydrator.py:105-129`). **CONFIRMADO**

## Regras

- R-RC-01 — 1 tarefa `redator_p{ponto_id}` por ponto, validador **próprio por tarefa** (`_validador_redator(acumulado["urls_usadas"])`, `:496`); sem saída válida após tentativas → `ponto.erro`, segue (`:523-532`). **CONFIRMADO**
- R-RC-02 — Validador: `RedatorSaida.model_validate` + URLs de `relatorio+lacunas` via regex + `urls_citadas`; fora da allowlist → `ValueError` → correção (`:594-610`). **CONFIRMADO** por `tests/test_garantias.py::test_redator_rejeita_url_fora_das_usadas`.
- R-RC-03 — `salvar_relatorio` grava `relatorio_ponto, lacunas_ponto` (`src/db/repository.py:182-189`). **CONFIRMADO**
- R-RC-04 — `consolidar` (`src/db/repository.py:394-510`): exige pontos; ponto sem relatório vira **seção de ponto incompleto** (não aborta); FAILED só se **zero** relatórios (`:415-420`); `## {id}. {enunciado}` em ordem 1..N; `lacunas=[{ponto_id,lacunas}]` (inclui falhos); URLs globais dedup; tokens por `SUM`; `## Avaliação de veracidade` quando há boletim (`:468-478`); `UPDATE ... COMPLETED` + commit. **CONFIRMADO**
- R-RC-05 — Ordem: `consolidar` (COMPLETED + commit) **antes** do webhook; falha do webhook só loga, status segue COMPLETED (`src/orchestrator.py:149-173`). **CONFIRMADO** (D-01: risco aceito).
- R-RC-06 — Webhook D-01: **5 tentativas** (esperas 1,2,4,8s); só 5xx/rede retenta; 4xx levanta na hora; esgotadas → `RuntimeError` (`src/webhook.py:14-50`). `timeout_s` de `config.pipeline.webhook_timeout_s` (15). **CONFIRMADO** por `tests/test_webhook.py` (2×500→sucesso; 5 falhas→raise).
- R-RC-07 — `run.concluido{status, pontos_falhos, metricas_tokens, avaliacao_pontos[]}` emitido após consolidar (`src/orchestrator.py:150-159`); `GET` inclui boletim. **CONFIRMADO** (D-08).

## Erros e HTTP

- `ValueError("pesquisa ... não tem pontos")` / `"nenhum ponto com relatório"` → FAILED (`:160-164`). **CONFIRMADO**
- `RuntimeError` do webhook engolido (`:166-173`) — COMPLETED mantido. **CONFIRMADO**
