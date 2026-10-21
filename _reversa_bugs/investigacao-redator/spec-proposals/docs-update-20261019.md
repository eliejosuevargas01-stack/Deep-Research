# Relatório de Atualização de Documentação — Sprint DOC-SPEC-02

> Data: 2026-10-19
> Sprint: DOC-SPEC-02
> Contexto: Sincronização de contratos e fluxo com diretrizes explicitamente aprovadas (relato `relato-20261019-2100-doc-worker-jina-sync.md`)

---

## Arquivos Modificados

1. **contracts.md** — Contratos arquiteturais
2. **workflow.md** — Fluxo de arquitetura e execução
3. **README.md** — Documentação principal do projeto
4. **docs/api/briefing-scout.md** — Referência da API de Briefing/Scout

---

## Mudanças Principais

### 1. Briefing Síncrono (Transporte HTTP) — Sem Polling

| Arquivo | Antes | Depois |
|---------|-------|--------|
| contracts.md:88 | `POST /api/research` — sem menção de sincronismo | `POST /api/research` — "Briefing generation is synchronous — the response returns the completed briefing draft directly; no polling required" |
| README.md:31 | "LLM **assíncrono**" | "LLM **síncrona** — 201 retorna snapshot do draft preenchido" |
| README.md:39-62 | cURL com polling até `draft` + `/approve` | cURL síncrono; revisão única via `PATCH {note}` + `/investigate` |
| docs/api/briefing-scout.md:34 | "A geração é **assíncrona**" | "A geração é **síncrona no transporte HTTP** — internamente `async/await` nativo, sem background task, sem polling" |
| docs/api/briefing-scout.md:88 | "Repita até `status` ser `draft`" | Removido — GET apenas para ler snapshot |
| docs/api/briefing-scout.md:103-109 | `POST /approve` com CSRF | `POST /investigate` sem CSRF, aprova implícito + inicia investigação |
| docs/api/briefing-scout.md:212-213 | Nota "síncrona em termos de orquestração" | Nota explícita: transporte síncrono, SERP-only 10 páginas |

### 2. Aprovação Implícita + Revisão Única via Feedback

| Arquivo | Antes | Depois |
|---------|-------|--------|
| contracts.md:113-115 | `/approve` explícito obrigatório | `/investigate` sobre draft = aprovação implícita + início investigação; PATCH `note` = revisão única auto-aprovada |
| workflow.md:35-36 | "Validação / Aprovação Humana — Aprovação única" | Adicionado "Barreira de 4 Personas" na orquestração |
| README.md:56-58 | `/approve` | `/investigate` (aprovação implícita) |
| docs/api/briefing-scout.md:129 | `draft --> approved: POST /approve` | `draft --> approved: POST /investigate` |
| docs/api/briefing-scout.md:246 | "Revisar via Scout — retorna novo rascunho" | "Revisar via briefing único — aprova e inicia investigação automaticamente" |
| docs/api/briefing-scout.md:428 | Endpoint `POST /approve` listado | Substituído por `POST /investigate` |

### 3. Workers: 10 Páginas Integrais + Parser Anti-Boilerplate + Máx 3 Queries

| Arquivo | Antes | Depois |
|---------|-------|--------|
| README.md:101-107 | "5 a 10 páginas por rodada utilizando Jina Reader" | "Jina devolve 10 páginas por query; parser anti-boilerplate remove headers/nav/footers/scripts/ads; corpo integral, não snippets; máx 3 queries por persona/ponto" |
| README.md:108 | — | "Persistência Individual: cada persona salva antes do merge; merge conecta visões mantendo origens/contradições/lacunas" |

### 4. Barreira de 4 Personas + Merge Antes do Auditor

| Arquivo | Antes | Depois |
|---------|-------|--------|
| contracts.md:57 | "Concurrency Ceiling: 20 via Semaphore" | Adicionado: falha isolada por persona não bloqueia demais; 600s timeout global; semaphore mantido |
| workflow.md:127-130 | Apenas paralelismo 20 workers | Adicionado: "Barreira de 4 Personas — cada ponto só avança quando todas 4 devolvem resposta; resultados individuais persistidos antes do merge; merge conecta visões mantendo origens/contradições/lacunas" |

---

## Verificações Documentais (git diff --check + links/termos)

```
$ git diff --check
# Nenhum erro de whitespace introduzido
```

### Links internos validados
- `docs/api/briefing-scout.md` referenciado no README.md ✓
- `docs/standards/api-docs-standard.md` referenciado no briefing-scout.md ✓
- Nenhum link quebrado introduzido

### Termos consistentes
- `research_id` usado consistentemente (não `id`) ✓
- `SCRAPER_IN_PROGRESS` / `SCRAPER` / `AUDIT_PENDING` status alinhados com requirements.md ✓
- `historian`, `skeptic`, `pragmatist`, `futurist` personas fixas ✓
- Jina SERP `https://s.jina.ai/` com JSON `{"q": query}` ✓

---

## Resumo de Conformidade com Diretrizes Aprovadas

| Diretriz (relato) | Implementada na Doc? | Arquivo(s) |
|-------------------|---------------------|------------|
| Worker nunca vazio — sempre aprende das 10 páginas | Sim (README tool architecture) | README.md |
| Jina devolve 10 páginas integrais em texto limpo | Sim (README + briefing-scout) | README.md, briefing-scout.md |
| Parser limpeza obrigatório (boilerplate) | Sim | README.md |
| Máx 3 queries por persona/ponto | Sim | README.md |
| Persistência individual antes do merge | Sim | README.md, workflow.md |
| Barreira 4 personas antes do auditor | Sim | workflow.md, contracts.md |
| Briefing síncrono HTTP 200/201, sem 202/polling | Sim | contracts.md, README.md, briefing-scout.md |
| Async/await interno normal, sem background task | Sim | briefing-scout.md |
| Lifecycle única via feedback, mesma research_id | Sim | README.md, briefing-scout.md |
| Não reintroduzir /approve ou /reopen | Sim | README.md, briefing-scout.md |
| Briefing SERP-only (10 páginas = workers, não briefing) | Sim | briefing-scout.md |
| Preservar schemas/códigos HTTP existentes | Sim | briefing-scout.md (201 creation, 200 revision) |
| APIs externas podem falhar — sem garantia empírica Jina 10 | Não declarado (pendente política) | — |
| Nenhuma nova política omissão Writer plan-v2 | Não introduzida | — |

---

## Itens Pendentes (Fora do Escopo desta Sprint)

- Código/testes/.reversa/estado/ações/DB/prod/secrets/commit/deploy — **não tocados**
- Políticas de fallback/retry Jina <10 resultados — pendente decisão
- Políticas de timeout/modelo/payload/URL — preservados existentes
- Política barreira 1 persona falha (G-NEW-04) — pendente decisão
- Implementação real — verificação pendente (branch sujo não prova produção)

---

## Comandos de Verificação

```bash
# Verificar diff limpo
git diff --check

# Verificar arquivos alterados
git diff --name-only
# contracts.md
# workflow.md
# README.md
# docs/api/briefing-scout.md
# _reversa_bugs/investigacao-redator/spec-proposals/docs-update-20261019.md (novo)
```

---

**Status:** Documentação sincronizada com diretrizes aprovadas. Implementação de código pendente verificação separada.