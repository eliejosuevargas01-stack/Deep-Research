# Redação e consolidação — tarefas

- [x] Webhook 5 tentativas (1,2,4,8s; 5xx retenta; 4xx encerra; esgotadas raise) — D-01, `src/webhook.py:14-50`, `tests/test_webhook.py`. `CONFIRMADO`.
- [x] Consolidação resiliente (ponto incompleto vira seção; FAILED só se zero relatórios) — `src/db/repository.py:394-443`. `CONFIRMADO`.
- [x] `avaliacao_pontos` no dossiê + webhook + `run.concluido` — D-08. `CONFIRMADO`.
- [ ] Provar falha de webhook com teste de integração (`executar` com notificador que levanta; hoje só lido `src/orchestrator.py:166-173`). **LACUNA** (executável, não escrito).
- [ ] Decidir destino de callbacks não entregues (sem fila/coluna/reenvio). `CONFIRMADO` (ausência lida).
