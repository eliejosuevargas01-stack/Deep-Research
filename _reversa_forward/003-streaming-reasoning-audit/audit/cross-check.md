# Relatório de Auditoria Cruzada (Cross-Check)

> Data: 2026-10-22
> Feature: `003-streaming-reasoning-audit`
> Artefatos Auditados:
> - Requirements: `_reversa_forward/003-streaming-reasoning-audit/requirements.md`
> - Roadmap: `_reversa_forward/003-streaming-reasoning-audit/roadmap.md`
> - Actions: `_reversa_forward/003-streaming-reasoning-audit/actions.md`

## 1. Resumo Executivo da Auditoria

A auditoria cruzada estritamente leitora avaliou a consistência mútua, cobertura de requisitos, coerência com a base legada e sanidade da decomposição de tarefas da feature `003-streaming-reasoning-audit`.

Foram identificados **11 apontamentos (findings)**:

| Severidade | Quantidade |
|------------|------------|
| CRITICAL   | 1          |
| HIGH       | 4          |
| MEDIUM     | 3          |
| LOW        | 3          |
| **Total**  | **11**     |

---

## 2. Tabela de Findings

| ID | Severidade | Eixo | Descrição | Onde está |
|----|------------|------|-----------|-----------|
| A001 | CRITICAL | Consistência / Cobertura | Contrato externo de webhook quebrado: RF-05 exige envio de `reasoning_dossier` e `reasoning_auditoria` no evento `research.completed`, mas Roadmap (Fase 4), Actions (T009) e Cenário 3 (Gherkin) omitem `reasoning_auditoria`, prevendo apenas `reasoning_dossier`. | `requirements.md` (RF-05, Cenário 3), `roadmap.md` (Fase 4), `actions.md` (T009) |
| A002 | HIGH | Sanidade do Actions | Contradição direta de status: o Resumo de `actions.md` declara "Concluídas: 0, Em aberto: 10", mas todas as 10 linhas da tabela (T001 a T010) estão marcadas com `[X]` (concluído) antes do coding. | `actions.md` (Resumo vs Tabela linhas 20-29) |
| A003 | HIGH | Cobertura | Decisão do Roadmap Fase 4 de atualizar endpoints (`/api/v1/plan`, `/search`, `/audit`, `/writer`, `/pipeline/{id}/status`) não possui ações correspondentes em `actions.md` (nenhuma ação cobre `app/api/v1/endpoints/`). | `roadmap.md` (Fase 4) vs `actions.md` |
| A004 | HIGH | Cobertura | RF-06 (Auditor e ferramentas de inspeção consumindo reasoning de etapas anteriores) não possui decisão técnica no Roadmap nem tarefa de implementação no Actions. | `requirements.md` (RF-06) vs `roadmap.md` (Fase 3) vs `actions.md` (T008) |
| A005 | HIGH | Cobertura | Cobertura insuficiente de cenários Gherkin: ausência de cenários de aceitação para Planner (RF-04), Auditor (RF-04, RF-06), streaming com tool_calls (RF-01) e cenários de falha/desconexão SSE (RNF-01). | `requirements.md` (Seção 4) |
| A006 | MEDIUM | Consistência | Ambiguidade de nomenclatura de campos entre Banco (RF-03: `reasoning_planejamento`, `reasoning_coleta`, `reasoning_auditoria`) e API (RF-04: `reasoning`), com Actions T006 prevendo expor `reasoning_planejamento` no schema da API. | `requirements.md` (RF-03, RF-04) e `actions.md` (T006) |
| A007 | MEDIUM | Sanidade do Actions | Paralelismo contraditório e subutilizado: T002 marcada como paralela `[//]` apesar de depender de T001; tarefas independentes T007, T008 e T009 marcadas como sequenciais `-`. | `actions.md` (T002, T006-T009) |
| A008 | MEDIUM | Sanidade do Actions | Violação de target file layering: T009 agrupa 4 arquivos de 3 camadas distintas (`writer.py`, `webhook_client.py`, schemas, `pipeline_runner.py`); T006-T008 agrupam core e schemas sob um único alvo. | `actions.md` (T006-T009) |
| A009 | LOW | Sanidade do Actions | Divergência numérica: Resumo declara 4 ações paralelizáveis (`[//]`), mas a tabela contém apenas 3 ações com essa marcação (T001, T002, T006). | `actions.md` (Resumo vs Tabela) |
| A010 | LOW | Sanidade do Actions | Sintaxe de dependência em range (`T001-T009`) em T010 em vez de lista explícita de identificadores unívocos separados por vírgula. | `actions.md` (T010) |
| A011 | LOW | Rastreabilidade | Ausência de identificadores estruturados de decisão (`D-xx`) nas diretrizes das Fases 1 a 5 do Roadmap. | `roadmap.md` (Fases 1 a 5) |

---

## 3. Detalhamento e Impacto dos Findings CRITICAL e HIGH

### A001 — Contrato externo de webhook quebrado (CRITICAL)
- **Impacto:** O requisito RF-05 estipula formalmente que o payload despachado no evento `research.completed` deve conter tanto `reasoning_dossier` quanto `reasoning_auditoria`. Todavia, o Roadmap (Fase 4), a Ação T009 e o Cenário 3 do Gherkin especificam apenas a entrega de `reasoning_dossier`. Se implementado conforme o Roadmap/Actions, o cliente externo receptor do webhook não receberá o raciocínio da auditoria, quebrando o contrato de entrega para os sistemas downstream.
- **Sugestão de Resolução:** Alinhar os artefatos via `/reversa-clarify` ou edição manual, sincronizando o Roadmap (Fase 4), a Ação T009 e o Cenário 3 do Gherkin para incluir explicitamente `reasoning_auditoria`.

### A002 — Contradição de status em `actions.md`: `[X]` vs `[ ]` (HIGH)
- **Impacto:** Na tabela de `actions.md`, todas as tarefas de T001 a T010 estão marcadas com `[X]` (concluído), enquanto a tabela Resumo indica `Concluídas: 0 | Em aberto: 10`. Como o ciclo está na fase pré-coding (`current-stage: actions`), agentes automatizados ou subagentes de `/reversa-coding` que inspecionarem os checkboxes considerarão o plano 100% entregue e encerrarão a execução sem implementar o código.
- **Sugestão de Resolução:** Utilizar `/reversa-to-do` ou editar manualmente `actions.md` para resetar os checkboxes de T001 a T010 para `[ ]`.

### A003 — Atualização dos routers/endpoints da API sem ação correspondente (HIGH)
- **Impacto:** O Roadmap Fase 4 estabelece a necessidade de atualizar os endpoints `/api/v1/plan`, `/api/v1/search`, `/api/v1/audit`, `/api/v1/writer` e `/api/v1/pipeline/{id}/status`. Entretanto, nenhuma ação do `actions.md` tem como alvo os arquivos em `app/api/v1/endpoints/`. Os schemas serão alterados, mas os endpoints HTTP não serão atualizados para repassar os novos campos, resultando em respostas da API sem o reasoning pretendido.
- **Sugestão de Resolução:** Decompor novas ações em `actions.md` via `/reversa-to-do` ou edição manual, mapeando explicitamente cada arquivo de endpoint (`app/api/v1/endpoints/plan.py`, `search.py`, `audit.py`, `writer.py` e `pipeline.py`).

### A004 — RF-06 (Auditor consumindo reasoning anterior) sem cobertura no Roadmap e Actions (HIGH)
- **Impacto:** O RF-06 determina que o Auditor deve ter acesso ao reasoning gerado pelas etapas anteriores para aprimorar a rastreabilidade metodológica. No Roadmap e em Actions (T008), planejou-se apenas a geração de reasoning pelo Auditor, omitindo totalmente a lógica e o prompt para consumo do reasoning prévio (Planner e Personas). Isso deixará uma funcionalidade explicitada nos requisitos sem implementação.
- **Sugestão de Resolução:** Utilizar `/reversa-clarify` para detalhar a interface de consumo do reasoning pelo Auditor e atualizar `roadmap.md` e `actions.md`.

### A005 — Cobertura incompleta de cenários Gherkin (HIGH)
- **Impacto:** O `requirements.md` apresenta apenas 3 cenários de caminho feliz, deixando sem critério formal de aceitação: o Planner (RF-04), o Auditor (RF-04/RF-06), chamadas estruturadas de streaming com `tool_calls`/`generate_json` (RF-01) e todos os fluxos de exceção/resiliência SSE (interrupções, timeouts, fallback de modelos sem reasoning). Isso reduz a confiabilidade dos testes automatizados e perpetua a reprovação apontada em `audit/requirements-audit.md`.
- **Sugestão de Resolução:** Atualizar a Seção 4 de `requirements.md` com cenários Gherkin dedicados para cada RF e para casos negativos/resiliência.

---

## 4. Itens Verificados e Aprovados (Por Eixo)

### Cobertura
- **RF-01, RF-02 e RF-03:** Mapeados com sucesso para decisões técnicas no Roadmap (Fases 1, 2 e 3).
- **Fase 1 e Fase 2 do Roadmap:** Totalmente decompostas em ações atômicas no Actions (T001 a T005).
- **Cenários Gherkin existentes:** Possuem tarefas de implementação e validação mapeadas em `actions.md` (T007, T009, T010).

### Consistência
- **Compatibilidade com Modelo Relacional:** Os nomes das tabelas (`pesquisa`, `pontos`, `conteudo_coletado`) coincidem rigorosamente com os modelos declarados em `app/db/models.py`.
- **Rastreabilidade de Domínio:** Os atores do monólito (`LLMClient`, `Planner`, `Searcher`, `Auditor`, `Writer`, `PipelineRunner`, `WebhookClient`) correspondem aos módulos existentes na arquitetura da base de código.

### Coerência com o Legado
- **Arquitetura Monolítica Modular:** O plano preserva o desacoplamento e a autonomia dos endpoints do pipeline conforme `_reversa_sdd/prd.md`.
- **Compatibilidade com a Feature 002:** Não há quebra nos mecanismos de segurança (`X-API-Key`) e continuidade assíncrona (`PipelineRunner`) entregues no adendo anterior.

### Sanidade do Actions
- **Ausência de Ciclos de Dependência:** O grafo de dependências é estritamente acíclico e direcionado.
- **Exclusividade de Alvo em Tarefas Concorrentes:** Nenhuma ação paralela (`[//]`) compartilha o mesmo arquivo alvo.
- **Existência de Identificadores Base:** Todas as ações referenciadas em dependências (T001 a T009) existem no plano.
