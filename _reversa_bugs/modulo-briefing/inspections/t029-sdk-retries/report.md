# Inspeção independente T029 — retries SDK

## Resultado
Produto **PASS no recorte OpenAI 503**; evidência **CONDITIONAL** quanto a isolamento/relato histórico; processo **CONDITIONAL** quanto a documentação. Zero defeitos novos de produto, 3 observações (2 LOW documentais, 1 LOW de isolamento), confiança alta; todos `promoted_to: null`. Não fecha T029 nem autoriza aprovação integral da feature. T030/F-ERROR-01 e T031/F-CONSISTENCY-01 continuam abertos, fora do recorte.

## Preflight / integridade
Root `/root/projects/deep-research`; branch `main`; HEAD `c741ce77dedfb88d11a8f0916482c721251f112d`. AGENTS.md, `.reversa/state.json`, `.reversa/active-requirements.json` e `.reversa/reversa-config.json` lidos. Feature ativa `001-modulo-briefing`, coding; produto definido por requirements greenfield, não pelas regras implícitas do legado. Worktree previamente sujo/untracked; não atribuído à inspeção.
Última linha de progress contém baseline congelada: 91 hashes, todos coincidentes antes e depois dos checks. Progress contém 64 linhas; seu hash capturado separadamente permaneceu idêntico (record exclui self por design). Única escrita: este relatório novo. Sem subdelegação, todo_list, bugs/views, código/testes, ações ou progresso modificados.

## Mapa spec / código / testes / dados
- Spec: `_reversa_forward/001-modulo-briefing/actions.md:82`, RF-10 em `requirements.md` (limite total 4 tentativas externas; esclarecimentos :143–162), `audit/t029-t031-planning-delta.md:17–19`, D5 vigente em `audit/t011-integration-decomposition.md:95–120`, especialmente :111. Exige os dois kwargs e uma tentativa HTTP OpenAI com 503. `audit/cross-check.md:9` é PASS documental, não prova runtime.
- Código: `app/briefing/llm_binding.py:81–85` contém somente dois controles e três comentários no bloco de retry; :90 invoca `acompletion`; :93–99 converte falha elegível em `LLMAttemptError`. Transporte seguro de `app/services/llm.py:19–101` lido, não alterado. Reconstrução de SHA pré-dispatch removendo bloco mínimo foi informada pelo parent, não refeita aqui.
- Testes: `tests/test_briefing_llm_binding.py`, 12 métodos, 10 anteriores + 2 T029. :223–277 usa `acompletion` real, OpenAI SDK real, HTTPX MockTransport 503, cliente async fechado por contexto, assertRaises em :273 e count em :277. :279–298 verifica kwargs por AsyncMock, incluindo seleção runtime de modelo/chave. Modelo OpenAI é fixture, não requisito do produto.
- Dados: fixtures falsas em memória de settings/chave/modelo; MockTransport conta requests. Nenhum DB, fila, cache persistido ou rede de provedor exercitado. Representação redacted da chave no display não prova Unicode; validade ASCII foi informada pelo parent, sem imprimir token.
- Dedupe: inspeção anterior `_reversa_bugs/modulo-briefing/inspections/t023-t028-binding/report.md` identifica F-CONTRACT-01, F-ERROR-01, F-CONSISTENCY-01. Só primeiro reavaliado.

## Lentes no recorte
1. **Conformidade:** kwargs `num_retries=0` e `max_retries=0` explícitos, PASS no contrato acordado. Não generaliza provedores/configurações globais.
2. **Fluxo de dados:** controles inteiros zero saem do dict diretamente para `acompletion`; teste happy path verifica modelo/chave/mensagens/timeout. Sem alteração de dados persistidos; ownership DB pertence T031.
3. **Contratos/integrações:** LiteLLM 1.104.0, OpenAI 2.54.0, HTTPX 0.28.1 observados via metadata instalada. Trace independente sobre MockTransport confirmou exatamente `POST /v1/chat/completions`, count 1. Probe bloqueou `socket.socket.connect`; nenhuma conexão live bem-sucedida.
4. **Erros/edges:** teste exige `LLMAttemptError`, não apenas count. Segurança completa dos campos/traceback e matriz 500/conexão pertence T030, não comprovada por esse assert. Controle sucesso-após-503 foi informado pelo parent (`LLMAttemptError not raised`), não reexecutado aqui.
5. **Cobertura:** 2 focados e 12 módulo PASS. Contraprova independente remove ambos controles somente em wrapper runtime e delega ao `acompletion` real: count 3, teste falha com `AssertionError: 3 != 1`. Não prova necessidade causal isolada de cada controle; prova sensibilidade conjunta do teste. Histórico RED não reconstruído.
6. **Concorrência/consistência:** contagem local sequencial; isolamento de globais sondado abaixo. Sem auditoria cross-process/orquestrador ou alegação de ausência de tarefas internas do SDK.
Condicionais: configuração/flags e isolamento ativados; segurança limitada a não imprimir fixtures e bloquear sockets na sondagem. Performance, autorização/API, migrations, live, SLA, todos os providers excluídos.

## Observações / findings (não produto)

### O-TEST-01 — cleanup não restaura redirects previamente True
- Lente cobertura/consistência; severidade **LOW**; confiança **alta**; `promoted_to: null`.
- Evidência: `tests/test_briefing_llm_binding.py:247–261` restaura factories/sync getter/flags; patch :267 restaura async getter. Não restaura atributos dos clientes globais modificados por `app/services/llm.py:76–83`.
- Probe `python3 -B -c` (socket bloqueado, unittest SDK, snapshot globals, clientes semeados) exit **0**: execução normal `globals_changed []`, `telemetry_is_none True`; depois semear `follow_redirects=True` nos dois clientes de módulo e executar mesmo teste deixou `[False, False]`, embora teste PASS. Probe restaurou valores originais em finally; processo descartado.
- Portanto isolamento completo não demonstrado para estado inicial alternativo. Nenhuma mudança de callbacks/telemetry observada nos nomes monitorados (`callbacks`, success/failure, variantes async, telemetry, suppress_debug_info, turn_off_message_logging); isso não prova todos os globais/background.
- `telemetry=False` explícito ausente (:264–270), default observado None; não foi confirmado tráfego de telemetria. Não afirmar causalidade de retry/logging decorrente de `turn_off_message_logging=True`.

### O-DOC-01 — relato de execução diverge de teste atual
- Lente evidência; severidade **LOW**; confiança **alta**; `promoted_to: null`.
- `audit/t029-execution.md:30` diz `_enforce_safe_transport` patchado; teste atual :271 e binding :72 executam helper real. RED3/GREEN1 histórico :12–20 é relato, traceback original incompleto; contraprova desta inspeção é nova evidência, não autenticação do histórico.
- Comando `python3 -B -c` com leitura física de linha 25 retornou `execution_line25_backslash_count 0`, exit **0**. Contradiz nota de contexto do parent que alegava barras antes de aspas; baseline SHA do documento coincide. Não registrar inexistente defeito de escape nem corrigir documento.

### O-DOC-02 — W020 mantém T024 pendente apesar de entregue
- Lente rastreabilidade; severidade **LOW**; confiança **alta**; `promoted_to: null`.
- `regression-watch.md:129` adendo cita T024 pendente; `actions.md:79–80` marca T024/T027 entregues. Evidência por leitura `python3 -B -c`, exit **0**. Drift documental, não defeito runtime. Históricos anteriores não reinterpretados como estado atual.

Cluster: qualidade da evidência de T029 (cleanup e relato documental); nenhum cluster novo de defeito produto. Contagens: cobertura/consistência 1; documental 2; alta 3, média 0, baixa 0. Limite multi-provider é exclusão, não finding.

## Checks reais (sequenciais, workdir absoluto)
- `python3 -B -m unittest tests.test_briefing_llm_binding.BindingTests.test_no_internal_retries_on_503_openai_sdk tests.test_briefing_llm_binding.BindingTests.test_kwargs_include_no_retry_controls -v`: **exit 0**, 2 testes OK.
- `python3 -B -m unittest tests.test_briefing_llm_binding -v`: **exit 0**, 12 testes OK.
- `python3 -B -c` probe trace/isolation: **exit 0**, 1 request no cenário normal; 2 execuções unitárias SDK OK; mudança redirects seeded confirmada acima.
- `python3 -B -c` probe negativo removendo ambos kwargs, wrapper delegando SDK real: processo **exit 0** por assert de contraprova esperada; unittest interno **FAILED (failures=1)**, requests 3, errors 0. Não relatar exit 1 do processo. Sockets bloqueados.
- `git diff --check`: **exit 0**.
- SHA/readset: **91/91** congelados iguais, progress separado igual, 64 linhas.
Warnings Pydantic ReadOnly e asyncio slow-task vistos; não constituem falha destes checks.

Não executados aqui: discover global (128 exit0 informado pelo parent), compile (exit0 informado pelo parent), QA independente, instalações, DB, .env, rede live, commit/push/deploy. Nenhuma tarefa fechada ou finding corrigido.

## Conclusões separadas
- **Produto PASS:** F-CONTRACT-01 corrigido no caminho instalado OpenAI 503: exatamente 1 HTTP request + `LLMAttemptError`, ambos controles presentes, contraprova conjunta sensível.
- **Evidência CONDITIONAL:** prova runtime positiva/negativa suficiente ao recorte; isolamento de estado alternativo incompleto; proveniência histórica RED limitada. Não invalida PASS de produto.
- **Processo CONDITIONAL:** relato helper e W020 demandam revisão documental futura fora desta única escrita. T029 continua aberta; QA sequencial posterior e T030/T031 não aprovados por este relatório.
