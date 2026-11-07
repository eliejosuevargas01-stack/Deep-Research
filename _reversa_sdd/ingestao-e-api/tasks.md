# ingestao-e-api — tasks

- [x] Auth por API key com `GET /health` aberto — feito `src/api.py:23-42`, `tests/test_api_key.py:32-87`. `CONFIRMADO`.
- [x] `GET /research` expor `auditorias[]` + `avaliacao_pontos` — feito `src/api.py:130-157` (D-04/D-08). `CONFIRMADO`.
- [x] SSE com snapshot/replay/heartbeat — feito `src/api.py:76-125`, `tests/test_eventos.py:81-107`. `CONFIRMADO`.
- [x] `PUT /config` rejeitar `base_url/api_key` — feito `src/settings.py:93-98,209-212` (D-10). `CONFIRMADO`.
- [ ] Validar `atualidade` semanticamente (regex aceita `0H` — `src/contracts.py:61`). Risco: janela sem sentido. `CONFIRMADO`.
- [ ] Documentar/remover alias `/api/v1/settings` ou promovê-lo ao schema (`include_in_schema=False` — `src/api.py:54,59`). Risco: contrato duplo. `CONFIRMADO`.
