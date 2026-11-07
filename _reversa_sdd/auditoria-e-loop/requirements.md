# Auditoria e loop — comportamento observado

Fonte: `src/orchestrator.py` (`_auditar`), `src/hydrator.py` (`payload_auditor`), `src/contracts.py` (`AuditorSaida`), `src/planner.py`, `src/db/repository.py` (`obter_auditorias`, `obter_avaliacao`).

## Entradas

- Acumulado por ponto via `hidratar` → `{rodadas, urls_usadas, urls_lidas}` integral (`src/orchestrator.py:334-335`, `src/db/repository.py:354-389`). **CONFIRMADO**
- Payload auditor: `research_id, ponto_id, persona="auditor", soul, atualidade, tentativa_atual, max_rodadas_auditoria, perguntas_auditoria, informacao_coletada_acumulada` (compactada D-11) + `compactacao{}` (`src/hydrator.py:81-102`). **CONFIRMADO**

## Regras

- R-AL-01 — 1 tarefa auditor por ponto/rodada, id `auditor_p{ponto_id}_r{rodada}`, via `_executar_lote` (retentativa 2). Auditor sem saída → **não aborta**: segue ao redator com 12 `false` + `auditor_ausente:true` + `perguntas_nao_concluidas` + `erro_coleta` (`src/orchestrator.py:363-401`). **CONFIRMADO**
- R-AL-02 — Booleanos **estritos**: não-`bool` → `ValueError` (`src/contracts.py:172-180`); exatamente 12 chaves (`:182-187`). **CONFIRMADO** (D-02; `tests/test_contracts_e_gate.py::test_auditor_exige_booleanos_estritos`).
- R-AL-03 — `planner.avaliar` (`src/planner.py:18-41`): `taxa=aprovadas*100/12` 2 casas; `aprovado=taxa>=alvo`; 3 ações. **CONFIRMADO** (`tests/test_contracts_e_gate.py::test_tabela_de_decisao_do_feature_06`).
- R-AL-04 — Nova rodada: `pendentes` = só `false` (`:444-448`); `ignoradas` = `urls_lidas` acumuladas (`:449`); `rodada+=1`. **CONFIRMADO**.
- R-AL-05 — Histórico completo: `obter_auditorias` lê `agent_executions agent_role='auditor'` ordenado ponto/rodada, sem sobrescrever (`src/db/repository.py:257-287`); `GET` acrescenta taxa/aprovado por item (`src/api.py:136-153`). **CONFIRMADO** (D-04).
- R-AL-06 — `avaliacao_pontos` oficial (D-08): `obter_avaliacao` monta boletim SDD §5.7 das últimas respostas por ponto (`src/db/repository.py:289-325` via `planner.avaliacao_pontos` `src/planner.py:44-76` — docstring atual, sem "sem chamador"); alimenta consolidação (`:468-478`), `GET` (`src/api.py:154-156`) e evento `run.concluido` (`src/orchestrator.py:150-158`). **CONFIRMADO**.
- R-AL-07 — Eventos: `auditoria.executada{ponto_id,rodada,perguntas_true,total_perguntas,porcentagem_aprovacao,aprovado,perguntas_respondidas,model_used,total_tokens[,auditor_ausente]}` (`:419-434`, `:373-388`); `ponto.aprovado` / `ponto.reprovado` por ponto (`:435-442`); `redator.iniciado` ao encerrar (`:475`). **CONFIRMADO**
