# planejamento — design

## Fluxo `_planejar` (`src/orchestrator.py:176-223`)

1. Payload = dump da requisição.
2. `hydrator.montar("planner", payload)` → sistema `planner.md` + JSON (`src/hydrator.py:39-48`). `CONFIRMADO`.
3. Loop `tentativas_por_agente`×: `executor.planejar` → valida; falha vira `call.erro` + tarefa corrigida; cada tentativa registrada (inclusive rejeitadas). `CONFIRMADO`.
4. Sucesso → `_registrar` (com `urls_lidas/usadas` do plano, D-07, `:194-200`) → `plano_publico` + `salvar_plano` → evento `plano.pronto{pontos, total_pontos}` (`:218-223`). `CONFIRMADO`.
5. Esgotou → `PipelineError` → `FAILED`. `CONFIRMADO`.

## Decisão de fluxo (`src/planner.py:18-41`)

`avaliar` puro: taxa → compara alvo → 3 ações. `_auditar` por ponto; `NOVA_RODADA` preenche `pendentes` + `ignoradas` e incrementa; demais encerram p/ redação. `CONFIRMADO`.

## Módulos

`_planejar/_corrigir`, `PlanoLLM/PontoPlano`, `taxa_aprovacao/avaliar/avaliacao_pontos`, `planner.md`, `montar`/`SOULS["planner"]`. `CONFIRMADO`.

## Trade-offs

- Correção por re-prompt com motivo (barato, sem canal estruturado). `INFERIDO`.
- `validar_para` ordena in-place após validar — ordem de saída irrelevante. `CONFIRMADO`.
