# T035 — evidência de execução dos schemas D4

## Escopo

Verificação isolada de `app/briefing/schemas.py` congelado e cobertura em `tests/test_briefing_schemas.py`. Nenhuma alteração de produção nesta verificação. Escritas autorizadas: este relatório e arquivo de testes. Nenhum router, model, storage, dependency, documento de produto, DB, `.env`, rede, instalação, deploy ou commit.

## Contrato observado (leitura)

### `BriefingResponse`

- `version: int = Field(default=1, ge=1)`, `error: str | None = None`, `approved_at: datetime | None = None`.
- `id`, `theme`, `status: BriefingStatus`, `points` com default vazio, `extra=forbid`; conteúdo draft/approved validado para 3–7 pontos.

### `BriefingVersionResponse`

- `version: int = Field(ge=1)`, `status: BriefingStatus`, `created_at: datetime` obrigatórios.
- `points` usa `default_factory=list`; `error` e `approved_at` são opcionais; `extra=forbid`.
- Draft/approved validam 3–7 pontos; generating/failed aceitam lista vazia.
- Sem `id`, `theme`, `briefing_id`, `prompt`, `search`, `updated_at`.

## Proveniência TDD — retificação

TDD vertical RED antes da implementação **não está comprovado**. O log disponível `/root/.hermes/profiles/orchestrator/cache/delegation/live/deleg_31c8c179/task-1.log` dá esta sequência:

- Linhas 53–54, 15:15:48–15:15:49: teste baseline executado; relatório anterior registra 6 testes verdes.
- Linhas 61–62, 15:18:30–15:18:31: lote de novos testes escrito.
- Linhas 63–68, 15:19:09–15:19:23: alegação de RED e patch de produção; patch aconteceu antes de runner posterior demonstrável.
- Linhas 69–72, 15:19:58: primeiro runner posterior mostrado retorna ERROR após patch de produção.
- Linhas 73–80, 15:20:15–15:20:56: ajustes de testes/fixtures e GREEN posterior.

Embora lote de testes tenha sido escrito antes do patch, log não demonstra runner RED comportamental pré-produção. Os 22 erros anteriormente reportados são pós-produção e misturam problemas de import/enum/fixture: não provam ausência de comportamento no schema. Não inferir causa completa além dos trechos disponíveis; saída do runner está truncada. Resultado GREEN atual mostra assertions passando contra schema atual, não comprova TDD histórico. Histórico sem hash do transcript. Os 6 testes baseline constam no relatório original/log; comparação independente com snapshot versionado indisponível porque estes arquivos constam untracked. **F-TEST-01 retificado no relatório original; não é defeito de produto.**

## Testes e contraprovas atuais

- `tests/test_briefing_schemas.py`: 27 métodos (6 baseline preservados, 21 novos). O método anteriormente chamado `...require_nonempty_title_description` foi renomeado para `...accept_valid_cardinality`, pois cobria somente cardinalidade.
- Novos assertions cobrem payload JSON completo e ordenado de `BriefingResponse` com data UTC aware (`Z`); payload e defaults de `BriefingVersionResponse`; enum/required/extra/schema fields; título e descrição vazios, whitespace e valor não-string em lista válida de 3 e 7 pontos para draft/approved; errores localizados no campo, sem confusão com cardinalidade.
- Contraprova 1 (`/root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe1_model_dump.py`): patch in-memory que remove `approved_at` faz a `TestCase` própria (`ExactPayload.test_exact_payload`) falhar com `AssertionError` (asserção `set(d)` detecta ausência do campo); restore termina sem failures/errors. 1 failure/0 errors. Exit 0. Nota: o teste falha via `assertEqual(set(d), {...})`, não via `KeyError: 'approved_at'`. **F-TEST-02 corrigido: relatório anterior alegava KeyError, probe real gera AssertionError via assertEqual(set(d), {...}).**
- Contraprova 2 (`/root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe2_validation.py`): patch ingênuo do método decorado `_non_empty` não invalida core schema Pydantic já compilado; teste continua rejeitando título vazio. Contraprova real patcha `schemas.validate_points` usado pelo validator runtime; teste de cardinalidade inválida falha com `ValidationError not raised`; restore termina sem failures/errors. 1 failure/0 errors. Exit 0.
- Contraprova mantida (`/root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/maintained_assertion_probe.py`): mutante remove `approved_at` em memória; teste mantido `test_briefing_response_json_dump_exact_payload_and_utc_datetime` falha com `AssertionError`. 1 failure/0 errors. Restore PASS. Exit 0. Comando: `PYTHONPATH=/root/projects/deep-research python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/maintained_assertion_probe.py`.
- Probes alteram símbolos somente em memória, sem arquivo mutante no repo e sem alteração persistente no schema.

## Checks executados

- `python3 -B -m unittest tests.test_briefing_schemas` → exit 0; 27 testes, 96 subtests (runner `TestResult.addSubTest`).
- `python3 -B -m unittest tests.test_briefing_validation tests.test_briefing_lifecycle tests.test_briefing_domain` → exit 0; 26 testes.
- AST de `tests/test_briefing_schemas.py` → 27 métodos `test_*`.
- `PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/t035-pycache python3 -m py_compile app/briefing/schemas.py tests/test_briefing_schemas.py` → exit 0.
- `git diff --check -- app/briefing/schemas.py tests/test_briefing_schemas.py` → exit 0. `git diff --stat` não mostra esses caminhos por serem untracked; status observado anteriormente lista ambos untracked/pré-existentes, não arquivos criados por esta verificação.
- Contraprova 1: `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe1_model_dump.py` → PATCHED failures=1 errors=0, EVIDENCIA 'approved_at'; RESTORED failures=0 errors=0. Exit 0.
- Contraprova 2: `python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-probe/probe2_validation.py` → NAIVE_PATCH still_rejects=True; PATCHED failures=1 errors=0; RESTORED failures=0 errors=0. Exit 0.
- Contraprova mantida: `PYTHONPATH=/root/projects/deep-research python3 -B /root/.hermes/profiles/orchestrator/cache/scratch/t035-parent-replays/maintained_assertion_probe.py` → MAINTAINED_TEST_MUTANT tests=1 failures=1 errors=0; RESTORED_MAINTAINED_TEST tests=1 failures=0 errors=0. Exit 0.
- Descoberta combinada de testes e suite global não executadas; parent pode executar após writers paralelos.

## Arquivos desta verificação

- Modificado: `tests/test_briefing_schemas.py` — quatro métodos adicionados; um método novo renomeado para refletir assertion real.
- Modificado: este relatório autorizado.
- `app/briefing/schemas.py` permanece congelado e inalterado por esta verificação.

## Cobertura por schema (atualizada pós-F-TEST-03)

- `BriefingResponse`: 27 métodos de teste totais; método de campos inválidos agora exercita **ambos** schemas.
- `BriefingVersionResponse`: exercitado explicitamente no mesmo loop (48 casos: 2 schemas × 2 estados draft/approved × 2 campos title/description × 3 valores inválidos × 2 cardinalidades válidas 3 e 7).
- Subtests callback totais: 96 (antes 72). Diferença de 24 callbacks corresponde à duplicação do loop para o segundo schema.
- Seis métodos baseline preservados inalterados (L23–L48). Nenhum método baseline removido ou relaxado. **Contagem verificada: 27 métodos, 96 callbacks via TestResult.addSubTest.**
- `app/briefing/schemas.py` permanece congelado e inalterado.

## Limites e pendências

- TDD vertical histórico não comprovado; testes atuais não reconstroem RED retroativamente.
- F-TEST-01 (proveniência TDD) retificado no relatório original; não é defeito de produto.
- F-TEST-02 (discrepância textual no relatório da contraprova 1) corrigido: `AssertionError` via `assertEqual(set(d), {...})`, não `KeyError`.
- F-TEST-03 (cobertura mantida incompleta) endereçado: `BriefingVersionResponse` agora exercitado explicitamente no método estendido (48 combos). **27 métodos, 96 callbacks reais confirmados.**
- Verificação somente schemas puros; não é QA de router, integração HTTP, banco ou runtime.
- Nenhum documento de produto foi alterado. Arquivos untracked vistos no status eram preexistentes neste escopo.
- T025/T026, `actions.md`, `progress.jsonl`, aprovação/fechamento e auditoria final permanecem fora desta entrega; parent controla estado compartilhado.
