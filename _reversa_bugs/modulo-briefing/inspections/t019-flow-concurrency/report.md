# T019 — auditoria independente de fluxo, identidade, canaries, concorrência e exaustão Jina

## Veredicto

**PASS no recorte auditado.** Zero defeitos confirmados; zero bugs registrados. As observações O-02, O-03 e O-04 foram completamente sanadas com cobertura comportamental rigorosa, sem mocks indevidos da lógica de domínio nem fakes ociosos. Cancelamento assíncrono externo propaga sem corrupção de estado e a exaustão de retries do cliente real Jina compõe com o serviço de forma determinística e segura.

Auditor leaf independente; gravação exclusiva deste relatório em `_reversa_bugs/modulo-briefing/inspections/t019-flow-concurrency/report.md`. Branch `main`. Preflight validado: `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json`. Contexto de bugs `modulo-briefing`, feature `001-modulo-briefing` em estágio `coding`. Nenhum código de produção, teste, configuração, taxonomy, view, actions.md ou progress.jsonl foi alterado.

## Mapa da feature e fontes sob inspeção

- **Requisitos e especificações**: `_reversa_forward/001-modulo-briefing/requirements.md:51–60,161–162` (RF-01 a RF-10); `_reversa_sdd/prd.md:40–46,84`; `_reversa_sdd/sdd/briefing.md:54–63,76–78`.
- **Implementação sob teste**: `app/briefing/service.py:58–101` (`generate_briefing`, `_parse_points`), `app/briefing/domain.py:84–104,127–140` (`Briefing`, `new_briefing`, `complete_briefing`, `fail_briefing`), `app/briefing/serp_client.py:38–118` (`JinaSerpClient`), `app/briefing/prompt_loader.py:6–23` (`PromptUnavailable`, `load_briefing_prompt`).
- **Testes sob auditoria**:
  - `tests/test_briefing_generation_flow_qa.py` (3 métodos, 150 linhas) — Recorte A (O-02 e O-03).
  - `tests/test_briefing_generation_concurrency_qa.py` (3 métodos, 153 linhas) — Recorte B (O-04, cancelamento e composição Jina).
  - `tests/test_briefing_generation.py` (30 métodos, 418 linhas) — Suíte de geração original.
- **Relatórios de execução**: `_reversa_forward/001-modulo-briefing/audit/coverage-flow-execution.md` e `_reversa_forward/001-modulo-briefing/audit/coverage-concurrency-execution.md`.
- **Dados e fronteiras**: Objetos de domínio imutáveis em memória; cliente SERP Jina real acoplado a `httpx.MockTransport` local; LLM assíncrono fake injetado com asserções ativas de payload; zero I/O externo não controlado; sem banco de dados ou chamadas reais de rede.

## Lentes e evidências de inspeção

### Lente 1: Canaries e Sanitização de Conteúdo (O-02)

Auditado em `tests/test_briefing_generation_flow_qa.py:28–84`:
1. **Canaries distintos injetados**:
   - `prompt_canary`: `"FLOWQA-PROMPT-CANARY-7f3a"` injetado via `prompt_loader`.
   - `serp_canary`: `"FLOWQA-SERP-CANARY-9c1e"` injetado no snippet retornado pela SERP.
   - `raw_canary`: `"FLOWQA-RAW-CANARY-4b8d"` injetado no corpo da resposta crua do LLM.
2. **Fake assevera entradas ativamente**: A função `llm(system, user)` valida em runtime que `prompt_canary` está presente em `system` (`self.assertIn(prompt_canary, system)`) e que `serp_canary` está presente na descrição serializada dentro do payload `user` (`self.assertTrue(any(serp_canary in d for d in descs))`).
3. **Retorno malformado**: O LLM fake retorna string não-JSON contendo `raw_canary` (`f"not-json-at-all {{{raw_canary}}}"`).
4. **Sanitização comprovada**: Após 4 tentativas de LLM esgotadas e 1 busca SERP, o resultado é `BriefingStatus.FAILED`, `error="Geração de briefing indisponível"` e `points=()`. O teste serializa e concatena `repr(result) + str(result.error) + json.dumps(dataclasses.asdict(result), default=str)` e assevera que nenhum dos 3 canaries está presente.
5. **Detalhe interno de PromptUnavailable**: Em `test_prompt_unavailable_detail_never_leaks_and_no_external_io` (`:61–84`), `detail_canary = "FLOWQA-PROMPT-DETAIL-CANARY-2a6f"` é embutido na exceção `PromptUnavailable`. Comprova-se que a busca SERP e o LLM registram exatamente zero chamadas (`seen == []`), o estado final é FAILED com erro fixo `"Prompt de briefing indisponível"`, `points=()`, e `detail_canary` não vaza em `repr(result) + str(result.error)`.

### Lente 2: Identidade de Domínio e Cobertura de Fluxos (O-03)

Auditado em `tests/test_briefing_generation_flow_qa.py:85–147`:
1. **Spy na fábrica real**: `mock.patch.object(svc, "new_briefing", side_effect=factory)` envolve `svc.new_briefing` real (`real_new(theme)`), gerando UUID real e preservando as regras puras de validação. Nenhum UUID fake ou relógio fixo é injetado.
2. **Snapshot inicial preservado**: Em cada fluxo, `initial, snapshot = created[0]` comprova que o briefing nasceu com `status=BriefingStatus.GENERATING`, `version=1`, `points=()` e `error=None`, e que `dataclasses.asdict(initial) == snapshot`.
3. **Preservação de identidade e versão**: Em todos os cenários, `result.id == initial.id` (mesmo ID preservado entre as transições de domínio) e `result.version == 2` (avanço monotônico de versão).
4. **Cinco fluxos testados**:
   - `direct_success`: search=1, llm=1, status=DRAFT, error=None.
   - `retry_success`: search=1, llm=3 (2 falhas LLMAttemptError + 1 sucesso), status=DRAFT, error=None.
   - `exhaust_llm`: search=1, llm=4, status=FAILED, error="Geração de briefing indisponível".
   - `prompt_failure`: search=0, llm=0, status=FAILED, error="Prompt de briefing indisponível".
   - `serp_failure`: search=1, llm=0, status=FAILED, error="Busca SERP indisponível".
5. **Validação estrita de conteúdo em DRAFT**: Para os fluxos de sucesso, valida-se que `result.points` possui exatamente 3 pontos e que `[(p.title, p.description) for p in result.points]` é idêntico a `[(item["title"], item["description"]) for item in json.loads(VALID)]`. Nos fluxos com falha, `result.points == ()`.

### Lente 3: Concorrência Sequencial e Reuso de Payload (O-04)

Auditado em `tests/test_briefing_generation_concurrency_qa.py:21–65`:
1. **Sequencialidade estrita**: O teste introduz `await asyncio.sleep(0)` dentro da corrotina LLM fake com contadores instrumentados (`active` e `maximum_active`). Em ambos os cenários (3 falhas seguidas de sucesso, e 4 falhas seguidas de esgotamento), `maximum_active == 1` e `active == 0` ao final, provando ausência de sobreposição ou paralelismo espúrio nos retries.
2. **Busca única**: Exatamente 1 busca SERP executada (`searches == 1`).
3. **Reuso integral do payload**: `len({payload for _, payload in calls}) == 1` comprova que exatamente o mesmo JSON serializado de busca e tema foi enviado em todas as 4 chamadas, com `system == "prompt"` invariante.
4. **Conteúdo final**: Sucesso resulta em `BriefingStatus.DRAFT` com 3 pontos exatos instanciados como `BriefingPoint(title, description)` comparados contra `VALID_POINTS`. Esgotamento resulta em `BriefingStatus.FAILED`, erro fixo `"Geração de briefing indisponível"` e `points=()`.

### Lente 4: Cancelamento Assíncrono de Task Externa

Auditado em `tests/test_briefing_generation_concurrency_qa.py:66–118`:
1. **Propagação de CancelledError**: Executado via `task = asyncio.create_task(generate_briefing(...))`. O teste aguarda início via `asyncio.Event`, invoca `task.cancel()` e comprova que `await task` levanta `asyncio.CancelledError`.
2. **Cleanup garantido**: O bloco `finally` dentro do trabalhador executa antes do cancelamento resolver, confirmando `cleanup.is_set()` e `active == 0`.
3. **Preservação de transições de domínio**: `service.fail_briefing` é espionado (`observed_fail`). Comprova-se `fail_calls == 0`, atestando que cancelamentos externos não chamam transições de falha espúrias nem mascaram o cancelamento cooperativo do asyncio.

### Lente 5: Composição Real do Adapter Jina e Exaustão de Rede

Auditado em `tests/test_briefing_generation_concurrency_qa.py:119–153`:
1. **Adapter real**: Utiliza subclasse `CountingClient(JinaSerpClient)` acoplada ao cliente real `JinaSerpClient`, chamando `super().search(theme)` sem mockar a máquina de estados interna do adapter.
2. **Simulação de transporte**: `httpx.AsyncClient(transport=httpx.MockTransport(handler))` intercepta e responde com HTTP 500 (`text="private transport detail"`).
3. **Contagem factual de rede e chamadas**:
   - `search_calls == 1` (exatamente uma chamada ao método `search` do adapter).
   - `requests == 4` (exatamente 4 tentativas HTTP 500 disparadas internamente pelo adapter Jina).
   - `llm_calls == 0` (zero chamadas disparadas para o serviço LLM).
4. **Resultado e segurança**: O serviço captura a exceção de exaustão `SerpSearchError(4)` e produz `BriefingStatus.FAILED`, `error="Busca SERP indisponível"` (sem vazar `"private transport detail"`), e `points=()`.

## Execução factual e validação técnica

Todos os comandos foram executados em ambiente isolado via Python stdlib (`python3 -B`), retornando exit code **0**:

```bash
# 1. Suíte de QA de fluxo (Recorte A — O-02 e O-03)
python3 -B -m unittest tests.test_briefing_generation_flow_qa -v
# Ran 3 tests in 0.009s — OK

# 2. Suíte de QA de concorrência e integração Jina (Recorte B — O-04, cancelamento e Jina real)
python3 -B -m unittest tests.test_briefing_generation_concurrency_qa -v
# Ran 3 tests in 0.012s — OK

# 3. Suíte baseline de 7 módulos (domínio, prompt_loader, schemas, serp_client, validation, lifecycle, lifecycle_qa)
python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_prompt_loader tests.test_briefing_schemas tests.test_briefing_serp_client tests.test_briefing_validation tests.test_briefing_lifecycle tests.test_briefing_lifecycle_qa
# Ran 49 tests in 0.084s — OK

# 4. Suíte original de geração
python3 -B -m unittest tests.test_briefing_generation
# Ran 30 tests in 0.207s — OK

# 5. Compilação estrita de bytecode sem poluir cache
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python3 -B -m py_compile tests/test_briefing_generation_flow_qa.py tests/test_briefing_generation_concurrency_qa.py
# exit 0 (sem saída)

# 6. Verificação de integridade git
git diff --check
# exit 0 (sem saída)
```

**Resumo das execuções:**
- Testes focados T019 auditados: 6 testes (3 em `flow_qa` + 3 em `concurrency_qa`).
- Testes originais de geração: 30 testes em `test_briefing_generation.py`.
- Baseline de briefing: 49 testes nos 7 módulos fundamentais.
- Suíte combinada de geração e baseline auditada diretamente neste ciclo: 85 testes, todos GREEN.
- Compilação sintática e formatação git validadas com sucesso.

## Limites e escopo da auditoria

- **Sem persistência em banco ou migração**: O módulo sob inspeção opera puramente em memória e com injeção de dependência assíncrona; persistência em PostgreSQL e schemas Alembic pertencem a tarefas subsequentes (T011+).
- **Sem rede externa**: Chamadas de rede foram exercidas através de `httpx.MockTransport` e clientes de teste determinísticos; nenhuma credencial real ou chamada HTTP externa para `https://s.jina.ai/` foi realizada.
- **Isolamento de concorrência**: As asserções de sequencialidade e cancelamento atestam a mecânica assíncrona dentro do loop de eventos asyncio no processo Python; não constituem garantia de exclusão mútua distribuída entre múltiplos processos (que depende de locks de banco/broker em tarefas posteriores).
- **Catálogo de bugs inalterado**: Zero defeitos foram identificados; nenhum bug foi registrado e a taxonomia/views do catálogo não foram alteradas.

## Readset próprio — Integridade SHA-256

Verificação de integridade realizada antes e após a execução da auditoria. Todos os hashes permanecem estritamente idênticos:

| Arquivo | SHA-256 (antes = depois) |
|---|---|
| `tests/test_briefing_generation_flow_qa.py` | `dbc54a26725c07b0ee2f2c9576fefab8353d6cea302db2fa5ae6a93eac48f13b` |
| `tests/test_briefing_generation_concurrency_qa.py` | `2305d85a1965b70faa8d85ebb28c9e2a22321903c09efa02186efc2658869c4e` |
| `_reversa_forward/001-modulo-briefing/audit/coverage-flow-execution.md` | `96d335f9e11f938b7ca192981aeb1aff0134ca2b2780dc709a37b6db8169931c` |
| `_reversa_forward/001-modulo-briefing/audit/coverage-concurrency-execution.md` | `d809538d3d1919a844b30164117e86c05fbf2ded25514b3f68cc6b544e85fd0e` |
| `app/briefing/service.py` | `1b64ff68eff0799c3e2d6137783df53a33805babcf3f5154d6a6b08b089cb060` |
| `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` |
| `app/briefing/serp_client.py` | `49fa6c8912fe52aca33604ffb10279893c50ca392c665a78615a0496db4f06f4` |
| `app/briefing/prompt_loader.py` | `f53c700a70cfa89f0f64d7d4b4821ba634d9a30c319924606dd915b050bef7c9` |
| `app/briefing/schemas.py` | `09dfac5db84451ff810cf8f903efe91f5ed9dffd47e765a85e8e505f93e8744a` |
| `tests/test_briefing_generation.py` | `df730a92c5e432cd3ec79e0472e6ab8472652f56f0ba93c8d4ddc2d01b86b789` |
| `tests/test_briefing_generation_boundaries_qa.py` | `5937f8f9606fbf0d3e8c529b9e5e82f88d5391673ae77762441e4b7da646fee4` |
| `tests/test_briefing_domain.py` | `a20c3361edcfc035229f12f3067eaa49e79a3df1fa90144848ffce00f841bef2` |
| `tests/test_briefing_prompt_loader.py` | `2c2dfaf8fb7ef5434884fba38108279af56f7ceb811d45c96d73bec2d437a9a4` |
| `tests/test_briefing_schemas.py` | `efb0b71f21b6a6634e20254ee17795fa129da916f3b415fe57144560f3aac94e` |
| `tests/test_briefing_serp_client.py` | `9fef3c625c22f2e2d81071d979d60c88b0735bcfae2e906316a5ae7ccc65b29b` |
| `tests/test_briefing_validation.py` | `8fed01d4fdc4f0bef91526f197b083ca3e02f4d24e77061fecc5ab3b2c86ebaa` |
| `tests/test_briefing_lifecycle.py` | `a48fa6fb8d2649c8bfb68d327d60de24981be0ceaea92e3ebb775fa2bd4e38e2` |
| `tests/test_briefing_lifecycle_qa.py` | `a459957771779f723d6d47dd987cc02404613994e3a298fb98b2bcde893efce2` |
| `_reversa_forward/001-modulo-briefing/actions.md` | `02e42e6c3d58324fb392e12d1b4b66957c7d8dd2eca0eb2579f16e450663cb7e` |
| `_reversa_forward/001-modulo-briefing/progress.jsonl` | `0df9747c7c371be0ce52ddc2c85ae21e3d006418dd897847b790c5eb337f0824` |
| `_reversa_forward/001-modulo-briefing/requirements.md` | `4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5` |
| `_reversa_forward/001-modulo-briefing/roadmap.md` | `913c13a64fdeca2d99893e77461f112798bd5b0a771a8f5241c586497689f621` |
| `_reversa_sdd/prd.md` | `d78d05e0bfbd6c937eecf9d0899d4e5d131d780e99a5fbb2dd2ae507584651da` |
| `_reversa_sdd/sdd/briefing.md` | `27c1731e4fb6771957e5ef17b1bfe748f979a3c16331c87c1d2029f666f9c76b` |
| `.reversa/state.json` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` |
| `.reversa/active-requirements.json` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` |
| `.reversa/reversa-config.json` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` |
| `AGENTS.md` | `9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844` |
