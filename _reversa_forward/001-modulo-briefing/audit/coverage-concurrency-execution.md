# Execução de cobertura de concorrência — T019 recorte B

## Escopo

Testes adicionais apenas. Cobre retries LLM sequenciais/esgotados, cancelamento externo de Task e composição de exaustão do cliente Jina real com `generate_briefing`. Serviço, domínio, cliente, configuração e testes irmãos não alterados. A inspeção T006–T010 reportou O-02 (canary ausente), O-03 (identidade em fluxos) e O-04 (assert de sequencialidade insuficiente); este recorte cobre os comportamentos aqui indicados, sem reabrir achados fora do escopo.

## Testes e execução

Arquivo: `tests/test_briefing_generation_concurrency_qa.py` (153 linhas).

- `test_llm_retries_and_exhaustion_are_sequential_and_reuse_search_payload`: erros conhecidos em 3 chamadas e sucesso na quarta; esgotamento em 4 erros. Mede concorrência ativa máxima 1 e zero ao fim, uma busca, mesmo payload em todas tentativas, estado final DRAFT/FAILED e mensagem fixa. `llm_attempts` default 4, sem chamada adicional. Compara pontos retornados título/descrição exatos contra VALID_POINTS no sucesso e `()` na falha.
- `test_external_task_cancellation_propagates_and_skips_failure_transition`: aguarda início via Event com guarda de 1s, cancela Task externa, observa `CancelledError`, cleanup no `finally`, contador ativo zerado e transição `fail_briefing` não chamada. Guarda `finally` cancela e aguarda tarefa em falha de assert.
- `test_real_jina_client_exhaustion_composes_with_service_failure`: `CountingClient(JinaSerpClient)` local conta exatamente 1 chamada ao método `search` sem substituir política interna de retries. `httpx.MockTransport` retorna HTTP 500 em 4 requisições; serviço fica FAILED com mensagem fixa, sem chamada LLM e com pontos vazios `()`.

Comandos e resultados:

- `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python3 -m compileall -q tests/test_briefing_generation_concurrency_qa.py` — exit 0.
- `python3 -m unittest tests/test_briefing_generation_concurrency_qa.py -v` — exit 0; 3 testes passam.
- `python3 -m unittest tests/test_briefing_domain.py tests/test_briefing_generation.py tests/test_briefing_generation_boundaries_qa.py tests/test_briefing_generation_concurrency_qa.py tests/test_briefing_generation_flow_qa.py tests/test_briefing_lifecycle.py tests/test_briefing_lifecycle_qa.py tests/test_briefing_prompt_loader.py tests/test_briefing_schemas.py tests/test_briefing_serp_client.py tests/test_briefing_validation.py` — exit 0; suíte combinada de 89 testes passa (não baseline pré-complementos de 79). Esse check incluiu arquivos QA irmãos durante o batch, contrariando isolamento requerido; parent repetiu somente após encerramento, em módulos separados 3/3, focados 34, baseline 49, descoberta 89, compile 3 e diff, cada exit 0.
- `git diff --check` — exit 0; sem erros de sintaxe ou espaçamento.

## Limites

CountingClient e contadores de concorrência medem apenas esta invocação async no processo atual; não garantem exclusão mútua global nem binder/logs crossprocess. HTTP real, credencial real e rede não foram usados; transporte foi simulado e chave fictícia local. Teste não cobre todos canaries de prompt/SERP/saída/detalhes de exceção; O-02 integral permanece parcial. Identidade por factory e snapshots por fluxo pertencem ao recorte A de fluxo em arquivo irmão; não alegar cobertura aqui. Nenhum histórico RED é inferido nem alegado.
