# Capsula de reproducao - BUG-20261023-EPVA

| Campo | Valor |
|---|---|
| Bug | BUG-20261023-EPVA (display 1) |
| Contexto | pipeline-de-pesquisa |
| Branch | (git status nao inspecionado; correcao aplicada sobre arvore de trabalho atual) |
| Ambiente | Linux 6.8.0-147-generic, Python 3.14.7 |
| Comando | `python _reversa_bugs/pipeline-de-pesquisa/bugs/BUG-20261023-EPVA-webhook-4xx-como-entregue/reproduce.py` (raiz do projeto) |
| Exit code | 1 |
| Taxa | 1/1 (falha em toda tentativa) |
| Classificacao | deterministic |

## Saida observada (literal, 2026-10-23)

```text
retorno do cliente: {'status': 'entregue', 'http_status_code': 404, 'tentativas': 1, 'resposta': '{"erro":"recurso nao encontrado"}'}
http_status_code observado: 404
status gravado: entregue
Traceback (most recent call last):
  ...
  File ".../reproduce.py", line 38, in main
    assert observado == esperado_por_espec, (
AssertionError: DEFEITO CONFIRMADO: receptor respondeu 404 (rejeitou o evento) mas o cliente gravou 'entregue' em vez de 'falha_definitiva'.
```

## Leitura da reproducao

O receptor simulado responde `404 Not Found`, ou seja, rejeitou o evento.
O `WebhookClient` deveria classificar como nao entregue. Em vez disso:

- `attempt` = 1 (nao houve retry, comportamento correto para 404: receptor
  respondeu, nao ha indisponibilidade)
- `status` = `"entregue"` (defeito)
- `http_status_code` = 404 fica registrado dentro do proprio retorno, o que
  torna a inconsistencia auditavel posteriormente mas nao impede a gravacao
  do status errado

## Isolamento

`research_repo` ficou `None`, portanto `_update_repo_status` retornou no
primeiro if (`app/services/webhook_client.py`, linhas 93 e 94) e nao houve
acesso a banco. A reproducao isola exclusivamente a logica de classificacao.
