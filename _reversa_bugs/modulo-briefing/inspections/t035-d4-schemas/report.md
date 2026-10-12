# Relatório de Inspeção Profunda — T035 (Schemas D4 do Módulo de Briefing)

- **Data de execução:** 2026-10-11
- **Feature:** `_reversa_forward/001-modulo-briefing` (estágio: `coding`)
- **Escopo do recorte:** Schemas Pydantic v2 (`app/briefing/schemas.py`), testes unitários de schemas (`tests/test_briefing_schemas.py`) e relatório de execução (`_reversa_forward/001-modulo-briefing/audit/t035-execution.md`).
- **Papel:** Auditor independente (`leaf auditor`), somente diagnóstico. Zero alterações em código, testes, roadmap, ações ou documentação externa de produto.
- **Veredito do produto:** **PASS** no recorte puro D4; sem garantia de imutabilidade das instâncias Pydantic após construção.
- **Veredito de entrega / rollout:** **CONDITIONAL**: inspeção T035 concluída; QA própria T035 e fechamento formal pelo parent continuam necessários. QA irmã T034 não substitui QA T035.

---

## 1. Mapa da Feature (Recorte T035)

1. **Especificações canônicas e vigentes:**
   - `_reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md`: seção D4 (linhas 57–77) define explicitamente:
     - `BriefingResponse`: campos `id: UUID`, `theme: str`, `status: BriefingStatus`, `points: list[BriefingPoint] = Field(default_factory=list)`, `version: int = Field(default=1, ge=1)`, `error: str | None = None`, `approved_at: datetime | None = None`. Validador de modelo mantém obrigatoriedade de 3 a 7 pontos para status `draft` e `approved`.
     - `BriefingVersionResponse`: snapshot histórico contendo `version: int = Field(ge=1)`, `status: BriefingStatus`, `points: list[BriefingPoint] = Field(default_factory=list)`, `error: str | None = None`, `approved_at: datetime | None = None`, `created_at: datetime`, e `model_config = {"extra": "forbid"}`. Não contém `id`, `theme`, `briefing_id`, `prompt`, `search` ou `updated_at`.
     - Schemas de requisição (`BriefingCreateRequest`, `BriefingEditPointsRequest`, `BriefingApproveRequest`, `BriefingReopenRequest`) e consulta aprovada (`ApprovedBriefingResponse`) mantidos inalterados.
   - `_reversa_forward/001-modulo-briefing/requirements.md`: RN-01 (tema 3–300), RN-03 (3 a 7 pontos na geração, edição e aprovação), RN-05 (edição 3–7), RN-06 (aprovação com 3–7 válidos), RF-01 a RF-10 e seção 9 (esclarecimentos).
   - `_reversa_sdd/prd.md` e `_reversa_sdd/sdd/briefing.md`: conformidade dos limites de cardinalidade (3–7), alvo habitual 5, segurança de segredos e extra forbid.
   - `_reversa_forward/001-modulo-briefing/audit/cross-check.md`: reauditoria documental Sprint 8 confirmou PASS documental do plano para T035.

2. **Código sob inspeção:**
   - `app/briefing/schemas.py`: 117 linhas, definindo `BriefingPoint`, `BriefingCreateRequest`, `BriefingEditPointsRequest`, `BriefingApproveRequest`, `BriefingReopenRequest`, `BriefingResponse`, `BriefingVersionResponse`, `ApprovedBriefingResponse`.
   - `app/briefing/domain.py`: regras puras reutilizadas (`validate_theme`, `validate_points`, `BriefingStatus`, limites `THEME_MIN`/`THEME_MAX`, `POINTS_MIN`/`POINTS_MAX`).

3. **Testes unitários e probes:**
   - `tests/test_briefing_schemas.py`: 299 linhas, 27 métodos `test_*` na classe `BriefingResponseSchemaTests`, executando 72 callbacks de `subTest`.
   - Probes em `/root/.hermes/profiles/orchestrator/cache/scratch/`:
     - `t035-probe/probe1_model_dump.py`: probe in-memory de exact payload para `model_dump`.
     - `t035-probe/probe2_validation.py`: probe de validação em tempo de execução via `schemas.validate_points`.
     - `t035-parent-replays/maintained_assertion_probe.py`: probe mantido pelo parent testando mutante de `approved_at` contra o teste de suíte `test_briefing_response_json_dump_exact_payload_and_utc_datetime`.

4. **Dados e contratos externos:**
   - Serialização JSON com formato ISO-8601 UTC aware (`Z`) para datetimes.
   - Schemas OpenAPI exportados via `model_json_schema()` contendo enums, required e `additionalProperties: False`.

5. **Bugs e incidentes preexistentes:**
   - Catálogo global de bugs não reauditado neste recorte; zero defeitos de produto confirmados nesta inspeção.
   - Histórico de T014 corrigiu tipagem de status e cardinalidade no estágio anterior.

---

## 2. Varredura por Lentes Especializadas

### 2.1 Lente 1: Conformidade com a Especificação (Spec Compliance)
- **Verificação:** Comparação exata campo a campo entre `_reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md` (D4:57–77) e `app/briefing/schemas.py`.
- **Achados:**
  - `BriefingResponse` possui exatamente `id: UUID`, `theme: str`, `status: BriefingStatus`, `points: list[BriefingPoint] = Field(default_factory=list)`, `version: int = Field(default=1, ge=1)`, `error: str | None = None`, `approved_at: datetime | None = None`, e `model_config = {"extra": "forbid"}`.
  - `BriefingVersionResponse` possui exatamente `version: int = Field(ge=1)`, `status: BriefingStatus`, `points: list[BriefingPoint] = Field(default_factory=list)`, `error: str | None = None`, `approved_at: datetime | None = None`, `created_at: datetime`, e `model_config = {"extra": "forbid"}`.
  - Campos proibidos (`id`, `theme`, `briefing_id`, `prompt`, `search`, `updated_at`) estão ausentes de `BriefingVersionResponse`.
  - Requisitos de cardinalidade (3 a 7 pontos para `draft` e `approved`) e lista vazia para `generating` e `failed` atendidos integralmente.
- **Conclusão:** Conformidade D4 observada nos símbolos inspecionados e nos checks listados. Zero desvios funcionais demonstrados.

### 2.2 Lente 2: Fluxo de Dados e Tipagem (Data Flow & Typing)
- **Verificação:** Serialização de payloads JSON, isolamento de coleções mutáveis por default, tipos de datetime e timezone, enums.
- **Achados:**
  - Serialização UTC: datetime aware com timezone UTC gera representação canônica ISO-8601 com sufixo `Z` (`2026-01-01T12:00:00Z`), testada em ambos os schemas.
  - Isolamento de listas padrão (`default_factory=list`): verificado que instâncias separadas criadas sem passar `points` não compartilham a mesma lista na memória (mutação de `r1.points.append(...)` não contamina `r2.points`).
  - Enums: `status` serializa como string pura do valor (`generating`, `draft`, `failed`, `approved`) no `model_dump(mode="json")` e reflete a lista de strings na propriedade JSON Schema.
  - Conversão de inteiros: `version` valida `ge=1` e rejeita valores `<= 0`.

### 2.3 Lente 3: Contratos e Integrações (Contracts & Schema Compatibility)
- **Verificação:** Retrocompatibilidade de construção, imutabilidade de requisições e schema JSON.
- **Achados:**
  - Compatibilidade com código anterior: instanciação legada de `BriefingResponse(id=..., theme=..., status=..., points=...)` sem especificar `version`, `error` ou `approved_at` continua válida e adota `version=1`, `error=None`, `approved_at=None`.
  - Rejeição de campos extras: `model_config = {"extra": "forbid"}` rejeita campos não mapeados em todos os schemas D4 e seus itens `BriefingPoint`.
  - Schemas de requisição inalterados: nenhuma alteração indevida foi introduzida em `BriefingCreateRequest`, `BriefingEditPointsRequest`, `BriefingApproveRequest` ou `BriefingReopenRequest`.
  - Nenhuma regra estrita de tipo arbitrária ou não aprovada (como `strict=True` forçado para `version` rejeitando coercões válidas do Pydantic v2) foi adicionada fora da especificação.

### 2.4 Lente 4: Estados de Erro e Edge Cases (Error States & Cardinality)
- **Verificação:** Limites de contagem de pontos (0, 1, 2, 3, 4, 5, 6, 7, 8), campos vazios ou whitespace em `title` e `description`.
- **Achados:**
  - Estados `draft` e `approved` rejeitam 0, 1, 2 e >= 8 pontos com `ValidationError` de domínio.
  - Estados `draft` e `approved` aceitam exatamente 3, 4, 5, 6 e 7 pontos.
  - Estados `generating` e `failed` aceitam lista vazia de pontos sem acionar validação de cardinalidade.
  - Ponto individual rejeita `title` ou `description` vazios (`""`), somente espaços (`"   "`) ou tipos não-string (`7`) independentemente da cardinalidade do payload.
  - Localização do erro no Pydantic: erros de campo individual são apontados no caminho específico `("points", i, "title")` ou `("points", i, "description")`, e não como falha genérica de cardinalidade em `("points",)`.

### 2.5 Lente 5: Cobertura de Testes e Aliasing (Test Quality & Test Aliasing)
- **Verificação:** Análise de AST e execução de testes em `tests/test_briefing_schemas.py`, contagem programática de subtests, validação dos mutantes in-memory e proveniência TDD.
- **Achados:**
  - Quantitativo: 27 métodos `test_*` na AST, 27 testes executados pelo runner `unittest`, 72 callbacks de `subTest` registrados programaticamente.
  - Probes in-memory executados sem erros:
    - Probe 1 (`scratch/t035-probe/probe1_model_dump.py`): exit 0.
    - Probe 2 (`scratch/t035-probe/probe2_validation.py`): exit 0.
    - Parent probe (`scratch/t035-parent-replays/maintained_assertion_probe.py`): exit 0 (prova que o teste mantido falha com 1 failure e 0 errors quando `approved_at` é removido em memória).
  - Observações detalhadas de teste e proveniência registradas na Seção 3 abaixo.

### 2.6 Lente 6: Concorrência e Consistência (Concurrency & Mutability)
- **Verificação:** Concorrência e thread-safety em schemas puros em memória.
- **Achados:**
  - Schemas são classes Pydantic v2 sem estado global mutável.
  - O uso de `Field(default_factory=list)` evitou aliasing nos quatro pares probe e nos dois testes mantidos; concorrência não foi exercitada.

---

## 3. Catálogo de Achados da Auditoria

```yaml
- finding_id: F-TEST-01
  lens: Cobertura de testes
  summary: Retificação de proveniência TDD histórica confirmada no log de delegação sem evidência de runner RED pré-produção.
  confidence: alta
  evidence:
    - "/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_31c8c179/task-1.log: linhas 61-78 (patch de produção às 15:19:21 antes do runner post-new às 15:19:58)"
    - "_reversa_forward/001-modulo-briefing/audit/t035-execution.md: linhas 21-32"
  suspected_severity: low
  signals: [process-observation]
  promoted_to: null
  notes: "O log da delegação demonstra que o patch de código em app/briefing/schemas.py ocorreu às 15:19:21, antes da execução do runner de teste às 15:19:58. O primeiro runner posterior retornou ERROR; saída truncada não permite confirmar contagem nem causas completas. Alegação histórica de 22 erros não estabelece RED pré-produção. O relatório t035-execution.md retificou a alegação com transparência. Conforme regra de auditoria, não se exige re-execução destrutiva do código para forjar histórico. Trata-se de observação processual, não defeito de produto."

- finding_id: F-TEST-02
  lens: Cobertura de testes
  summary: Discrepância menor de descrição na evidência do Probe 1 entre texto do relatório e asserção real.
  confidence: alta
  evidence:
    - "_reversa_forward/001-modulo-briefing/audit/t035-execution.md: linha 37 (alegação de KeyError: 'approved_at')"
    - "/root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe1_model_dump.py: linhas 27-29, 51-55 (asserção set(d) detecta ausência de approved_at como AssertionError, não KeyError)"
    - "/root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/maintained_assertion_probe.py: linhas 1-23 (parent reproduziu mutante contra o teste real mantido com AssertionError)"
  suspected_severity: low
  signals: [documentation-discrepancy]
  promoted_to: null
  notes: "O relatório t035-execution.md descreve que o probe1 falha com KeyError, mas o código real do probe1 utiliza asserção de conjuntos (set(d)) gerando AssertionError ('approved_at'). O parent supriu essa validação de forma mais robusta no script maintained_assertion_probe.py, onde o mutante fez o teste da suíte mantida falhar com 1 failure e 0 errors. A evidência de contraprova é sólida; trata-se apenas de imprecisão textual no relatório, sem impacto no produto."

- finding_id: F-TEST-03
  lens: Cobertura de testes
  summary: Teste de valores inválidos de título e descrição exercita diretamente BriefingResponse mas não instancia BriefingVersionResponse.
  confidence: alta
  evidence:
    - "tests/test_briefing_schemas.py: linhas 249-268 (método test_title_description_invalid_values_rejected_independent_of_cardinality usa self.response)"
    - "app/briefing/schemas.py: linhas 24-36, 90-106 (BriefingPoint é compartilhado e validado por BriefingPoint._non_empty)"
  suspected_severity: low
  signals: [test-aliasing]
  promoted_to: null
  notes: "O método de teste especializado em valores inválidos (vazio, whitespace, número) exercita apenas BriefingResponse via self.response. Como BriefingVersionResponse utiliza o mesmo modelo BriefingPoint e executa validate_points via seu próprio model_validator, a validação é garantida pelo modelo subjacente. A ausência de chamada explícita de BriefingVersionResponse nesse loop específico de teste é uma observação de cobertura/aliasing, não defeito de produto."
```

---

## 4. Verificação de Integridade e Preservação

1. **Manifesto L86 do `progress.jsonl`:**
   - Conferência de 108 hashes SHA-256 pré-despacho registrados na linha 86 de `_reversa_forward/001-modulo-briefing/progress.jsonl`.
   - Todos os 108 arquivos foram lidos e seus hashes conferidos: **108/108 íntegros, zero divergências, zero arquivos ausentes**.

2. **Verificação de `git status` e diffs:**
   - `git diff --check`: exit code 0 (zero erros de formatação ou conflitos em arquivos rastreados).
   - `app/briefing/schemas.py` e `tests/test_briefing_schemas.py` encontram-se como `??` (untracked), exatamente como recebidos no início da sessão. Nenhuma modificação foi feita nesses arquivos nesta auditoria.
   - Esta inspeção escreveu somente o presente relatório; não há prova de estado de arquivos fora do manifesto além dos dois alvos untracked lidos.

3. **Execução de comandos e suites:**
   - `python3 -B -m unittest tests.test_briefing_schemas -v`: exit code 0 (27 testes executados, 0 falhas, 0 erros).
   - AST analysis: 27 métodos `test_*`.
   - Subtest counts: 72 subtests executados com sucesso via callback `addSubTest`.
   - Probes em scratch (`probe1_model_dump.py`, `probe2_validation.py`, `maintained_assertion_probe.py`): todos com exit code 0.
   - Probes em memória pura de cardinalidade e campos (48 variações de campos inválidos + 36 de cardinalidade + 4 pares de isolamento de defaults): todos com asserções atendidas e zero mutação no repositório.

---

## 5. Limites e Não-Escopo

- **Fora do escopo:**
  - Endpoints HTTP reais, roteamento FastAPI, autenticação e CSRF (T025 e T026).
  - Persistência física em PostgreSQL/SQLite e migrações Alembic (0006).
  - Integração com LiteLLM, Jina SERP e chamadas de rede.
  - Auditoria e relatório do QA irmão (`_reversa_bugs/modulo-briefing/inspections/t034-traceability-qa/report.md`), que permaneceu intocado e não lido.
  - Alteração do status da tarefa T035 em `actions.md` ou `progress.jsonl`, que permanece sob controle exclusivo do orquestrador parent.

---

## 6. Veredito Final

- **Veredito do produto:** **PASS** no recorte puro D4 inspecionado; sem aprovação de router, DB, runtime HTTP ou segurança de mensagens.
- **Veredito de processo / entrega:** **CONDITIONAL**. Inspeção T035 sem defeitos de produto; QA própria T035 e fechamento formal pelo parent ainda necessários antes de T025/T026.
- **Achados promovidos a bug:** **0**. Todos os 3 achados foram mantidos com `promoted_to: null` (duas observações de teste/processo e uma discrepância textual de relatório).

## 7. Ledger de evidência, ressalvas e contagens

Readset semântico: AGENTS.md; .reversa/state.json, active-requirements.json, config.toml e reversa-config.json; requirements.md; PRD e SDD greenfield; actions.md (T035:90); cross-check.md (verdict vigente:5,26,36); D4:57–77; schemas.py; domain.py; tests/test_briefing_schemas.py; audit/t035-execution.md; progress.jsonl L86; três scripts scratch e transcript:53–80. Demais 108 entradas do manifesto somente hash, sem inspeção semântica de runtime fora do recorte. Nenhum relatório sibling novo lido ou hashado.

Mapa spec→code→test preciso: D4:59–67 → schemas.py:72–87 → tests:76–99,175–209; D4:68–76 → schemas.py:90–106 → tests:102–172,189–247,269–295; RN-03/RF-03/RF-06 → domain.py:40–53 e schemas.py:24–35,83–106 → tests:27–48,139–159,249–267. Testes:249–267 têm 24 callbacks, exclusivamente BriefingResponse. Probe independente desta inspeção confirmou 48 combinações nos dois schemas; não converte essas combinações em cobertura mantida de BriefingVersionResponse. Compartilhamento do modelo não prova cobertura própria da versão. F-TEST-03 permanece LOW, não prioridade sobre defeitos demonstrados, não bug produto.

Preservação histórica de seis métodos baseline: alegada em t035-execution.md:35 e história original; esta inspeção não refez comparação AST contra snapshot original. Não há baseline Git desses arquivos untracked. Requisições/ApprovedBriefingResponse são consistentes com D4 e patch transcript disponível é restrito às respostas; não se afirma comparação histórica versionada completa. Schemas Pydantic são mutáveis após construção; default isolado não prova frozen, thread-safety global ou invariantes sob atribuição posterior. Não houve teste concorrente. Não há alegação de sanitização automática de error: whitelist pública sem prompt/search não prova ausência de segredos nas strings, logs ou traceback. Dados UTC testados não criam requisito novo de rejeitar datetime naive. `version` não recebeu contrato strict bool/string adicional.

Resultados diretos, root /root/projects/deep-research, batch fail-fast `&&`, exit final 0 (cada predecessor concluído 0):
- `python3 -B -m unittest tests.test_briefing_schemas -v`: 27 testes OK.
- Runner stdlib inline com AST e TestResult.addSubTest: 27 métodos, 27 testsRun, 72 callbacks; 24 no método de campos inválidos, 16 cardinalidade corrente, 8 consulta aprovada, 6 cardinalidade inválida versão, 4 válida versão, 4 enum, demais 2 cada nos seis métodos restantes. Não confundir callbacks com testes ou invocações externas.
- `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe1_model_dump.py`: PATCHED failures=1 errors=0, EVIDENCIA 'approved_at'; RESTORED failures=0 errors=0. TestCase própria ExactPayload, não teste mantido.
- `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe2_validation.py`: NAIVE_PATCH still_rejects=True; PATCHED failures=1 errors=0, AssertionError: ValidationError not raised; RESTORED failures=0 errors=0. Probe próprio, não suíte mantida.
- `PYTHONPATH=. python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/maintained_assertion_probe.py`: MAINTAINED_TEST_MUTANT tests=1 failures=1 errors=0; RESTORED_MAINTAINED_TEST tests=1 failures=0 errors=0.
- `git diff --check`: exit0, tracked somente. Arquivos alvo untracked conferidos por leitura e SHA-256, não por diff vazio.
- Segundo batch `python3 -B -c` com imports somente schemas/domain, fixtures sintéticas locais: PURE_FIELD_PROBES 48; CARDINALITY_PROBES 36; DEFAULT_ISOLATION_PAIRS 4, exit0. Contagem de cardinalidade = dois schemas × dois estados × nove contagens 0..8. Isolamento = dois schemas × generating/failed. Probes inline não foram adicionados à suíte.
- Conferência independente do checkpoint fixo L86 antes e depois runtime: 108/108 SHA-256 válidos (64 hex), arquivos existentes, zero diferenças. Denominador exclui naturalmente novo report próprio e sibling QA porque nenhum integra manifesto L86. Não usar denominadores históricos 105/105 de cross-check L84 como resultado desta inspeção.

Resultados herdados, não reexecutados: L86.t035_verification.discover_suite_count=161; L86.checks.suite_161_exit=0; L86.t035_verification.py_compile=0. Suite global, compilação e QA T034 não necessários para recorte; não atribuídos a este auditor.

Dataset canônico embutido em YAML acima: F-TEST-01, F-TEST-02, F-TEST-03; sem duplicatas declaradas; promoted_to null em todos. Totais por lente: cobertura de testes 3, demais 0; confiança alta 3; severidade low 3; bugs produto 0, promovidos 0. Cluster apenas evidência/cobertura de schemas, não causa estrutural de defeito runtime. Observação F-TEST-01 já retificada, F-TEST-02 imprecisão documental residual, F-TEST-03 oportunidade de cobertura mantida separadamente autorizada. Auditor não corrige nem cria tarefa, bug ou view. Somente novo report próprio escrito. Nenhuma skill alterada, subdelegação ou todo_list.
