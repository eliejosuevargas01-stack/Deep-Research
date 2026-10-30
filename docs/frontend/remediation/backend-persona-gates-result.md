# Relatório de Implementação e Remediação: Portões de Qualidade e Contrato de Personas por Pesquisa

**Data/Hora do Relógio Real:** `2026-10-26T19:08:56Z`  
**Autor:** Hermes Backend Corrective Worker (`ag/gemini-3.8-flash-high`, reasoning: high, via 9router)  
**Escopo:** Checkpoint 1 (Modo Síncrono); Backend e Portões de Auditoria/Busca/Redação  
**Arquivos de Domínio:** `app/core/personas.py`, `app/core/auditor.py`, `app/core/searcher.py`, `app/core/writer.py`, `app/core/pipeline_runner.py`, `app/api/v1/endpoints/search.py`  
**Testes Dedicados:** `tests/integration/test_persona_pipeline_gates.py` (9 testes criados, 100% aprovados)  
**Status da Suíte Completa:** 390 passed, 0 failed  

---

## 1. Identificação do Blocker Real e Evidência Empírica

Durante os testes empíricos com navegador real e provedores configurados (`docs/frontend/remediation/evidence/live-payloads.jsonl`), foi comprovado o seguinte bloqueio impeditivo no fluxo fim a fim:

1. **Planejamento (`POST /api/v1/plan`)**:
   - Requisição realizada com `n_pontos: 2` e `personas: ["historiador", "cetico"]`.
   - O plano gerou com sucesso 2 eixos e persistiu o snapshot em `metadados_planejamento` (HTTP 201).
2. **Busca Web Concorrente (`POST /api/v1/search`)**:
   - A busca executou corretamente apenas as 2 personas solicitadas (`historiador` e `cetico`), salvando suas fontes e conclusões em `conteudo_coletado`.
   - Contudo, internamente no `Searcher` (`app/core/searcher.py:1355`), a condição de completude avaliava `REQUIRED_PERSONAS = len(self.personas)` (tamanho estático da classe = 4), marcando a coleta como `parcial` em vez de `coletado`, e mantendo loops fixos que assumiam a existência das 4 personas canônicas.
3. **Auditoria de Qualidade (`POST /api/v1/audit`) - Ponto Crítico**:
   - Em `app/core/auditor.py:640`, a precondição de integridade definia:
     ```python
     REQUIRED_PERSONAS = {"historiador", "visionario", "cetico", "futurista"}
     missing_personas = REQUIRED_PERSONAS - set(resultados_personas.keys())
     ```
   - Como a pesquisa deliberadamente selecionou apenas `historiador` e `cetico`, a auditoria reprovou sumariamente ambos os pontos com nota 0/12:
     `pontos_fracos: "Reprovado por coleta incompleta: persona(s) ausente(s): ['futurista', 'visionario']."`
4. **Bloqueio do Redator Final (`POST /api/v1/writer`)**:
   - Devido à reprovação artificial da auditoria, o Writer foi estritamente bloqueado com HTTP 400 (`UNAPPROVED_POINTS`), impedindo que pesquisas legítimas com subconjunto de personas atingissem o dossiê final.

---

## 2. Contrato Canônico de Personas por Pesquisa (`app/core/personas.py`)

Para solucionar a falha de forma arquitetural e duradoura sem enfraquecer nenhum portão de qualidade, foi criado o módulo central `app/core/personas.py`:

### 2.1. Princípios Contratuais
1. **Snapshot Persistido por Pesquisa**:
   - O subconjunto de personas contratado para uma pesquisa é gravado no momento do planejamento em `pesquisa.metadados_planejamento["preferencias"]["personas"]`.
   - Todas as etapas downstream (`Searcher`, `Auditor`, `Writer` e `PipelineRunner`) resolvem a obrigatoriedade de personas a partir desse snapshot.
2. **Compatibilidade Conservadora com Planos Legados**:
   - Pesquisas legadas que não possuem snapshot em `metadados_planejamento` (ou cujo JSON seja nulo/malformado) assumem o padrão conservador estrito com **todas as 4 personas canônicas** (`["historiador", "visionario", "cetico", "futurista"]`).
3. **Proibição Estrita de Derivação Oportunista**:
   - **NUNCA** deriva a obrigatoriedade a partir de quais resultados calham de estar presentes em `resultados_personas`.
   - Se uma persona **SELECIONADA** faltar ou apresentar análise vazia / dados corrompidos, a auditoria e o redator continuam **bloqueando obrigatoriamente**.
4. **Segregação de Papéis Internos**:
   - As únicas personas de busca web selecionáveis são `historiador`, `visionario`, `cetico` e `futurista`.
   - Papéis como `planejador`, `avaliador_semantico`, `auditor`, `redator final` e `auditor_redacao` permanecem exclusivamente internos e não podem ser selecionados ou injetados como alvos de busca.

---

## 3. Modificações Estruturais no Backend

### 3.1. Auditoria (`app/core/auditor.py`)
- **Resolução Dinâmica**: `execute_audit` recupera o registro da pesquisa e resolve `required_personas_list = resolve_required_search_personas(pesquisa)`.
- **Precondição de Coleta Incompleta**: `missing_personas = required_personas - set(resultados_personas.keys())`. Se houver ausência de persona selecionada, reprova honestamente com diagnóstico detalhado.
- **Checagens de Integridade e Unicidade**: Validação de análise não-vazia, conclusões estruturadas, diário de ações, unicidade de claim IDs e vínculo claim→trecho entregue agora iteram sobre `required_personas_list`.
- **Prevenção de Injeção em Tarefas de Reparo (`_build_tasks_and_weak_points` e `_project_tasks_from_criteria`)**:
  - Aceitam o parâmetro `allowed_personas`.
  - O campo `personas_alvo` das tarefas projetadas é filtrado contra as personas contratadas da pesquisa, impedindo que tarefas de reparo direcionem buscas para personas não selecionadas (ex: não injeta `visionario` em pesquisa restrita a `historiador` + `cetico`).

### 3.2. Busca Web Concorrente (`app/core/searcher.py`)
- **Resolução de Metas**: `target_personas = resolve_required_search_personas(pesquisa, fallback_personas=self.personas)`.
- **Contrato de Completude**: `REQUIRED_PERSONAS = len(target_personas)`. Apenas quando todas as personas alvo estiverem presentes e com sucesso o ponto é promovido a `coletado`.
- **Recomposição Parcial (DR-010)**:
  - Condição corrigida de `len(active_personas) < 4` para `len(active_personas) < len(target_personas)`.
  - Recomposição de tentativas anteriores itera sobre `target_personas`, impedindo vazamento de roles alheios.
  - Loops de consolidação de Markdown e URLs fonte iteram sobre `target_personas`.
  - Lista pública de retorno preserva as personas de `target_personas`.

### 3.3. Redação Final (`app/core/writer.py`)
- Em `_verificar_prontidao_pesquisa`, adicionada validação estrita de evidências para todas as `required_personas` da pesquisa:
  - Valida que `resultados_personas` da coleta aprovada contém todas as personas requeridas.
  - Valida que nenhuma persona requerida possui análise vazia ou conclusões malformadas.
  - Bloqueia com `READINESS_FAILED` em caso de dados faltantes ou corrompidos de personas selecionadas.
  - Permite normalmente a passagem de subconjuntos legítimos (ex: 2 personas) aprovados pela auditoria.

### 3.4. Pipeline Autônomo e Sincronização (`app/core/pipeline_runner.py`)
- No método `PipelineRunner.run`:
  - `allowed_personas = resolve_required_search_personas(pesquisa)` é repassado ao `Searcher`.
  - Os clientes de `Auditor` e `Writer` recebem as personas globais do sistema (`auditor`, `redator final`).
  - As tarefas de retentativa (`p_alvos`) filtram candidatos com `if p_nome in allowed_personas`.
- Implementado o helper exportado `execute_sync_pipeline(id_pesquisa, callback_url, transport)` para execuções inline e validações de integração.

### 3.5. Endpoint de Busca (`app/api/v1/endpoints/search.py`)
- Linhas 80-92 atualizadas para utilizar `resolve_required_search_personas(pesquisa_record)` para o fallback de snapshot quando o payload omitir o campo `personas`.

---

## 4. Garantia de Preservação dos Portões de Qualidade

Nenhum critério ou tolerância de qualidade foi afrouxado:
- **12 Critérios Canônicos**: O vetor ordinal 1..12 do Auditor continua sendo integralmente exigido com tipos estritos (`StrictInt`, `StrictBool`).
- **Corte Mínimo**: Permanece rigorosamente em 11/12 (ou 12/12 quando configurado).
- **Validador Semântico**: Avaliação semântica com verificação de sobreposição e redundância entre eixos permanece 100% ativa.
- **Proveniência de Trechos e URLs**: Trechos continuam exigindo correspondência material de hash SHA-256 e offsets no corpo das fontes lidas via Reader (`read_ok`).
- **Sem Dados Fabricados**: Ausência de fallbacks especulativos ou aprovações sintéticas.

---

## 5. Suíte de Testes de Integração e Resultados Obtidos

Arquivo dedicado: `tests/integration/test_persona_pipeline_gates.py`

Comando de execução:
```bash
.venv/bin/pytest tests/integration/test_persona_pipeline_gates.py -v
```

### Resultados dos Testes Específicos:
| Teste | Cenário Validado | Resultado |
|---|---|---|
| `test_full_pipeline_with_2_personas_subset_succeeds_end_to_end` | Ciclo completo: Plan (2 pontos, 2 personas) -> Search (2 coletadas) -> Audit (ambos aprovados sem exigir 4 personas) -> Writer (concluído) | **PASSED** |
| `test_audit_and_writer_block_when_selected_persona_is_missing` | Quando persona selecionada (`cetico`) falta na coleta, Audit reprova por coleta incompleta e Writer bloqueia | **PASSED** |
| `test_audit_and_writer_block_when_selected_persona_evidence_is_malformed` | Quando persona selecionada tem análise vazia, Audit reprova por inconsistência e Writer bloqueia | **PASSED** |
| `test_legacy_research_without_snapshot_strictly_requires_all_4_personas` | Pesquisa legada sem snapshot exige as 4 personas canônicas e reprova se apenas 2 estiverem presentes | **PASSED** |
| `test_independent_researches_do_not_cross_contaminate_persona_contracts` | Pesquisas concomitantes com personas distintas (A: `historiador`; B: `visionario`+`futurista`) são auditadas isoladamente sem contaminação | **PASSED** |
| `test_audit_repair_tasks_never_target_unselected_roles` | Critério reprovado projeta tarefas em `personas_alvo` estritamente contidas no subconjunto da pesquisa | **PASSED** |
| `test_search_retry_missing_selected_role_recomposes_to_coletado` | Retentativa focada de persona ausente recompõe coleta anterior (1/2 -> 2/2) atingindo status `coletado` | **PASSED** |
| `test_pipeline_helper_sync_with_2_personas_plan` | Helper `execute_sync_pipeline` executa pesquisa autônoma de 2 personas até a redação final com sucesso | **PASSED** |
| `test_resolve_required_search_personas_fallback_safety` | Teste unitário e de contrato contra metadados `None`, JSONs corrompidos, chaves ausentes e fallbacks | **PASSED** |

### Execução de Regressão Global:
```bash
.venv/bin/pytest tests/integration/ tests/unit/
```
**Resultado:** `390 passed, 8 warnings in 52.73s` (0 falhas em todo o repositório).
