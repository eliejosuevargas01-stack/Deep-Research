# Relatório de Diagnóstico e Correção de Timeout em Produção (/api/v1/search)

## 1. Causa Raiz do Erro 500 no Teste Real
Durante a execução de teste com provedores reais (`live-payloads.jsonl` e `live-ui-observations.json`):
- O planejamento (`POST /api/v1/plan`) para 2 pontos com as personas `historiador` e `cetico` foi concluído com sucesso (HTTP 201 em 140.075s).
- Em seguida, a busca web concorrente (`POST /api/v1/search`) falhou após **482.37s** com **HTTP 500**: `{"detail": "Erro interno do servidor."}`.

### Rastreamento da Exceção (`live-capture.log`):
```text
File ".../httpcore/_backends/anyio.py", line 35, in read:
    return await self._stream.receive(max_bytes=max_bytes)
    await self._protocol.read_event.wait()
asyncio.exceptions.CancelledError

During handling of the above exception:
File "app/api/v1/endpoints/search.py", line 97, in search_points:
    resumo = await searcher.execute_search(...)
File "app/core/searcher.py", line 1574, in execute_search:
    resumos.append(await _processar_ponto(ponto))
File "app/core/searcher.py", line 1212, in _processar_ponto:
    persona_results = await asyncio.wait_for(
        asyncio.gather(*tasks),
        timeout=SEARCH_POINT_TIMEOUT_SECONDS,
    )
TimeoutError
```

### Análise Técnica:
1. **Estouro de Prazo Limite (`SEARCH_POINT_TIMEOUT_SECONDS = 480.0s`)**:
   No teste com provedores reais, as duas personas consultaram a SERP e leram 14 URLs completas da web, seguidas de chamadas analíticas ao modelo LLM real. O tempo total acumulado atingiu 482.37s, disparando o timeout de 480s de `asyncio.wait_for`.
2. **Cancelamento Abrupto sem Await das Tasks**:
   `asyncio.wait_for` cancelou o futuro do `asyncio.gather(*tasks)` enquanto o cliente `httpx`/`httpcore` ainda lia bytes de resposta HTTP de uma chamada em andamento, gerando `asyncio.CancelledError`.
3. **Propagação de `TimeoutError` não Tratado pelo Endpoint**:
   O bloco `except (asyncio.CancelledError, asyncio.TimeoutError)` em `_processar_ponto` salvou o conteúdo parcial, mas executou um `raise` incondicional do `TimeoutError`. Como `app/api/v1/endpoints/search.py` capturava apenas `ValueError`, a exceção `TimeoutError` subiu até o handler genérico do FastAPI em `app/main.py`, que gerou a resposta genérica **HTTP 500**.
4. **Ausência de Erro Tipado e Ação Corretiva para o Frontend**:
   O frontend recebeu HTTP 500 sem metadados acionáveis sobre a possibilidade de retry, e pontos subsequentes não foram processados.

---

## 2. Correções Implementadas

### 2.1. Criação e Await Explícito de Tasks no `Searcher` (`app/core/searcher.py`)
- As corrotinas de `_executar_persona` agora são encapsuladas explicitamente em `asyncio.Task` nomeadas (`persona_{p}_{p_id}`).
- Ao ocorrer `TimeoutError` ou `CancelledError`:
  - Todas as tasks que ainda não terminaram recebem `task.cancel()`.
  - O loop executa `await asyncio.gather(*tasks, return_exceptions=True)`, garantindo que todas as tasks sejam canceladas e finalizadas de forma limpa, fechando conexões HTTP e evitando vazamento de tarefas em background.

### 2.2. Exceção Tipada `SearchTimeoutError` (`app/tools/errors.py`)
- Criada a classe `SearchTimeoutError(TimeoutError)` carregando:
  - `id_pesquisa`, `ponto_id`, `ponto_n`, `timeout_seconds`, `diagnostico`.

### 2.3. Persistência e Liberação de Reserva do Ponto
- No momento do timeout, as evidências parciais (fontes, trechos e envelopes já completados por outras personas) são salvas atomicamente em `conteudo_coletado`.
- O ponto é registrado com status `falha_coleta` com diagnóstico explicativo.
- A reserva atômica (`reservado_ate`) é liberada. O ponto **não fica preso em `em_andamento`**.

### 2.4. Resposta HTTP 504 no Endpoint (`app/api/v1/endpoints/search.py`)
- O endpoint captura `SearchTimeoutError` e `TimeoutError` e retorna **HTTP 504 Gateway Timeout** estruturado:
```json
{
  "detail": {
    "tipo": "TIMEOUT_ERROR",
    "mensagem": "Tempo limite de busca excedido (480.0s) no ponto 1. Coleta interrompida.",
    "diagnostico": "Interrupção por timeout (480.0s excedidos no ponto 1)...",
    "id_pesquisa": "0f1c33b4-6e97-4348-81a8-8d84e7fca8ac",
    "ponto_id": "af83cc21-dec0-4c34-9650-fac14effbd00",
    "ponto_n": 1,
    "timeout_segundos": 480.0,
    "re_tentavel": true
  }
}
```

### 2.5. Bloqueio Íntegro no Writer e Retentativa Segura (Safe Retry)
- Uma tentativa de chamar o Writer (`POST /api/v1/writer`) com o ponto em `falha_coleta` é estritamente bloqueada (HTTP 400 `UNAPPROVED_POINTS`).
- Uma nova chamada `POST /api/v1/search` com o mesmo `id_pesquisa` reprocessa o ponto pendente sem replanejamento e sem perda de dados.

---

## 3. Análise de Orçamento de Tempo (Safe Timing)
- **Observado no teste real**: 2 personas lendo 14 URLs reais levaram ~482s (~240s por persona).
- **Causa da latência**: Provedores de busca e leitura na internet sujeitos a rate limits, páginas volumosas e latência de inferência de modelos de raciocínio.
- **Configuração**: `SEARCH_POINT_TIMEOUT_SECONDS` agora aceita configuração por variável de ambiente (mantendo 480s como padrão de produção), permitindo ajustes operacionais caso a infraestrutura de rede externa apresente latências superiores a 8 minutos por ponto.

---

## 4. Testes Automatizados de Regressão Criados

Arquivo: `tests/integration/test_web_timeout.py` (3 testes determinísticos utilizando SQLite isolado):

1. `test_search_point_timeout_returns_504_and_releases_reservation`:
   - Configura deadline curto (0.2s) com `SlowMockTransport` assíncrono.
   - Valida retorno HTTP 504 com payload tipado `TIMEOUT_ERROR`, `re_tentavel=True` e `ponto_n=1`.
   - Confirma no SQLite que o ponto não ficou em `em_andamento`, está em `falha_coleta` e com reserva liberada.
2. `test_search_timeout_blocks_writer_until_successful_retry`:
   - Simula estouro de timeout (HTTP 504), confirma que o Writer bloqueia com HTTP 400, e em seguida executa retry com sucesso (HTTP 200) na mesma pesquisa.
3. `test_search_timeout_preserves_partial_evidence_from_completed_persona`:
   - Simula cenário onde uma persona (`historiador`) conclui rapidamente e outra (`cetico`) estoura timeout.
   - Confirma retorno HTTP 504 e persistência segura das fontes e conclusões do historiador no banco de dados.

```bash
$ .venv/bin/pytest tests/integration/test_web_timeout.py -v
3 passed in 1.48s
```

Suíte integral do repositório:
```bash
$ .venv/bin/pytest -q
381 passed, 8 warnings in 47.82s
```
