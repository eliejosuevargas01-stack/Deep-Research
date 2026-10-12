# Sprint 5 — T017: reauditoria de contratos e validação numérica (F-contratos-01)

## Veredicto

**PASS** — Achado anterior `F-contratos-01` devidamente sanado. Zero novos achados bloqueadores ou de regressão (critical 0, high 0, medium 0, low 0). Sem alterações em código de produto ou testes nesta inspeção. `promoted_to: null`.

## Preflight e mapa

- **Repositório**: `/root/projects/deep-research`, branch `main`.
- **Contexto**: `modulo-briefing`.
- **Configuração**: `.reversa/state.json` (pt-BR, `_reversa_sdd`), `.reversa/active-requirements.json` (feature `001-modulo-briefing`, stage `coding`), `.reversa/reversa-config.json` (`allowLegacyEdits: true`, inalterado).
- **Recorte**: Reauditoria estrita de T017 sobre a guarda de validação numérica em `app/briefing/service.py:30–42` e novo teste unitário em `tests/test_briefing_generation.py:401–416`.
- **Contratos e especificações**: `roadmap.md:23,98–104,155` e `data-delta.md:99`. O contrato estabelece que `llm_timeout_s` deve ser `int`/`float` não-`bool`, finito e estritamente positivo (> 0), lançando `ValueError("Configuração de timeout LLM inválida")` antes de qualquer operação de I/O externo. Não há imposição de teto fixo arbitrário para timeouts positivos finitos (ex.: `60`, `60.0`, `1e100` continuam válidos e aceitos).

## Reauditoria do achado F-contratos-01

### 1. Diagnóstico da correção em `service.py`

Trecho auditado em `app/briefing/service.py:30–42`:
```python
def _valid_config(llm_attempts: int, llm_timeout_s: float) -> None:
    if isinstance(llm_attempts, bool) or not isinstance(llm_attempts, int) or not 1 <= llm_attempts <= 4:
        raise ValueError("Configuração de tentativas LLM inválida")
    if isinstance(llm_timeout_s, bool) or not isinstance(llm_timeout_s, (int, float)):
        raise ValueError("Configuração de timeout LLM inválida")
    try:
        timeout_float = float(llm_timeout_s)
    except (OverflowError, ValueError):
        raise ValueError("Configuração de timeout LLM inválida")
    if not math.isfinite(timeout_float) or timeout_float <= 0:
        raise ValueError("Configuração de timeout LLM inválida")
```

- **Mecanismo da guarda**: Ao tentar `float(llm_timeout_s)` dentro do bloco `try...except (OverflowError, ValueError):`, qualquer valor inteiro fora do intervalo representável por ponto flutuante IEEE 754 (como `-10**1000` e `10**1000`) levanta `OverflowError` em nível de conversão e é imediatamente interceptado, levantando `ValueError("Configuração de timeout LLM inválida")`.
- **Precedência estrita sobre `math.isfinite`**: A chamada a `math.isfinite(timeout_float)` sequer é alcançada para inteiros não representáveis. Em teste instrumentado via probe (com spy/patch em `math.isfinite`), a contagem de chamadas a `math.isfinite` foi exatamente 0 para ambos os valores extremos (`-10**1000` e `10**1000`).
- **Garantia de zero I/O**: A função `_valid_config` é chamada na linha 68 de `app/briefing/service.py` como a primeira instrução síncrona de `generate_briefing`, antes de invocar `prompt_loader`, `serp_client.search` ou `llm_complete`. Em todos os casos inválidos, a lista de eventos de I/O permanece estritamente vazia (`events == []`).
- **Preservação de timeouts finitos positivos**: Valores válidos sem estouro numérico (`60`, `60.0`, `1e100`) são convertidos normalmente, satisfazem `math.isfinite(timeout_float) and timeout_float > 0`, e prosseguem para o fluxo de geração sem restrição de hardcap não contratada.

### 2. Avaliação do teste unitário em `tests/test_briefing_generation.py`

Trecho auditado em `tests/test_briefing_generation.py:401–415`:
```python
    async def test_extreme_numeric_timeout_values_raise_value_error_before_io(self):
        for bad_timeout in (-10**1000, 10**1000):
            seen = []
            async def search(theme): seen.append("search")
            async def llm(system, user): seen.append("llm")
            with self.assertRaisesRegex(ValueError, "Configuração de timeout LLM inválida"):
                await generate_briefing(
                    "valid theme",
                    serp_client=client_for(search),
                    llm_complete=llm,
                    prompt_loader=lambda: seen.append("prompt"),
                    llm_timeout_s=bad_timeout,
                )
            self.assertEqual(seen, [])
```

- **Estrutura de iteração**: O teste implementa um laço `for` explícito cobrindo a tupla `(-10**1000, 10**1000)`. Não utiliza `self.subTest`.
- **Rastreabilidade de histórico (RED vs. GREEN)**: No histórico da falha original (RED), a execução abortava no primeiro elemento (`-10**1000`) com `OverflowError`, sem chegar a avaliar o segundo elemento. No estado corrigido (GREEN), ambas as iterações são executadas integralmente e validadas com sucesso. RED é informação histórica do parent, não reexecutada nesta inspeção; não se afirma RED positivo nem RED dos outros 29 métodos. Nesta execução GREEN, os 30 métodos passaram.
- **Asserção de contrato**: Valida exatamente `ValueError` com casamento por regex da mensagem `"Configuração de timeout LLM inválida"`.
- **Verificação de ausência de I/O**: Os spies de `search`, `llm` e `prompt_loader` registram eventos em `seen`; o teste assevera `self.assertEqual(seen, [])` ao final de cada iteração.

## Execução própria e evidências completas

Todos os comandos foram executados em `/root/projects/deep-research` sob ambiente isolado (`python3 -B`, prefixo pycache em scratch `/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache`), sem rede externa, sem dependências de banco de dados ou variáveis de `.env`.

### 1. Teste focado T017
```sh
python3 -B -m unittest tests.test_briefing_generation.GenerationTests.test_extreme_numeric_timeout_values_raise_value_error_before_io -v
```
**Saída (exit 0)**:
```text
test_extreme_numeric_timeout_values_raise_value_error_before_io (tests.test_briefing_generation.GenerationTests.test_extreme_numeric_timeout_values_raise_value_error_before_io) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.004s

OK
```

### 2. Suíte do gerador de briefing (`test_briefing_generation.py`)
```sh
python3 -B -m unittest tests.test_briefing_generation
```
**Saída (exit 0)**:
```text
..............................
----------------------------------------------------------------------
Ran 30 tests in 0.156s

OK
```
*(30 testes executados, incluindo os 29 pré-existentes mais o novo teste de timeout numérico extremo).*

### 3. Descoberta de suíte completa de briefing
```sh
python3 -B -m unittest discover -s tests -p 'test_briefing_*.py'
```
**Saída (exit 0)**:
```text
...............................................................................
----------------------------------------------------------------------
Ran 79 tests in 0.242s

OK
```
*(79 testes totais na suíte do módulo de briefing).*

### 4. Baseline anterior (7 arquivos de teste complementares)
```sh
python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_schemas tests.test_briefing_prompt_loader tests.test_briefing_serp_client tests.test_briefing_validation tests.test_briefing_lifecycle tests.test_briefing_lifecycle_qa
```
**Saída (exit 0)**:
```text
.................................................
----------------------------------------------------------------------
Ran 49 tests in 0.095s

OK
```
*(49 testes de baseline executados e aprovados com 100% de sucesso).*

### 5. Compilação estrita em scratch
```sh
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python3 -B -m py_compile app/briefing/service.py tests/test_briefing_generation.py
```
**Saída (exit 0)**: Sem emissão de erros ou advertências.

### 6. Integridade de formatação Git
```sh
git diff --check
```
**Saída (exit 0)**: Limpo, sem espaços em branco espúrios ou conflitos.

### 7. Probe independente de fronteira numérica e zero I/O
```sh
python3 -B -c 'import asyncio, json
from unittest.mock import patch
from app.briefing import service
from app.briefing.service import generate_briefing

class S:
    async def search(self, theme): events.append("search"); return []

events = []
async def llm(system, user): events.append("llm"); return json.dumps([{"title": "T", "description": "D"}] * 3)
def loader(): events.append("prompt"); return "system"

async def main():
    for timeout in (-10**1000, 10**1000):
        events.clear()
        with patch.object(service.math, "isfinite", side_effect=AssertionError("isfinite reached")) as finite:
            try:
                await generate_briefing("valid theme", serp_client=S(), llm_complete=llm, prompt_loader=loader, llm_timeout_s=timeout)
            except ValueError as exc:
                assert str(exc) == "Configuração de timeout LLM inválida"
            else:
                raise AssertionError("ValueError missing")
            assert events == []
            finite.assert_not_called()
        print("negative" if timeout < 0 else "positive", "ValueError Configuração de timeout LLM inválida; io []; isfinite 0")
    for timeout in (60, 60.0, 1e100):
        events.clear()
        result = await generate_briefing("valid theme", serp_client=S(), llm_complete=llm, prompt_loader=loader, llm_timeout_s=timeout)
        assert result.status == "draft"
        assert events == ["prompt", "search", "llm"]
        print("accepted", timeout, "draft", events)

asyncio.run(main())'
```
**Saída (exit 0)**:
```text
negative ValueError Configuração de timeout LLM inválida; io []; isfinite 0
positive ValueError Configuração de timeout LLM inválida; io []; isfinite 0
accepted 60 draft ['prompt', 'search', 'llm']
accepted 60.0 draft ['prompt', 'search', 'llm']
accepted 1e+100 draft ['prompt', 'search', 'llm']
```

## Preservação do readset e rastreabilidade

- **Base de comparação**: Snapshot registrado pelo parent em `_reversa_forward/001-modulo-briefing/progress.jsonl` (38 registros totais), no registro 38 chave `inspection_readset_sha256`.
- **Integridade dos 32 arquivos congelados do readset**: Verificação automatizada comparou todos os 32 hashes SHA-256 antes e após a execução desta reauditoria. Divergências observadas: **zero**.
- **Arquivos adicionais monitorados**:
  - `_reversa_forward/001-modulo-briefing/progress.jsonl`: Inalterado.
  - `_reversa_bugs/modulo-briefing/inspections/t006-t010-service/report.md`: Inalterado e preservado intacto.
  - `AGENTS.md`, `.reversa/state.json`, `.reversa/active-requirements.json`, `.reversa/reversa-config.json`: Inalterados.
- **Escrita estrita**: O único arquivo gerado por este agente é `_reversa_bugs/modulo-briefing/inspections/t017-numeric-timeout/report.md`. Nenhum arquivo em `app/**`, `tests/**`, `_reversa_forward/**`, `.reversa/**` ou `_reversa_sdd/**` foi modificado.


### SHA-256 capturados antes/depois

32 arquivos do readset mais progress e relatório original: 34 caminhos únicos. Os quatro arquivos de preflight adicionais já pertencem ao readset. Todos hashes abaixo iguais antes/depois dos checks; comparação após escrita do report será repetida no fechamento.

| Arquivo | SHA-256 antes = depois |
|---|---|
| `.reversa/active-requirements.json` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` |
| `.reversa/reversa-config.json` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` |
| `.reversa/state.json` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` |
| `AGENTS.md` | `9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844` |
| `_reversa_bugs/modulo-briefing/inspections/t006-t010-service/report.md` | `510ba309612346afbee1dbec09943c3cacbfae36641b9242a7a480a41039f638` |
| `_reversa_forward/001-modulo-briefing/actions.md` | `6b26c533e649d81c4da87773005740ea4549d80759f6763edc1910592e362e93` |
| `_reversa_forward/001-modulo-briefing/audit/cross-check.md` | `a76d27ff51e61e1341dca48ae3839bc7f920de7dc9d59052ae3df8256431a28c` |
| `_reversa_forward/001-modulo-briefing/data-delta.md` | `4368adc2a811aab8fd1bb87de8b834d0801b509aa43ba2d3bb008333be666cb6` |
| `_reversa_forward/001-modulo-briefing/execution-policy.md` | `4a40e628d7e89f61859a7b6975a28d710ee062575143a6c4dbd25fb49a4ecb74` |
| `_reversa_forward/001-modulo-briefing/interfaces/briefing-http.md` | `a32e241a5510869a23b7632718931378a76680d50dd778ec1cbdbd9cec4e1184` |
| `_reversa_forward/001-modulo-briefing/interfaces/jina-serp.md` | `ea59e7cef89e7eed0447462abd41c6843dec9992ac6fbba3ed4ffa7b71bce4dd` |
| `_reversa_forward/001-modulo-briefing/legacy-impact.md` | `d36c84068fcacf7008907b37c78ced2680308befe473e943ff947eff8077bbc2` |
| `_reversa_forward/001-modulo-briefing/progress.jsonl` | `695a8fbd8003a1754cedb1f63814c603a84c44e9b84ffb99c705875255b1ed16` |
| `_reversa_forward/001-modulo-briefing/regression-watch.md` | `e7c1c66e432b80216faa6beb1daa6c29af8d879217212496e17834a7ab35eea8` |
| `_reversa_forward/001-modulo-briefing/requirements.md` | `4d749e76bf4d07d1d6f2ae33cc933116c43f2c745f07462a298b5012e8c4d8c5` |
| `_reversa_forward/001-modulo-briefing/roadmap.md` | `913c13a64fdeca2d99893e77461f112798bd5b0a771a8f5241c586497689f621` |
| `_reversa_sdd/prd.md` | `d78d05e0bfbd6c937eecf9d0899d4e5d131d780e99a5fbb2dd2ae507584651da` |
| `_reversa_sdd/sdd/briefing.md` | `27c1731e4fb6771957e5ef17b1bfe748f979a3c16331c87c1d2029f666f9c76b` |
| `app/briefing/__init__.py` | `ea5345be042575d62fc60f480f6bf44b7491dfe77bb083bb9861699a5e227b16` |
| `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` |
| `app/briefing/prompt_loader.py` | `f53c700a70cfa89f0f64d7d4b4821ba634d9a30c319924606dd915b050bef7c9` |
| `app/briefing/schemas.py` | `09dfac5db84451ff810cf8f903efe91f5ed9dffd47e765a85e8e505f93e8744a` |
| `app/briefing/serp_client.py` | `49fa6c8912fe52aca33604ffb10279893c50ca392c665a78615a0496db4f06f4` |
| `app/briefing/service.py` | `1b64ff68eff0799c3e2d6137783df53a33805babcf3f5154d6a6b08b089cb060` |
| `app/prompts/briefing.md` | `57f5ac3a9d2682f03f9515ee642e50b758ff1169523435781ced35061b21743d` |
| `requirements.txt` | `98fb88107d4ec2dbbfce80735f6cb626da65f6f9b740e42f0bfaca93eb1d1ada` |
| `tests/test_briefing_domain.py` | `a20c3361edcfc035229f12f3067eaa49e79a3df1fa90144848ffce00f841bef2` |
| `tests/test_briefing_generation.py` | `df730a92c5e432cd3ec79e0472e6ab8472652f56f0ba93c8d4ddc2d01b86b789` |
| `tests/test_briefing_lifecycle.py` | `a48fa6fb8d2649c8bfb68d327d60de24981be0ceaea92e3ebb775fa2bd4e38e2` |
| `tests/test_briefing_lifecycle_qa.py` | `a459957771779f723d6d47dd987cc02404613994e3a298fb98b2bcde893efce2` |
| `tests/test_briefing_prompt_loader.py` | `2c2dfaf8fb7ef5434884fba38108279af56f7ceb811d45c96d73bec2d437a9a4` |
| `tests/test_briefing_schemas.py` | `efb0b71f21b6a6634e20254ee17795fa129da916f3b415fe57144560f3aac94e` |
| `tests/test_briefing_serp_client.py` | `9fef3c625c22f2e2d81071d979d60c88b0735bcfae2e906316a5ae7ccc65b29b` |
| `tests/test_briefing_validation.py` | `8fed01d4fdc4f0bef91526f197b083ca3e02f4d24e77061fecc5ab3b2c86ebaa` |

## Observações de QA e limites

- **Observações O01–O06**: As observações de cobertura de QA levantadas em relatórios anteriores permanecem pendentes como itens de matriz complementar de testes (não configuram defeitos no código de produto).
- **Ações abertas**: Tarefas de integração e persistência de dados (`T011`, `T012`, `T013`) permanecem abertas no roadmap, fora do escopo desta reauditoria puramente unitária e estática.
- **Limites**: Não foram exercitados bindings reais de rede ou integração externa com provedores LLM/SERP, permanecendo no perímetro contratual e de testes com transporte isolado.
