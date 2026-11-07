# verification — comandos

Reproducao exata das provas. Raiz: /root/projects/deep-research. Sem tocar data/.

## pytest — suite completa

Comando: cd /root/projects/deep-research && .venv/bin/python -m pytest tests -q
Saida colada em pytest.txt. CONFIRMADO.

## api-smoke — TestClient com banco, workspace e perfil temporarios

Script em /tmp/smoke_api.py executado com .venv/bin/python. Cobre POST /research 202, GET id 200, GET inexistente 404, POST invalido 422, GET/PUT /config, alias /api/v1/settings, listagem de rotas. Resumo em api-smoke.md. CONFIRMADO.

## db-inventory — PRAGMA do SQLite tmp via Repositorio

Script em /tmp/db_inv.py executado com .venv/bin/python. Cria Pipeline com FakeExecutor sobre tmp inv.db, criar mais executar 1 ponto, depois PRAGMA table_info e contagem de linhas. Colado em db-inventory.md. CONFIRMADO.

## runner-e2e — fake CLI mais fan-out 40

Comando: .venv/bin/python -m pytest tests/test_hermes_runner.py tests/test_pipeline.py::test_coleta_fan_out_40_em_um_lote -v
Fake CLI: tests/fake_hermes.py via hermes_bin em tests/test_hermes_runner.py:24. Detalhes em runner-e2e.md. CONFIRMADO.

## Checagens auxiliares

- which hermes vazio: LACUNA, sem Hermes real neste host.
- diff SOUL.md vs SOUL.template.md: IDENTICOS.
- git status: alteracoes fora de _reversa_sdd sao pre-existentes da arvore suja, nao desta tarefa.
