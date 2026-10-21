# Investigation: base verificável PLAN-005-A

> Escopo documental: roadmap.md, questions.md, investigation.md existentes. Sem implementação, testes runtime, DB ou provedor com credencial.
> Observações referem-se ao código local; propostas não são estado implementado. Requirements 005 e adendo normativo de 2026-10-19 prevalecem sobre rascunhos e specs antigas.

## 1. Evidências locais e invalidação sucinta

| Tema | Observado com arquivo/linha | Conclusão corrigida / delta futuro |
|---|---|---|
| Teto do worker legado | `app/services/pipeline/worker.py:89-92` usa `min(3, max(1, settings.MAX_WORKER_QUERIES))`; primeira query por f-string em `:93-97`; Search com cinco em `:110-118`; cortes em `:128/139` | Falsa alegação de ausência de teto invalidada. Falta primeira query LLM, deduplicação e corpos integrais no caminho convergido. |
| Conteúdo Search modular | `app/investigation/tools.py:58-78` junta title/description/content/text/snippet; `:165-170` envia q apenas; `:177-183` pode retornar DDG como sucesso | Não é snippet-only: content/text podem conter corpos. Também não comprova dez corpos integrais nem limpeza. Proposta: itens corpo/URL/título/consulta separados, num=10 e rejeição de snippet substituto/fallback falso. |
| URLs lidas | `tools.py:39-60` coleta URLs recursivamente; `app/investigation/worker.py:426-438` adiciona `jina_result.urls` a read_urls e entrega conteúdo agregado | Lista atual não prova leitura de cada corpo nem vínculo correto. Delta: read_urls apenas de corpos efetivamente entregues; used_urls subset validado. |
| Barreira modular | `app/investigation/storage.py:66-78` usa any_pending, uma linha de sucesso basta para status AUDIT_PENDING; `:58-64` incrementa tentativa por falha | Conclusão antiga “Path B já exige quatro válidas” invalidada. Verificar quatro personas distintas válidas por rodada no banco antes merge. |
| Orquestração e erro | `app/investigation/service.py:297-316` gather return_exceptions seguido de audit se não SCRAPER_FAILED; `:330-343` força teto quando contador cresceu | gather não é barreira persistida; falha individual pode contaminar teto. Remover essa promoção e separar falha técnica de reprovação factual. |
| Persistência atual | `app/models/domain_models.py:60-73`: research_step_results com step_id/worker/result/used_urls/read_urls/status, sem rodada; `storage.py:84-121` lê histórico e pendências sem rodada | Não inferir rodada nem promover histórico. Campo nullable e tabela merge propostos no roadmap §4. |
| Auditor atual | `app/audit/service.py:104-126` lê todas as linhas do ponto; `:146-150` corta payload JSON em 60000 caracteres; `:434-440` usa attempt_count + 1 limitado a quatro | Agregação não é merge persistido; leitura precisa selecionar snapshot/rodada, sem cortar análises relevantes silenciosamente. Contexto insuficiente vira erro explícito, não JSON truncado. |
| Teto normativo | `app/audit/domain.py:105-118`: aprovado vira AUDIT_APPROVED, quarta reprovação AUDIT_CAVEAT; `audit/service.py:486-529` grava veredito | Reutilizar máquina, mas vincular merge/rodada e ordinal; contador atual misturado não é identidade histórica confiável. Infraestrutura inconclusiva não consome reprovação. |
| Modular termina sem Writer | `app/investigation/service.py:362-385` termina após check_all_points_completed; `app/audit/service.py:552-572` apenas transita WRITE | Alegação antiga de reuso já existente do Writer invalidada. Integração explícita ainda futura, incluindo retomada WRITE sem workers pendentes. |
| Legado chama Writer | `app/services/research.py:124-144` executa lotes e `_write_report`; `ready_point_batches` definido em `:79` | Alegação antiga de símbolo de lotes invisível invalidada. Reutilizar agendamento de dependências no modular, não duplicar ciclos. |
| Writer real | `app/services/pipeline/writer.py:14-21` exige 200 palavras e heading por ponto; `:35` pede alvo 400; `:38-48` exige evidência e links conhecidos; `:60` considera início * candidato factual | “Mínimo 400” invalidado: 400 é alvo de prompt. Ausência de evidência e negrito têm defeitos reais a corrigir, preservando fatos com fonte. URL membership não prova entailment (`:44`). |
| Evidência e Report | `app/models/domain_models.py:76-89` Evidence com unicidade ponto/persona/URL e versão; `:103-110` reports com research_id único | Não apagar Evidence nem relaxar verbatim. Resultados/merge guardam aprendizado novo da mesma URL; Writer lê citações verificadas atribuídas sem depender só da primeira projeção Evidence. Report único continua guardrail persistente. |
| HTML atual | `app/services/search.py:25-52`: HTMLParser exclui script/style/noscript/svg/head; entrada e saída cortadas, não remove header/footer/nav | Relaxar limpeza como ponytail invalidado. Stdlib deve remover header/footer/nav/script/style obrigatórios e anúncios/ruído marcado, sem cortes informativos. Parser não garante limpeza semântica perfeita ou imunidade a prompt injection. |
| Briefing | `app/briefing/router.py:141/232` POST e PATCH; `:292-315` autoaprova e agenda modular após revisão; `app/investigation/router.py:29-33` investigate202 | Dez corpos aplicam-se apenas personas. Transferi-los ao Scout SERP-only, como rascunho anterior sugeria, invalidado. |
| Prefixos | `app/main.py:95-100` inclui routers sem prefixo extra; `app/routers/research.py:21` prefix=/api; briefing/router.py:53 e investigation/router.py:24 sem prefixo | Rotas verificadas no roadmap §5, sem inventar alias /api para /briefings. Decorators de approve legado não autorizam approve novo. |
| Anti-SSRF | `app/tools/outbound.py:12-25` PinnedResolver valida IPs na conexão; `:31-51` rejeita destinos privados/reservados e protocolos/portas inválidos | Manter essas proteções e redirects desabilitados onde existentes. `_valid_url` em tools.py:29-36 valida formato, não substitui anti-SSRF. Proxy/URLs de saída devem passar fronteira pública antes da rede. |

Estas correções substituem conclusões falsas dos rascunhos interrompidos; autochecks e aprovação anteriores não são gates vigentes. Nenhuma alegação de “zero ocorrências” para nomes citados como histórico é mantida.

## 2. Alternativas avaliadas e escolha mínima

### Ciclo único em vez de dois motores alinhados manualmente

Escolha: evoluir `InvestigationService.run_investigation` e tornar `run_research` adaptador, preservando contrato legado e dependências via `ready_point_batches`. Reutiliza tool calling, persistência append-only e auditor modular; evita novo framework e divergência repetida. Manter dois ciclos com merge comum apenas foi rejeitado: teto, barreira, retomada e Writer continuariam independentes. Mudança deve preservar eventos e callback e ser testada pelos entrypoints, não só por helper mockado.

### Rodada e merge persistidos, histórico sem identidade inventada

Escolha: rodada nullable explícita em ponto/resultados e tabela proposta `investigation_merges` com chave única ponto/rodada. Merge determinístico conserva quatro IDs, análises, fontes, contradições e lacunas. Pseudo-persona merge foi rejeitada porque polui contagem e APIs de resultados; LLM extra de merge não é necessário. JSON existente em audit/AuditTrail referencia merge/rodada sem tabela nova de auditoria.

Backfill 1 rejeitado: histórico não registra rodada e attempt_count inclui falhas técnicas. Ordenar por timestamp tampouco prova quais quatro textos pertencem à mesma rodada. Manter NULL histórico e excluir da barreira; DONE/Report preservados, ativo sem rodada fica retido com diagnóstico. Nova pesquisa recebe 1 na escrita, não por default retroativo. Migração e constraints detalhadas no roadmap §4, prontas para data-delta; não implementadas.

### Verbatim sem apagar aprendizado

`app/services/pipeline/worker.py:26-38/149-181` já valida quote contra fonte e projeta Evidence; reutilizar validação no modular, com trechos exatos e fonte original integral em memória. Análise estruturada serializada em result permite preservar aprendizado e atribuição além das linhas Evidence. Unicidade Evidence por URL continua; resultado/merge guardam citações novas, Writer consome bundle verificado sem perda por colisão. Auditor recebe merge inteiro, não últimas linhas arbitrárias de todos os retries. Falha contexto explícita substitui corte silencioso de material relevante.

### Stdlib antes de nova dependência

HTMLParser já existe; estender sem limites de slice para coleta integral e com exclusão de header/footer/nav/script/style e ruído marcado por tags/atributos. Não delegar limpeza ao LLM nem instalar trafilatura/readability por conveniência. Testar tags aninhadas/malformadas e texto informativo longo; ambiguidade de conteúdo não autoriza extração destrutiva. Scout permanece separado e SERP-only.

### Limitações não equivalem a fracasso factual nem a aprovação parcial

Quarta reprovação de material auditável conclui com ressalva. Falha técnica individual não conclui nem produz quarta análise. Writer limitado só após todos conclusivos; pode usar template determinístico sem fatos quando não há conteúdo aproveitável. Relatório misto cita fatos e declara limites por ponto. Regras de Markdown não devem equiparar **negrito** a lista nem isentar fatos por formatação/rótulo.

## 3. Fontes externas e grau de prova

- Fonte oficial consultada sem credenciais: `https://raw.githubusercontent.com/jina-ai/reader/main/src/api/searcher.ts`, linhas 114-116 aceitam count/num entre 0 e 20; parâmetro count tem default 10 nessa revisão consultada, propriedade targetResultCount=6 em linha 59. `main` é mutável; isso não garante default nem entrega do endpoint/proxy em produção.
- `https://jina.ai/search/`: requirements §10 registra documentação pública com default cinco; extração nesta sprint falhou com CRAWL_NOT_FOUND. Não apresentar como revalidação atual nem como impedimento a solicitar dez explicitamente.
- Escolha do plano: enviar num=10 no adapter investigativo e validar dez corpos completos, não depender de defaults. Search pode devolver corpos via content/text; Reader não é obrigatório por interpretação do nome Search. Nenhuma chamada live autenticada, garantia de integralidade física ou homologação de proxy foi executada.

## 4. Contexto SDD, precedência e migrações

Preflight leu AGENTS.md, state/active-requirements/forward-autonomous e política .reversa/reversa-config.json. Gancho de plan/template não encontrado no diretório .reversa observado; não criar nem executar scripts de conveniência. Estado permanece readonly e ainda marca requirements, não plano aprovado.

Arquivos `_reversa_sdd/architecture.md`, `c4-context.md`, `state-machines.md`, `dependencies.md`, `code-analysis.md` não existem no snapshot consultado; mapa AGENTS contém referências históricas, não prova existência atual. Usar código real e adendo aprovado como âncoras. Requirements 001 preserva SERP e privacidade; 002 preserva personas, tool calling e decisão única; 003 preserva auditoria factual e limites; 004 preserva Writer/callback, exceto alterações explícitas RN-507/508 e precedência do adendo. Não reabrir requirements.

Inspeção estática das migrations: cadeia 0001 até 0007, head 0007 (`alembic/versions/0007_investigation_step_results_and_status.py`, revision=0007/down_revision=0006). 0001 cria domínio e attempt_count; 0006 cria armazenamento briefing; 0007 cria research_step_results e reconcilia status. Não afirmar que 0007 introduz attempt_count. Próximo ID só no coding. Não houve acesso a banco nem prova upgrade PostgreSQL; fixture/create_all não substitui migration efêmera.

## 5. Provas pendentes para ações

1. Coleta: MockTransport num=10, dez páginas com marcador final além de 100000 caracteres, HTML limpo integral; nove corpos, inacessível e contexto insuficiente falham sem sucesso parcial; redirects/SSRF/segredos negativos.
2. Worker: primeira query LLM obrigatória, duplicata sem rede, até três distintas, parada cedo, síntese estruturada não vazia e fontes lidas; conteúdo externo não vira instrução.
3. Banco isolado: quatro linhas committed na rodada, barreira negativa com 3/4, duplicata, falha, branco e histórico NULL; merge antes auditor; corrida/CAS/veredito obsoleto; upgrade/downgrade PostgreSQL efêmero.
4. Ciclo: inicial+3 reprovações, nenhuma quinta coleta; falha técnica não conta; todos conclusivos antes Writer; adaptador legado preserva dependências e modular chega Report/DONE inclusive retomada WRITE.
5. Writer/API: zero Evidence e relatório misto honestos, Markdown factual negativo inclusive negrito, Report único, callback falho não desfaz DONE; POST201/PATCH200 síncronos, revisão repetida409, investigate202 e Scout SERP-only.

Verificação documental PLAN-005-A: matriz contém RF-501..509 (9), RN-501..510 (10), DT-501..510 (10), contados programaticamente. Paths completos `app/*.py` citados foram conferidos em disco; marcador Markdown inválido ausente nos três documentos. `git diff --check` tracked retornou 0. Separadamente, `git diff --no-index --check /dev/null <documento>` retornou 1 para cada untracked, sem diagnóstico de whitespace (diferença de conteúdo, não erro de whitespace). Nenhum hardbreak com espaços finais introduzido. Comparação readonly com backup de recuperação preserva requirements e active/state; forward-autonomous já contém alterações do coordenador e não foi editado por este worker. Backups não modificados.

Não executados: testes de produto, install, runtime de provedor/LLM, migrations, DB, deploy ou recuperação de pesquisas reais. Premissas Q-501/Q-502 continuam pendentes de política. Próximos artefatos: data-delta e ações; auditoria independente depois, sem autoconceder aprovação.
