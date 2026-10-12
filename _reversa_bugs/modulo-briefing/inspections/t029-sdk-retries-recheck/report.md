# Reauditoria T029/T032/T033 — três observações LOW

## Veredito
**PRONTO PARA QA FOCADA, SEQUENCIAL.** O-TEST-01, O-DOC-01 e O-DOC-02 **SANADAS** no recorte solicitado. Três observações LOW reavaliadas, confiança alta; zero pendentes neste recorte, zero novos defeitos de produto, zero bugs promovidos. Não constitui aceite global nem fecha T029/T032/T033. `promoted_to: null` para cada observação.

## Preflight e mapa curto
Root `/root/projects/deep-research`, branch `main`, HEAD `c741ce77dedfb88d11a8f0916482c721251f112d`. AGENTS.md e `.reversa/state.json`, `active-requirements.json`, `reversa-config.json` lidos. Feature ativa `_reversa_forward/001-modulo-briefing`, estágio coding. Worktree já sujo; alterações preexistentes não atribuídas à reauditoria.

- **Spec:** `requirements.md` permanece fonte de produto greenfield. Recorte corretivo em `_reversa_forward/001-modulo-briefing/actions.md:83–87`: T029 one-request OpenAI 503; T032 cleanup; T033 qualificação documental. Não reabre contrato/planejamento.
- **Código:** `app/briefing/llm_binding.py:72,81–98`: helper real, `num_retries=0`, `max_retries=0`, chamada e conversão elegível em `LLMAttemptError`. Produto PASS anterior preservado, sem mudança de produção.
- **Testes:** `tests/test_briefing_llm_binding.py:223–286`, SDK/LiteLLM reais com HTTPX MockTransport 503; módulo contém 12 métodos (11 async + 1 sync). Getter HTTP async substituído, não `acompletion` nem helper.
- **Dados:** settings/chave/modelo fictícios em memória; transporte simulado. Sem DB ou dados persistidos exercitados.
- **Dedupe:** somente O-TEST-01/O-DOC-01/O-DOC-02 de `../t029-sdk-retries/report.md:28–42`. T030/F-ERROR-01 e T031/F-CONSISTENCY-01 conhecidos, excluídos.

## Observações reavaliadas

### O-TEST-01 — SANADA
Lentes cobertura/consistência; severidade original **LOW**, confiança **alta**, `promoted_to: null`.

Evidência estática: `tests/test_briefing_llm_binding.py:226–228` captura redirects dos dois clientes antes do helper; `:258–269` registra cleanup e restaura atributos/factories/getter/flags; `:271` fecha cliente HTTPX por `async with`; `:275–278` restaura getter e logging/telemetry via contextos de patch (`telemetry=False`, `create=True`); `:280–286` conserva helper real, `assertRaises(LLMAttemptError)` e count 1.

Probe independente `python3 -B -c`, `BindingTests(...).run(unittest.TestResult())`, `socket.socket.connect` bloqueado: seeds False/False e True/True resultaram respectivamente `[False, False]` e `[True, True]`, cada caso 1 teste, 0 failures, 0 errors. Descriptors das duas factories e dos dois getters, flags `_SAFE_TRANSPORT_ACTIVE/_SAFE_TRANSPORT_ERROR`, presença/ausência e valores de telemetry/logging/callbacks monitorados preservados. Probe restaura estado original em `finally`. **Exit 0**. Não extrapola para todos os globais/background do SDK.

### O-DOC-01 — SANADA
Lente evidência documental; severidade original **LOW**, confiança **alta**, `promoted_to: null`.

`_reversa_forward/001-modulo-briefing/audit/t029-execution.md:22` qualifica RED/GREEN e detalhes RED como auto-relato histórico com traceback parcial não autenticado; `:40–47` separa validação factual atual. `:41` registra helper real conforme teste atual; `:42` registra contraprova anterior removendo ambos kwargs, 3 requests, unittest interno FAILED (failures=1), processo exit 0 esperado. `:43` distingue checks do auditor e discover informado pelo parent; `:44` reproduz resultado CONDITIONAL do relatório anterior, não novo gate.

História `:12–20,32` pode permanecer: limitação explicitamente qualificada, não autenticável por execução nova. Contraprova não reexecutada nesta reauditoria nem usada para fabricar prova histórica. Comando discover físico `:27` tem **zero barras invertidas**, verificado por leitura; nenhum defeito de escape. Checks semânticos **exit 0**.

### O-DOC-02 — SANADA
Lente rastreabilidade documental; severidade original **LOW**, confiança **alta**, `promoted_to: null`.

`_reversa_forward/001-modulo-briefing/regression-watch.md:158–163` supersede explicitamente parágrafo histórico `:129`; `:160` registra T024/T027 implementadas e QA persistido local, sem inventar pendência de segunda acompletion. Fonte existente `audit/qa-sprint7-persisted.md:3–4,38–50` declara PASS local e seus checks, corroborada por `actions.md:80–81` [X]. Não reexecutada QA DB neste recorte. `regression-watch.md:161–163` mantém T030/T031/API e fechamento W020 pendentes; T032 aberto representa gate ainda não fechado, não contradiz entrega para reauditoria.

Leitura semântica, referência local e tabelas Markdown verificadas: 14 tabelas regression-watch com larguras consistentes; execution sem tabelas. **Exit 0**. IDs históricos preservados.

## Checks e integridade
- `python3 -B -m unittest tests.test_briefing_llm_binding -v`: **exit 0**, Ran 12 tests in 0.501s, OK. Teste SDK exige count 1 e `LLMAttemptError`.
- Probe redirects/estado, imports normais e socket bloqueado durante TestCase.run: **exit 0**, dois seeds PASS.
- Probe adicional bloqueando socket desde imports, com `OSError` para fallback nativo SDK: **exit 0**, dois seeds PASS; fetch de model-cost map bloqueado, fallback local observado. Primeira versão usando `AssertionError` desde import: **exit 1**, import abortou antes de testes; substituída pelo probe acima, não falha de produto.
- Validação semântica/tabelas/referência/discover/AST em Python stdlib: **exit 0**, AST 12. Primeira contagem de pipes por remoção de code spans falhou sobre cerca Markdown; contagem corrigida usa separadores físicos não escapados, sem editar documentos.
- `git diff --check`: **exit 0**. Abrange diff rastreado, não arquivos untracked.
- Baseline da última linha `progress.jsonl:66`: **94/94 SHA-256 coincidentes** antes e após checks. Progress separado preservado, 66 linhas, SHA-256 `399f80ad6c84f7dc81aa7d6312619ff978c41e291ba0645c289ea61a0bf9baac`.

Warnings Pydantic ReadOnly/asyncio slow-task não produziram falhas. Uma tentativa inicial de preflight apontou diretório inexistente `input_repo` (exit 126); root absoluto correto usado nas verificações subsequentes.

## Contagens, cluster e exclusões
Cobertura/consistência: 1 LOW sanada. Documental: 2 LOW sanadas. Confiança: alta 3, média 0, baixa 0. Findings novos: critical 0, high 0, medium 0, low 0. Pendentes neste recorte: 0. Bugs promovidos: 0. Cluster anterior qualidade da evidência saneado no escopo, sem novo cluster de produto.

Não executados: discovery/global, QA paralela, QA DB/API, live/provedores, .env, instalação, commit/push/deploy. Sem reauditoria T030/T031, segurança integral de traceback, ownership/transações, todos os providers ou tarefas internas SDK. Limitações conhecidas não duplicadas como defeitos.

Única escrita de projeto: este relatório novo. Relatório anterior, produção, testes, docs, ações, progress, state, views e bugs preservados. Nenhuma ação fechada. Próximo gate: QA focada sequencial após entrega verificada deste relatório; aceite global permanece fora do recorte.
