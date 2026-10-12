# T018/O-06 — inspeção independente de fronteiras e proveniência

## Veredicto

**PASS no recorte auditado.** Zero novos defeitos confirmados; zero bugs registrados. O-01/O-05 têm cobertura comportamental real, não fixture vacuous. O-06 corrigiu classificação histórica sem fabricar vínculo de versões. Histórico RED integral permanece **UNPROVEN**, não convertido em aprovação de disciplina TDD.

Auditor leaf; somente este relatório gravado. Branch `main`; árvore já tinha alterações anteriores. Preflight: `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json`. Feature ativa `001-modulo-briefing`, estágio `coding`; `actions.md:62–64` mantém T017 concluída e T018/T019 abertas. Nenhum estado/checkbox alterado.

## Mapa e fontes

- Produto: `_reversa_forward/001-modulo-briefing/requirements.md:51–60,161–162` (RF-01/03/08/10; 30s configurável); `_reversa_sdd/prd.md:40–46,84`; `_reversa_sdd/sdd/briefing.md:54–63,76–78`.
- Concretização: `_reversa_forward/001-modulo-briefing/roadmap.md:146–158`, matriz a–m; `actions.md:63`.
- Implementação: `app/briefing/service.py:30–40,43–55,68–101`; `app/briefing/domain.py:31–53,107–139`.
- Testes: `tests/test_briefing_generation_boundaries_qa.py`, quatro métodos em 22/96/182/231, 285 linhas (277 + oito linhas de reparo); suíte original `tests/test_briefing_generation.py`, 30 métodos.
- Documentos auditados: `audit/coverage-boundaries-execution.md`, `audit/generation-red-provenance.md`, sob pasta da feature.
- Dados: registro imutável em memória; SERP/LLM injetados; HTTP MockTransport na suíte original. Sem DB/rede/binding LLM real neste gate.

## Lentes e evidências

### Conformidade, contratos e erros — O-01

`boundaries_qa.py:23–61`: 11 temas inválidos, incluindo 2/301 com/sem strip, vazio/whitespace, None/int/bool/list/dict. `InvalidContent` e loader/search/LLM exatamente zero; fakes têm retornos válidos e contadores, evitando falha incidental por fixture inválida.

`:63–94`: tema normalizado 3/300 aceito; DRAFT, tema exato, três pontos, loader/search/LLM exatamente uma chamada.

`:97–162`: oito configurações inválidas de tentativas e oito timeouts; strings/None/bool e NaN/±inf cobertos. `ValueError` com mensagem **exata**, `Configuração de tentativas LLM inválida` / `Configuração de timeout LLM inválida`; zero I/O. `:164–180`: configuração válida 1/30 e 4/60 aceita; não impõe teto de 30s indevido. Extremos inteiros T017 continuam cobertos na suíte original `:401–414`.

### Fluxo de dados e cobertura — O-05

`boundaries_qa.py:183–229`: 2 campos × 8 valores × 3 posições = 48 cenários. Cada payload começa com **três pontos válidos**, altera somente title ou description selecionado; missing/empty/whitespace/None/int/bool/list/dict. Logo falha não depende de contagem inválida. FAILED, mensagem segura fixa, points `()`, busca uma vez, LLM quatro vezes, comprovados por asserções executadas.

`:232–261`: cinco formatos inválidos — múltiplas cercas, javascript, python, lixo após cerca, prefixo textual. FAILED/mensagem fixa/search1/LLM4. `:263–281`: cerca JSON exata válida gera DRAFT/três pontos. Este positivo não asserciona contadores; não é alegado como prova de contagem exata. Negativos de cercas não assercionam points vazio; isolamento de campo e implementação `domain.py:134–139` sustentam ausência de conteúdo parcial no recorte.

Runner instrumentado em memória, sem editar testes: **84 subtests = 13 + 18 + 48 + 5**, **85 invocações reais de generate_briefing**, uma cerca válida fora de subTest. Quatro métodos GREEN.

### Rastreabilidade — O-06

Matriz `generation-red-provenance.md:43–72`: AST confirmou 30 nomes únicos, conjunto exato igual à suíte original. Quatro linhas classificadas ERROR nominal, 26 sem ERROR individual comprovado. Não significa quatro RED comportamentais integrais ou 26 testes necessariamente nunca RED.

Logs lidos em recortes limitados, sem reexecutar histórico:
- `/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_c0b7c80c/task-0.log:44,52`: unittest `_FailedTest`, ImportError anterior ao serviço; happy path não executado como RED comportamental.
- Mesmo log `:88,106,128`: ERROR nominal visível dos testes config/prompt/known LLM failure. Resumos truncados não provam traceback integral, causa completa ou versão/hash. Relatório corrigido não inventa essas causas.
- Mesmo log `:154,162`: callable InvalidContent/RuntimeError e callable TimeoutError aparecem `... ok`. Erro global do comando não transforma esses métodos em ERROR.
- `/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_1112e09b/task-0.log:23–30,33–36`: probes ±10**1000 mostram OverflowError; teste extremo tem ERROR nominal, depois GREEN. Primeiro RED aborta no valor negativo; **não inferir RED positivo individual**. Teste atual percorre ambos valores; GREEN atual confirmado.

Hashes publicados: dez linhas em coverage e cinco em provenance, todas com 64 hex e iguais ao disco atual. Hash atual não prova conteúdo de versão histórica; vínculo histórico permanece **UNPROVEN** (`generation-red-provenance.md:18`). Referências de método em coverage `:21–24` conferem AST. Referências nominais dos quatro ERROR e dois callable ok conferem recortes; linha 154 contém ambos callable ok.

## Checks próprios e comandos

Todos abaixo executados neste auditor, exit **0**:

```bash
python3 -B -m unittest tests.test_briefing_generation_boundaries_qa tests.test_briefing_generation -v
python3 -B -m unittest tests.test_briefing_generation_boundaries_qa tests.test_briefing_generation
python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_prompt_loader tests.test_briefing_schemas tests.test_briefing_serp_client tests.test_briefing_validation tests.test_briefing_lifecycle tests.test_briefing_lifecycle_qa
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/t018-boundaries-audit-pycache python3 -m py_compile tests/test_briefing_generation_boundaries_qa.py tests/test_briefing_generation.py app/briefing/service.py app/briefing/domain.py
git diff --check
```

Resultados: suíte focada **34/34** (4 fronteiras + 30 geração); baseline explícito sete módulos **49/49**. Repetição focada 34 em 0.175s, baseline 49 em 0.106s; OK. Compile e diff sem saída/erro.

Probe `python3 -B -c` com wrapper async no símbolo importado pelo teste e `TextTestResult.addSubTest`: quatro métodos em 0.030s, OK; Counter service=85, config=18, fences=5, fields=48, themes=13; asserts de contagem exit 0. AST/proveniência/hash check via Python stdlib: exit 0; conjuntos exatos 30/30, ERROR nominal 4, complemento 26, referências 22/96/182/231, hashes 10+5 iguais ao disco. Primeira consulta AST considerou apenas FunctionDef e retornou zero; corrigida para AsyncFunctionDef antes das conclusões, sem alterar artefatos.

## Limites e observações não promovidas

- Sem leitura/execução de testes flow/concurrency QA irmãos ou respectivos relatórios; sem discovery glob nesta auditoria. Concorrência dedicada pertence ao worker irmão; suíte original foi executada explicitamente conforme escopo.
- `coverage-boundaries-execution.md:43–48` registra discovery do worker contrariando isolamento original e reprodução posterior pelo parent. Observação de processo já reconhecida; não bug de produto e não check reproduzido neste leaf.
- Não auditados: runtime Jina/LLM, persistência/HTTP/auth, frontend, semântica de conclusividade, deploy. Fakes não fecham T011/T012/T013.
- Sem pytest, DB, rede, .env, instalação, commit/push/deploy, delegação, escrita de skills, novos bugs/views ou correção de produção/testes/docs/estado.
- Cluster novo: nenhum. Achados confirmados por lente/confiança: conformidade 0; fluxo 0; contratos 0; erros 0; cobertura 0; concorrência fora do recorte dedicado; promoted_to: null. Limitação histórica UNPROVEN e observação de processo acima permanecem explícitas.

## Readset próprio — SHA-256 antes/depois

26 arquivos estáveis; comparação pós-check: **zero alterações**. Cada digest abaixo igual antes/depois. Arquivos irmãos mutáveis não entram no readset nem são tratados como violação. Fonte/spec/baseline adicional teve hash capturado antes de sua leitura/execução; actions/progress incluídos desde início.

| Arquivo | SHA-256 antes = depois |
|---|---|
| `tests/test_briefing_generation_boundaries_qa.py` | `5937f8f9606fbf0d3e8c529b9e5e82f88d5391673ae77762441e4b7da646fee4` |
| `tests/test_briefing_generation.py` | `df730a92c5e432cd3ec79e0472e6ab8472652f56f0ba93c8d4ddc2d01b86b789` |
| `app/briefing/service.py` | `1b64ff68eff0799c3e2d6137783df53a33805babcf3f5154d6a6b08b089cb060` |
| `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` |
| `app/briefing/schemas.py` | `09dfac5db84451ff810cf8f903efe91f5ed9dffd47e765a85e8e505f93e8744a` |
| `_reversa_forward/001-modulo-briefing/actions.md` | `02e42e6c3d58324fb392e12d1b4b66957c7d8dd2eca0eb2579f16e450663cb7e` |
| `_reversa_forward/001-modulo-briefing/progress.jsonl` | `338cf28faf422cca7dd24abbc1bca12bed637382ca3e05cf2a82290e76dd20b5` |
| `_reversa_forward/001-modulo-briefing/requirements.md` | `4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5` |
| `_reversa_forward/001-modulo-briefing/roadmap.md` | `913c13a64fdeca2d99893e77461f112798bd5b0a771a8f5241c586497689f621` |
| `_reversa_sdd/prd.md` | `d78d05e0bfbd6c937eecf9d0899d4e5d131d780e99a5fbb2dd2ae507584651da` |
| `_reversa_forward/001-modulo-briefing/audit/coverage-boundaries-execution.md` | `9029cd09f2352996a9099072a6fe784e3f3fe8238ce2545d3e8d55b654101714` |
| `_reversa_forward/001-modulo-briefing/audit/generation-red-provenance.md` | `304313ff16312f9a6ffbae6a20e821ed8114c0f0232e170c381698ef3e96808a` |
| `.reversa/state.json` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` |
| `.reversa/active-requirements.json` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` |
| `.reversa/reversa-config.json` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` |
| `AGENTS.md` | `9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844` |
| `app/briefing/prompt_loader.py` | `f53c700a70cfa89f0f64d7d4b4821ba634d9a30c319924606dd915b050bef7c9` |
| `app/briefing/serp_client.py` | `49fa6c8912fe52aca33604ffb10279893c50ca392c665a78615a0496db4f06f4` |
| `tests/test_briefing_domain.py` | `a20c3361edcfc035229f12f3067eaa49e79a3df1fa90144848ffce00f841bef2` |
| `tests/test_briefing_prompt_loader.py` | `2c2dfaf8fb7ef5434884fba38108279af56f7ceb811d45c96d73bec2d437a9a4` |
| `tests/test_briefing_schemas.py` | `efb0b71f21b6a6634e20254ee17795fa129da916f3b415fe57144560f3aac94e` |
| `tests/test_briefing_serp_client.py` | `9fef3c625c22f2e2d81071d979d60c88b0735bcfae2e906316a5ae7ccc65b29b` |
| `tests/test_briefing_validation.py` | `8fed01d4fdc4f0bef91526f197b083ca3e02f4d24e77061fecc5ab3b2c86ebaa` |
| `tests/test_briefing_lifecycle.py` | `a48fa6fb8d2649c8bfb68d327d60de24981be0ceaea92e3ebb775fa2bd4e38e2` |
| `tests/test_briefing_lifecycle_qa.py` | `a459957771779f723d6d47dd987cc02404613994e3a298fb98b2bcde893efce2` |
| `_reversa_sdd/sdd/briefing.md` | `27c1731e4fb6771957e5ef17b1bfe748f979a3c16331c87c1d2029f666f9c76b` |
