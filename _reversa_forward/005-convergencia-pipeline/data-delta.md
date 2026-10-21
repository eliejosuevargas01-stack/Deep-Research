# Delta de dados — PLAN-005-B

> 🟡 Desenho proposto, não implementado nem aprovado. Autoridade: requirements e roadmap §4 reconciliados. Nenhum dado histórico alterado nesta etapa documental.

## 1. Base observada e precedência

🟢 `app/models/domain_models.py` define `ResearchPoint`, `ResearchStepResult`, `Evidence`, `Report` e `AuditTrail`. `research_step_results` ainda não tem rodada. Grafo Alembic inspecionado estaticamente: `0001` até `0007`, head `0007`, parent `0006`, arquivo `alembic/versions/0007_investigation_step_results_and_status.py`. `attempt_count` já existe antes de 0007; não confundir identidade da rodada com contador de auditorias. Próxima revisão será resolvida no coding após consultar novamente grafo, sem reservar ID agora.

## 2. Alterações propostas

| Alvo | Delta proposto | Histórico e escrita nova |
|---|---|---|
| `research_points.investigation_round` | INTEGER nullable; CHECK `investigation_round IS NULL OR investigation_round > 0` | Sem backfill e sem server/default retroativo; nova execução recebe 1 explicitamente pelo serviço |
| `research_step_results.round` | INTEGER nullable; CHECK `round IS NULL OR round > 0` | NULL histórico consultável mas inelegível para nova barreira; nova linha exige inteiro positivo na fronteira de gravação |
| `research_step_results` | UNIQUE `(research_id, step_id, round, worker)` | Sem reescrever/deduplicar histórico; NULL mantém semântica SQL de unicidade distinta, sem NULLS NOT DISTINCT |
| `research_step_results.result` | Preservar coluna Text; novo conteúdo estruturado serializado | Sem converter texto histórico automaticamente; análise, aprendizados, citações, contradições e lacunas preservados |
| `research_step_results.used_urls/read_urls/status/worker/step_title` | Preservar colunas existentes | Worker real e resultado válido; erro técnico não é análise nem reprovação |
| `investigation_merges` | Nova tabela descrita abaixo | Nunca pseudo-persona em `research_step_results` |
| `ResearchPoint.audit`, `AuditTrail.details` | JSON existente recebe `merge_id`, `round`, ordinal e veredito sanitizado | Nenhuma coluna de audit nova exigida; registros anteriores preservados |

Nullable serve somente compatibilidade histórica: não autoriza storage novo a inserir NULL. Validar inteiro positivo, rejeitando bool, ausência e valores não positivos. Banco verifica positividade quando presente; contrato de nova escrita verifica presença. Não criar default que fabrique identidade antiga. Ativos sem identidade confiável ficam retidos com diagnóstico; não inferir de timestamp, `attempt_count` ou ordem. DONE/Report existentes permanecem intactos e não são reprocessados. Migração não reinicia pesquisas.

### Nova tabela, proposta fechada

| Coluna proposta | Tipo SQLAlchemy portátil | Obrigação |
|---|---|---|
| `id` | `Uuid` | PK, UUID criado na aplicação |
| `research_id` | `Uuid` | NOT NULL, FK `research.id`, CASCADE coerente com domínio |
| `step_id` | `Uuid` | NOT NULL, FK `research_points.id`, CASCADE |
| `round` | `Integer` | NOT NULL, CHECK `round > 0` |
| `content` | `JSON` | NOT NULL, objeto estruturado não vazio validado no serviço |
| `created_at` | `DateTime(timezone=True)` | NOT NULL, timestamp UTC explícito na criação |

UNIQUE `(research_id, step_id, round)`. Usar `JSON`/`Uuid` genéricos, não JSONB, ARRAY ou UUID exclusivamente PostgreSQL. Validação de quatro membros e conteúdo não vazio fica em schema/serviço, sem CHECK JSON específico de dialeto. FKs independentes não provam que ponto pertence à pesquisa: storage deve consultar `ResearchPoint.id == step_id AND ResearchPoint.research_id == research_id` antes de resultados/merge. Nomes de constraints e classe ORM nova ficam para actions/coding; tabela e campos acima são propostos, não símbolos já existentes.

## 3. Resultado, barreira e concorrência

Evoluir `app/investigation/schemas.py`, `app/investigation/storage.py` (`save_step_result`) e `app/investigation/service.py` (`run_investigation`), sem nova framework. Novo `result` guarda análise não vazia após strip, aprendizados, citações `{claim, exact_quote, source_url, source_title}`, contradições e lacunas. Validar/sanitizar todos campos; `used_urls` só contém URLs cujos corpos realmente chegaram ao contexto, não links encontrados recursivamente no JSON. Não persistir corpos integrais, prompts ou raciocínio privado.

Uma linha terminal imutável por persona/rodada. Retries de transporte precedem gravação terminal. Reenvio idêntico relê linha; divergente gera conflito interno explícito, sem overwrite/upsert destrutivo. Erro fatal persistido não vira sucesso na mesma rodada por recuperação tácita. Q-502 não autoriza nova recuperação automática.

Barreira consulta banco, não apenas gather: exige exatamente `historian`, `skeptic`, `pragmatist`, `futurist`, conforme `PERSONA_NAMES` em `app/investigation/prompts.py`, com sucesso e análise estruturada válida no mesmo ponto, pesquisa e rodada positiva atual. 3/4, duplicata, branco, falha, outra rodada ou NULL histórico nunca liberam auditor.

Transação curta verifica associação e CAS de ponto/rodada/estado, lê quatro resultados committed e grava merge único. `content` mantém quatro IDs e cópias integrais atribuídas em ordem `PERSONA_NAMES`, fontes, contradições e lacunas. Merge determinístico, sem LLM extra nem fatos novos. Colisão única relê e valida snapshot equivalente, não substitui conteúdo. Commit antecede rede do auditor. Veredito revalida CAS da mesma rodada/merge e registra ordinal, `ResearchPoint.audit` e `AuditTrail.details` no mesmo commit; resposta obsoleta descartada com erro seguro. Nenhuma sessão/transação compartilhada aberta durante HTTP/LLM.

Rodada seguinte só após reprovação factual válida. Quatro avaliações totais, inicial mais três; quarta reprovação conclui `AUDIT_CAVEAT`. Falha de persona não incrementa contador nem força conclusão. Writer só recebe todos pontos não vazios em `AUDIT_APPROVED`/`AUDIT_CAVEAT`.

## 4. Evidence e entrega sem perda

Preservar `evidences`, `Evidence.version`, `version_id_col` e `uq_evidence_source` sobre `(research_point_id, persona, source_url)`. Reutilizar `_quote_supported` em `app/services/pipeline/worker.py` contra corpo integral limpo em memória antes da projeção. Mesma persona/URL mantém primeiro Evidence imutável. Citações novas verificadas além desse primeiro Evidence sobrevivem integralmente em result e merge, sem relaxar unicidade nem apagar aprendizado.

Bundle futuro do Writer reúne citações verificadas de merges das rodadas conclusivas e Evidence legado autorizado, com proveniência e atribuição. Material pendente/NULL sem proveniência não vira fato automaticamente. URL conhecida/verbatim não substituem validação factual. Para zero Evidence e nenhum conteúdo aproveitável, relatório curto honesto por ponto, sem fontes inventadas; relatório misto preserva fatos sustentados e limitações. Corrigir Markdown sem liberar fatos sem fonte.

Preservar `reports.research_id` único. CAS para WRITE, sessão fechada antes de `_write_report`; Report e DONE persistidos antes de callback. Retomada WRITE sem Report tenta escrita; DONE com Report não reescreve. Colisão relê Report, falha callback não desfaz DONE nem apaga relatório.

## 5. Plano Alembic futuro — não executar nesta sprint

Somente PostgreSQL efêmero descartável, nunca base de desenvolvimento/produção ou URL ambiente herdada. Executor futuro cria instância exclusiva com banco terminado em `_test`, valida host/porta contra instância recém-criada e iguala `TEST_DATABASE_URL` a `DATABASE_URL`; ambiente test, sem `.env`. Sufixo `_test` sozinho não prova isolamento. Nenhum DDL em DB existente.

1. Reconsultar grafo e definir revisão e parent no coding. Verificar migrations criam todas tabelas usadas, sem usar `create_all()` para completar instalação faltante.
2. Clean upgrade: banco vazio exclusivo; `alembic upgrade head` pelo runner isolado; inspecionar tabelas, FKs, uniques, tipos e checks, inserir nova rodada válida e rejeitar zero/negativo. Provar barreira/merge e associação pesquisa/ponto pelo serviço.
3. Populated upgrade: segunda base descartável no head anterior observado; semear múltiplos retries textuais históricos, linhas NULL após upgrade, pesquisas ativas sem identidade, DONE com Report e Evidence versionado. Guardar snapshots/contagens, aplicar nova migration e comparar: nenhuma promoção para rodada 1, alteração textual, reclassificação, remoção ou sobrescrita. Duplicatas históricas permanecem; novos positivos colidem por unique. Storage rejeita nova linha sem rodada.
4. Downgrade: somente essa base descartável, após reconhecer perda de colunas/tabela novas. Voltar ao parent real e conferir remoção apenas de `investigation_merges`, novos campos/constraints; dados e estruturas anteriores preservados. Reupgrade prova reversibilidade estrutural, não restauração dos dados novos descartados.
5. Descartar instâncias/volumes exclusivos. Registrar comandos, exit codes e asserts em evidência do coding. Não executar agora nem declarar gate aprovado.

`tests/test_briefing_migration.py` e `tests/investigation/test_investigation_migration.py` são regressões existentes; SQLite/create_all não comprovam upgrade PostgreSQL. `tests/test_postgres.py` exige URL explícita coincidente e banco `_test`, mas validação futura exige também origem descartável da instância.

## 6. Cobertura cruzada

| RF | Delta de dados | Contrato relacionado | Exercício em onboarding |
|---|---|---|---|
| RF-501 | Corpo integral só em memória; proveniência persistida | Tool interna, sem rota pública | Dez corpos longos/parser |
| RF-502 | Identidade persona/ponto/rodada | Sem campo HTTP novo | Query obrigatória e 1 a 3 distintas |
| RF-503 | Resultado imutável e rodada positiva | Assinaturas preservadas | Quatro linhas válidas |
| RF-504 | Merge único committed/CAS | Auditor interno | Barreira negativa e merge antes audit |
| RF-505 | Ordinal audit e caveat | Investigação background | Quatro reprovações, nenhuma quinta |
| RF-506 | Report único inclusive zero Evidence | GET report existente | Limitação honesta/DONE |
| RF-507 | Citações verificadas no bundle | Markdown em Report | Prosa/negrito/lista/tabela negativos |
| RF-508 | CAS WRITE, retomada e callback pós-DONE | Legado/resume preservados | Ambos entrypoints até Report |
| RF-509 | Sem migration de payload/frontend | POST201/PATCH200/409/202 | HTTP síncrono/decisão única |

Q-501/Q-502 permanecem premissas de falha segura, não respostas humanas. Nenhuma migration, teste runtime ou alteração de dados executados aqui.
