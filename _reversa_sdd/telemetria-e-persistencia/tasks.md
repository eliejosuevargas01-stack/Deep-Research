# Telemetria e persistência — tarefas

- [x] `research_events` + `idx_events_lookup` nos dois dialetos — `src/db/schema.sql:76-85`, `src/db/sqlite_manager.py:81-90`. `CONFIRMADO`.
- [x] Telemetria real `state.db` `:ro` + fallback `usage.json` → `orquestrador` — `src/telemetria.py:97`, `src/hermes_runner.py`. `CONFIRMADO` (testes `test_lacunas.py`).
- [x] DB integral × prompt compactado (D-11) — `hidratar` sem corte + `tests/test_evidencias.py:95-96`. `CONFIRMADO`.
- [ ] Executar `schema.sql` em PostgreSQL real e registrar diff. **LACUNA** (PG nunca executado).
- [ ] `state.db` ausente / `cwd IS NULL` sem teste dedicado (caminhos lidos `:93,:107`). **LACUNA** parcial (executável via tmp+monkeypatch).
- [ ] Truncamento 20k sem teste de estouro. **LACUNA** parcial.
- [ ] Concorrência sob `RLock` nunca exercitada. **LACUNA**.
