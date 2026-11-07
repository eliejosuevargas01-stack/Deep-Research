# Coleta por personas — comportamento observado

Fonte: `src/orchestrator.py` (`_coletar`), `src/hydrator.py` (`payload_buscador`), `src/contracts.py` (`BuscadorSaida`), `src/evidencias.py`, `src/prompts/buscador.md`, `src/hermes_runner.py` (`INSTRUCAO_LOTE`).

## Entradas

- Estado por ponto `{ponto_id: {ponto, pendentes, ignoradas, rodada}}` montado de `obter_pontos`. **CONFIRMADO** (`src/orchestrator.py:137-145`)
- `payload_buscador(...)` com `research_id, tema, atualidade, ponto, persona, rodada, perguntas_pendentes, urls_ignoradas, max_queries` (`src/orchestrator.py:235-245`, `src/hydrator.py:51-78`). **CONFIRMADO**
- `max_queries_por_persona = 3` (`src/config.py:17`, `config/hermes_config.yaml:6`); backend entrega no payload, quem limita é o agente. **CONFIRMADO**
- Teste: `tests/test_garantias.py::test_payloads_carregam_atualidade_e_lacunas`. **CONFIRMADO**

## Regras

- R-CP-01 — 4 personas fixas `historiador, cetico, visionario, futurista`; 1 tarefa por persona/ponto/rodada, id `{persona}_p{ponto_id}_r{rodada}` (`src/orchestrator.py:247-257`). **CONFIRMADO**
- R-CP-02 — Fan-out em **um único lote**: `_coletar` monta N×4 tarefas e chama `_executar_lote` uma vez (`src/orchestrator.py:259`); profundidade 10 → 40 tarefas. **CONFIRMADO** por `tests/test_pipeline.py::test_coleta_fan_out_40_em_um_lote` (lote 40).
- R-CP-03 — Teto 40 **não é enforced pelo backend**: sem fatiamento; vive na instrução (`INSTRUCAO_LOTE`, `src/hermes_runner.py:43-53`), em `max_concurrent_children: 40` (`config.yaml:10`, perfil) e no contrato (`profundidade le=10`, `src/contracts.py:58`). **CONFIRMADO** (D-05).
- R-CP-04 — Blacklist no backend E no prompt: filtra `urls_lidas/usadas` contra `ignoradas` (`src/orchestrator.py:278-280`); prompt avisa. **CONFIRMADO** por `tests/test_garantias.py::test_blacklist_remove_url_repetida_entre_rodadas`.
- R-CP-05 — Falha isolada por persona: sem saída = `logger.warning` e segue; ponto só sai do run se **zero** sucessos (`ponto.erro` evento, remove do estado, `src/orchestrator.py:314-322`). **CONFIRMADO** por `tests/test_pipeline.py::test_falha_de_uma_persona_nao_derruba_o_ponto` e `::test_falha_total_do_ponto_marca_run_como_failed`.
- R-CP-06 — Retentativa: saída inválida vira `_corrigir` (prompt + `## Correção obrigatória`) até `tentativas_por_agente`. **CONFIRMADO** (`src/orchestrator.py:547-578`).
- R-CP-07 — Eventos por coleta: `ponto.iniciado` (`:262`), `fonte.lida` com **arrays** `urls_lidas/urls_usadas` (`:291-301`), `ponto.coletado` com `urls_usadas/urls_lidas` acumuladas + `personas` (`:303-313`). **CONFIRMADO** (formato backend = arrays; divergência F1 do audit-frontend sobre UI não se aplica ao backend).
- R-CP-08 — Compactação (D-11): auditor/redator recebem `compactar_acumulado` (dedup + ruído conservador, fatos intactos) + `compactacao{}`; DB nunca reescrito. **CONFIRMADO** — `src/evidencias.py:1-123`, `src/hydrator.py:90-101,115-128`, `tests/test_evidencias.py:18-103`.

## Mapeamento

- RF02 (40), RF03 (acúmulo; prompt compactado sem perda factual, DB integral), RF06 (retentativas/blacklist), RNF03 (isolamento). `INFERIDO`.
