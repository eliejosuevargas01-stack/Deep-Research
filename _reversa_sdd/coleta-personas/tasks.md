# Coleta por personas — tarefas

- [x] Teto 40 por construção (`profundidade le=10`, lote N×4, `max_concurrent_children: 40`) — D-05. **CONFIRMADO**.
- [x] Eventos `fonte.lida`/`ponto.coletado` com arrays de URLs — `src/orchestrator.py:291-313`. **CONFIRMADO**.
- [x] Compactação sem perda factual + `compactacao{}` — D-11, `tests/test_evidencias.py`. **CONFIRMADO**.
- [ ] **Validar teto real de 40 contra Hermes real.** Neste host prova só via `FakeExecutor` (`test_coleta_fan_out_40_em_um_lote`) e YAML. **LACUNA** (depth 10 real nunca executado).
- [ ] Observar taxa de URLs filtradas pela blacklist (filtro silencioso `src/orchestrator.py:278-280`). Risco: custo sem sinal. `CONFIRMADO`.
- [ ] Revisar `tentativas_por_agente = 2` com dados de produção. `CONFIRMADO` (`src/config.py:18`).
