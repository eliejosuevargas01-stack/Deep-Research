# Perguntas (todas respondidas em D-01..D-12)

- Q-01 webhook sem entrega → D-01: 5 tentativas (1,2,4,8s); 5xx/rede retenta, 4xx encerra; esgotadas raise; status segue COMPLETED. `src/webhook.py:14-50`.
- Q-02 formato agregado → D-08: `avaliacao_pontos` oficial no dossiê (`## Avaliação de veracidade`), webhook e `GET /research/{id}` (omitido sem pontos). `src/planner.py:44-76`, `src/db/repository.py:289-325,468-478,502`, `src/orchestrator.py:150-159`, `src/api.py:154-156`.
- Q-03 booleano estrito → D-02: manter rejeição de não-bool. `src/contracts.py:172-180`.
- Q-04 frontend → D-03: fluxo único v1.2 (`main.tsx` só monta `AppV12`; `apiV12.ts` + `ssePesquisa.ts` + `v12/`); legado `App.tsx`/`api.ts` fora do bundle.
- Q-05 histórico auditorias → D-04: `auditorias[]` por ponto/rodada em `GET` via `obter_auditorias`. `src/db/repository.py:257-287`, `src/api.py:136-153`.
- Q-06 teto 40 → D-05: `profundidade` 1..10 (`src/contracts.py:58` `le=10`), lote N×4, `max_concurrent_children: 40`. Sem trava nova.
- Q-07 bloco morto → D-06: removido; `config/hermes_config.yaml` hoje só seção `pipeline` (14 linhas, sem `delegation`).
- Q-08 urls planner → D-07: `PlanoLLM.urls_lidas/urls_usadas` (`src/contracts.py:118-141`), `_registrar` (`src/orchestrator.py:194-200`), consolidação lê tudo (`src/db/repository.py:445-457`).
- Q-09 modelos por papel → D-09: forte `ocg/deepseek-v4.1-flash` (planner/auditor/redator/default) + leve `gemini/gemini-3.5-flash-lite` (4 buscadores). `src/settings.py:31-55`, entrypoint `modelo_do_papel`, `config.yaml:1-21` 7 papéis, `MODELS.json:107-110`.
- Q-10 API key → D-10: `X-API-Key`/Bearer/`?api_key=` SSE; 401; `GET /health` aberto mesmo com chave. `src/api.py:23-42`; `tests/test_api_key.py:32-87`.
- Q-11 compactação → D-11: DB integral; prompt compactado sem perda factual + `compactacao{}`. `src/evidencias.py:1-123`, `src/hydrator.py:90-101,115-128`, `src/db/repository.py:354-389`.
- Q-12 latest → D-12: `FROM nousresearch/hermes-agent:latest` aceito (`engine/Dockerfile:2-5`).

Nenhuma pergunta aberta.
