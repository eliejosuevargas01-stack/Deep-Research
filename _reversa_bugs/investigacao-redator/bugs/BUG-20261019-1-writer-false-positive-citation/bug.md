---
schema_version: 1
id: BUG-20261019-1
display_number: 22
context: investigacao-redator
title: "Writer guardrail false positive: **Proposta didática:** classificado como lista factual sem citação"
status: closed
phase: verified
severity: high
priority: P1
security_suspected: false
visibility: internal
created: "2026-10-19T20:10:00-03:00"
updated: "2026-10-21T08:45:00-03:00"
area:
  - writer-stage
  - citation-validation
module:
  - pipeline-writer
feature:
  - deep-research-execution
  - report-rendering
origin:
  type: inspection
  external_ref: "_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md"
reported_by: reversa-diagnostic
reported_at: "2026-10-19T20:10:00-03:00"
environment:
  app: deep-research
  branch: main
  commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
traceability:
  specs:
    - "app/CRITERIA.md#b33-teto-de-tentativas"
    - ".reversa/principles.md#iii-resiliencia-por-degradacao-graciosa-e-limites-rigidos"
  expected_behavior: "Linha **Proposta didática:** (negrito markdown, não lista factual) não deve disparar guardrail de citação; apenas afirmações factuais sem fonte devem ser rejeitadas."
  observed_behavior: "writer.py:60 `line.startswith((\"-\", \"*\", \"|\"))` captura negrito iniciado por asterisco como candidato factual/lista; linha sem link dispara RuntimeError linha 68."
  affected_code:
    - "app/services/pipeline/writer.py:56-68"
root_cause:
  state: confirmed
  hypothesis: "Heuristica line.startswith(('*',...)) captura negrito markdown como lista factual"
  causal_path:
    - "Modelo gera linha **Proposta didática:** ..."
    - "candidate_lines inclui linha (não começa com #, >, References)"
    - "line.startswith(('*',)) -> True (asterisk do negrito)"
    - "has_substance=True, is_factual_candidate=True"
    - "Sem ]:(http... na linha -> RuntimeError linha 68"
  evidence:
    - ref: "_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md:28-30"
      observation: "Falso positivo confirmado: starts_with_asterisk=True, has_substance=True, is_factual_candidate=True, rejected=True"
  code_refs:
    - file: "app/services/pipeline/writer.py"
      symbol: "_write_report.candidate_lines.is_factual_candidate"
      commit: "582ed04abd3f03de8d38f8d162d1d945534e6b54"
spec_verdict: null
resolution_kind: null
closure:
  policy: local-software
  satisfied: false
change_set: []
regression_tests: []
labels:
  - false-positive
  - citation-guardrail
  - markdown-heuristic
relations: []
express: false
---
# BUG-20261019-1 — Writer guardrail false positive: negrito confundido com lista factual

## Summary
O guardrail de citação do Writer (`writer.py:56-68`) usa heurística sintática `line.startswith(("-", "*", "|"))` para detectar linhas candidatas a conteúdo factual (listas, tabelas, prosa terminada em pontuação). Essa heurística **não distingue Markdown semântico**: um parágrafo iniciado com `**Proposta didática:**` (negrito) começa com `*` e é classificado como `is_factual_candidate=True`. Como a linha não possui citação inline `[texto](url)`, o guardrail rejeita com `RuntimeError: Writer published uncited factual content (prose, list, or table)`.

## Expected Behavior
Apenas afirmações factuais (declarações de fato, dados, claims verificáveis) em formato de lista, tabela ou prosa terminada em ponto final devem exigir citação inline. Propostas didáticas, avisos, cabeçalhos em negrito, e relatórios de lacuna/auditoria sem fonte não devem disparar o guardrail.

## Actual Behavior
Linha `**Proposta didática:** desenhe dois cartões...` é rejeitada porque:
1. `line.startswith(("*"))` → `True` (asterisco do negrito)
2. `has_substance=True` (tem palavras ≥4 e letras)
3. `is_factual_candidate=True` (condição OR linha 60-62)
4. Sem `](http` na linha → `RuntimeError` linha 68

## Steps to Reproduce
1. Executar `_write_report` com evidence não-vazia (78 registros no diagnóstico)
2. Modelo gera texto contendo linha iniciada por negrito markdown `**Proposta didática:** ...`
3. Validação `candidate_lines` inclui a linha (não começa com `#`, `>`, `References`, não é tabela)
4. `line.startswith(("*"))` → `True` → `is_factual_candidate=True`
5. `re.search(r"\]\(https?://[^\s)]+\)", line)` → `None`
6. Lança `RuntimeError` linha 68

## Evidence
- Diagnóstico: `_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md` (linhas 26-30)
- Código fonte: `app/services/pipeline/writer.py:56-68`
- Teste isolado reproduzido: `starts_with_asterisk=True, has_substance=True, is_factual_candidate=True, rejected=True`

## Suspected Area
`app/services/pipeline/writer.py` função `_write_report`, bloco `candidate_lines` (linhas 49-68).

## Acceptance Criteria
1. Linha `**Proposta didática:** ...` (negrito, não lista) passa no guardrail sem exigir citação.
2. Lista factual real `- Fato comprovado` sem citação continua rejeitada.
3. Tabela markdown `| Coluna |` com conteúdo factual sem citação continua rejeitada.
4. Prosa terminada em `.` `!` `?` sem citação continua rejeitada.
5. Relatório de lacuna/auditoria sem links não é rejeitado incondicionalmente (bug separado #2).
6. Testes de reprodução e regressão passam.

## Traceability
(espelho legível do front matter YAML)

## Agent Notes
- **Não criar bypass genérico por prefixos**: negrito factual sem fonte continua negativo, listas/tabelas factuais sem fonte continuam negativas.
- **Casos de lacunas reais** (relatório de auditoria, aviso de dado faltante) não devem exigir fonte.
- **Links fornecidos** devem sempre pertencer às evidências (validação linhas 45-48 mantida).
- Ponderar limite mínimo de palavras no caso de lacunas.
- Não alterar contrato extra sem autorização.
- Comparar RF401/402 requirements feature004; se adendo necessário, propor somente, spec requer gate obrigatório.
- Quarta reprovação encerra busca, não entrega; falta de conteúdo deve gerar lacuna sem inventar evidência/link.
- Não transformar aprovação auditor em requisito para Writer.