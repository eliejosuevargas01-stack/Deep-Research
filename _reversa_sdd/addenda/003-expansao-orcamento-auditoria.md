# Adendo 003: Expansão de Orçamento de Evidências e Contexto na Auditoria (10x Scale)

> **Status:** Aprovado  
> **Data:** 2026-10-26  
> **Referência:** Revisão Normativa de Limites Operacionais do Auditor (Gemini 3.8 Flash 1M Tokens)

---

## 1. Motivação

Adequar os limites de caracteres do Auditor aos modelos de LLM contemporâneos de janela longa (notadamente `Gemini 3.8 Flash`, com capacidade nativa de até 1 milhão de tokens de contexto), evitando reprovações espúrias e punitivas (rejeição sumária com nota 0/12 critérios) em investigações aprofundadas com alto volume legítimo de evidências textuais coletadas.

Nos parâmetros anteriores, fixados em 32.000 caracteres de evidência e 120.000 caracteres de JSON total, pesquisas extensas com dezenas de fontes e centenas de parágrafos analíticos estouravam o orçamento sintático prematuramente. Como consequência, pontos de auditoria perfeitamente válidos e comprovados eram reprovados automaticamente pelo guardrail estrito de orçamento sem sequer chegar à avaliação semântica do LLM.

---

## 2. Revisão Normativa

Os parâmetros de orçamento operacional do Auditor no arquivo `app/core/auditor.py` são formalmente expandidos em escala de 10x, incorporando flexibilidade de parametrização em tempo de execução via variáveis de ambiente com fallbacks seguros:

1. **`AUDIT_EVIDENCE_BUDGET_CHARS`**:
   - **Limite anterior**: 32.000 caracteres.
   - **Novo limite padrão**: 320.000 caracteres.
   - **Suporte a Override**: Leitura dinâmica da variável de ambiente `AUDIT_EVIDENCE_BUDGET_CHARS` (`int(os.getenv("AUDIT_EVIDENCE_BUDGET_CHARS", 320000))`).

2. **`AUDIT_JSON_BUDGET_CHARS`**:
   - **Limite anterior**: 120.000 caracteres.
   - **Novo limite padrão**: 1.200.000 caracteres.
   - **Suporte a Override**: Leitura dinâmica da variável de ambiente `AUDIT_JSON_BUDGET_CHARS` (`int(os.getenv("AUDIT_JSON_BUDGET_CHARS", 1200000))`).

---

## 3. Rastreabilidade e Módulos Afetados

| Módulo / Artefato | Caminho do Arquivo | Descrição do Impacto |
|---|---|---|
| **Auditor de Qualidade** | `app/core/auditor.py` | Atualização das constantes `AUDIT_EVIDENCE_BUDGET_CHARS` (320.000) e `AUDIT_JSON_BUDGET_CHARS` (1.200.000) com suporte a override via variáveis de ambiente. Formatação dinâmica de mensagens de erro e diagnóstico de estouro de orçamento. |
| **Testes de Aceitação de Auditoria** | `tests/unit/test_audit_acceptance.py` | Adequação dos valores de referência e fixtures de teste que validam os limites máximos de orçamento e rejeições dirigidas. |
| **Especificação Técnica da Auditoria** | `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md` | Atualização da documentação formal dos tetos de payload e guardrails de evidências. |

---

## 4. Conformidade e Garantias de Segurança

- **Margem de Segurança Operacional**: O teto de 1.200.000 caracteres (~300.000 a 350.000 tokens) opera com folga confortável dentro da janela de contexto de 1M tokens do Gemini 3.8 Flash, mitigando riscos de estouro de payload no transporte HTTP.
- **Parametrização Flexível**: Permite ajuste dinâmico em ambientes de staging/produção sem necessidade de refatoração ou rebuild de imagens de container.
- **Garantia de Qualidade**: Elimina falsos negativos decorrentes de orçamentos subdimensionados, preservando a exigência irrestrita do cumprimento dos 12 critérios de qualidade semântica.
