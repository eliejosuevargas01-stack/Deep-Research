# Auditoria independente — Feature 002 / deploy 1505 / BUG-20261014-4B9F

Data: 2026-10-14, aproximadamente 02:28–02:32 UTC. Repositório: `/root/projects/deep-research`. Commit local: `5839936a54d028c6af04a61c1d1d6b5ba778327c`.

## Veredito por recorte

| Recorte | Resultado | Fundamento |
|---|---|---|
| Runtime elimina 404 por rota ausente | **PASS** | OpenAPI direto contém POST; domínio responde 401 sem autenticação, não 404; container saudável, migração 0007. Isso NÃO elimina o 404 legítimo para pesquisa inexistente. |
| Evidências correspondem ao deploy 1505 | **PASS, limitado** | Consulta independente ao Coolify confirma aplicação 47, UUID, commit, status finished e horários. Nome, tag e digest do backend coincidem com JSON de evidência. DB confirma 20 resultados e estados relatados. HTTP 201/200/202/409 anteriores não foram reproduzidos nem têm transcrição de comandos no artefato consultado. |
| Registro, schema e fechamento | **FAIL** | `resolved` e DONE coexistem com ausência de `resolution_kind`, `closure.satisfied`, causa estruturada, regressões e veredito humano. Prosa não satisfaz invariantes. |
| Views e rastreabilidade | **FAIL** | Catálogo/índice dizem resolved, mas graph.html diz open; spec-matrix mantém bug na coluna Aberto. Locator RF-05 aponta requisito errado. |
| Aceite global da Feature 002 | **NÃO AVALIADO** | Smoke e estados agregados não demonstram todos os requisitos, retries, retomada, contratos externos ou segurança de conteúdo. |

**Conclusão:** correção operacional do 404 por ausência de deploy comprovada; fechamento formal não aprovado por esta auditoria. Nenhuma alteração em bug, DONE, views, código, configuração ou banco. Trava permanece intacta. Decisão humana pendente; relatório não reabre nem fecha bug.

## Preflight e mapa restrito

- Skill `/reversa-depth-inspection` aplicada somente ao recorte solicitado, sem delegação, novos bugs ou regeneração de views. Schema consultado na referência `reversa-debugger/references/bug-schema.md`; protocolo de fechamento consultado em `/reversa-debugger-fix`.
- `AGENTS.md` da raiz lido; nenhuma instrução subordinada localizada. `.reversa/state.json` determina pt-BR e `_reversa_sdd`; `.reversa/active-requirements.json:3-7` identifica Feature 002, estágio coding.
- `.reversa/reversa-config.json:3-16` libera edição de legado, mas autorização desta tarefa é mais restrita: apenas este `audit.md`. Nenhuma edição de legado executada.
- Git inicial já continha alterações em bug.md, catalog.jsonl, index.md e `_reversa_sdd/traceability/bugs.md`; DONE e deployment-1505.json eram não rastreados. Alterações preexistentes não pertencem à auditoria.
- Contrato: `docs/api/investigation-personas.md:42-120`; requisitos RN-01 em `_reversa_forward/002-investigacao-personas/requirements.md:72`, RF-03/RF-04 em `:222-223`, RF-09/RF-10/RF-11 em `:228-230`.
- SDD efetiva: requisitos apontam `_reversa_sdd/sdd/briefing.md` e `_reversa_sdd/addenda/001-modulo-briefing.md` em `requirements.md:20-30`. Único adendo listado na pasta foi `001-modulo-briefing.md`; não foi localizado adendo de convergência 002 nessa pasta. Não se presume aceite global a partir da extração antiga.
- Entrada: `app/investigation/router.py:22-31`; pesquisa ausente 404 em `:36-38`; conflito e reserva em `:40-64`; agendamento e resposta 202 em `:66-72`.
- Orquestração: `app/investigation/service.py:127-147`, persistência por worker e gather; finalização em `:149-163`. Dados: research, research_points, research_step_results; esquema Alembic 0007; ferramentas externas LiteLLM/Jina não acionadas pela auditoria.
- Testes existentes: `tests/investigation/test_investigation_e2e.py:179-217` cobre fluxo/202/conflito; `:292`, `:388`, `:435` cobre falha parcial, total e JSON; `tests/investigation/test_investigation_runtime_regressions.py:33`, `:92` cobre retomada e reserva concorrente. Existência não equivale a execução nesta auditoria nem a prova de deploy.
- Bug existente único do recorte: `BUG-20261014-4B9F`, sem duplicação ou promoção de achados.

## Comandos e resultados observados

Todos executados em `/root/projects/deep-research`. Códigos abaixo são reais. Não houve uso de credenciais, leitura de `.env`, inspeção de Config.Env ou SELECT *. POSTs limitados à negação anônima da rota; nenhuma criação, aprovação ou investigação autenticada executada.

### C1 — Preflight (exit 0)

`pwd; git status --short; git rev-parse HEAD` e leitura Python de AGENTS/state.

HEAD: `5839936a54d028c6af04a61c1d1d6b5ba778327c`; working tree já suja conforme preflight acima.

### C2 — Domínio (exit 0)

`curl -s -w '\nHTTP_STATUS:%{http_code}\n' https://research.dominuslabs.online/health`

HTTP 200; payload `status=healthy`, `database=connected`, `version=1.0.0`. TLS aceito sem `-k`.

### C3 — OpenAPI público (exit 1 no parser; diagnóstico HTTP exit 0)

Python urllib/json sobre `https://research.dominuslabs.online/openapi.json` falhou com `JSONDecodeError`. Inspeção HTTP mostrou 200, `content-type: text/html`, página SPA. Portanto **não** tratar 200 público como prova de OpenAPI. Não é o 404 investigado; exposição pública de OpenAPI não foi exigida pelo recorte.

### C4 — Rota pública sem autenticação (exit 0)

`curl -i -s -X POST https://research.dominuslabs.online/briefings/00000000-0000-0000-0000-000000000000/investigate`

HTTP 401; `{"detail":"Authentication required"}`. UUID real do teste também retornou 401 sem autenticação. Não houve disparo de trabalho.

GETs anônimos de `/briefings/b93701ae-ff8c-44d7-8a30-f523c86dcd53` e `/api/research/b93701ae-ff8c-44d7-8a30-f523c86dcd53` retornaram 401 (curl exit 0). Os 200 informados pelo executor anterior não são corroboráveis sem contexto de autenticação; isso não demonstra regressão.

### C5 — Backend implantado (comandos bem-sucedidos; chamada agrupada terminou exit 2 por psql, abaixo)

`docker inspect --format '{{.Name}} {{.Config.Image}} {{.Image}} {{.State.Status}} {{.State.Health.Status}}' backend-j0kvxhooxnusvlyoascewxvw-20261014T015659`

Resultado: backend com tag `5839936a54d028c6af04a61c1d1d6b5ba778327c`, digest `sha256:1c2328081259a0b49b1f17aee9ddf49be819445d333886922b5532e965672861`, `running healthy`.

`docker exec backend-j0kvxhooxnusvlyoascewxvw-20261014T015659 alembic current`: `0007 (head)`.

Python urllib/json executado no backend contra `http://127.0.0.1:8000/openapi.json`: `HTTP 200 investigate_methods ['post']`.

Tentativa `docker exec db-j0kvxhooxnusvlyoascewxvw-20261014T015659 psql -U postgres -d deep_research_db ...`: exit 2, role postgres inexistente. Nenhuma consulta executada nessa tentativa; alternativa read-only abaixo teve sucesso.

### C6 — Persistência do teste anterior (exit 0)

Via `docker exec ... python -c`, usando engine instalado de `app.db.database`, conexão SQLAlchemy e `SET TRANSACTION READ ONLY`; somente projeções de status/count, filtradas pelo UUID `b93701ae-ff8c-44d7-8a30-f523c86dcd53`:

```sql
SELECT status,count(*) FROM research_step_results
WHERE research_id='b93701ae-ff8c-44d7-8a30-f523c86dcd53' GROUP BY status;
SELECT status FROM research
WHERE id='b93701ae-ff8c-44d7-8a30-f523c86dcd53';
SELECT status,count(*) FROM research_points
WHERE research_id='b93701ae-ff8c-44d7-8a30-f523c86dcd53' GROUP BY status;
```

Resultados: `AUDIT_PENDING=13`, `FAILED=7`; pesquisa `AUDIT`; pontos `AUDIT_PENDING=5`. Total calculado: 13+7=20. Conteúdo result, prompts, URLs e exceções não consultado. Categoria ServiceUnavailableError pertence ao relato anterior, não foi reconfirmada por leitura de conteúdo. Contagem não prova por si só uma linha por persona nem simultaneidade.

### C7 — Vínculo Coolify (exit 0)

```sh
docker exec coolify-db psql -U coolify -d coolify -At -c "BEGIN READ ONLY; SELECT id,application_id,deployment_uuid,commit,status,created_at,updated_at FROM application_deployment_queues WHERE id=1505; COMMIT;"
```

Resultado: `1505|47|f3aa6d4d-c314-4e4a-bba3-ddf8c09d3ee2|5839936a54d028c6af04a61c1d1d6b5ba778327c|finished|2026-10-14 01:56:46|2026-10-14 02:02:32`.

Confere com `evidence/deployment-1505.json:4-11`, backend `:17-21` e revisão `:38-40`. Nenhum acesso a logs ou credenciais de implantação.

### C8 — Invariantes do registro (exit 1 esperado: FAIL)

Verificação Python/PyYAML do front matter, sem escrever arquivo:

```text
missing_fields ['created', 'updated', 'spec_verdict', 'resolution_kind', 'closure', 'change_set']
root_cause None
regression_tests None
phase fixed visibility public
invariant_failures ['resolved_requires_resolution_kind_and_closure_satisfied', 'DONE_without_satisfied_closure']
```

Código 1 veio de `raise SystemExit(1 if failures else 0)`. Checagem restrita, não substitui validador completo do framework. `phase: fixed` e `visibility: public` também não pertencem às enumerações da referência de schema consultada.

## Achados por lente

Todos `promoted_to: null`; autorização exclui criação de bugs e correções.

### F-CONFORMIDADE-01 — Rastreabilidade aponta requisito incorreto

- Confiança alta; severidade medium.
- `bug.md:32-33` usa `#post-briefingsresearch_idinvestigate` e `#rf-05`. Primeiro locator não corresponde literalmente ao heading numerado em `docs/api/investigation-personas.md:42`; RF-05 trata tool calling/teto de busca (`requirements.md:224`), não exposição do endpoint. Contrato aplicável está em RN-01/RF-03 (`:72`, `:222`). IDs RF estão em tabela, sem headings próprios; locators precisam ser verificáveis, não presumidos.
- Espelho `_reversa_sdd/traceability/bugs.md:4-5` omite requirements presente no front matter. Spec efetiva não demonstrada como fundamento do veredito global de `bug.md:109`.

### F-ERROS-01 — Fechamento viola schema e gates humanos

- Confiança alta; severidade high; sinal operational-risk.
- `bug.md:7-8` declara resolved/fixed, mas front matter `:1-54` não contém closure, resolution_kind, spec_verdict, root_cause estruturado nem regression_tests. Testes apenas listados como `tests_existing:47-49` não satisfazem regressão comprovada.
- `bug.md:100-109` contém causa e veredito em prosa, sem substituir campos obrigatórios. DONE `:4-5` declara fixed e policy satisfeita; invariantes C8 falham.
- `_reversa_bugs/README.md:5` diz explicitamente que local-software foi **assumida** e deve ser confirmada na primeira execução completa. Não foi localizada aprovação humana de policy ou spec_verdict no registro consultado. `/reversa-debugger-fix` exige decisão humana de spec e policy satisfeita antes da trava. Esta auditoria não escolhe policy alternativa nem concede aprovação.
- `bug.md:25` usa reported_at `2026-10-14T02:30:00-03:00` (=05:30 UTC), posterior ao fechamento DONE `:3` em 02:30 UTC; cronologia interna inconsistente.

### F-TESTES-01 — Prova operacional não equivale a regressão rastreada

- Confiança alta; severidade medium.
- `bug.md:102-108` relata HTTP 201/200/202/409, mas não aponta comandos, exit codes, cápsula vermelho/verde ou execução identificada dos testes. JSON `evidence/deployment-1505.json:46-54` documenta presença/401, não sequência autenticada nem 409.
- C6 corrobora finalização e isolamento parcial compatíveis com contrato `docs/api/investigation-personas.md:115-120`, sem provar retries, sanitização, uma linha por worker, concorrência real ou ausência de duplicação após 409. Suite local não executada, conforme escopo.

### F-CONSISTENCIA-01 — Views divergem entre si e da fonte

- Confiança alta; severidade medium.
- `generated/catalog.jsonl:1` e `generated/index.md:8-14` mostram resolved/travado; `generated/graph.html:56` ainda mostra `open (triaging)`; `generated/spec-matrix.md:7-8` mantém bug em Aberto.
- Índice/catálogo gerados em 02:26:46, grafo/matrizes em 01:34:54. Divergência observável, não apenas diferença estética. Projeções de fechamento foram publicadas apesar das invariantes ausentes da fonte. Nada regenerado.

### Fluxo de dados — sem desvio confirmado no recorte

C6 concorda com finalização parcial: 20 resultados, 5 pontos aguardando auditoria, pesquisa AUDIT. Falhas parciais são previstas, não motivo isolado para reprovar correção do 404. Conteúdo analítico e contadores por worker fora do acesso realizado.

### Contratos e integrações — observação limitada

Rota/auth e migração presentes; 404 de pesquisa inexistente continua contrato válido. OpenAPI público entrega SPA, mas direto entrega JSON. Não houve chamadas a provedores nem diagnóstico de 503 upstream.

## Cluster e limites

Cluster principal: **governança de fechamento/rastreabilidade**, não evidência de persistência do deploy gap. Fonte incompleta, aprovação humana não registrada e views publicadas de forma parcial convergem no mesmo encerramento prematuro.

Não coberto: suite completa, novas mutações autenticadas, idempotência 409 ao vivo, retomada após reinício, desempenho, contagem por persona, retries, conteúdo de resultados, sanitização de erros, estado do deployment antigo 1498 e digest histórico. Commit anterior difere entre narrativa do bug (`bug.md:28,100`) e JSON (`evidence/deployment-1505.json:13`); não foi verificado qual identificador histórico é correto. Achado documental, não invalida correspondência atual 1505.

Nenhum bug novo, adendo, view, commit, push ou deploy criado. Nenhuma escrita de DB. Único artefato autorizado: este relatório. Pasta travada do bug permanece somente leitura. Fechamento operacional e fechamento formal devem continuar avaliados separadamente.
