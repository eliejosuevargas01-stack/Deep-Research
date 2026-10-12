# Parecer de Aceitação QA Especialista — T018: Gate Local de Fronteiras e Formato

## 1. Veredito e Status de Aceitação
- **Status do Gate Local T018:** **ACEITO / PASS LOCAL** (100% verde, deterministicamente provado).
- **Escopo Auditado:** Aceitação técnica de limites de fronteiras numéricas, tipos inválidos, campos isolados defeituosos e parsing de cercas de markdown no serviço de briefing (`tests/test_briefing_generation_boundaries_qa.py`).
- **Não-Vacuidade:** Comprovada ausência de testes vacuous. Todas as 85 invocações executam o pipeline real de `generate_briefing` com verificação estrita de efeitos colaterais de I/O, estados de resultado e mensagens contratuais.
- **Status de Gates Complementares/Integrados:**
  - **T004 (Gate Integrado de Tema):** Permanece **ABERTO** (aguarda validação integrada de pipeline completo / E2E).
  - **T005 / T011 (Gates de Persistência e Repositório):** Permanecem **ABERTOS** (aguardam camada de persistência durável, endpoints HTTP e repositório).

---

## 2. Rastreabilidade de Requisitos Cobertos pelo Gate T018

| Requisito | Regra / Limite Auditado | Comportamento e Asserção Comprovados | Status Local |
|---|---|---|---|
| **RN-01 / RF-01** | Fronteira de tamanho (3 a 300 caracteres) e tipos inválidos de tema | 11 casos inválidos (`ab`, 301 chars com/sem strip, vazio, whitespace, `None`, `0`, `True`, `[]`, `{}`) disparam `InvalidContent` com exatamente zero chamadas de I/O (prompt loader = 0, SERP = 0, LLM = 0). 2 casos válidos nos extremos (3 e 300 chars com whitespace externo) normalizam com strip e geram status `DRAFT` com 3 pontos e 1 chamada de cada dependência. | **PASS** |
| **RN-03 / RF-03** | Rascunho com 3 a 7 pontos de foco; payload íntegro | Validação de payloads válidos de 3 pontos geram `DRAFT` com contagem exata e formato correto. Falhas em pontos individuais forçam esgotamento para estado `FAILED` sem conteúdo parcial espúrio. | **PASS** |
| **RF-04** | Prompt injetável via prompt loader | Injeção de `fake_loader` executada estritamente zero vezes quando a entrada é inválida, e exatamente uma vez no fluxo válido. | **PASS** |
| **RF-08** | Erro seguro e sem vazamento de detalhes internos | Em todas as falhas de parsing/payload inválido, o briefing retorna status `FAILED` com mensagem de erro contratual fixa `"Geração de briefing indisponível"` e tupla de pontos vazia `()`. | **PASS** |
| **RF-10** | Retentativas sequenciais (até 4 tentativas totais LLM) | Falhas de payload inválido isolado ou formato de cerca esgotam o ciclo de tentativas: exatamente 1 chamada de SERP (reutilizada) e 4 chamadas sequenciais de LLM antes de assumir status `FAILED`. | **PASS** |
| **Configuração de Serviço** | Tipos inválidos e valores não-finitos para tentativas e timeout | 8 tentativas inválidas (`"0"`, `"5"`, `True`, `1.5`, `"4"`, `None`, `[]`, `{}`) disparam `ValueError` com mensagem exata `"Configuração de tentativas LLM inválida"` e zero I/O. 8 timeouts inválidos (`"0"`, `"-1"`, `True`, `nan`, `inf`, `-inf`, `None`, `"30"`) disparam `ValueError` com mensagem exata `"Configuração de timeout LLM inválida"` e zero I/O. | **PASS** |

---

## 3. Auditoria Detalhada dos 84 SubTests e 85 Invocações

A execução do arquivo `tests/test_briefing_generation_boundaries_qa.py` contém 4 métodos assíncronos que exercitam:

1. **`test_theme_boundaries_and_types_enforce_domain_or_draft_with_zero_or_exact_io`** (13 invocações / 13 subTests):
   - 11 subtests com temas inválidos (`subtest: invalid_theme`): asserção de `InvalidContent` + contadores zero para loader, search e LLM.
   - 2 subtests com temas válidos de fronteira (`subtest: valid_theme`): asserção de `BriefingStatus.DRAFT`, tema normalizado após strip, 3 pontos, contadores exatamente 1.
2. **`test_config_invalid_types_and_nonfinite_timeouts_raise_value_error_zero_io`** (18 invocações / 18 subTests):
   - 8 subtests de tentativas inválidas (`subtest: bad_attempts`): asserção de `ValueError`, mensagem exata `"Configuração de tentativas LLM inválida"`, contadores zero de I/O.
   - 8 subtests de timeout inválido (`subtest: bad_timeout`): asserção de `ValueError`, mensagem exata `"Configuração de timeout LLM inválida"`, contadores zero de I/O.
   - 2 subtests de configurações válidas (`subtest: valid_cfg`): (1 tentativa, 30.0s) e (4 tentativas, 60.0s), gerando `BriefingStatus.DRAFT`.
3. **`test_single_invalid_field_in_3point_payload_exhausts_retries_to_failed`** (48 invocações / 48 subTests):
   - Matriz combinatória de 2 campos (`title`, `description`) × 8 valores anômalos (`MISSING`, `""`, whitespace, `None`, `123`, `True`, `[]`, `{}`) × 3 índices de posição de item (0, 1, 2).
   - Cada caso altera isoladamente um único campo de um payload inicial com 3 pontos válidos.
   - Asserções por subtest: `status == BriefingStatus.FAILED`, `error == "Geração de briefing indisponível"`, `points == ()`, `len(search_calls) == 1`, `len(llm_calls) == 4`.
4. **`test_fences_and_raw_json_formatting_rules`** (6 invocações / 5 subTests):
   - 5 subtests de formatos inválidos (`subtest: bad_raw`): múltiplas cercas, cerca ```` ```javascript ````, cerca ```` ```python ````, lixo após a cerca, prefixo textual antes do JSON.
   - Asserções por subtest: `status == BriefingStatus.FAILED`, `error == "Geração de briefing indisponível"`, `len(search_calls) == 1`, `len(llm_calls) == 4`.
   - 1 invocação fora de subtest com formato fenced padrão válido (```` ```json\n...\n``` ````): asserção de `status == BriefingStatus.DRAFT` e `len(points) == 3`.

**Total Geral:**
- **SubTests Unittest:** 13 + 18 + 48 + 5 = **84 subtests** (todos verdes).
- **Invocações do Serviço:** 13 + 18 + 48 + 6 = **85 chamadas a `generate_briefing`**.

---

## 4. Evidências de Execução Isolada e Comandos de Verificação

Todas as verificações foram executadas no ambiente do projeto com workdir `/root/projects/deep-research`:

### 4.1. Suíte Focada de Fronteiras T018
```bash
python3 -B -m unittest tests.test_briefing_generation_boundaries_qa -v
```
**Resultado:**
```text
test_config_invalid_types_and_nonfinite_timeouts_raise_value_error_zero_io (tests.test_briefing_generation_boundaries_qa.TestBriefingGenerationBoundariesQA.test_config_invalid_types_and_nonfinite_timeouts_raise_value_error_zero_io) ... ok
test_fences_and_raw_json_formatting_rules (tests.test_briefing_generation_boundaries_qa.TestBriefingGenerationBoundariesQA.test_fences_and_raw_json_formatting_rules) ... ok
test_single_invalid_field_in_3point_payload_exhausts_retries_to_failed (tests.test_briefing_generation_boundaries_qa.TestBriefingGenerationBoundariesQA.test_single_invalid_field_in_3point_payload_exhausts_retries_to_failed) ... ok
test_theme_boundaries_and_types_enforce_domain_or_draft_with_zero_or_exact_io (tests.test_briefing_generation_boundaries_qa.TestBriefingGenerationBoundariesQA.test_theme_boundaries_and_types_enforce_domain_or_draft_with_zero_or_exact_io) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.030s

OK
```
- **Exit Code:** `0`

### 4.2. Baseline de Regressão de Módulos Briefing (49 Testes)
```bash
python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_prompt_loader tests.test_briefing_schemas tests.test_briefing_serp_client tests.test_briefing_validation tests.test_briefing_lifecycle tests.test_briefing_lifecycle_qa
```
**Resultado:**
```text
Ran 49 tests in 0.090s

OK
```
- **Exit Code:** `0`

### 4.3. Compilação Sintática Isolada
```bash
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/t018-qa-pycache python3 -B -m py_compile tests/test_briefing_generation_boundaries_qa.py app/briefing/service.py app/briefing/domain.py
```
- **Resultado:** Compilação limpa, sem erros de sintaxe ou warnings.
- **Exit Code:** `0`

### 4.4. Integridade de Git e Whitespace
```bash
git diff --check
```
- **Resultado:** Zero erros de trailing whitespace, marcadores de conflito ou indentação espúria.
- **Exit Code:** `0`

### 4.5. Instrumentação de Contagem Exata In-Memory
```python
# Instrumentação com TestResult personalizado e wrapper async sobre generate_briefing
# Resultado:
# Tests run: 4
# Errors: 0, Failures: 0
# SubTests recorded: 84
# Service invocations recorded: 85
# CONFIRMED: exactly 84 subtests, 85 invocations, all green, zero vacuous.
```
- **Exit Code:** `0`

---

## 5. Salvaguardas e Isolamento
- **Código de Produção:** Nenhuma linha de `app/briefing/*` ou qualquer módulo sob `app/` foi alterada.
- **Testes Pré-existentes:** Nenhuma modificação realizada em testes de produto ou suítes anteriores.
- **Artefatos Reversa:** Nenhum checkbox em `actions.md`, nenhuma entrada em `progress.jsonl` e nenhum estado em `.reversa/state.json` foi modificado por esta avaliação.
- **Arquivo Único Criado:** Este parecer `/root/projects/deep-research/_reversa_forward/001-modulo-briefing/audit/qa-sprint5-boundaries.md`.
