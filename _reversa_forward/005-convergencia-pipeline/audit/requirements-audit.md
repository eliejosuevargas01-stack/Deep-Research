# Requirements Audit

> Identificador da feature: `005-convergencia-pipeline`  
> Data: `2026-10-20`  
> Documento auditado: `_reversa_forward/005-convergencia-pipeline/requirements.md`  
> Auditor: Reversa Quality Auditor (Revalidação Editorial Independente, sprint T002)  
> Hash do artefato auditado: `221c62523541417c9fcf78c5c5cc14b55628429dbdca96598d3aaa6058ad1dfe`  

## Resumo

| Métrica | Auditoria Inicial | Revalidação Editorial Delta |
|---------|-------------------|-----------------------------|
| Total de itens avaliados | 22 | 22 |
| Aprovados herdados | — | 19 |
| Revalidados e Aprovados no delta | — | 3 (Q-003, Q-015, Q-016) |
| Total Aprovados | 19 | 22 |
| Reprovados / Ressalvas | 3 | 0 |
| Veredito | Aprovado com ressalvas | **Aprovado** |

## Itens por categoria

### Clareza

- [X] Q-001 | Clareza | Cada frase do requirements possui sujeito, predicado e objeto explícitos, com redação assertiva *(herdado da auditoria inicial)*
- [X] Q-002 | Clareza | Não há sentenças iniciadas por "talvez", "provavelmente" ou "se possível" sem qualificação numérica estrita *(herdado da auditoria inicial)*
- [X] Q-003 | Clareza | Termos e siglas de domínio ("SERP", "SSRF", "AUDIT_CAVEAT") possuem expansão ou definição no primeiro uso *(revalidado [X] na emenda editorial §2)*

### Completude

- [X] Q-004 | Completude | Todas as 11 seções canônicas do documento estão preenchidas com conteúdo substantivo sem placeholders *(herdado da auditoria inicial)*
- [X] Q-005 | Completude | Cada Requisito Funcional (RF-501 a RF-509) possui critério de aceite mensurável e testável *(herdado da auditoria inicial)*
- [X] Q-006 | Completude | Lacunas críticas Q-501 e Q-502 estão formalizadas como premissas de falha segura, sem falsificar resolução humana *(herdado da auditoria inicial)*

### Consistência

- [X] Q-007 | Consistência | Identificadores RN-501 a RN-510 e RF-501 a RF-509 mantêm alinhamento sem desvios entre seções 4, 5 e 7 *(herdado da auditoria inicial)*
- [X] Q-008 | Consistência | Níveis de confidência (🟢 / 🟡 / 🔴) nas tabelas são coerentes com as fontes rastreadas em `_reversa_sdd/` *(herdado da auditoria inicial)*
- [X] Q-009 | Consistência | Manutenção da precedência de briefing síncrono (201/200) e Scout SERP-only sem conflito com background investigation *(herdado da auditoria inicial)*

### Cobertura

- [X] Q-010 | Cobertura | Todos os 9 Requisitos Funcionais (RF-501 a RF-509) são cobertos por cenários Gherkin formais na seção 7 *(herdado da auditoria inicial)*
- [X] Q-011 | Cobertura | Cobertura especificada contempla fluxos normais e casos negativos/limites (409, ausência de busca, barreira incompleta) *(herdado da auditoria inicial)*
- [X] Q-012 | Cobertura | Regras de negócio citam a rastreabilidade original de adendos normativos (§1, §2, §3, §4) e PRD *(herdado da auditoria inicial)*

### EdgeCases

- [X] Q-013 | EdgeCases | Limites operacionais rígidos (10 corpos integrais, 1..3 queries, 4 personas, 4 reprovações) estão quantificados *(herdado da auditoria inicial)*
- [X] Q-014 | EdgeCases | Estados vazios, nulos ou incompletos na barreira de sincronização e na redação recebem tratamento explícito *(herdado da auditoria inicial)*
- [X] Q-015 | EdgeCases | Prazos limite (timeouts) de rede e transporte de personas não estão quantificados em RN-502/RF-502 *(revalidado [X] na emenda editorial §6 com rastreabilidade existente)*

### Jargão

- [X] Q-016 | Jargão | Estados operacionais ("WRITE", "DONE") e entidades legadas ("Evidence") aparecem sem contextualização funcional *(revalidado [X] na emenda editorial §2 com contextualização precisa)*
- [X] Q-017 | Jargão | Conceitos técnicos de engenharia preservam precisão sem uso de metáforas informais *(herdado da auditoria inicial)*

### SoluçãoImplícita

- [X] Q-018 | SoluçãoImplícita | Documento descreve o comportamento funcional e garantias de barreira sem impor código prescritivo *(herdado da auditoria inicial)*
- [X] Q-019 | SoluçãoImplícita | Ausência de acoplamento com bibliotecas, frameworks de agentes ou parsers externos além da stdlib e projeto *(herdado da auditoria inicial)*

### Princípios

- [X] Q-020 | Princípios | Aderência integral ao Princípio I (Rastreabilidade Factual / Verbatim Citation), vedando fatos sem fonte em qualquer formatação *(herdado da auditoria inicial)*
- [X] Q-021 | Princípios | Aderência integral ao Princípio II (Privacidade e Isolamento de Prompts), tratando inputs e fontes raspadas como dados não confiáveis *(herdado da auditoria inicial)*
- [X] Q-022 | Princípios | Aderência aos Princípios III (Degradação Graciosa) e IV (Concorrência Segura e Idempotência com persistência append-only) *(herdado da auditoria inicial)*

---

## Revalidação dos Itens Anteriormente Reprovados e Retratação de Sugestão Inválida

### 1. Revalidação de Q-003 (Clareza / Siglas de Domínio)
- **Situação anterior:** Reprovado. Siglas como `SERP`, `SSRF` e o estado `AUDIT_CAVEAT` eram introduzidas sem expansão formal.
- **Avaliação do Delta (§2):** A emenda incluiu definições explícitas e concisas no início da seção 2:
  - `SERP` (*Search Engine Results Page*): resultados resumidos de busca usados pelo Scout do briefing, sem leitura integral das páginas.
  - `SSRF` (*Server-Side Request Forgery*): requisições induzidas a destinos indevidos, bloqueadas pela proteção outbound.
  - `LLM` (*Large Language Model*): modelo de linguagem que formula queries e análises.
  - `Persona investigativa`, `Rodada` e `Merge` (definido como consolidação persistida das 4 análises válidas da mesma rodada antes da auditoria, e não como novo estado global).
  - Estados `ResearchPoint.status`: `AUDIT_CAVEAT` (ponto conclusivo com ressalvas após o teto de reprovações) e `AUDIT_APPROVED` (ponto conclusivo aprovado).
- **Status:** **APROVADO [X]**.

### 2. Revalidação de Q-015 (EdgeCases / Prazos Limite e Timeouts)
- **Situação anterior:** Reprovado. Retries técnicos eram mencionados, mas sem quantificação dos timeouts de transporte em texto.
- **Avaliação do Delta (§6):** A emenda documentou a referência normativa existente e vinculante para RN-502 no Princípio IV (`.reversa/principles.md:33`) e defaults de código implementados (`app/investigation/llm_binding.py:26`, `app/investigation/tools.py:110` e `app/investigation/worker.py:19`):
  - 90s por chamada LLM/Jina.
  - 600s globais por worker/persona.
  - Até três tentativas técnicas de transporte.
  - Nota de salvaguarda: o texto deixa explícito que essa referência não redefine Scout nem timeout HTTP do briefing, não presume cobertura total de caminhos e não falsifica aprovação humana inexistente.
- **Status:** **APROVADO [X]**.

### 3. Revalidação de Q-016 (Jargão / Estados Operacionais e Entidades Legadas) e Retratação Formal
- **Situação anterior:** Reprovado. Menções a `WRITE`, `DONE` e `Evidence` careciam de semântica no ciclo de vida.
- **Retratação de sugestão antiga:** O relatório inicial sugerira a inclusão de um fluxo simplificado contendo `INVESTIGATING -> MERGED -> AUDITING -> WRITE -> DONE`. O auditor retrata formalmente essa sugestão como **inválida e incorreta**: no modelo do sistema, `MERGED` **não é estado global** de `Research.status`, e sim um artefato persistido por rodada (`investigation_merges`) antes da auditoria do ponto. Propagar essa sugestão teria violado a integridade do domínio.
- **Avaliação do Delta (§2):** A emenda adotou a contextualização conceitual exata sem inventar estados:
  - `Research.status = WRITE`: etapa do Redator, não terminal nem garantia de relatório concluído.
  - `Research.status = DONE`: conclusão terminal com relatório persistido em `content_markdown`.
  - `Evidence`: entidade legada de evidência atribuída a ponto/persona/fonte, cuja mera existência física no banco não prova veracidade por si só (depende de citação verbatim verificada).
  - Referências no código: `app/models/domain_models.py`, `app/audit/domain.py` e `app/services/pipeline/worker.py`.
- **Status:** **APROVADO [X]**.

### 4. Manutenção das Premissas de Falha Segura (Q-501 e Q-502)
- As lacunas operacionais Q-501 (coleta com menos de 10 corpos) e Q-502 (falha/crash em worker individual) continuam formalizadas como falhas seguras explícitas, bloqueando promoção indevida de dados parciais e sem fabricar falsas aprovações humanas.

---

## Veredito

**Aprovado**

Todos os 22 itens avaliados estão plenamente aprovados (22/22). Não restam ressalvas nem pendências textuais ou conceituais impeditivas em `requirements.md`.

---

## Verificações Programáticas e Integridade

### 1. Rastreabilidade dos Snapshots e Hashes

| Arquivo | Hash Snapshot Original (Freeze 8) | Hash Atual (Revalidação 10) | Status |
|---|---|---|---|
| `requirements.md` | `0d97ddb4c34a4f50cb3f997ff2f557774319dbfea8fb87341c1a18f37a043d7a` | `221c62523541417c9fcf78c5c5cc14b55628429dbdca96598d3aaa6058ad1dfe` | Emenda editorial delta autorizada |
| `actions.md` | `ba5c6fc0096c20d17b3d7236880374b3669dfb495293ba032fad1328c468fb86` | `0af14f5db0801f78f2e1d5a71b2f35309adab52abaf7b6ac7688e544810d9cd2` | Alinhamento de notas T031 autorizado |
| `roadmap.md` | `718769ee2e19ada032092345ed9408a8514a23bf6adf4202b16d0112108db986` | `718769ee2e19ada032092345ed9408a8514a23bf6adf4202b16d0112108db986` | 100% Inalterado |
| `investigation.md` | `f9dc6839d5a67aade9728b083c2cd36eaa16afbaeffeaed4164905f961cdc39f` | `f9dc6839d5a67aade9728b083c2cd36eaa16afbaeffeaed4164905f961cdc39f` | 100% Inalterado |
| `questions.md` | `c6c9171af8cea3642b633467a62ee6b4c235b2776a12c0767de1f380999e96ae` | `c6c9171af8cea3642b633467a62ee6b4c235b2776a12c0767de1f380999e96ae` | 100% Inalterado |
| `data-delta.md` | `06f33dfddfc37a337e182d7e6b3c98a50ed6ed4674a8f6593dc547afeb4863a9` | `06f33dfddfc37a337e182d7e6b3c98a50ed6ed4674a8f6593dc547afeb4863a9` | 100% Inalterado |
| `onboarding.md` | `f5042a0e66e723ce81754b22c987fd224a1acacd3952b7ea70206384b6449b48` | `f5042a0e66e723ce81754b22c987fd224a1acacd3952b7ea70206384b6449b48` | 100% Inalterado |
| `interfaces/pipeline-http.md` | `8afd6c66835d78797604b5dee133f01adb390db0c735024df37d15e7361ed904` | `8afd6c66835d78797604b5dee133f01adb390db0c735024df37d15e7361ed904` | 100% Inalterado |

### 2. Comandos e Exit Codes Reais
- `git diff --name-only`: exit code `0` (13 arquivos modificados no baseline preservados intactos).
- `git status --porcelain`: exit code `0` (nenhum arquivo indexado indevidamente).
- `sha256sum`: exit code `0` (conferência exata de todos os hashes do manifesto de revalidação).

### 3. Exclusões Confirmadas
- Nenhuma alteração em arquivos de ambiente (`.env`), segredos ou credenciais.
- Nenhuma conexão com banco de dados de produção ou execução de suites de testes destrutivas.
- Nenhum deploy, instalação de pacotes (`npm`/`pip`) ou comandos de manipulação de histórico git (`git checkout`, `reset`, `clean`, `commit`, `push`, `stash`).
- Preservação estrita dos limites de atuação da auditoria leitora.

---

## Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-10-20 | Auditoria inicial de qualidade textual: veredito 'Aprovado com ressalvas' (19 pass / 3 fail) | Reversa Quality Auditor |
| 2026-10-20 | Revalidação editorial delta T002: aprovação de Q-003, Q-015, Q-016 após emenda de §2 e §6; veredito elevado para 'Aprovado' (22 pass / 0 fail) | Reversa Quality Auditor |

---

## Aviso de Integridade e Próximo Passo

O arquivo `requirements.md` **NÃO** foi modificado durante esta etapa de auditoria.

Com a aprovação total de `requirements.md` (22/22) e a coerência atestada em `cross-check.md`, o próximo passo recomendado é a consolidação do gate em `T003` e prosseguimento para o início de coding em `T004`.

> Digite **CONTINUAR** para prosseguir conforme a sugestão acima.
