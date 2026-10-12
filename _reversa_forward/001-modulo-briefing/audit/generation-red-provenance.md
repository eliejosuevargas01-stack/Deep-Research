# Proveniência e Rastreabilidade do Módulo de Geração (O-06)

## 1. Contexto e Rastreabilidade Factual RED

Este documento registra a proveniência factual dos **30 métodos de teste** de `tests/test_briefing_generation.py` em conformidade com o escopo O-06 para a feature `001-modulo-briefing`.

### Análise Factual de Logs Históricos
- **Total de métodos na suíte (AST)**: 30
- **Métodos com ERROR nominal histórico em logs**: 4
  - `test_invalid_config_raises_before_any_io` (`deleg_c0b7c80c/task-0.log:88` — somente ERROR nominal visível; causa e versão integral não demonstradas no recorte)
  - `test_invalid_prompt_marks_failed_before_any_external_io` (`deleg_c0b7c80c/task-0.log:106` — somente ERROR nominal visível; causa e versão integral não demonstradas no recorte)
  - `test_llm_known_failure_retries_reusing_serp_and_succeeds` (`deleg_c0b7c80c/task-0.log:128` — somente ERROR nominal visível; causa e versão integral não demonstradas no recorte)
  - `test_extreme_numeric_timeout_values_raise_value_error_before_io` (`deleg_1112e09b/task-0.log:30` — causa `OverflowError` na conversão float de `-10**1000`, confirmada no report T017 / parent)
- **Métodos sem ERROR nominal individual comprovado em logs**: 26
- **Ajustes sobre o relatório anterior rejeitado**:
  - `test_happy_path_composes_prompt_search_and_llm_into_same_draft` (`deleg_c0b7c80c/task-0.log:44,52`): erro de importação (`ImportError`/capacidade ausente antes de `service.py`), não RED comportamental de teste.
  - `test_callable_timeout_error_without_deadline_propagates` e `test_callable_invalidcontent_and_runtimeerror_propagate_without_retry` (`deleg_c0b7c80c/task-0.log:154,162`): registrados como `... ok` no log, não `ERROR`.
  - Vínculos históricos de hash para os 30 métodos não possuem prova documental direta nos resumos truncados ("UNPROVEN").
  - O requisito O-06 é documentado estritamente de forma factual sem autoaprovação por declaração própria.

---

## 2. Readset e Hashes de Referência atuais (SHA-256)

Hashes atuais (64 caracteres hexadecimais):

| Componente / Arquivo | Caminho | SHA-256 Digest (64 hex) |
|---|---|---|
| Suíte de Testes | `tests/test_briefing_generation.py` | `df730a92c5e432cd3ec79e0472e6ab8472652f56f0ba93c8d4ddc2d01b86b789` |
| Serviço Orquestrador | `app/briefing/service.py` | `1b64ff68eff0799c3e2d6137783df53a33805babcf3f5154d6a6b08b089cb060` |
| Modelo de Domínio | `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` |
| Loader de Prompt | `app/briefing/prompt_loader.py` | `f53c700a70cfa89f0f64d7d4b4821ba634d9a30c319924606dd915b050bef7c9` |
| Cliente SERP | `app/briefing/serp_client.py` | `49fa6c8912fe52aca33604ffb10279893c50ca392c665a78615a0496db4f06f4` |

Execução local atual: `python3 -B -m unittest tests.test_briefing_generation` → **30/30 GREEN** (execução dinâmica com dependências injetadas/fakes, não verificação estática nem binder real).

---

## 3. Matriz de Proveniência dos 30 Métodos de Teste

| # | Nome do Método (AST) | Categoria Log Histórico | Origem / Evidência Nominal | Status GREEN Atual |
|---|---|---|---|---|
| 01 | `test_happy_path_composes_prompt_search_and_llm_into_same_draft` | Aborto por Import (capacidade ausente) | `deleg_c0b7c80c/task-0.log:44` | ok (30/30) |
| 02 | `test_invalid_theme_fails_before_any_io` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 03 | `test_invalid_config_raises_before_any_io` | ERROR histórico observado | `deleg_c0b7c80c/task-0.log:88` | ok (30/30) |
| 04 | `test_valid_config_edges_pass` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 05 | `test_real_prompt_loader_rereads_file_per_generation` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 06 | `test_invalid_prompt_marks_failed_before_any_external_io` | ERROR histórico observado | `deleg_c0b7c80c/task-0.log:106` | ok (30/30) |
| 07 | `test_unknown_prompt_loader_error_propagates` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 08 | `test_serp_failure_marks_failed_without_llm` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 09 | `test_llm_known_failure_retries_reusing_serp_and_succeeds` | ERROR histórico observado | `deleg_c0b7c80c/task-0.log:128` | ok (30/30) |
| 10 | `test_llm_exhaustion_marks_failed_with_safe_error` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 11 | `test_llm_invalid_output_counts_attempt_and_can_recover` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 12 | `test_llm_wrong_list_shapes_exhaust_to_failed` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 13 | `test_nonstring_llm_return_counts_attempt` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 14 | `test_llm_attempts_cap_respects_custom_values` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 15 | `test_llm_timeout_retries_until_draft` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 16 | `test_callable_timeout_error_without_deadline_propagates` | Não comprovado (`ok` em log) | `deleg_c0b7c80c/task-0.log:154` | ok (30/30) |
| 17 | `test_callable_invalidcontent_and_runtimeerror_propagate_without_retry` | Não comprovado (`ok` em log) | `deleg_c0b7c80c/task-0.log:154` | ok (30/30) |
| 18 | `test_cancelled_llm_propagates_without_retry` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 19 | `test_json_fence_is_accepted_but_garbage_is_rejected` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 20 | `test_accepts_all_in_range_counts` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 21 | `test_concurrent_invocations_overlap_llm_without_service_lock` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 22 | `test_attempts_within_one_invocation_never_overlap` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 23 | `test_timeout_exhaustion_marks_failed` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 24 | `test_unknown_serp_error_and_cancel_propagate` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 25 | `test_real_jina_client_composition_retries_internally_behind_single_search` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 26 | `test_prompt_failure_message_is_fixed_and_distinct` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 27 | `test_unclosed_json_fence_is_rejected` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 28 | `test_failed_and_draft_preserve_identity_and_fixed_messages` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 29 | `test_error_paths_never_leak_raw_output_or_provider_data` | Não comprovado individualmente | Sem recorte em log | ok (30/30) |
| 30 | `test_extreme_numeric_timeout_values_raise_value_error_before_io` | ERROR histórico observado (`OverflowError`) | `deleg_1112e09b/task-0.log:30` | ok (30/30) |

---

## 4. Resumo Sintético

- **Métodos AST na suíte**: 30
- **Comportamento ERROR nominal comprovado em logs**: 4
- **Comportamento não comprovado individualmente em logs**: 26 (4 + 26 = 30)
- **Status atual**: 30/30 GREEN em teste local com dependências injetadas.
