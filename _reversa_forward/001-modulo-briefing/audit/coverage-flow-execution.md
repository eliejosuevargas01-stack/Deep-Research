# T019 recorte A — execução de testes O02/O03

## Escopo

Somente QA test-only. Um arquivo novo com três métodos de teste, sem alteração de produção, configuração, estado, actions ou testes QA irmãos. Referências foram `app/briefing/service.py`, `domain.py`, `prompt_loader.py`, `serp_client.py`, `tests/test_briefing_generation.py` e observações O02/O03 em `_reversa_bugs/modulo-briefing/inspections/t006-t010-tests/report.md`.

## Alterações e cobertura

- `tests/test_briefing_generation_flow_qa.py:28-59` — O02: canaries distintos para system prompt, descrição SERP e resposta LLM malformada. LLM fake confirma os canaries de entrada no system/payload; retorno inválido inclui canary próprio. Serviço executado real: falha após quatro tentativas, uma busca, estado FAILED, erro fixo e pontos vazios; `repr`, erro e `dataclasses.asdict` não contêm os três canaries.
- `tests/test_briefing_generation_flow_qa.py:61-83` — erro `PromptUnavailable` com detalhe canary; comprova mensagem fixa e zero chamadas de busca/LLM, sem canary no resultado.
- `tests/test_briefing_generation_flow_qa.py:85-146` — O03: cinco fluxos em `subTest`: sucesso direto, sucesso após duas falhas LLM, exaustão LLM, falha de prompt e falha SERP. Spy envolve fábrica real `new_briefing`, guarda snapshot inicial; em cada fluxo afirma uma criação, estado inicial generating/v1/pontos vazios, snapshot inicial preservado, mesmo ID final e versão 2, estado/erro/conteúdo e contagens específicas. Não injeta UUID, relógio, banco ou rede; transições de domínio não são patchadas.
- Patch mínimo no teste de identidade: `[(p.title,p.description) for p in result.points]` deve corresponder aos valores de `json.loads(VALID)`, sem mocks adicionais/UUID fixo. `BranchFAILED()` existente preservar. Métodos 3 mesmos, nenhum refactor.

Limites: teste de falha SERP usa `SerpSearchError(4)` como erro de fronteira; não demonstra as quatro tentativas reais do adapter. Não captura logs, então não afirma segurança de logs. Exceções desconhecidas propagadas não foram tratadas como conteúdo sanitizado.

## Execução factual

- `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python -m unittest -v tests/test_briefing_generation_flow_qa.py` — exit 0; 3 testes aprovados; métodos: `test_canaries_from_prompt_serp_and_raw_never_leak`, `test_prompt_unavailable_detail_never_leaks_and_no_external_io`, `test_real_factory_identity_preserved_per_flow`.
- Mesmo prefixo, `python -m py_compile tests/test_briefing_generation_flow_qa.py` — exit 0.
- Oito módulos baseline, explicitamente: `python -m unittest tests/test_briefing_domain.py tests/test_briefing_schemas.py tests/test_briefing_prompt_loader.py tests/test_briefing_serp_client.py tests/test_briefing_validation.py tests/test_briefing_lifecycle.py tests/test_briefing_lifecycle_qa.py tests/test_briefing_generation.py` — exit 0; 79 testes aprovados.
- `git diff --check` — exit 0, sem saída.
- Arquivo novo: 147 linhas (teste) + 3 linhas de asserção de conteúdo exato = 150 linhas.

## Hashes de integridade

Hash capturado antes da escrita para arquivos de serviço e baseline e repetido após testes; todos iguais:

| Arquivo | SHA-256 |
|---|---|
| `app/briefing/service.py` | `1b64ff68eff0799c3e2d6137783df53a33805babcf3f5154d6a6b08b089cb060` |
| `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` |
| `app/briefing/prompt_loader.py` | `f53c700a70cfa89f0f64d7d4b4821ba634d9a30c319924606dd915b050bef7c9` |
| `app/briefing/serp_client.py` | `49fa6c8912fe52aca33604ffb10279893c50ca392c665a78615a0496db4f06f4` |
| `tests/test_briefing_generation.py` | `df730a92c5e432cd3ec79e0472e6ab8472652f56f0ba93c8d4ddc2d01b86b789` |
| `.reversa/state.json` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` |
| `.reversa/active-requirements.json` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` |
| `.reversa/reversa-config.json` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` |

Um `pytest --collect-only` explícito consultou apenas os oito arquivos baseline antes da execução; coletou 79 testes e não executou testes. Nenhuma descoberta glob de QA irmãos, rede, DB, instalação ou alteração de produto/config. Sem findings RED inventados. Process deviation anterior: `pytest --collect-only` sem teste executado, não repetido.