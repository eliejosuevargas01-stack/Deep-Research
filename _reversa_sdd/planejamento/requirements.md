# planejamento — requirements

Comportamento observado da etapa `_planejar` + decisão de fluxo `planner.py`.

## Requisitos

- `R-plan-01` — `_planejar` monta payload = `requisicao.model_dump(mode="json")`, hidrata prompt `planner`, cria `Tarefa(id="planner")`. `CONFIRMADO` — `src/orchestrator.py:177-183`.
- `R-plan-02` — Saída validada por `PlanoLLM.model_validate(dados).validar_para(profundidade)`: nº pontos == profundidade; `ponto_id` 1..N (ordena após validar). `CONFIRMADO` — `src/contracts.py:134-141`.
- `R-plan-03` — Retentativa até `tentativas_por_agente`: inválido vira `call.erro` + registra + reenvia com `## Correção obrigatória`. `CONFIRMADO` — `src/orchestrator.py:186-204`; `tests/test_pipeline.py::test_planner_invalido_retenta_e_registra_tentativa_rejeitada`.
- `R-plan-04` — `salvar_plano`: `plano_inicial` + linhas `research_points` (UPDATE + DELETE + INSERT, commit único). `CONFIRMADO` — `src/db/repository.py:71-94`.
- `R-plan-05` — Sem plano válido → `PipelineError`, run `FAILED`. `CONFIRMADO` — `src/orchestrator.py:205-206`.
- `R-plan-06` — `PontoPlano`: `ponto_id ≥1`, `enunciado` não vazio, `subperguntas/hipoteses/lacunas_iniciais` ≥3, `perguntas_auditoria` exatamente `"1".."12"`, extras ignorados. `CONFIRMADO` — `src/contracts.py:73-141`.
- `R-plan-07` — Varredura exploratória obrigatória: ≤5 `web_search` + `web_extract`; planner devolve `urls_lidas/urls_usadas` (D-07); `_registrar` grava na linha do planner (`:194-200`); consolidação inclui (`src/db/repository.py:445-457`). Compactação posterior **não muda o plano** (só prompts auditor/redator). `CONFIRMADO` — `src/prompts/planner.md`, `src/hermes_runner.py:30-41`, `src/contracts.py:118-133`.
- `R-plan-08` — Prompt exige cobertura das 12 perguntas. `CONFIRMADO` — `src/prompts/planner.md`.
- `R-plan-09` — `taxa_aprovacao`: `round(aprovadas*100/total, 2)`, vazio conta 12. `CONFIRMADO` — `src/planner.py:12-15`.
- `R-plan-10` — `avaliar`: aprovado se `taxa >= round(alvo,2)` → redator; senão limite → `ACAO_REDATOR_LIMITE`; senão nova rodada. `CONFIRMADO` — `src/planner.py:18-41`.
- `R-plan-11` — `avaliacao_pontos` oficial (D-08): agregado SDD §5.7 consumido por `obter_avaliacao` → consolidação + `GET` + `run.concluido`. `CONFIRMADO` — `src/planner.py:44-76`.
- `R-plan-12` — Executor `Executor.planejar` (Hermes real: 1 processo, planner não delega; "Não delegue esta etapa"). `CONFIRMADO` — `src/hermes_runner.py:39`.

## Mapeamento

- RF05, RF01 (plano N pontos). `INFERIDO`.

## Invariantes

- Plano com N≠profundidade ou ids fora de sequência nunca persiste. `CONFIRMADO`.
