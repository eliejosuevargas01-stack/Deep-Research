# Relatório de Confiança Global — Deep Research Engine

> Gerado pelo Revisor Documental (`/reversa-reviewer`) em 2026-10-16  
> Escopo: Auditoria transversal e integral de toda a documentação (Spec SDD vs Forwards vs Docs vs Legado)  
> Diretriz de Classificação: `references/confidence-rules.md`  
> Baseline Git: `3201e6550ee592e1f7d9a9d3d5bef6254a45cb3f`  
> Status: 100% Auditado, Deliberado e Confirmado pelo Operador

---

## 1. Resumo Geral

| Nível | Quantidade | Percentual | Definição Operacional |
|-------|------------|------------|-----------------------|
| 🟢 CONFIRMADO | 564 | 100.00% | Provado em código (`arquivo:linha`), DDL, testes ou formalmente deliberado pelo operador |
| 🟡 INFERIDO   | 0   | 0.00%   | Nenhuma inferência remanescente na documentação |
| 🔴 LACUNA     | 0   | 0.00%   | Nenhuma lacuna ou divergência em aberto |
| **Total**     | **564** | **100.00%** | Total de afirmações substantivas auditadas |

**Confiança geral do projeto:** **100.00%**  
*Cálculo canônico:* `(🟢 + 🟡 * 0.5) / Total * 100` = `(564 + 0 * 0.5) / 564 * 100` = **100.00%**

---

## 2. Inventário por Documento

### 2.1 Especificações Reversa (SDD) — `_reversa_sdd/`

| Documento | 🟢 | 🟡 | 🔴 | Total | Confiança | Status |
|-----------|----|----|----|-------|-----------|--------|
| `_reversa_sdd/prd.md` | 35 | 0 | 0 | 35 | 100.00% | 100% Confirmado pelo operador |
| `_reversa_sdd/sdd/briefing.md` | 63 | 0 | 0 | 63 | 100.00% | 100% Confirmado in-place |
| `_reversa_sdd/addenda/001-modulo-briefing.md` | 25 | 0 | 0 | 25 | 100.00% | 100% Confirmado in-place |
| `_reversa_sdd/traceability/bugs.md` | 12 | 0 | 0 | 12 | 100.00% | 100% Confirmado |
| **Subtotal SDD** | **135** | **0** | **0** | **135** | **100.00%** | |

### 2.2 Ciclo Forward — `_reversa_forward/`

| Documento | 🟢 | 🟡 | 🔴 | Total | Confiança | Status |
|-----------|----|----|----|-------|-----------|--------|
| `001-modulo-briefing/requirements.md` | 32 | 0 | 0 | 32 | 100.00% | 100% Confirmado |
| `001-modulo-briefing/roadmap.md` | 10 | 0 | 0 | 10 | 100.00% | 100% Confirmado |
| `001-modulo-briefing/actions.md` | 38 | 0 | 0 | 38 | 100.00% | 100% Confirmado |
| `001-modulo-briefing/legacy-impact.md` | 16 | 0 | 0 | 16 | 100.00% | 100% Confirmado |
| `001-modulo-briefing/regression-watch.md` | 32 | 0 | 0 | 32 | 100.00% | 100% Confirmado |
| `002-investigacao-personas/requirements.md` | 45 | 0 | 0 | 45 | 100.00% | 100% Confirmado |
| `002-investigacao-personas/roadmap.md` | 30 | 0 | 0 | 30 | 100.00% | 100% Confirmado |
| `002-investigacao-personas/actions.md` | 40 | 0 | 0 | 40 | 100.00% | 100% Confirmado |
| `002-investigacao-personas/legacy-impact.md` | 10 | 0 | 0 | 10 | 100.00% | 100% Confirmado |
| `002-investigacao-personas/regression-watch.md` | 8 | 0 | 0 | 8 | 100.00% | 100% Confirmado |
| **Subtotal Forward** | **261** | **0** | **0** | **261** | **100.00%** | |

### 2.3 Documentos Canônicos e Raiz

| Documento | 🟢 | 🟡 | 🔴 | Total | Confiança | Status |
|-----------|----|----|----|-------|-----------|--------|
| `GOAL.md` | 22 | 0 | 0 | 22 | 100.00% | 100% Confirmado |
| `contracts.md` | 28 | 0 | 0 | 28 | 100.00% | 100% Confirmado (§1 alinhado a Bearer) |
| `workflow.md` | 16 | 0 | 0 | 16 | 100.00% | 100% Confirmado |
| `plan.md` | 26 | 0 | 0 | 26 | 100.00% | 100% Confirmado (Princípio IV emendado) |
| `QA_MATRIX.md` | 10 | 0 | 0 | 10 | 100.00% | 100% Confirmado |
| `AGENTS.md` | 18 | 0 | 0 | 18 | 100.00% | 100% Confirmado (specs reais) |
| **Subtotal Raiz** | **120** | **0** | **0** | **120** | **100.00%** | |

### 2.4 Documentação de Referência de API — `docs/`

| Documento | 🟢 | 🟡 | 🔴 | Total | Confiança | Status |
|-----------|----|----|----|-------|-----------|--------|
| `docs/api/briefing-scout.md` | 20 | 0 | 0 | 20 | 100.00% | 100% Confirmado |
| `docs/api/investigation-personas.md` | 16 | 0 | 0 | 16 | 100.00% | 100% Confirmado |
| `docs/standards/api-docs-standard.md` | 12 | 0 | 0 | 12 | 100.00% | 100% Confirmado |
| **Subtotal Docs API** | **48** | **0** | **0** | **48** | **100.00%** | |

---

## 3. Síntese das Deliberações Confirmadas pelo Operador

1. **Ciclo de Vida do Briefing:**
   - O briefing é interativo e conversacional: operador submete tema -> Scout gera rascunho de 3 a 7 pontos -> operador analisa e responde com direcionamento -> Scout formula nova busca com tema + relatório anterior + feedback, ajusta pontos e auto-aprova diretamente para a investigação.
   - Se o operador aprovar o rascunho inicial direto, não há 2ª busca: é aprovado e avança imediatamente para os workers.
   - Aprovação é definitiva: tentativas de reabertura após aprovação retornam HTTP 409 Conflict.
   - O acionamento de 'Iniciar Investigação' opera aprovação em etapa única.
2. **Autenticação e Acesso Externo:**
   - Chamadas de API aceitam oficialmente tanto `Authorization: Bearer <API_AUTH_SECRET>` quanto `X-API-Key: <API_AUTH_SECRET>`.
   - Sessão administrativa no frontend tem validade de 24 horas.
3. **Execução das Personas Investigadoras:**
   - Cada persona executa até 3 buscas web por ponto com parada voluntária inteligente.
   - Respostas malformadas recebem até 3 tentativas de autocorreção.
   - Timeout máximo de 10 minutos (600s) por agente.
   - Sucesso parcial (>= 1 persona com sucesso no ponto) qualifica o ponto para avanço para a auditoria.
   - Pesquisa inteira só transita para `FAILED` em falha total (100% dos pontos falharem).
   - Ao reiniciar servidor, retoma apenas as personas pendentes de execução.
   - Personas herdam o modelo do Scout (`gemini/gemini-3.8-flash`) caso não haja modelo exclusivo configurado.
4. **Armazenamento e Privacidade:**
   - Prompts brutos e cadeia de raciocínio ficam estritamente em RAM temporária.
   - No banco de dados são persistidos apenas o texto analítico final, 100% das URLs retornadas pela ferramenta de busca em `read_urls` e a versão ativa do briefing (sobrescrevendo rascunhos antigos).
   - Purgar arquivos temporários e rascunhos em disco ao término.
5. **Rede e Auditoria:**
   - Jina Search gerencia segurança de rede e scraping na nuvem; a aplicação é responsável pela ingestão e análise.
   - O agente Auditor avalia as evidências com base estrita no checklist de 12 perguntas de `app/prompts/auditor.md`.
   - Webhooks disparam notificação em `DONE` e `FAILED` caso haja URL configurada.
   - Relatório final é redigido em Markdown completo com citações factuais diretas numeradas.
   - Erros externos são apresentados em mensagens limpas e sanitizadas de até 500 caracteres.
   - Interface com identidade visual dark mode estilo Linear nativo.

---

## 4. Limpeza de Documentação Concluída

* **Removida pasta legada `reversa/` (7 arquivos):** `00-index.md`, `01-nucleo-persistencia.md`, `02-api-ingress.md`, `03-servicos-pipeline.md`, `04-frontend.md`, `05-testes-infra.md`, `ambiguity_log.md`.
* **Removido `TASKS.md`:** Lista morta de tarefas concluídas.
* **Removidos rascunhos e relatórios rejeitados em `_reversa_sdd/` (5 arquivos):** `review-forward-002-core.md`, `review-forward-002-core-validation.md`, `review-prd.md`, `review-sdd-briefing.md`, `review-forward-001-core.md`.
* **Saneado `AGENTS.md`:** Eliminadas referências a arquivos inexistentes.

---

## 5. Revisão Cruzada Independente (OpenCode / Muse Spark 1.3 Free)

- **Engine externa consultada:** OpenCode (`opencode/muse-spark-1.3-contributor-free`)
- **Artefato gerado:** `_reversa_sdd/cross-review-result.md` (16.4 KB, 123 linhas)
- **Apontamentos recebidos:** 2
- **Aceitos:** 2 | **Rejeitados:** 0 | **Pendentes:** 0
- **Síntese da auditoria externa:**
  - *Conformidade do núcleo C1–C7:* 100% aprovado (tema 3–300, pontos 3–7, reopen 409, auth dupla Bearer/X-API-Key, sessão 24h, 3 buscas web por ponto com parada voluntária, 3 autocorreções JSON, timeout 600s, sucesso parcial/FAILED 100%, retomada seletiva pós-restart, herança Scout, títulos sem teto 500 em `sa.Text`, `read_urls` com 100% URLs Jina, sanitização de erros ≤500 chars, proxy Jina opcional).
  - *Deliberações:* As 30 deliberações do operador foram formalmente validadas e transcritas com 100% de fidelidade nas especificações.
  - *Demarcação de Prontidão:* O revisor independente salientou a distinção entre especificações normativas 100% deliberadas e a implementação física das tarefas T036–T040 (Sprint C8), que permanecem abertas em `actions.md` aguardando execução via `/reversa-coding`.
