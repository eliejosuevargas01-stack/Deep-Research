# Requirements Audit

> Feature: `002-investigacao-personas`
> Data: 2026-10-13 — reavaliação independente após reestruturação e reconciliação canônica (Rodada 5)
> Documento: [requirements.md](../requirements.md)
> Escopo: qualidade de escrita. Não constitui codeQA, runtimeQA nem cobertura de testes de implementação.

## Resumo

| Métrica | Valor |
|---|---|
| Itens | 28 |
| PASS | 28 |
| FAIL | 0 |
| CRITICAL | 0 |
| Veredito | Aprovado |
| Cenários Gherkin reais | 23 |
| Requisitos funcionais | 13 (RF-01–RF-13) |
| Regras de negócio | 14 (RN-01–RN-14) |

A reestruturação integral do `requirements.md` e a reconciliação com o template canônico sanaram com sucesso a totalidade das 7 fragilidades textuais apontadas na rodada anterior:

1. **Normalização de limites e fronteira HTTP 422 (Q-028):** a tabela 4.2.3 (`requirements.md:180`) estipula `step_title sa.Text` sem teto de 500 caracteres para títulos gerados pelo Scout, alinhada à decisão Q11 e a `requirements.md:131,169`; a validação do tema do usuário (3–300 caracteres, rejeitando >300 com HTTP 422 explícito) foi incorporada formalmente à especificação de RF-01 (`requirements.md:220`), à subseção 4.1 (`requirements.md:130`) e aos cenários Gherkin (`requirements.md:257-263`).
2. **Completude estrutural do template canônico (Q-004):** o documento incorpora integralmente as 11 seções canônicas: Resumo executivo (`requirements.md:12`), Contexto com legado e tabela de fontes/confidência 🟢 (`requirements.md:18-34`), Personas e cenários de uso com glossário e papéis analíticos (`requirements.md:36-67`), Regras de negócio com badges 🟢 e subseções 4.1–4.4 (`requirements.md:70-213`), Requisitos Funcionais com tabela de prioridade/aceite/confidência (`requirements.md:216-233`), Requisitos Não Funcionais (`requirements.md:236-244`), 23 cenários Gherkin (`requirements.md:247-388`), Prioridade MoSCoW (`requirements.md:392-413`), Esclarecimentos Rodadas 1–3 (`requirements.md:416-436`), Lacunas (`requirements.md:439-446`) e Histórico de alterações (`requirements.md:449-455`).
3. **Discriminação de códigos de falha do Scout no PATCH (Q-005):** a redação de RF-12 (`requirements.md:231`), a descrição do PATCH (`requirements.md:136`) e o cenário Gherkin correspondente (`requirements.md:356-362`) discriminam formalmente HTTP 500 (erro interno/configuração), HTTP 502 (geração de modelo indisponível) e HTTP 503 (busca Jina indisponível), sanando a alternativa indeterminada "500/502" e alinhando com a decisão Q12.
4. **Cenários Gherkin dedicados para todos os RFs (Q-027):** a seção 7 contém 23 cenários Gherkin cobrindo a totalidade dos 13 Requisitos Funcionais, suprindo cenários dedicados para RF-01 (`requirements.md:250-263`), RF-02 (`requirements.md:264-276`), RF-06 (`requirements.md:307-311`) e RF-11 (`requirements.md:338-343`).
5. **Glossário e conceituação de papéis das personas (Q-019):** a subseção 3.2 (`requirements.md:45-53`) conceitua os papéis analíticos e focos cognitivos de cada worker (`historian`, `skeptic`, `pragmatist`, `futurist`); a subseção 3.3 (`requirements.md:54-67`) define explicitamente todas as siglas (UUID, PK, FK, LLM, RAM) e termos conceituais (Tool Calling, Harness, Backfill, Hook de Startup, Append-Only, Verbatim Citation).
6. **Segregação de restrições técnicas (Q-020):** as opções de frameworks e bibliotecas (FastAPI, LiteLLM, asyncio.gather, SQLAlchemy, Jina Search) foram isoladas na subseção dedicada 4.4 "Restrições técnicas aprovadas pelo operador" (`requirements.md:205-213`), desonerando as regras de negócio puras (RN-01 a RN-14) e os requisitos funcionais.
7. **Rastreabilidade factual estrita e citação verbatim (Q-022):** RN-14 (`requirements.md:115-118`) referencia expressamente o Princípio I e estipula a obrigatoriedade de citação factual estrita (*verbatim*, trecho exato reproduzido da fonte original), reforçando que URLs provam apenas acessibilidade, enquanto a citação literal comprova veracidade.

Com zero itens reprovados e zero ocorrências de itens críticos, o veredito emitido é **Aprovado**.

## Fontes, fallback e limites

Raiz: `/root/projects/deep-research`. `.reversa/state.json:6` resolve `_reversa_sdd`; não declara `forward_folder`. `.reversa/active-requirements.json:3-7` resolve a feature ativa `002-investigacao-personas` e etapa `coding`. `AGENTS.md` foi consultado como mapa documental, não certificação de entrega.

Templates locais `.reversa/templates/quality-template.md` e `.reversa/templates/requirements-template.md` ausentes. Fallback utilizado, sem instalação: `/root/.hermes/profiles/orchestrator/skills/software-development/reversa/templates/forward/body/quality-template.md` e `requirements-template.md`. Hooks `.reversa/hooks.yml` e `.reversa/hooks.yaml` ausentes; ganchos `before-quality`/`after-quality` não executados nem criados.

Fontes reversas consultadas: `_reversa_sdd/prd.md`, `_reversa_sdd/sdd/briefing.md` e `_reversa_sdd/addenda/001-modulo-briefing.md`. `_reversa_sdd/architecture.md` e `domain.md` ausentes na árvore reversa: nenhum conteúdo inferido. Princípios ativos consultados em `.reversa/principles.md`. Decisões vigentes Q1–Q13 lidas em `requirements.md:416-436` e `progress.jsonl` (últimos registros). O relatório paralelo `cross-check.md` não foi lido, em respeito estrito ao isolamento de auditorias.

Convenção: referências `requirements.md:L` designam `_reversa_forward/002-investigacao-personas/requirements.md:L`. Referências `.reversa/principles.md:L` são relativas à raiz. Categorias seguem a nomenclatura canônica do template: Clareza, Completude, Consistência, Cobertura, EdgeCases, Jargão, SoluçãoImplícita e Princípios.

## Itens por categoria

### Clareza

- [X] Q-001 | Clareza | A carga e os parâmetros de cada worker são inequívocos?
  > evidência: requirements.md:14,79,223 define N × 4 e tupla `(research_id, step_id, step_title, persona)`.
- [X] Q-002 | Clareza | Parada voluntária e teto de buscas têm comportamento objetivo?
  > evidência: requirements.md:89,224,290-306 define até 3 buscas por worker, parada voluntária, bloqueio na 4ª e retries técnicos sem desconto.
- [X] Q-003 | Clareza | O conteúdo de result e erros sanitizados está delimitado?
  > evidência: requirements.md:112,181,240 define síntese analítica não-vazia, erro sanitizado máx 500 caracteres.
- [X] Q-025 | Clareza | Tentativas totais e retries técnicos designam um único limite?
  > evidência: requirements.md:92,112,227,421 converge em 3 tentativas totais (1 inicial + até 2 retries técnicos com backoff exponencial 2s/4s); correções JSON com orçamento separado de até 3 tentativas.
- [X] Q-028 | Clareza | A fronteira de validação HTTP 422 do tema e a aceitação sem teto de títulos gerados estão normalizadas no corpo normativo?
  > evidência: requirements.md:130-131,169,180,220-221,257-263,271-276,433,435. Tabela 4.2.3 padronizada com `sa.Text` sem limite de 500 para títulos gerados pelo Scout (Q11); validação de tema 3–300 com HTTP 422 explícito normatizada em RF-01, 4.1 e cenários Gherkin (Q13).

### Completude

- [X] Q-004 | Completude | Todas as seções obrigatórias do template canônico estão preenchidas?
  > evidência: requirements.md:12-455. Todas as 11 seções presentes (Resumo executivo, Contexto com legado, Personas e cenários com papéis e glossário, Regras de negócio com badges 🟢 e subseções 4.1–4.4, Requisitos Funcionais, Requisitos Não Funcionais, Critérios Gherkin, Prioridade MoSCoW, Esclarecimentos, Lacunas e Histórico de alterações).
- [X] Q-005 | Completude | O tratamento de falha do Scout no PATCH tem resposta HTTP unívoca e discriminada por causa?
  > evidência: requirements.md:136,231,356-362,434. Discrimina HTTP 500 (configuração interna), HTTP 502 (modelo indisponível) e HTTP 503 (busca Jina indisponível) em RN, RF-12 e cenário Gherkin conforme Q12.
- [X] Q-006 | Completude | Sucesso parcial e falha total têm desfechos especificados?
  > evidência: requirements.md:148,151,200-203,229,326-337 define avanço para AUDIT quando >=1 ponto tem sucesso e FAILED quando 100% dos pontos falham.
- [X] Q-007 | Completude | Migração e backfill têm escopo textual definido?
  > evidência: requirements.md:153-165,168-170,180,230,338-343 define migração do enum de status, eliminação de SEARCH_SUCCESS para AUDIT_PENDING, ampliação para sa.Text e backfill de briefings órfãos.
- [X] Q-027 | Completude | Todos os RF têm critérios de aceite identificáveis nos cenários Gherkin?
  > evidência: requirements.md:218-232,249-388. Total de 23 cenários Gherkin cobrindo a totalidade dos 13 requisitos funcionais (incluindo RF-01, RF-02, RF-06 e RF-11 dedicados).

### Consistência

- [X] Q-008 | Consistência | O estado pós-aprovação é uniforme?
  > evidência: requirements.md:72,124,132,159,196,221,268,278,419 define pesquisa em SCRAPER e pontos em SCRAPER_PENDING aguardando /investigate.
- [X] Q-009 | Consistência | Identificador público e paths usam research_id?
  > evidência: requirements.md:42,72,119-128,130,132,134,178,220-223,231,253-255,266,280,346,351,370,374,379 usa universalmente research_id e extingue id legado.
- [X] Q-010 | Consistência | Ponto, persona e worker mantêm significado estável?
  > evidência: requirements.md:14,45-53,79,178-184 define ponto investigado (step_id), persona cognitiva e worker assíncrono (N × 4).
- [X] Q-011 | Consistência | Os estados de ponto usados pertencem ao conjunto declarado?
  > evidência: requirements.md:168,198-203,229,329,335 usa SCRAPER_* e AUDIT_PENDING; SEARCH_SUCCESS expurgado formalmente.

### Cobertura

- [X] Q-012 | Cobertura | Fluxos centrais de investigação possuem Gherkin positivo e negativo?
  > evidência: requirements.md:277-306,312-318 cobre disparo 202, conflito 409, parada voluntária, cota de buscas, retry de rede e persistência de URLs.
- [X] Q-013 | Cobertura | Falha isolada, sucesso parcial e falha total aparecem em Gherkin?
  > evidência: requirements.md:319-337 cobre isolamento de falha de worker, avanço para AUDIT com >=1 sucesso e transição para FAILED em 100% de falha.
- [X] Q-014 | Cobertura | Mudanças de reopen e PATCH da 001 aparecem em Gherkin?
  > evidência: requirements.md:344-362 cobre reopen 409, PATCH 200 por feedback e falha terminal do Scout discriminada (500/502/503).
- [X] Q-015 | Cobertura | Retomada após reinício possui cenário?
  > evidência: requirements.md:363-368 cobre hook de startup do FastAPI reagendando apenas personas sem linha gravada em research_step_results.
- [X] Q-026 | Cobertura | Erros de acesso, ID, zero pontos e exaustão JSON possuem cenários próprios?
  > evidência: requirements.md:369-388 cobre 404 para pesquisa inexistente, 401/403 para não-admin, 409 para pesquisa sem pontos e FAILED por exaustão de correções JSON.

### EdgeCases

- [X] Q-016 | EdgeCases | Timeouts têm limites concretos?
  > evidência: requirements.md:92,225,240,321 define 90s LLM, 90s Jina e 600s global por worker.
- [X] Q-017 | EdgeCases | Tipos, vazios e exaustão de reparos JSON estão definidos?
  > evidência: requirements.md:112,227,382-388 exige result string não-vazia e used_urls array de strings; após 3 correções sem sucesso, grava FAILED com literal de erro e used_urls=[].
- [X] Q-018 | EdgeCases | Zero pontos, ID inexistente e acesso negado têm desfechos definidos?
  > evidência: requirements.md:72,369-381 define 409, 404 e 401/403 respectivamente.
- [X] Q-023 | EdgeCases | attempt_count possui inicialização e incremento idempotente na retomada?
  > evidência: requirements.md:170,199,323,387,428 define 0 inicial, +1 por falha definitiva e despacho na retomada restrito a personas sem linha no banco.
- [X] Q-024 | EdgeCases | Disparo concorrente exige validação/transição atômicas?
  > evidência: requirements.md:72,222,285-289 exige validação de SCRAPER_PENDING e bloqueio 409 atômico antes do despacho em background.

### Jargão

- [X] Q-019 | Jargão | Termos técnicos, papéis das personas e siglas são explicados para novo integrante?
  > evidência: requirements.md:45-53,54-67. Seção 3.2 define os papéis cognitivos e focos de historian, skeptic, pragmatist, futurist. Seção 3.3 traz glossário com expansão de UUID, PK, FK, LLM, RAM, Tool Calling, Harness, Backfill, Hook de Startup, Append-Only e Verbatim Citation.

### SoluçãoImplícita

- [X] Q-020 | SoluçãoImplícita | O texto distingue comportamento, contrato externo e prescrições técnicas de implementação?
  > evidência: requirements.md:205-213. Seção 4.4 agrupa formalmente restrições técnicas aprovadas pelo operador (FastAPI, LiteLLM, asyncio.gather, SQLAlchemy, Jina Search), desonerando o corpo normativo de RNs e RFs que tratam do comportamento observável.

### Princípios

- [X] Q-021 | Princípios | Concorrência irrestrita está respaldada pela emenda ao Princípio IV?
  > evidência: .reversa/principles.md:30-33; requirements.md:30,75,210,243 autoriza explicitamente asyncio.gather concorrente irrestrito amparado na Emenda da Feature 002.
- [X] Q-022 | Princípios | O requisito de citação factual remete com precisão ao Princípio I (Verbatim Citation)?
  > evidência: .reversa/principles.md:9-12; requirements.md:27,66,115,242. RN-14 explicita a obrigação de citação factual estrita (*verbatim*, trecho exato reproduzido da fonte original conforme o Princípio I), reforçando que links comprovam apenas acessibilidade e a citação literal comprova veracidade.

## Itens reprovados, detalhe

Nenhum item reprovado nesta rodada de auditoria.

## Veredito

**Aprovado**

Regra aplicada: zero FAIL = Aprovado; 1–3 FAIL sem CRITICAL = Aprovado com ressalvas; mais de 3 FAIL ou qualquer CRITICAL = Reprovado.
Resultado consolidado da Rodada 5: 28 itens avaliados, 28 PASS, 0 FAIL, 0 CRITICAL. Veredito final: **Aprovado**.

## Histórico de alterações e proveniência

| Data | Registro | Proveniência |
|---|---|---|
| 2026-10-13, antes de Q1–Q10 consolidadas | Rodada 3 anterior: **Reprovado**, 26 itens, 17 PASS, 9 FAIL, 1 CRITICAL (Q-025). | Relatório anterior lido integralmente antes do rewrite; SHA-256 `75e93a2bda69dbf23d42da0d9fadef627004b2bf5fadd8b0a360bf255d9037e1`; requirements então `2e9ca7cbb28774332b129c73f804b68c038ce131ccf723570e61bb83091cd64b`. |
| 2026-10-13, após Q1–Q10 | Reavaliação independente Rodada 3: **Reprovado 21/28** (28 itens, 21 PASS, 7 FAIL, 0 CRITICAL). | Requirements então `13e33e00bd9d1bc75e09018f4eb7d9c76f652ec67b21c12ee766efcb32d71302`. Veredito 'Reprovado 21/28' preservado como histórico não vigente. |
| 2026-10-13, após Rodada 3 (Q11–Q13) | Reavaliação independente Rodada 4: **Reprovado**, 28 itens, 21 PASS, 7 FAIL, 0 CRITICAL. | Requirements `4b763da07cbc6bb4ea6c5c50e7b6f952c6360be0bb71fbeebfdd811aa3b41196`. IDs Q-001–Q-028 preservados por tema. |
| 2026-10-13, após reestruturação canônica | Reavaliação independente Rodada 5: **Aprovado**, 28 itens, 28 PASS, 0 FAIL, 0 CRITICAL. | Requirements vigente `098ddccd3a784436b8b944c89ebc969a90f9da2b71062bc04b5b0ada0352fbfb`. Totalidade das 7 reprovações sanada por alinhamento estrutural e normativo. |

Os vereditos anteriores **Reprovado** ficam expressamente preservados como registros históricos não vigentes. As deliberações Q11–Q13 foram plenamente harmonizadas no corpo normativo, nas regras de validação, na tabela de persistência e nos cenários Gherkin.

## Integridade e checks

Freeze baseline: `/root/.hermes/profiles/orchestrator/cache/scratch/feature002-round5-audit-baseline.json` (179 hashes).
Exclusões autorizadas: estritamente `audit/requirements-audit.md` e `audit/cross-check.md`. Comparação de baseline confirmou 177 entradas restantes com 0 diferenças (exit 0).

| Entrada | SHA-256 no baseline e na auditoria |
|---|---|
| requirements.md | `098ddccd3a784436b8b944c89ebc969a90f9da2b71062bc04b5b0ada0352fbfb` |
| .reversa/principles.md | `7f4080d07654e4bfacc79d0ec0ce5a8947751fe48aad9aa6efadd00114472da4` |

Checks estruturais mecânicos executados com Python stdlib:
- 28 itens Q-NNN avaliados; 28 IDs únicos (Q-001–Q-028);
- 28 PASS (`[X]`), 0 FAIL (`[ ]`), 0 CRITICAL; veredito Aprovado coerente com as regras;
- 8 categorias com contagens entre 1 e 5 (Clareza: 5, Completude: 5, Consistência: 4, Cobertura: 5, EdgeCases: 5, Jargão: 1, SoluçãoImplícita: 1, Princípios: 2);
- Zero itens reprovados; nenhuma inconsistência residual;
- Fences de código e tabelas Markdown íntegras; links locais validados;
- Conformidade com requisitos: 13 RFs, 14 RNs, 23 cenários Gherkin contabilizados.

**requirements.md NÃO foi modificado.** Escrita realizada exclusivamente no arquivo de auditoria `_reversa_forward/002-investigacao-personas/audit/requirements-audit.md`.

## Próximo passo

Avançar para a fase de planejamento `/reversa-plan`.

> Digite **CONTINUAR** para prosseguir conforme a sugestão acima.
