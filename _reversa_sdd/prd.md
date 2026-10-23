# PRD: Deep Research

> Selo 🟡 PLANEJADO. Documento gerado a partir de brief, ideation + personas.

**Versão:** 1.0
**Data:** 2026-10-21
**Autor:** reversa-drafter
**Status:** rascunho

---

## 1. Visão geral

🟡 Pipeline simples de pesquisa profunda na internet composto de 4 etapas, cada uma com um endpoint próprio, em Python (FastAPI), monolito modular, cada endpoint funciona por separado.

🟡 Valor entregue: 🟡 pesquisa profunda auditada com rastreabilidade a custo baixo — o usuário passa de dias manuais a um dossiê completo em menos de 10 minutos, com cada ponto aprovado/reprovado e fontes canônicas marcadas.

---

## 2. Problema

🟡 Pesquisas manuais levam dias, fontes não auditadas, relatório sem rastreabilidade; o custo atual é alto.

### Quem sente

🟡 Analistas, redatores, devs e times de research, sempre que precisam produzir uma investigação profunda sob demanda.

🟡 **Analista de Research**: sente no momento da consulta ao briefing de campanha ou início do planejamento estratégico, quando surge a necessidade de embasar uma decisão com dados de terceiros.

🟡 **Redator/Dev integrador**: sente ao desenvolver um produto que depende de pesquisa (relatórios corporativos, blog, conteúdo institucional) ou ao precisar consultar o dossier gerado.

---

## 3. Personas-alvo

> 🟡 Referência completa em [`personas.md`](./personas.md). Resumo das personas de usuário:

- 🟡 **Analista de Research**: profissional de pesquisa de mercado, nível técnico intermediário (análise de dados e triangulação de fontes; conhece métricas de qualidade, mas não escreve código). Dor principal: pesquisas manuais levam dias, fontes não são auditadas e o relatório final perde a rastreabilidade das fontes canônicas. Objetivo: dossier auditado com fontes canônicas, N pontos aprovados, em menos de 10 minutos.
- 🟡 **Redator/Dev integrador**: profissional avançado em integração de APIs e automação; escreve scripts Python e configura variáveis de ambiente. Dor principal: ferramentas existentes (Perplexity, GPT Deep Research) são caixas pretas sem auditoria por ponto nem rastreabilidade de fontes. Objetivo: integrar os 4 endpoints como serviço reusável e consumir o dossier final via webhook ou banco.

### Personas do sistema (7)

🟡 planejador, historiador, visionario, cetico, futurista, auditor, redator final. Número e identidade definidos por variável de ambiente; sem fallback hardcoded.

---

## 4. Métricas de sucesso

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Dossier com fontes canônicas | 🟡 % de pontos com URLs de origem rastreadas | 🟡 100% | 🟡 21/10/2026 |
| 🟡 N pontos aprovados | 🟡 quantidade | 🟡 todos os N pontos definidos por variável de ambiente (padrão 5) com status `aprovado` | 🟡 21/10/2026 |
| 🟡 Tempo < 10 min | 🟡 minutos | 🟡 < 10 (ciclo completo: plano → busca → auditoria → redação) | 🟡 21/10/2026 |

---

## 5. Escopo (in)

- 🟡 Endpoint `/api/v1/plan` (Etapa 1 — Plano de investigação).
- 🟡 Endpoint `/api/v1/search` (Etapa 2 — Busca).
- 🟡 Endpoint `/api/v1/audit` (Etapa 3 — Auditoria).
- 🟡 Endpoint `/api/v1/writer` (Etapa 4 — Redação).
- 🟡 Endpoints administrativos extras permitidos para cadastrar pesquisa e carregar/salvar configuração (chaves, base URLs, preferências).
- 🟡 Persistência SQLite permanente (sobrevive a redeploy sem perder dados).
- 🟡 Tabela de credenciais criptografada com override por variável de ambiente do container.
- 🟡 Base URL de Jina e de LLM configuráveis e persistidas.

---

## 6. Não-objetivos (out)

- 🟡 Não fazer tudo de uma vez só (cada endpoint funciona por separado).
- 🟡 Não complicar a pesquisa.
- 🟡 Não entregar resultado mediano.
- 🟡 Não ter mais de 4 endpoints principais.
- 🟡 Compliance: nenhuma exigência regulatória no MVP (resposta da entrevista).

---

## 7. Requisitos funcionais

### Etapa 1 — Plano de investigação

- 🟡 **RF-001**: `POST /api/v1/plan` recebe tema/entrada → salva no banco → LLM + tool Jina SERP (só lê resultados SERP, nunca abre páginas) → LLM formula query e escolhe N pontos mais relevantes → parser → persiste pontos no banco (`tema`, `id_pesquisa`, `ponto_id`, `ponto_n`).
- 🟡 **RF-002**: N por pesquisa definido em variável de ambiente (padrão 5, sem fallback hardcoded).

### Etapa 2 — Busca

- 🟡 **RF-003**: `POST /api/v1/search` recebe `id_pesquisa` do banco → processa todos os pontos em paralelo por LLM leve → aplica personas (`historiador`, `visionario`, `cectico`, `futurista`) → memória apenas para tool call.
- 🟡 **RF-004**: Tool Jina SERP + Scrapper (`s.jina.ai`) → filtro de URLs já lidas por `id_pesquisa` → parser concatena resposta inteira (sem cortar) em 1 item com links → persiste URLs em background → modelo decide mais query ou devolve resposta → parser (`tema`, `id_pesquisa`, `ponto`, `ponto_id`, `conteudo_coletado`, `urls_lidas`, `urls_fonte`) → banco.

### Etapa 3 — Auditoria

- 🟡 **RF-005**: `POST /api/v1/audit` recebe `id_pesquisa` do banco → LLM forte responde 12 perguntas de qualidade sobre o conteúdo coletado → parser (`id_pesquisa`, `tema`, `id_ponto`, `ponto`, `aprovado|reprovado`, `pontos_fracos`) → banco.

### Etapa 4 — Redação

- 🟡 **RF-006**: `POST /api/v1/writer` recebe `id_pesquisa` do banco (somente quando todos os pontos finalizados) → concatena tudo → LLM forte gera dossier completo com fontes canônicas marcadas → parser → banco → POST para webhook de callback.

### Administração e configuração

- 🟡 **RF-007**: Endpoints administrativos extras para cadastrar pesquisa e carregar/salvar configuração (chaves, base URLs, preferências).
- 🟡 **RF-008**: Toda credencial (chave, base URL, preferência) persistida em tabela criptografada, com override por variável de ambiente do container.

---

## 8. Modelo de dados (tabelas)

- 🟡 **`pesquisa`** — usada pelo endpoint 1 (cadastro) e pelo writer (relatório final). Campos mínimos: 🟡 `id_pesquisa`, `tema`.
- 🟡 **`pontos`** — usada pelo plan (1 item por ponto) e pelo auditor (status). Campos: 🟡 `tema`, `id_pesquisa`, `ponto_id`, `ponto_n`, `ponto`, `aprovado|reprovado`, `pontos_fracos`.
- 🟡 **`conteudo_coletado`** — usada pelo search e pelo auditor. Campos: 🟡 `tema`, `id_pesquisa`, `ponto`, `ponto_id`, `conteudo_coletado`, `urls_lidas`, `urls_fonte`.
- 🟡 **`credenciais`** (tabela criptografada) — 🟡 chave, base URL, preferência; override por variável de ambiente do container.

---

## 9. Variáveis de ambiente

- 🟡 **N pontos por pesquisa** — padrão 5; sem fallback hardcoded (valor ausente exige configuração explícita).
- 🟡 **Personas do sistema** — número (7) e identidade (planejador, historiador, visionario, cetico, futurista, auditor, redator final); sem fallback hardcoded.
- 🟡 **Credenciais e base URLs** — override por variável de ambiente do container sobre a tabela criptografada (chaves, base URL de Jina, base URL de LLM, preferências).

---

## 10. Restrições (técnicas + não-funcionais)

| Tipo | Descrição |
|---|---|
| 🟡 Stack | 🟡 Python + FastAPI, monolito modular, exatamente 4 endpoints principais |
| 🟡 Prazo | 🟡 21 de outubro, 22h (horário de Brasília) |
| 🟡 Compliance | 🟡 Nenhuma exigência regulatória (LGPD ou outra) no MVP |
| 🟡 Orçamento | 🟡 [INDEFINIDO, validar com usuário] |
| 🟡 NFR — Retries | 🟡 1 tentativa inicial + 3 retries |
| 🟡 NFR — Timeout | 🟡 600s por chamada |
| 🟡 NFR — LLM | 🟡 chamadas HTTP a modelos apenas OpenAI-compatible |
| 🟡 NFR — Jina | 🟡 Jina acessado via tool (SERP + Scrapper `s.jina.ai`); base URL configurável e persistida |
| 🟡 NFR — Persistência | 🟡 SQLite permanente (sobrevive a redeploy sem perder dados) |
| 🟡 NFR — Config | 🟡 N e personas definidos exclusivamente por variável de ambiente, sem fallback hardcoded |
| 🟡 NFR — Personas | 🟡 7 personas do sistema: planejador, historiador, visionario, cetico, futurista, auditor, redator final |

---

## 11. Dependências externas

- 🟡 Jina SERP + Scrapper (`s.jina.ai`) — tool nas etapas plan e search.
- 🟡 Modelos LLM OpenAI-compatible — LLM leve (busca em paralelo) e LLM forte (auditoria e redação); base URLs configuráveis e persistidas.
- 🟡 Webhook de callback — destino do POST do dossier final (writer).

---

## 12. Riscos

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 Custo de tokens (Jina SERP + LLM forte estoura orçamento viável) | 🟡 alto | 🟡 média | 🟡 limitar N pontos via variável de ambiente; monitorar consumo por endpoint |
| 🟡 Qualidade da persona (perda de coerência de tom e foco das 7 personas degrada output) | 🟡 alto | 🟡 média | 🟡 definir identidade via variável de ambiente; validar coerência antes da redação |
| 🟡 Complexidade do código (acoplamento entre os 4 endpoints gera bugs em produção) | 🟡 médio | 🟡 média | 🟡 manter monolito modular com endpoints isolados, cada um funcionando por separado |
| 🟡 Falhas em produção (dependência de Jina e LLM OpenAI-compatible) | 🟡 alto | 🟡 alta | 🟡 retries 1+3 e timeout 600s; credenciais com override por env do container |
| 🟡 Orçamento não definido | 🟡 médio | 🟡 média | 🟡 validar com usuário antes do próximo estágio |

---

## 13. Critérios de aceite (alto nível)

- 🟡 **Dado** o Analista de Research envia um tema via `/api/v1/plan`, **Quando** o LLM formula a query e escolhe N pontos (só com resultados SERP), **Então** os pontos são persistidos no banco e o usuário recebe `id_pesquisa` e a lista de pontos para análise.
- 🟡 **Dado** os pontos persistidos, **Quando** o usuário dispara `/api/v1/search`, **Então** os pontos são processados em paralelo por LLM leve com as personas, URLs já lidas são filtradas por `id_pesquisa`, e `conteudo_coletado` + `urls_lidas` + `urls_fonte` são persistidos sem cortar a resposta.
- 🟡 **Dado** conteúdo coletado, **Quando** o usuário executa `/api/v1/audit`, **Então** o LLM forte responde 12 perguntas de qualidade e cada ponto recebe status `aprovado` ou `reprovado` com `pontos_fracos` persistidos.
- 🟡 **Dado** todos os N pontos finalizados, **Quando** o usuário chama `/api/v1/writer`, **Então** o dossier completo com fontes canônicas marcadas é gerado, persistido e enviado via POST ao webhook de callback.
- 🟡 **Dado** o Redator/Dev integrador configura chaves e base URLs via endpoint administrativo, **Quando** o container define variáveis de ambiente de override, **Então** credenciais e N/ personas são carregados sem fallback hardcoded.

---

## Pendências de cobertura

- 🟡 [INDEFINIDO] Orçamento: limite viável de custo de tokens não definido nas fontes — validar com usuário antes de `/reversa-spec-sdd`.

---

Gerado por reversa-drafter em 2026-10-21T22:00:00Z
Fontes: newproject-brief.md, ideation.md, personas.md, state.json (newproject_progress.interview)
