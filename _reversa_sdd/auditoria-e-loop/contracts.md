# Auditoria e loop — contratos

## `payload_auditor` (`src/hydrator.py:81-102`)

`research_id, ponto_id, persona "auditor", soul, atualidade, tentativa_atual, max_rodadas_auditoria, perguntas_auditoria, informacao_coletada_acumulada` (compactada D-11) + `compactacao{linhas/chars}`. **CONFIRMADO**

## `AuditorSaida` (`src/contracts.py:167-187`)

`extra="ignore"`; `_coerir_booleanos` rejeita não-`bool` antes da checagem de chaves; exatamente 12 chaves `"1".."12"`. **CONFIRMADO** (D-02).

## Decisão `avaliar` (`src/planner.py:33-41`)

`{tentativa_atual, perguntas_true, total_perguntas, porcentagem_aprovacao(2 casas), meta_veracidade_alvo, aprovado, proxima_acao(1 de 3)}`. **CONFIRMADO**

## Boletim `avaliacao_pontos` (`src/planner.py:44-76` + `src/db/repository.py:289-325`)

`{research_id, tentativa_atual, tema, avaliacao_pontos: [{ponto_id, perguntas_true, total_perguntas, porcentagem_aprovacao, meta_veracidade_alvo, aprovado}]}`. Montado das últimas respostas por ponto; `None` sem pontos. **CONFIRMADO** (D-08; docstring atual, sem menção obsoleta).

## `research_points` (escritas da auditoria)

`ultimo_resultado_auditor` JSON, `porcentagem_aprovacao`, `aprovado` 0/1, `rodada_atual` (`src/db/repository.py:160-180`); leitura converte p/ bool. Histórico em `agent_executions`, não sobrescrito. **CONFIRMADO**

## Divergências vs PRD/SDD

- Nenhuma pendente nesta unidade: `avaliacao_pontos` plugado (D-08), histórico exposto (D-04), docstring atualizada.
