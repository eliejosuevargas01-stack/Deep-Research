# Sprint 5 — T006/T010: testes e evidências

## Veredicto

**FINDINGS — seis observações de cobertura, nenhum bug de produto confirmado.** Severidades das lacunas: critical 0, high 0, medium 3, low 3. Todos os achados têm confiança alta e `promoted_to: null`. Severidade descreve risco da evidência insuficiente, não defeito observado no serviço. Próximo gate: incorporar casos mantidos em QA após inspeção do serviço; nenhuma correção nesta etapa.

## Escopo e preflight

Branch `main`, root `/root/projects/deep-research`. AGENTS.md e `.reversa/{state,active-requirements,reversa-config}.json` lidos. Feature ativa `_reversa_forward/001-modulo-briefing`, contexto `modulo-briefing`, idiomas pt-BR, `allowLegacyEdits: true`. Árvore já suja no início, com mudanças e exclusões anteriores à inspeção; nenhuma delas alterada aqui. Único artefato escrito: este relatório. Sem rede, DB, instalação, .env, delegação, todo_list ou leitura de relatórios irmãos.

Mapa: requirements.md RN-01–04/RF-01–04/RF-08/RF-10; roadmap.md:85–160, em especial matriz :146–158; actions.md:45/65. Implementação: `service.generate_briefing`, `_valid_config`, `_parse_points`, domínio `new_briefing/complete_briefing/fail_briefing`, loader e `JinaSerpClient.search`. Testes: `tests/test_briefing_generation.py`, 402 linhas, 29 métodos. Dados: registro imutável em memória, arquivo de prompt, payload JSON user, resultados SERP canned/MockTransport; sem persistência. Não consultar catálogo de bugs nem promover achados: recorte exclusivo de lente definido pelo delegador.

## Matriz a–m: teste e assert factual

Referências de linha abaixo pertencem a `tests/test_briefing_generation.py`.

| Cenário roadmap | Teste / linhas | O que assert comprova | Limite |
|---|---|---|---|
| a happy path | `test_happy_path_composes_prompt_search_and_llm_into_same_draft`:20–35; identidade/versão :364–386 | DRAFT, tema strip, 3 pontos, ordem search/llm, uma chamada de cada, system integral, JSON user exato incluindo `formato_saida`; versão 2 e título T0 em teste separado | UUID do DRAFT não comparado ao registro inicial; ver O-03 |
| b tema inválido | `test_invalid_theme_fails_before_any_io`:37–43 | whitespace lança InvalidContent, lista de spies vazia incluindo loader | 2/301 e tipos inválidos não exercitados neste serviço; O-01 |
| c SERP falha | `test_serp_failure_marks_failed_without_llm`:105–115; cliente real :319–345 | FAILED, erro fixo, fake search chamado uma vez, LLM não chamado; caso real recupera na quarta requisição | identidade na falha SERP não verificada; exaustão real de quatro falhas não composta aqui |
| d LLM duas falhas e sucesso | `test_llm_known_failure_retries_reusing_serp_and_succeeds`:117–132 | DRAFT, search 1, LLM 3, mesmo user nas tentativas | não observa UUID inicial nem máximo ativo de retries |
| e exaustão LLM | `test_llm_exhaustion_marks_failed_with_safe_error`:134–147 | FAILED, mensagem fixa, search 1, LLM 4 | canary não injetado no teste de segurança; O-02 |
| f prompt inválido | `test_invalid_prompt_marks_failed_before_any_external_io`:77–93; erro seguro :347–356; sucesso :20–35 | vazio/whitespace/None/int e PromptUnavailable geram FAILED antes de search/llm; detalhe interno não vaza; system preservado | loader real ausente/ilegível não exercitado aqui; não afirmar gate global do loader |
| g parse/count inválido | `test_llm_invalid_output_counts_attempt_and_can_recover`:149–162; `test_llm_wrong_list_shapes_exhaust_to_failed`:164–178 | erro JSON recupera na segunda; null/objeto/primitivos/2/8 pontos falham após 4, search 1 | campos ausentes/whitespace usados em listas com 1 ponto, confundidos com count inválido; O-05 |
| h cancelamento LLM | `test_cancelled_llm_propagates_without_retry`:240–249 | CancelledError propagado, uma chamada LLM | cancelamento levantado pelo callable, não cancelamento externo de Task; não monitora fail_briefing |
| i timeout por tentativa | `test_llm_timeout_retries_until_draft`:205–216; exaustão :297–307 | timeout 0.01s sobre sleep 0.05s consome tentativa: recuperação em 2 ou FAILED em 4 | 60s só configuração aceita com resposta imediata, não expiração longa; nenhum SLA provado |
| j configuração inválida | `test_invalid_config_raises_before_any_io`:45–52 | attempts 0/5/True/1.5 e timeout 0/-1/True/NaN/inf lançam ValueError com spies zero | attempts str/None e timeout str/None não mantidos; O-01 |
| k retorno não-string | `test_nonstring_llm_return_counts_attempt`:180–191 | None/dict/int consomem 4 tentativas e FAILED | search registrado mas não contado nesse teste; outros testes provam reuso |
| l exceção desconhecida | `test_callable_invalidcontent_and_runtimeerror_propagate_without_retry`:228–238; TimeoutError :218–226 | InvalidContent interno, RuntimeError e TimeoutError não imposto propagam em uma chamada | não spy de fail_briefing; loader desconhecido :95–103 e SERP desconhecido/cancel :309–317 têm cobertura adicional |
| m cerca/count | `test_json_fence_is_accepted_but_garbage_is_rejected`:251–259; `test_accepts_all_in_range_counts`:261–267; `test_unclosed_json_fence_is_rejected`:358–362 | cerca json válida aceita; prefixo rejeitado; 3/4/5/6/7 retornam contagem exata; cerca sem fechamento FAILED; 2/8 em g | cerca múltipla, linguagem errada, lixo posterior e tipos de campos não mantidos; O-05 |

## Isolamento e fronteiras

`unittest.IsolatedAsyncioTestCase` cria loop por teste. Fakes async locais, listas/contadores reinitializados por teste e por iteração; `client_for` usa staticmethod, sem binding inesperado. Patch de new_briefing limitado a context manager e domínio real usado para criar snapshot. `SERP` é lista global mutável compartilhada, mas nenhum fake/teste atual a altera e serviço apenas serializa; risco futuro de fixture, não vazamento observado. VALID é string imutável. Iterações são aguardadas antes da próxima, sem late-binding concorrente nesses loops. MockTransport não acessa rede e AsyncClient é fechado no finally. Testes reais de timeout usam asyncio.sleep, não sleep bloqueante.

Attempts 1 e 4 cobertos, custom cap 2 também; sucesso dentro de intervalos e exaustão comprovados. Timeout curto realmente expira; 30/60 só aceitação de configuração. Erros conhecidos, desconhecidos e CancelledError cobertos com exceções restritas. Concorrência entre invocações demonstrada :269–281, usando fakes distintos; não provar lock de instância Jina por esse caso. Sequencialidade de múltiplos retries não demonstrada pelo teste :283–295; O-04.

Loader real + tempfile :61–75: mesmo path recebe `first system`, depois `second system`, ambas observadas pelo LLM em gerações distintas. Prova releitura e refuta cache por path. Segunda chamada não assert DRAFT diretamente, mas observa system efetivamente entregue; restante do fluxo usa serviço real. Teste não compara default loader nem prova ausência de todo cache de infraestrutura.

Cliente Jina real + MockTransport :319–345: transport retorna HTTP 500 três vezes e sucesso na quarta. CountingClient registra UMA entrada search; transporte registra QUATRO. Prova tentativas internas do cliente e ausência de retry duplo nesse fluxo recuperável. Caso fake SerpSearchError(4) não prova execução de quatro tentativas; apenas fronteira de erro. Exaustão real integrada continua tarefa QA.

## Achados da lente cobertura

### O-01 — matriz b/j incompleta (medium)

Confiança alta; `promoted_to: null`; signals: operational-risk.

Evidência: roadmap:147/155 versus testes:37–52. Serviço valida tipos/limites corretamente em service:30–36/65 e domain:31–36; problema é regressão não protegida. Mutante em memória que devolve FAILED para attempts str ou timeout str/None, em vez de ValueError, passou 29/29. QA: adicionar tema de 2/301 caracteres e tipos não-string, limites válidos 3/300 no serviço; attempts str/None e timeout str/None, sempre spies loader/search/llm zero. Não aceitar probes transientes como testes mantidos.

### O-02 — teste de segurança com canary não injetado (medium)

Confiança alta; `promoted_to: null`; signals: security (cobertura, não vazamento confirmado).

Evidência: testes:388–398 define canary, mas loader retorna `good prompt`, SERP canned não contém canary e LLM levanta LLMAttemptError sem dados. `assertNotIn` não desafia qualquer origem sensível. Outros asserts de mensagem fixa e PromptUnavailable com detalhe interno são úteis, mas não sanam esse caso. Mutante que acrescenta raw à falha final apenas quando raw contém canary passou 29/29. QA: injetar canaries distintos em prompt, SERP, saída LLM inválida e detalhe de exceção conhecida quando contrato permitir; comparar resultado/erro, FAILED e pontos vazios. Logs só podem ser afirmados se capturados. Não exigir ocultação de erros desconhecidos que contrato manda propagar.

### O-03 — identidade não observada em todos os fluxos (low)

Confiança alta; `promoted_to: null`; signals: operational-risk.

Evidência: testes:368–380 reconstrói snapshot de domínio com UUID fixo e valida UUID na falha de parse; segundo patch :381–386 valida versão/título, não identidade inicial de sucesso. Falha SERP :105–115 tampouco compara id. Mutante que cria registro novo apenas na falha SERP passou 29/29. Mutante simples que recria registro no sucesso foi detectado (1 failure): criação dupla altera contagem observada no primeiro trecho, portanto não afirmar que toda recriação no sucesso passa. QA: factory spy que devolve registro real, guarda snapshot inicial e compara id/version final em sucesso direto, sucesso após retries, exaustão LLM, falha prompt e SERP; contar uma criação em cada fluxo. Implementação atual preserva briefing local nas chamadas complete/fail; nenhum bug de identidade demonstrado.

### O-04 — nome de teste de sequencialidade promete mais que assert (medium)

Confiança alta; `promoted_to: null`; signals: concurrency.

Evidência: testes:283–295 incrementa active, espera, decrementa e levanta CancelledError na PRIMEIRA tentativa. assert max == 1 é inevitável porque cancelamento encerra geração; não exercita dois retries. Serviço atual usa await dentro de loop sequencial :80–96, correto estaticamente. QA: fake que falha com LLMAttemptError três vezes, sucesso na quarta, guarda número de chamadas/max ativo e decremente em finally; max 1, 4 chamadas, search 1. Separar cancelamento externo de Task, com cleanup observado, do cancelamento levantado pelo callable.

### O-05 — validação de campos confundida com contagem (low)

Confiança alta; `promoted_to: null`; signals: operational-risk.

Evidência: testes:166 contém missing title, missing description e title whitespace em listas de UM item. Domínio rejeita count primeiro :41–42: não chega a validar campos :49–52. Primitivos [1,2,3] testam tipo de ponto, não title/description não-string. Mutante que normaliza campos ausentes/não-string/falsy somente em listas válidas 3–7 passou 29/29. Serviço/domain atuais validam corretamente. QA: listas de 3 válidos com apenas um campo inválido (None/int/bool/list/dict, ausente, vazio, whitespace), title e description separadamente; assert tentativas, search 1, FAILED e mensagem fixa. Ampliar cercas malformadas múltiplas/linguagem errada/lixo posterior; cerca não fechada já protegida.

### O-06 — proveniência RED insuficiente para todos os 29 (low)

Confiança alta; `promoted_to: null`; signals: rastreabilidade.

Recorte do transcript autorizado `/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_c0b7c80c/task-0.log` encontrou erro inicial `Failed to import test module`/serviço ausente e referência a execução happy-path. Importabort comprova ausência de capacidade, não 29 asserts comportamentais vistos falhar. Delegador informa RED comportamental posterior, mas recorte consultado não estabelece rastreio por método. Não declarar todos os 29 vistos RED sem transcript completo das execuções e ligação de versões/hash. QA: registrar por cenário teste vigente, motivo da falha RED e execução GREEN quando houver evidência; marcar proveniência ausente sem inventar histórico nem modificar progress/config nesta inspeção.

## Execução e durabilidade

Execução própria: `pytest tests/test_briefing_generation.py -v --tb=short` retornou **29 passed in 0.25s**, exit 0 (Python 3.14.7, pytest 9.1.1). Sem mudança de código. Mutação dinâmica via compile/exec exclusivamente em memória, teste recarregado por rodada: baseline 29/0 failures/0 errors; config str/None FAILED 29/0/0; novo id no DRAFT 29/1/0; novo id na falha SERP 29/0/0; normalização permissiva de campos 29/0/0; vazamento condicional de raw-canary 29/0/0. Mutantes não escritos e subprocesso encerrou com fonte original recompilada. São demonstrações de lacuna de asserts, NÃO comportamento do produto entregue.

Trace próprio com sys.settrace/unittest: 29 testes, zero failures/errors; visitadas todas as linhas de execução de `_valid_config` (31–36), `_parse_points` (41–51) e `generate_briefing` (64–97, exceto linhas sem evento executável). Isso **não é branch coverage certificada nem resistência a mutantes**. Demonstração acima mostra que linhas cobertas podem conservar lacunas de contrato. Não instalar coverage nem afirmar porcentagem inventada.

Evidência atribuída ao delegador, não rerodada por esta lente: suites 29+78+49 exit 0, compile de dois arquivos e diff exit 0; probes transientes de 32 grupos observaram snapshots/UUID reais, tipos/limites zero I/O e canaries. Esses probes não substituem testes mantidos. Nenhuma afirmação de hashes anteriores à codificação ou de 97 probes.

Cluster principal: asserts/status passam sem desafiar campos válidos em count válido, origem sensível, identidade por caminho e múltiplos retries ativos. Não inferir defeito estrutural de produto dessa convergência.

## Readset e limites

SHA-256 capturado antes de escrever relatório (após leituras/probes; NÃO baseline pré-leitura). Repetição após relatório deve comparar exatamente estes valores. Não existe prova retroativa de ausência de mudança antes da captura.

| Arquivo | SHA-256 |
|---|---|
| AGENTS.md | 9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844 |
| .reversa/state.json | 27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df |
| .reversa/active-requirements.json | 802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45 |
| .reversa/reversa-config.json | 33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe |
| requirements.md (feature) | 4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5 |
| roadmap.md (feature) | 913c13a64fdeca2d99893e77461f112798bd5b0a771a8f5241c586497689f621 |
| actions.md (feature) | 310292266264d14b3d183a968d388ce86d698ac702d39ea11234dccab94f9bd5 |
| tests/test_briefing_generation.py | 2f37ec9a02cbe38cc9deea3e4f06605ac7e7df370ab6a3463a8affccbdd658b6 |
| app/briefing/service.py | 42514b9ef514c79aca7f7b8f19c300e254465b16afb09c303e0647afbb7b6e76 |
| app/briefing/domain.py | f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a |
| app/briefing/serp_client.py | 49fa6c8912fe52aca33604ffb10279893c50ca392c665a78615a0496db4f06f4 |
| app/briefing/prompt_loader.py | f53c700a70cfa89f0f64d7d4b4821ba634d9a30c319924606dd915b050bef7c9 |

Verificação final própria: readset repetido após escrita, **12 hashes iguais, zero divergências**; `git diff --check` retornou exit 0, sem saída. Por ser arquivo novo não rastreado, git diff não inclui seu conteúdo; escrita verificada pelo tool. Nenhum arquivo de produto/config/testes escrito por esta lente.

Não coberto: binding LLM real, rede/Jina real, persistência, HTTP/auth, logs não capturados, cache fora do loader, cross-process, demais lentes e testes de outros arquivos. Leitura tentada de `app/briefing/validation.py` retornou inexistente; validação reside em domain.py, lido. Nenhuma limitação de execução dos 29. Relatório não fecha T011/T012/T013 nem promove observações a bugs.
