# Inspeção independente — T008

## Resultado do gate

**APROVADO somente para comportamento isolado de loader e conteúdo do prompt.** Nenhum defeito funcional confirmado neste recorte. Integração de geração, ordem anterior ao agente e fronteiras HTTP/log não comprovadas; não encerram T008 nem feature por este relatório.

Contagens verificadas: **3 arquivos de produto/teste inspecionados; 4 testes duráveis aprovados; 8 probes adicionais aprovadas; 2 arquivos Python compilados; 0 bugs confirmados; 2 observações de severidade low e confiança alta; 0 bugs registrados.**

## Pré-checagem e limites

- Skill `reversa-depth-inspection` carregada. Lentes executadas sequencialmente neste worker leaf; somente diagnóstico.
- `.reversa/state.json:2-6,10` define pt-BR e estado global anterior; não comprova entrega atual.
- `.reversa/active-requirements.json:3-12` identifica `001-modulo-briefing`, estágio coding.
- `AGENTS.md:9-52,189-200` consultado como índice/contexto, não como fonte de regras herdadas.
- `git branch --show-current`: `main`, exit 0. `git status --short`: árvore já suja; três arquivos do recorte não rastreados. Não atribuídas alterações concorrentes a esta inspeção.
- `git log -3 --oneline -- app/briefing/prompt_loader.py app/prompts/briefing.md tests/test_briefing_prompt_loader.py`: saída vazia, exit 0; histórico destes arquivos não oferece evidência auxiliar.
- `execution-policy.md:11,18` exige auditoria independente, sem commit/push/deploy, banco externo ou uso de legado como verdade de produto.
- Restrição explícita permite criar somente este relatório. Não realizado bootstrap de `_reversa_bugs/`, leitura de catálogo fora do recorte, registro de bugs, alteração de views, código, testes, actions, progress ou state. Dedupe realizado entre lentes desta inspeção; dedupe contra catálogo externo não comprovado.

## Mapa do recorte

| Camada | Fonte / símbolo | Papel |
|---|---|---|
| Produto aprovado | `requirements.md:34-38,54,58,119-123,153` | SERP somente; foco 3–7, alvo habitual 5; prompt de arquivo atualizado; erro seguro |
| Ação | `actions.md:49` | T008: loader e prompt, ausência/vazio/formato, falha antes do agente |
| Âncora documental planejada | `_reversa_sdd/prd.md:42-43`; `_reversa_sdd/sdd/briefing.md:56-57,61,128,152` | Recarga, conteúdo, falhas; nenhum formato estrito aprovado |
| Código | `app/briefing/prompt_loader.py:6-23` — `PromptUnavailable`, `load_briefing_prompt` | Leitura UTF-8 sem cache; caminho padrão relativo ao pacote; tradução de erros |
| Prompt | `app/prompts/briefing.md:1` | Instrução de foco baseada somente na SERP recebida |
| Teste durável | `tests/test_briefing_prompt_loader.py:8-35` | Não vazio; ausente; whitespace; edição visível na próxima chamada |
| Dados / dependências | Arquivo local UTF-8, `pathlib.Path`, `tempfile`, `unittest` | Nenhum cache, tabela, fila, rede, DB ou chamada de agente no recorte |

Referências `requirements.md`, `actions.md` e `execution-policy.md` nesta tabela pertencem a `_reversa_forward/001-modulo-briefing/`.

## Critérios e evidências

| Critério | Evidência | Resultado |
|---|---|---|
| Ler disco em cada chamada, sem cache | Loader:18,23; teste:29-35; probe `reload_str_and_path` | PASS |
| Alteração vale próxima leitura | Teste:32-35; probe altera mesmo arquivo de versão 1 para versão 2 | PASS no loader; geração integrada fora |
| Ausente / leitura falhada | Loader:19-20; teste:12-18; probes de ausente e `PermissionError` via mock | `PromptUnavailable`, `str` seguro |
| UTF-8 inválido | Loader:18-20; probe bytes `b'\xff'` | `PromptUnavailable`, cause `UnicodeDecodeError` |
| Vazio e whitespace | Loader:21-22; teste:20-27; probes separadas `b''` e `b' \n\t'` | `PromptUnavailable` |
| Caminho padrão independente de cwd | Loader:15; probe muda cwd para scratch e compara conteúdo | PASS |
| 3–7 títulos/descrições, alvo habitual 5 adaptável | Prompt:1; probe textual | PASS; não exige exatamente 5 |
| Somente SERP, não responder/concluir ou pedir páginas/fontes externas | Prompt:1; probe textual | PASS; proibição de leitura de páginas cobre Reader sem exigir palavra literal |
| Mensagem pública não expõe caminho/detalhe | Loader:20,22; testes:17-18,26-27; probes | PASS para `str(PromptUnavailable)` |
| Falhar antes de chamar agente | Loader não chama agente; `requirements.md:122`; `actions.md:56` reserva orquestração T010 | Não comprovável sem integração |
| Formato | UTF-8 e conteúdo não whitespace validados | Nenhum placeholder, parser Markdown ou estrutura rígida aprovado; não exigidos |

Conteúdo de prompt verificado estaticamente e por assert textual. Isso não comprova obediência de LLM nem validação de saída gerada.

## Execução real

Todos comandos executados com workdir `/root/projects/deep-research`. Sem instalação, rede ou DB.

### E1 — testes e compilação

```sh
python3 -B -m unittest discover -s tests -p test_briefing_prompt_loader.py -v && PYTHONPYCACHEPREFIX="$TMPDIR/t008-audit-pycache" python3 -m py_compile app/briefing/prompt_loader.py tests/test_briefing_prompt_loader.py
```

Exit **0**. Saída: quatro testes `ok`, `Ran 4 tests in 0.006s`, `OK`. Compilação sem erro; pycache dirigido ao scratch, não ao repositório.

### E2 — probes inline

Comando `python3 -B - <<'PY' ... PY`, exit **0**. `TemporaryDirectory(dir=os.environ['TMPDIR'])`, scratch `/root/.hermes/profiles/orchestrator/cache/scratch`; nenhum arquivo de probe no repo. Casos executados e saída literal:

```text
PROBES: 8 PASS
PASS empty
PASS whitespace
PASS invalid_utf8
PASS unreadable_safe_str_cause_contains_path
PASS missing_safe_str_cause_contains_path
PASS reload_str_and_path
PASS default_independent_of_cwd
PASS prompt_approved_guidance
Exception chain retains local path; public str safe. No HTTP/log sink tested.
```

Método: gravar bytes vazio/whitespace/UTF-8 inválido e exigir mensagem exata `Prompt de briefing indisponível ou inválido`; simular `Path.read_text` com `unittest.mock.patch.object`, `PermissionError(13, 'Permission denied', str(p))`; verificar tipo da causa e presença do caminho somente nela; verificar ausente; alternar chamadas com `str` e `Path` após editar conteúdo; mudar cwd e restaurar em `finally`; assertar instruções aprovadas no prompt padrão.

Leitura falhada simulada, não prova de permissões de filesystem real; mock evita falso positivo de chmod sob root. SyntaxError de probe anterior informado pelo parent não foi reproduzido nem atribuído ao loader: testes duráveis e probes desta auditoria passaram.

## Lentes e consolidação

| Lente | Resultado | Achados deduplicados atribuídos |
|---|---|---|
| Conformidade | Critérios locais atendidos; ordem agente fora | 0 |
| Fluxo de dados | UTF-8 explícito, conteúdo original retornado, vazio recusado | 0 |
| Contratos / integrações | API local retorna `str` ou erro; sink HTTP/agente ausente | 0 |
| Erros / edge cases | Todos casos locais passaram; cadeia conserva causa | O-02 |
| Cobertura de testes | Quatro testes passam; parte das garantias só em probes | O-01 |
| Concorrência / consistência | Ausência de cache; cada leitura observa arquivo atual | 0 |

Lente de segurança limitada à exceção local alimenta O-02, sem duplicação. Sem transações ou concorrência de geração neste recorte. Edição simultânea não atômica do arquivo não constitui defeito confirmado: nenhuma exigência de atualização atômica foi aprovada.

### O-01 — regressões adicionais não duráveis

- **Tipo:** observação de cobertura; **severidade:** low; **confiança:** alta; **promoted_to:** null.
- **Evidência:** `tests/test_briefing_prompt_loader.py:9-35` não cobre bytes realmente vazios, UTF-8 inválido, falha de leitura, cwd alternativo nem orientação do prompt. E2 cobre estes casos e passa.
- **Esperado x real:** comportamento esperado comprovado; proteção durável contra regressão destes caminhos ainda ausente. Não promover a bug funcional.
- **Tarefa específica sugerida:** complemento de T008 para persistir casos locais já verificados por probes no teste durável, mantendo stdlib e isolamento. Separar teste de cadeia interna de teste da mensagem pública. Nenhuma implementação feita nesta auditoria.

### O-02 — cadeia de exceção mantém detalhe interno

- **Tipo:** observação de fronteira de erro; **severidade:** low; **confiança:** alta; **promoted_to:** null.
- **Evidência:** `app/briefing/prompt_loader.py:19-20` usa `raise ... from exc`. E2 confirma caminho em `__cause__` para ausente e leitura falhada, mas nunca no `str(PromptUnavailable)`.
- **Causalidade comprovada:** consumidor que formatar traceback completo pode incluir caminho interno da causa. Não há endpoint, serializador ou logger neste recorte demonstrando vazamento real. Não observado segredo, vazamento HTTP/log ou defeito HIGH.
- **Tarefa específica sugerida:** T010/T013 verificar fronteira real de erro: resposta pública deve usar mensagem segura; validar política de logs/tracebacks e redação de dados sensíveis. Não exigir remover chaining sem examinar consumidor e necessidade diagnóstica.

Nenhum cluster funcional confirmado. Duas observações independentes: cobertura local e fronteira futura de erro.

## Perguntas separadas dos findings

1. T010 fará leitura do prompt antes de chamar agente e devolverá falha de configuração segura? Deve ser provado por teste com agente spy; ordem entre leitura e busca segue decisão técnica fora deste recorte.
2. Qual política concreta de traceback/log será aplicada em T010/T013? Caminho interno na causa não demonstra vazamento por si só.

## Fora da inspeção

Agente, service, router, HTTP, persistência, schemas/domain, retry, SERP real, logs reais, integração de geração, validação da saída LLM, rastreabilidade persistida e edição/aprovação. Nenhum diff de worker paralelo inspecionado; nenhuma contagem global usada como prova. Catálogo externo de bugs não lido por limite de escopo. Sem mudança de código/testes/status, sem encerramento de ação ou feature, commit/push/deploy.
