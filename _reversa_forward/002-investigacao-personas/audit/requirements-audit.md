# Requirements Audit

> Identificador da feature: `002-investigacao-personas`  
> Data: `2026-10-12` (Rodada 2 — Pós-Saneamento)  
> Documento auditado: `_reversa_forward/002-investigacao-personas/requirements.md`  
> Escopo: clareza textual, completude, consistência e alinhamento com princípios. Não avalia código nem testes de implementação.

---

## 1. Resumo Executivo

| Métrica | Valor |
|---------|-------|
| Total de itens avaliados | 22 |
| Aprovados | 22 |
| Reprovados | 0 |
| Achados CRITICAL | 0 |
| Achados HIGH | 0 |
| Achados MEDIUM | 0 |
| Achados LOW | 0 |
| **Veredito** | **Aprovado** (Apto para plano técnico) |

A segunda rodada de auditoria de clareza textual do `requirements.md` da Feature 002 confirmou o saneamento completo e rigoroso de todos os 14 apontamentos levantados na Rodada 1. As contradições de ciclo de vida (`SCRAPER` vs `PENDING`) foram eliminadas, a tupla de despacho dos workers foi formalizada, a máquina de estados cobre cenários de falha parcial e total, a Seção 8 foi expandida com 13 cenários Gherkin cobrindo a totalidade dos fluxos operacionais e impactos da Feature 001, e a emenda ao Princípio IV de concorrência foi devidamente chancelada em `.reversa/principles.md`. O documento está claro, inequívoco, consistente e apto a subsidiar a elaboração do plano técnico (`plan.md`).

### Matriz de Resolução dos Achados da Rodada 1

| ID Rodada 1 | Severidade | Assunto | Status Rodada 2 | Evidência no `requirements.md` |
|---|---|---|---|---|
| **CRIT-01** | CRITICAL | Status pós-aprovação e migração (`SCRAPER` vs `PENDING`) | **Resolvido** | Linhas 23, 30, 47, 59, 64, 97 e 110 padronizam status pós-aprovação em `SCRAPER`. |
| **CRIT-02** | CRITICAL | Carga de parâmetros pelo worker | **Resolvido** | Linhas 14, 112 (RN-03) e RF-04 fixam tupla `(research_id, step_id, step_title, persona)`. |
| **CRIT-03** | CRITICAL | Contradição entre RN-01 e Gherkin de re-disparo | **Resolvido** | Linha 110 e Linha 168 exigem `SCRAPER_PENDING` e rejeitam 409 quando já em `SCRAPER_IN_PROGRESS`. |
| **CRIT-04** | CRITICAL | Violação do Princípio IV de concorrência | **Resolvido** | Princípio IV formalmente emendado em `.reversa/principles.md` e referenciado em RN-02 e Linha 152. |
| **HIGH-01** | HIGH | Omissão de comportamento em falha do PATCH por feedback | **Resolvido** | Linha 34, Linha 96 e Linhas 227-233 especificam transição para `FAILED` e HTTP 500/502. |
| **HIGH-02** | HIGH | Rotina e cenário para falha de 100% dos passos | **Resolvido** | Linha 51, Linha 104 e Linhas 209-214 detalham transição atômica para `FAILED` pós-gather. |
| **HIGH-03** | HIGH | Estado fantasma `SEARCH_SUCCESS` em `research_points` | **Resolvido** | Linha 68 e RF-11 expurgam formalmente `SEARCH_SUCCESS` do enum e migram legados. |
| **HIGH-04** | HIGH | Inconsistência de IDs nos endpoints da API | **Resolvido** | Linha 26, Linhas 30-34, Seção 4, Seção 5 e Seção 8 padronizam `{research_id}`. |
| **HIGH-05** | HIGH | Lacuna de critérios de aceitação Gherkin | **Resolvido** | Seção 8 expandida com 13 cenários cobrindo retries, cotas, falhas, reopen e PATCH. |
| **MED-01** | MEDIUM | Tipo e regras de sanitização em `result` | **Resolvido** | Linhas 80 e 149 definem tipo `sa.Text` e sanitização estrita com teto de 500 caracteres. |
| **MED-02** | MEDIUM | Timeout global por worker | **Resolvido** | Linha 116 (RN-07) estipula timeout global por worker fixado em 600s. |
| **MED-03** | MEDIUM | Inconsistência terminológica "ponto" vs "passo" | **Resolvido** | Terminologia unificada: "ponto" para entidade de briefing e "passo" para execução. |
| **LOW-01** | LOW | Afirmação de "Zero pontos abertos" | **Resolvido** | Seção 9 e cabeçalho devidamente justificados com todas as deliberações concluídas. |
| **LOW-02** | LOW | Prescrição de código interno em regras | **Resolvido** | Regras focadas em contratos funcionais e arquitetura de integração. |

---

## 2. Avaliação por Categorias (Checklist Q-NNN)

### 2.1 Clareza

- [X] Q-001 | Clareza | A identificação e atribuição de carga de trabalho para cada worker é unívoca e parametrizada?
  > Evidência: Linha 14, Linha 112 (RN-03) e RF-04 especificam expressamente que o despachante assíncrono repassa a tupla `(research_id, step_id, step_title, persona)` para cada worker.

- [X] Q-002 | Clareza | O critério de parada autônoma e o limite de tool calling da ferramenta de busca estão delimitados objetivamente?
  > Evidência: Linha 14, Linha 115 (RN-06) e o cenário Gherkin (Linha 179) definem o teto de 3 buscas por ponto, a possibilidade de retorno voluntário prévio com o JSON analítico, e a recusa do harness em executar a 4ª busca.

- [X] Q-003 | Clareza | A tipagem do campo `result` e as regras de sanitização de mensagens de erro em caso de falha estão claras e inequívocas?
  > Evidência: Linha 80 anota o tipo relacional como `sa.Text`, e Linha 149 explicita a sanitização prévia obrigatória (proibindo chaves de API, tokens e stack traces) com truncamento máximo a 500 caracteres.

### 2.2 Completude

- [X] Q-004 | Completude | Todas as seções canônicas de especificação de requisitos estão presentes e detalhadas sem lacunas?
  > Evidência: O documento possui todas as 9 seções obrigatórias: Resumo, Identificador único research_id (com impactos na 001), Modelo de dados, Máquina de estados consolidada, Regras de negócio, Requisitos funcionais, Requisitos não funcionais, Critérios de aceitação Gherkin e Pontos abertos.

- [X] Q-005 | Completude | O comportamento e o tratamento de falha do Scout no endpoint `PATCH /briefings/{research_id}` estão especificados?
  > Evidência: Linha 34, Linha 96 e Linhas 227-233 determinam que falha irrecuperável do Scout durante o PATCH transita a pesquisa para `FAILED`, o briefing para `failed` e retorna HTTP 500/502.

- [X] Q-006 | Completude | As regras de transição terminal para a pesquisa em cenários de sucesso parcial/total e falha global de 100% dos pontos estão especificadas?
  > Evidência: Linhas 101-104 e cenários Gherkin (Linhas 203-214) estipulam que o término do gather leva a pesquisa a `AUDIT` se pelo menos 1 ponto obtiver sucesso analítico, ou atomicamente a `FAILED` se 100% dos pontos resultarem em falha.

- [X] Q-007 | Completude | O escopo da migração Alembic e as regras de unificação de schema e backfill de dados legados estão definidos?
  > Evidência: Linhas 53-65 e RF-11 especificam a migração 0007, criação da tabela `research_step_results`, mapeamento de enums legados, criação de registros órfãos em `research` e cópia de pontos aprovados em `research_points`.

### 2.3 Consistência

- [X] Q-008 | Consistência | O status da pesquisa pós-aprovação de briefing é uniforme entre ciclo de vida, tabela de migração, máquina de estados e regras?
  > Evidência: Linhas 23, 30, 47, 59, 64, 97 e 110 são unânimes: a aprovação do briefing coloca imediatamente `research.status` em `SCRAPER` e os pontos em `SCRAPER_PENDING`.

- [X] Q-009 | Consistência | Os identificadores de path dos endpoints da API seguem a convenção canônica `{research_id}` sem variação?
  > Evidência: Linha 26 estabelece a convenção canônica e todas as rotas ao longo das Seções 2, 4, 5, 6 e 8 utilizam estritamente o parâmetro `{research_id}` (`/briefings/{research_id}/approve`, `/briefings/{research_id}/reopen`, `/briefings/{research_id}`, `/briefings/{research_id}/investigate`).

- [X] Q-010 | Consistência | Os termos de domínio ("ponto", "passo", "worker", "persona") são empregados com significado uniforme e alinhados ao schema?
  > Evidência: A terminologia separa consistentemente a entidade de negócio/briefing ("ponto", refletido em `research_points`) da etapa de execução investigativa ("passo", refletido em `step_id`/`step_title`), assim como "persona" (papel cognitivo) de "worker" (corrotina executora).

- [X] Q-011 | Consistência | O conjunto de status de `research_points` no modelo de dados corresponde exatamente aos estados operados e documentados?
  > Evidência: Linha 68 e RF-11 removem o status legado `SEARCH_SUCCESS` do enum e documentam estritamente os estados canônicos de ciclo de vida (`SCRAPER_*`, `AUDIT_*`, `WRITE_*`).

### 2.4 Cobertura de cenários

- [X] Q-012 | Cobertura de cenários | Os fluxos operacionais principais de investigação (disparo, re-disparo concorrente, parada voluntária, bloqueio por cota, retries e persistência) possuem cenários Gherkin?
  > Evidência: Linhas 159-195 detalham cenários para disparo HTTP 202, rejeição HTTP 409 em re-disparo, parada voluntária antecipada, recusa de 4ª busca, retry técnico sem consumo de cota e gravação de `read_urls` vs `used_urls`.

- [X] Q-013 | Cobertura de cenários | As regras de resiliência, tolerância a falhas parciais e falha terminal global (100% dos pontos) estão cobertas em Gherkin?
  > Evidência: Linhas 196-214 cobrem falha isolada de worker com incremento de `attempt_count`, sucesso global e avanço para `AUDIT`, e falha global de 100% dos pontos encerrando a pesquisa em `FAILED`.

- [X] Q-014 | Cobertura de cenários | As quebras de contrato e ajustes na Feature 001 (reopen bloqueado, PATCH por feedback e falha do PATCH) estão especificadas em Gherkin?
  > Evidência: Linhas 215-233 apresentam cenários completos para rejeição de reabertura pós-aprovação (HTTP 409), reprocessamento síncrono por feedback textual (HTTP 200) e falha do Scout durante o PATCH (HTTP 500/502 e `FAILED`).

- [X] Q-015 | Cobertura de cenários | O cenário de recuperação e retomada após reinício do servidor está explicitado em Gherkin?
  > Evidência: Linhas 234-239 descrevem o cenário de inicialização do FastAPI inspecionando pontos em `SCRAPER_IN_PROGRESS` e reagendando exclusivamente as personas incompletas.

### 2.5 Edge cases

- [X] Q-016 | Edge cases | Os limites de tempo (timeouts individuais e timeout global do worker) estão fixados com precisão numérica?
  > Evidência: Linha 116 (RN-07) estipula limites explícitos: 90s por chamada LLM, 90s por requisição Jina, e timeout global limite de 600s por worker completo.

- [X] Q-017 | Edge cases | Os limites de tamanho, formato de payload e truncamento de erros de execução estão formalmente definidos?
  > Evidência: Linha 34 limita notas de feedback entre 3 e 4000 caracteres; Linha 122 define até 3 correções dedicadas de JSON; Linha 149 fixa teto de 500 caracteres para gravação de mensagens de erro sanitizadas.

- [X] Q-018 | Edge cases | A concorrência e o bloqueio de múltiplos disparos de investigação estão protegidos contra condições de corrida?
  > Evidência: Linha 110 (RN-01) exige atomicidade na validação e atualização: `research.status == 'SCRAPER'` e pontos em `SCRAPER_PENDING`, transitando atomicamente para `SCRAPER_IN_PROGRESS` e bloqueando disparos concorrentes com HTTP 409.

### 2.6 Ausência de jargão

- [X] Q-019 | Ausência de jargão | Os termos técnicos, papéis cognitivos e integrações externas estão suficientemente contextualizados?
  > Evidência: Seções 1, 3 e 5 contextualizam detalhadamente as 4 personas analíticas (**historian**, **skeptic**, **pragmatist**, **futurist**), o formato de tool calling e o scraping limpo retornado pela Jina.

### 2.7 Ausência de solução implícita

- [X] Q-020 | Ausência de solução implícita | O documento preserva o foco em regras de negócio, contratos externos e schemas, sem acoplamento acidental a implementações transitórias?
  > Evidência: A especificação é centrada em contratos HTTP, transições de estado relacionais, limites operacionais mensuráveis e critérios de aceitação testáveis.

### 2.8 Alinhamento com princípios

- [X] Q-021 | Alinhamento com princípios | O requisito de concorrência irrestrita está plenamente respaldado por emenda formal ao Princípio IV em `.reversa/principles.md`?
  > Evidência: O arquivo `.reversa/principles.md` contém a emenda formal ao Princípio IV autorizando concorrência paralela irrestrita para a Feature 002 sob salvaguardas de timeout (600s), retries (3) e persistência append-only, referenciada na RN-02 e Linha 152.

- [X] Q-022 | Alinhamento com princípios | A rastreabilidade factual (Princípio I) e o isolamento de privacidade e segredos (Princípio II) estão garantidos?
  > Evidência: A RN-08 e RN-14 garantem gravação integral de `read_urls`, citação factual em `used_urls`, descarte de histórico bruto de mensagens em RAM (RN-04) e vedação explícita de segredos e chaves em logs e banco de dados (Seção 7).

---

## 3. Veredito Final

- **Classificação:** **Aprovado** (Apto para plano técnico).
- **Justificativa:** Todos os 22 itens avaliados cumpriram integralmente os critérios de clareza textual, completude, consistência relacional, cobertura Gherkin e alinhamento com os princípios arquiteturais do projeto. Nenhum achado restou pendente.

> **Aviso explícito:** O arquivo `requirements.md` **NÃO** foi modificado nesta etapa de auditoria. Nenhuma alteração foi realizada em código, testes, banco de dados ou configurações.

---

## 4. Sugestão de Próximo Passo

Conforme o fluxo do framework Reversa:
1. Avançar para a elaboração do plano técnico de arquitetura e implementação executando `/reversa-plan`.

> Digite **CONTINUAR** para prosseguir conforme a sugestão acima.
