# verification — runner-e2e

## HermesRunner com fake CLI, tests/test_hermes_runner.py

hermes fora do PATH; hermes_bin aponta para sys.executable mais tests/fake_hermes.py, tests/test_hermes_runner.py:24. CONFIRMADO, cobertos pelo pytest em pytest.txt.

- test_planejar_aciona_hermes_com_cwd_no_workspace: planner grava saidas/planner.json com ids 1 e 2, total_tokens 1250, model_used do perfil, chamadas.jsonl com cwd igual ao workspace, prompts/planner.md existe. CONFIRMADO.
- test_lote_executa_uma_tarefa_por_papel: 2 tarefas geram saidas por id mais __orquestrador__ com total_tokens 1250 via usage.json, tarefas.json com arquivo prompts/historiador_p1_r1.md. CONFIRMADO.
- test_sem_saida_vira_erro_por_tarefa: com FAKE_HERMES_SEM_SAIDA=1, call.erro contem sem saidas/historiador_p1_r1.json. CONFIRMADO.
- test_telemetria_le_tokens_e_modelo_do_state_db: state.db tmp com sessoes pai e filha, auditor_p1_r2 total_tokens 1050, tool_calls 4, _pai total_tokens 470. CONFIRMADO.

## Fan-out 40, tests/test_pipeline.py:239-260

test_coleta_fan_out_40_em_um_lote: profundidade 10 gera primeiro lote de coleta com 40 tarefas num so executar, tamanhos_lote 0 igual 40, maximo 40, 10 payloads historiador, run COMPLETED. CONFIRMADO.

## Limite

LACUNA: nenhum teste aciona o binario hermes real, ausente no host; delegate_task real e state.db de producao nunca observados.
