# Coleta por personas — desenho interno

## Ordem de chamadas (`Pipeline._coletar`, `src/orchestrator.py:225-322`)

1. Para cada `(ponto_id, persona)` monta `payload_buscador` + `hydrator.montar` (template `buscador.md` p/ as 4 personas, `src/hydrator.py:41`).
2. Um único `_executar_lote(workspace, tarefas, BuscadorSaida.model_validate)` (`:259`).
3. Por ponto: `ignoradas=set`, filtra lidas/usadas (`:279-280`), `_registrar` cada persona (`:282-288`), emite `fonte.lida` com arrays (`:291-301`); `hidratar` → `ponto.coletado` com acumulados (`:302-313`); zero sucessos → `ponto.erro` + remove (`:314-322`).

## `_executar_lote` (`src/orchestrator.py:547-578`)

Loop até `tentativas_por_agente`: `executor.executar` → `_registrar_orquestrador` (tokens delegador) → valida cada `call`; inválido → `_registrar` + `_corrigir`; tarefa sem `call` vira `AgentCall(erro="tarefa sem saída")`. **CONFIRMADO**

## Módulos e fronteiras

- `hydrator.payload_buscador` dado puro; `HermesRunner` executa; `Repositorio` persiste. `_coletar` não lê `state.db` — telemetria chega no `AgentCall`. **CONFIRMADO**
- `BuscadorSaida`: `informacao_coletada` strip + não-vazia; `urls_usadas=normalizar_urls`; `urls_lidas=normalizar_urls([*lidas,*usadas])` — usada sempre nas lidas (`src/contracts.py:144-164`). **CONFIRMADO**

## Higiene de URL (`src/contracts.py:20-51`)

`_limpar_url` tira espaços e `.,;)]>` finais; `normalizar_urls` dedup preservando ordem, ignora não-string/vazia, **levanta `ValueError` em URL inválida**. **CONFIRMADO**

## Decisões e trade-offs

- Bloqueio programático da re-busca no backend em vez de só prompt — defesa em profundidade. **INFERIDO** (mecanismo CONFIRMADO).
- Falha parcial tolerada (3 de 4 bastam); ponto zerado sai sem abortar run. **CONFIRMADO**.
- Compactação antes do prompt (D-11): DB integral, prompt sem duplicatas/ruído, fatos (dígito/URL/data/citação) intactos. **CONFIRMADO**.
