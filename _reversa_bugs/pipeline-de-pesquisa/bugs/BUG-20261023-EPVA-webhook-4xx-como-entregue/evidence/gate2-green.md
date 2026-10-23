# Gate 2 - evidencia do VERDE (depois da correcao)

## Correcao aplicada

`app/services/webhook_client.py`, dentro de `send_webhook`:

```diff
                 # Entrega confirmada com sucesso (código 2xx)
-                status_result = "entregue"
+                # BUG-20261023-EPVA: apenas 2xx confirma a entrega. Um 4xx é rejeição
+                # definitiva do receptor e não pode ser gravado como 'entregue'.
+                # A lista acima continua existindo só para decidir RETRY, nunca para
+                # decidir que a entrega ocorreu.
+                status_result = "entregue" if res.is_success else "falha_definitiva"
```

## Comando 1 - arquivo alvo

```bash
python -m pytest tests/unit/test_webhook_client.py -q
```

Saida literal (2026-10-23):

```text
..........                                                               [100%]
10 passed in 0.18s
```

Exit code 0. Os 5 casos de 4xx passam e os 5 preexistentes continuam passando.

## Comando 2 - reproducao original do bug

```bash
python _reversa_bugs/pipeline-de-pesquisa/bugs/BUG-20261023-EPVA-webhook-4xx-como-entregue/reproduce.py
```

Saida literal:

```text
retorno do cliente: {'status': 'falha_definitiva', 'http_status_code': 404, 'tentativas': 1, 'resposta': '{"erro":"recurso nao encontrado"}'}
http_status_code observado: 404
status gravado: falha_definitiva
OK: 404 tratado como falha.
```

Exit code 0. Antes da correcao o mesmo script encerrava com exit 1 (ver
`evidence/reproduction.md` e `evidence/gate1-red.md`).

## Comando 3 - suíte completa (regressao)

```bash
python -m pytest -q
```

Saida literal:

```text
........................................................................ [ 72%]
...........................                                              [100%]
99 passed, 1 warning in 6.22s
```

Exit code 0. Nenhuma regressao: os 99 testes do projeto passam, incluindo
`tests/integration/test_endpoints.py` e `tests/integration/test_edge_cases.py`,
que consomem `webhook_entrega.status` e aceitam os valores `entregue` e
`falha_definitiva`.

## Leitura

- Perna 1 (testes que provam o defeito): vermelho em `gate1-red.md`.
- Perna 2 (correcao que faz os testes passarem): verde neste arquivo.
- A politica de retry 1 + 3 para 429 e 5xx ficou intacta: a linha do `if` de
  `raise_for_status()` não foi alterada.
