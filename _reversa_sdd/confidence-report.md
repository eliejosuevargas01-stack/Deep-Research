# Relatório de confiança

Contagem de marcadores nas 4 docs de cada unidade (requirements/design/contracts/tasks) + raiz. `pytest` final: **78 passed** (`verification/pytest.txt`); frontend **51 passed** + `npm run build` OK.

> Contagem pós-sincronização D-09..D-12 (2026-11-07). Marcadores totais em `_reversa_sdd/**/*.md` (inclui raiz): ver `grep -rho` no `cross-review-result.md`.

## O que nunca foi executado (por unidade)

- ingestao-e-api: at-least-once do snapshot exige dedupe no cliente (documentado `src/api.py:88-92`); legado `App.tsx`/`api.ts` compila mas fora do bundle — resto provado (auth 200/401/202/422, SSE snapshot/replay, `auditorias`+`avaliacao_pontos`).
- planejamento: esgotamento de retentativas do planner (`PipelineError`) nunca executado; resto provado.
- coleta-personas: fan-out real 40 pelo Hermes nunca observado (só lote único backend + fake); resto provado.
- auditoria-e-loop: tudo executável neste host foi executado (booleanos, decisão, histórico, boletim oficial).
- redacao-e-consolidacao: `executar` com notificador que levanta (falha→COMPLETED) nunca executado; resto provado (5 tentativas, consolidação resiliente, `run.concluido` com boletim).
- configuracao-e-execucao: Hermes real, plugin `por_papel` no runtime e `state.db` de produção nunca observados; resto provado via fake (7 papéis, env-only, `latest`, `MODELS.json`, `state.db :ro`).
- telemetria-e-persistencia: DDL PostgreSQL, truncamento 20k, `state.db` ausente/`cwd IS NULL`, concorrência nunca executados; resto provado com `state.db` sintético (4 tabelas, DB integral × prompt compactado, fallback usage).

## Leitura

Maioria CONFIRMADO por `pytest` (78) + leitura de linha + smoke manual (API key 200/401/202, `PUT` 422/200, `GET` com `auditorias`+`avaliacao_pontos`); INFERIDO em trade-offs e mapeamento PRD/SDD; LACUNA em Hermes real + PostgreSQL + depth-10 real + at-least-once + legado frontend.
