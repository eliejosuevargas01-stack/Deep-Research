# Relatório de QA independente — Sprint 1 (Domínio, Schemas e Prompt Loader)

## 1. Escopo e delimitação do recorte

- **Feature:** `001-modulo-briefing` (`.reversa/active-requirements.json`).
- **Recorte inspecionado:** Ações T001, T002, T008, T014 e T015 (domínio puro, schemas Pydantic e loader/arquivo de prompt).
- **Código de produção congelado:**
  - `app/briefing/__init__.py`
  - `app/briefing/domain.py`
  - `app/briefing/schemas.py`
  - `app/briefing/prompt_loader.py`
  - `app/prompts/briefing.md`
- **Testes duráveis avaliados:**
  - `tests/test_briefing_domain.py` (10 testes criados neste QA)
  - `tests/test_briefing_schemas.py` (6 testes entregues)
  - `tests/test_briefing_prompt_loader.py` (4 testes entregues)
- **Delimitação estrita:** QA exclusivamente lógico e comportamental nos módulos existentes. Não foram exercidos nem afirmados: banco de dados, migrações, endpoints HTTP servidos, autenticação, camada de serviço/orquestrador, chamadas de rede à Jina Search ou provedor LLM, obediência real de modelo generativo, nem execução da pesquisa posterior.

## 2. Mapa de critérios, símbolos e resultados de execução

| Critério funcional / de spec | Símbolo de produção | Teste / probe executado | Exit code | Saída real resumida | Veredito local |
|---|---|---|:---:|---|:---:|
| Validação de tema: limites 3..300, normalização strip, rejeição de 2, 301, vazio, whitespace e tipos inválidos | `validate_theme` (`app/briefing/domain.py:27-33`) | `tests/test_briefing_domain.py`: `test_theme_normalized_boundaries`, `test_theme_empty_whitespace_and_types` | 0 | `ok` (testes unitários isolados) | **PASS** |
| Validação de pontos: limites 3..7, tipos inválidos, contagens 0/2/8 rejeitadas, 3..7 aceitas preservando ordem | `validate_points` (`app/briefing/domain.py:36-49`) | `tests/test_briefing_domain.py`: `test_point_count_boundaries_and_order_preserved`, `test_points_require_list` | 0 | `ok` (verificação de contagens e tipos) | **PASS** |
| Validação de campos de ponto: título e descrição não vazios, não whitespace, tipos inválidos e suporte a atributos | `validate_points` (`app/briefing/domain.py:40-48`) | `tests/test_briefing_domain.py`: `test_point_fields_empty_whitespace_types_and_missing`, `test_attribute_points_supported` | 0 | `ok` (dicts e SimpleNamespace validados) | **PASS** |
| Máquina de estados: 16 combinações dos 4 estados (`generating`, `draft`, `failed`, `approved`), tipos enum e str | `transition`, `BriefingStatus` (`app/briefing/domain.py:12-16,57-70`) | `tests/test_briefing_domain.py`: `test_all_sixteen_transitions_enum_and_string`, `test_unknown_transition_states_rejected` | 0 | `ok` (apenas 4 transições válidas permitidas) | **PASS** |
| Guarda de edição: permitida estritamente em `draft`, rejeitada nos demais estados e valores inválidos | `assert_can_edit` (`app/briefing/domain.py:52-54`) | `tests/test_briefing_domain.py`: `test_only_draft_editable` | 0 | `ok` (rejeição de generating, approved, failed e inválidos) | **PASS** |
| Reabertura e repetição de edição: ciclo aprovado -> rascunho -> aprovado sem bloqueio por pesquisa ou limite de iterações | `transition`, `assert_can_edit` (`app/briefing/domain.py:52-70`) | `tests/test_briefing_domain.py`: `test_reopen_and_repeat_edit_without_research_guard_or_limit` | 0 | `ok` (20 ciclos e edições repetidas) | **PASS** |
| Rejeição de status desconhecido em schemas | `BriefingResponse` (`app/briefing/schemas.py:77`) | `tests/test_briefing_schemas.py`: `test_unknown_status_is_rejected` | 0 | `ok` (`banana` gera ValidationError) | **PASS** |
| Exigência de 3..7 pontos para estados `draft` e `approved` em respostas | `BriefingResponse` (`app/briefing/schemas.py:80-84`) | `tests/test_briefing_schemas.py`: `test_draft_and_approved_require_three_to_seven_points` | 0 | `ok` (rejeição 0/2/8; aceitação 3..7) | **PASS** |
| Exigência de 3..7 pontos na resposta de briefing aprovado | `ApprovedBriefingResponse` (`app/briefing/schemas.py:87-95`) | `tests/test_briefing_schemas.py`: `test_approved_response_requires_three_to_seven_points` | 0 | `ok` (min 3, max 7 cumpridos) | **PASS** |
| Estados `generating` e `failed` aceitam lista vazia de pontos | `BriefingResponse` (`app/briefing/schemas.py:78,80-84`) | `tests/test_briefing_schemas.py`: `test_generating_and_failed_allow_empty_points` | 0 | `ok` (pontos vazios permitidos) | **PASS** |
| Serialização dos 4 estados e listagem no enum do JSON Schema | `BriefingResponse` (`app/briefing/schemas.py:77`) | `tests/test_briefing_schemas.py`: `test_states_serialize_and_json_schema_lists_enum` | 0 | `ok` (`generating`, `draft`, `failed`, `approved`) | **PASS** |
| Validação de pontos e proibição de campos extras nos schemas de resposta | `BriefingPoint`, `BriefingResponse` (`app/briefing/schemas.py:24-35,72-73`) | `tests/test_briefing_schemas.py`: `test_empty_titles_descriptions_and_extra_fields_are_rejected` | 0 | `ok` (ValidationError em campos vazios ou extras) | **PASS** |
| Contrato de schemas de request: criação, edição (3..7 pontos), aprovação e reabertura vazios, proibição de campos extras | `BriefingCreateRequest`, `BriefingEditPointsRequest`, `BriefingApproveRequest`, `BriefingReopenRequest` (`app/briefing/schemas.py:24-70`) | Probe inline python: 41 verificações de contratos Pydantic | 0 | `SCHEMAS: 41 checks PASS` | **PASS** |
| Leitura sem cache do prompt e detecção de atualizações no arquivo | `load_briefing_prompt` (`app/briefing/prompt_loader.py:10-23`) | `tests/test_briefing_prompt_loader.py`: `test_each_call_reads_updated_file` | 0 | `ok` (versão 1 -> versão 2 refletida) | **PASS** |
| Tratamento seguro de arquivo ausente e vazio/whitespace | `load_briefing_prompt`, `PromptUnavailable` (`app/briefing/prompt_loader.py:17-22`) | `tests/test_briefing_prompt_loader.py`: `test_missing_prompt_raises_safe_configuration_error`, `test_empty_prompt_raises_safe_configuration_error` | 0 | `ok` (mensagem genérica segura sem paths) | **PASS** |
| Prompt padrão não vazio e instruções de sistema conformes à spec (3..7 pontos, alvo 5, títulos/descrições, SERP-only, sem conclusão ou páginas) | `load_briefing_prompt` (`app/briefing/prompt_loader.py`), `app/prompts/briefing.md` | `tests/test_briefing_prompt_loader.py`: `test_default_prompt_is_nonempty`; Probe inline python (15 verificações de loader e conteúdo) | 0 | `LOADER/PROMPT: 15 checks PASS; public str safe; cause internal; cwd restored; scratch removed` | **PASS** |
| Independência de cwd no carregamento do caminho default e tratamento de erro de leitura não permissiva | `load_briefing_prompt` (`app/briefing/prompt_loader.py:12-20`) | Probe inline python (mock de `PermissionError`, leitura em cwd alternativo temporário, UTF-8 inválido) | 0 | `PromptUnavailable` com `__cause__` interno, string pública segura | **PASS** |

## 3. Registro de execução de comandos

Todos os comandos foram executados com workdir `/root/projects/deep-research`:

1. **Testes do domínio isolados:**
   - Comando: `python3 -B -m unittest discover -s tests -p test_briefing_domain.py -v`
   - Exit code: `0`
   - Saída: `Ran 10 tests in 0.001s; OK`
2. **Suíte completa de testes de briefing:**
   - Comando: `python3 -B -m unittest discover -s tests -p 'test_briefing_*.py' -v`
   - Exit code: `0`
   - Saída: `Ran 20 tests in 0.007s; OK`
3. **Probe complementar de contratos de schemas:**
   - Comando: `python3 -B -c "<inline-probe-schemas>"`
   - Exit code: `0`
   - Saída: `SCHEMAS: 41 checks PASS`
4. **Probe complementar de loader e integridade de prompt:**
   - Comando: `python3 -B -c "<inline-probe-loader>"`
   - Exit code: `0`
   - Saída: `LOADER/PROMPT: 15 checks PASS; public str safe; cause internal; cwd restored; scratch removed`
5. **Compilação estrita com pycache em diretório temporário:**
   - Comando: `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/qa-briefing-pycache python3 -B -m py_compile app/briefing/__init__.py app/briefing/domain.py app/briefing/schemas.py app/briefing/prompt_loader.py tests/test_briefing_domain.py tests/test_briefing_schemas.py tests/test_briefing_prompt_loader.py`
   - Exit code: `0`
   - Saída: sem erros
6. **Verificação de formatação e whitespace do Git:**
   - Comando: `git diff --check`
   - Exit code: `0`
   - Saída: sem alertas ou erros

## 4. Findings e Observações

- **Bugs funcionais confirmados (Crítico / Alto / Médio):** **0** (nenhum desvio detectado no código congelado em relação às specs aprovadas).
- **Observações mantidas (Low / Informativas):**
  - **O-01 (Fronteira interna de exceção do loader):** `app/briefing/prompt_loader.py:20` mantém `from exc`. O detalhe do erro (`PermissionError` / `FileNotFoundError` com caminho no disco) fica armazenado no atributo `__cause__`. O método `str(PromptUnavailable)` é seguro e não vaza o caminho. Consumidores futuros (como handlers HTTP ou loggers a serem implementados em T010/T011) devem extrair apenas a mensagem segura para respostas públicas.
  - **O-02 (Semântica de recuperação de estado terminal `failed`):** O estado `failed` não possui transições de saída definidas na máquina de estados pura (`BriefingStatus.FAILED: set()`), conforme deliberado na SDD (`briefing.md:100`). Recuperação manual/regeneração permanece pergunta aberta, não finding nem regra adicional. Não inferir histórico imutável, endpoint ou obrigação de transição futura. A matriz testada descreve somente comportamento puro atual.

## 5. Itens explicitamente NÃO TESTADOS

Por estarem fora deste recorte unitário e pendentes de implementação em tarefas posteriores (T004, T005, T006, T007, T009, T010, T011, T012):
1. **Camada de persistência e banco de dados:** tabelas, migrações Alembic, consultas SQL, transações, concorrência e isolamento.
2. **Camada de transporte e API HTTP:** rotas FastAPI, códigos de resposta HTTP reais (422, 409, 404, 503), headers e injeção de dependências.
3. **Serviços de negócio e orquestração:** retentativas sequenciais (até 4 tentativas), políticas de timeout e limites de concorrência.
4. **Chamadas externas de rede:** requisições à Jina Search API (`s.jina.ai`) e requisições ao provedor LLM.
5. **Comportamento generativo de IA:** obediência efetiva de modelos de linguagem às diretrizes do prompt ou garantia de não conclusividade nas respostas reais.
6. **Autenticação e controle de acesso:** tokens de sessão, permissões de operador e isolamento de tenant.

## 6. Parecer final e Gate de QA

- **Resultado do Gate:** **PASS** (aprovado para o escopo delimitado de Domínio, Schemas e Prompt Loader).
- **Contagem total de testes automatizados da suíte briefing:** **20 testes unitários duráveis** (10 domínio + 6 schemas + 4 loader), todos com status `OK`.
- **Integridade do repositório:** nenhum código de produção foi alterado; nenhuma tarefa ou status foi marcado indevidamente no roadmap.

## 7. Reprodução integral dos probes

Os rótulos `<inline-probe-...>` acima não são comandos executáveis. Scripts efetivamente executados seguem; rodar cada bloco com `python3 -B -` no workdir indicado. Nenhum validador foi reimplementado: probes chamam imports reais.

### Schemas (41 checks, exit 0)
```python
from uuid import UUID
from pydantic import ValidationError
from app.briefing import schemas as s
checks=0
def reject(fn):
 global checks
 try: fn()
 except ValidationError: checks+=1; return
 raise AssertionError("expected ValidationError")
p={"title":" t ","description":" d "}
for n in (0,2,3,4,5,6,7,8):
 if 3<=n<=7:
  assert len(s.BriefingEditPointsRequest(points=[p]*n).points)==n; checks+=1
 else: reject(lambda:s.BriefingEditPointsRequest(points=[p]*n))
for n in (2,3,300,301):
 value=" "+"á"*n+" "
 if n in (3,300): assert s.BriefingCreateRequest(theme=value).theme=="á"*n; checks+=1
 else: reject(lambda:s.BriefingCreateRequest(theme=value))
for value in ("", " \t\n", None,0,True,[],{}): reject(lambda:s.BriefingCreateRequest(theme=value))
for field in ("title","description"):
 for value in ("", " \t\n", None,0,True,[],{}): reject(lambda:s.BriefingEditPointsRequest(points=[{**p,field:value}]*3))
makers=[lambda:s.BriefingCreateRequest(theme="tema",extra=1),lambda:s.BriefingEditPointsRequest(points=[p]*3,extra=1),lambda:s.BriefingPoint(**p,extra=1),lambda:s.BriefingApproveRequest(extra=1),lambda:s.BriefingReopenRequest(extra=1),lambda:s.BriefingResponse(id=UUID(int=1),theme="tema",status="draft",points=[p]*3,extra=1),lambda:s.ApprovedBriefingResponse(id=UUID(int=1),theme="tema",points=[p]*3,extra=1)]
for make in makers: reject(make)
assert s.BriefingEditPointsRequest(points=[p]*3).points[0].title==" t "; checks+=1
print(f"SCHEMAS: {checks} checks PASS")
```

### Loader/prompt (15 checks, exit 0)
```python
import os,tempfile
from pathlib import Path
from unittest.mock import patch
from app.briefing.prompt_loader import load_briefing_prompt,PromptUnavailable
checks=0
with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as tmp:
 p=Path(tmp)/"briefing.md"
 def fail(cause=None):
  global checks
  try: load_briefing_prompt(p)
  except PromptUnavailable as exc:
   assert str(exc)=="Prompt de briefing indisponível ou inválido"
   assert tmp not in str(exc)
   if cause: assert isinstance(exc.__cause__,cause)
   checks+=1; return
  raise AssertionError("expected PromptUnavailable")
 fail(FileNotFoundError)
 for content in (b"",b" \n\t",b"\xff"):
  p.write_bytes(content); fail(UnicodeDecodeError if content==b"\xff" else None)
 with patch.object(Path,"read_text",side_effect=PermissionError(13,"Permission denied",str(p))): fail(PermissionError)
 p.write_text("first",encoding="utf-8"); assert load_briefing_prompt(str(p))=="first"; checks+=1
 p.write_text("second",encoding="utf-8"); assert load_briefing_prompt(p)=="second"; checks+=1
 expected=load_briefing_prompt(); cwd=os.getcwd()
 try:
  os.chdir(tmp); assert load_briefing_prompt()==expected; checks+=1
 finally: os.chdir(cwd)
 for text in ("3 a 7", "5 pontos como alvo habitual", "cada ponto com título e descrição", "somente os resultados SERP", "não responda ao tema nem apresente conclusão", "Não peça leitura de páginas", "não use outras fontes"):
  assert text in expected; checks+=1
print(f"LOADER/PROMPT: {checks} checks PASS; public str safe; cause internal; cwd restored; scratch removed")
```

Pré-checagem: skill `reversa-depth-inspection` aplicada com restrição substituindo bootstrap/bugs/views. `.reversa/state.json`, active-requirements e AGENTS lidos como contexto; produto vem de requirements RN-01–07/RF-01–10, PRD:99–107 e SDD briefing:54–63,95–100,169–170. Auditorias anteriores lidas: reauditoria-t014-t015 (3 resolvidos, 0 novos, horário original desconhecido) e inspecao-t008 (0 bugs, observações low de cobertura e exception chain). Esta execução não autentica logs históricos.

Git: branch `main`, HEAD `c741ce77dedfb88d11a8f0916482c721251f112d`, comandos exit 0. Árvore já suja antes de QA; mudanças externas não atribuídas a este worker. `git diff --check` não cobre novos arquivos não rastreados; unittest e py_compile exercitaram Python real. Apenas dois arquivos novos autorizados escritos. T015 é decisão documental de entidade isolada, não persistência entregue; imports locais não usam Research/ResearchPoint/ResearchStatus, mas não substituem gate DB futuro.

Lentes: conformidade, fluxo de dados, contratos, erros e cobertura PASS somente local; concorrência/consistência limitada à ausência de cache e identidade/ordem da lista retornada. Segurança limitada a tipos/extras e string de erro. Nenhuma evidência de atomicidade transacional ou autorização. **Ordem de leitura do prompt antes do agente: NÃO TESTADA.** Preservação persistida após edição rejeitada: NÃO TESTADA. Dados de briefing e rastreabilidade persistida: NÃO TESTADOS.

Observação LOW adicional de cobertura, `promoted_to: null`: `tests/test_briefing_prompt_loader.py:9–35` não fixa duravelmente zero bytes, UTF-8 inválido, PermissionError ou cwd alternativo; `tests/test_briefing_schemas.py:22–72` não fixa requests. Probes acima passaram. T008/T002 podem persistir esses casos em próxima implementação autorizada; nenhuma correção feita aqui. O-01: confiança alta, severidade LOW, `promoted_to: null`; T010/T013 validar sanitização em HTTP/log real. O-02 é pergunta aberta sem severidade de bug; não afirmar que recuperação terminal foi deliberadamente proibida pela spec.

Gate não equivale a aceite integral RF, não marca T004/T005/T006/T012 nem encerra feature. Falhas operacionais locais antes dos checks: duas tentativas de skill com nome incorreto e duas células de leitura com SyntaxError; corrigidas, não são bugs de produto. Pyright assinalou chamadas intencionalmente inválidas nos testes negativos; runtime confirmou exceções esperadas. Nenhuma instalação/rede/API/DB/commit/push/deploy.

