# planejamento — contracts

## Entrada do planner

`requisicao.model_dump(mode="json")`: `{tema, profundidade, veracidade_alvo, max_rodadas_auditoria, atualidade, callback_url}`. `CONFIRMADO` — `src/orchestrator.py:177`.

## Saída `PlanoLLM` (`src/contracts.py:118-141`)

`{pontos: PontoPlano[], urls_lidas: [], urls_usadas: []}` (D-07; `extra="ignore"`; `urls_usadas` absorvidas nas lidas; `validar_para`: `len==profundidade`, ids 1..N). `CONFIRMADO`.

## `PontoPlano` (`src/contracts.py:73-115`)

`ponto_id ≥1` sequencial; `enunciado` strip min 1 (canônico; `ponto_enunciado` é nome dos payloads buscador/redator); `subperguntas/hipoteses/lacunas_iniciais` ≥3; `perguntas_auditoria` 12 chaves (vazios filtrados antes). `CONFIRMADO`.

## Decisão `avaliar` (`src/planner.py:33-41`)

`{tentativa_atual, perguntas_true, total_perguntas, porcentagem_aprovacao(2 casas), meta_veracidade_alvo, aprovado, proxima_acao(1 de 3)}`. `CONFIRMADO`.

## `avaliacao_pontos` (`src/planner.py:60-76`)

`{research_id, tentativa_atual, tema, avaliacao_pontos: [{ponto_id, perguntas_true, total_perguntas, porcentagem_aprovacao, meta_veracidade_alvo, aprovado}]}`. Oficial D-08. `CONFIRMADO`.

## Tabelas

- `research_runs.plano_inicial`. `CONFIRMADO`.
- `research_points`: `(research_id, ponto_id UNIQUE)`, `enunciado, subperguntas, hipoteses, lacunas_iniciais, perguntas_auditoria`. `CONFIRMADO`.

## Divergências vs PRD/SDD

- `enunciado` (plano) × `ponto_enunciado` (payloads buscador/redator): mapear os dois. `CONFIRMADO` (`src/contracts.py:77`, `src/hydrator.py:71,121`).
- Nenhuma outra pendente: urls do planner registradas (D-07), boletim plugado (D-08).
