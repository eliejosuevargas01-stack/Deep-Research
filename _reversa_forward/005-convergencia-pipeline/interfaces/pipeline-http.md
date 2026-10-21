# Interface HTTP do pipeline — PLAN-005-B

> 🟢 Superfície observada; 🟡 convergência interna proposta. Sem novo endpoint, campo frontend, modelo, provedor ou SLA. Complementa roadmap §5 e data-delta, não substitui código.

## 1. Resolução dos paths e autenticação

`app/main.py` inclui `briefing_router`, `investigation_router` e `research_router` sem prefixo adicional. `app/briefing/router.py` e `app/investigation/router.py` não têm prefixo; `app/routers/research.py` usa `APIRouter(prefix="/api")`. Paths abaixo são externos completos, não `/api/briefings`.

Todos endpoints listados usam `require_admin` (`app/core/security.py`). Escolher apenas uma credencial: cookie `dr_session`, Authorization Bearer ou `X-API-Key`; Bearer/API key comparados a `API_AUTH_SECRET`. Cookie em POST/PATCH/PUT/DELETE exige `X-CSRF-Token`; Bearer/API key não exigem CSRF. Credenciais simultâneas e `X-Tenant-ID` recebem 400; ausentes/inválidas 401; cookie inválido/expirado 401; CSRF inválido 403. Nunca inserir senha/token literal em exemplos, logs ou relatórios. Erros de validação Pydantic recebem 422 com `detail`, sem eco do input conforme handler de `app/main.py`.

## 2. Briefing síncrono e decisão exclusiva

| Método e path | Request real | Response e semântica |
|---|---|---|
| POST `/briefings` | `BriefingCreateRequest`: somente `theme`, string validada de 3 a 300 caracteres | 201 `BriefingResponse`, geração e persistência concluídas antes da resposta |
| GET `/briefings/{research_id}` | UUID retornado pela criação, sem body | 200 `BriefingResponse`; 404 ausente |
| PATCH `/briefings/{research_id}` | `BriefingFeedbackRequest`: somente `note`, string de 3 a 4000 caracteres | 200 `BriefingResponse` após revisão síncrona, autoaprovação e agendamento de investigação |
| POST `/briefings/{research_id}/investigate` | UUID real, sem body novo | 202 `InvestigateResponse`, aprovação implícita/reserva e investigação background |

`BriefingResponse` em `app/briefing/schemas.py`: `research_id` UUID, `theme`, `status`, `points` com `title` e `description`, `version >= 1`, `error` nullable e `approved_at` nullable. DRAFT/APPROVED validam de 3 a 7 pontos. Status do briefing é enum próprio, não enum de Research. `InvestigateResponse` retorna `research_id`, `status="SCRAPER"`, `message="Investigação iniciada em background"`; 202 não afirma Report pronto.

Payloads exemplificativos não executados: criação `{"theme":"Energia solar em escolas"}`; revisão `{"note":"Detalhar custos e limites das fontes"}`. Campos extras proibidos. Não enviar objeto integral de briefing, `points`, `round`, `investigation_round`, `approved_at` ou `status` no PATCH. Omissão de note não é atualização parcial válida: 422. Payload misto proibido deve falhar sem escrita parcial.

Depois de criar, escolher **uma** alternativa: PATCH para revisar uma vez, ou investigate para aceitar draft sem revisar. PATCH já agenda investigação; nunca chamar investigate em seguida. Revisão repetida ou estado/versão incompatível recebe 409; não repetir revisão nem abrir approve alternativo. Versão inicial draft observada é 2; não codificar versão cliente para burlar decisão. Reserva/CAS evita agendamento duplicado; concorrência deve ter regressão. Sem nova chave de idempotência: POST de criação repetido pode criar outra pesquisa, não prometer deduplicação global.

POST/PATCH fazem Scout SERP-only; dez corpos integrais pertencem às personas investigativas, não ao briefing. Não retornar 202 para geração do briefing nem introduzir polling de geração. Nenhum `/briefings/{id}/approve` novo. Decorators legados de edit/approve não autorizam uso como segunda decisão modular.

### Erros e tempo existentes

`app/briefing/router.py`: POST preserva 500 configuração/prompt/erro interno e 503 busca/geração indisponível, além de 422 de input. PATCH preserva 404 inexistente, 409 estado/versão/segunda revisão, 422 conteúdo, 500 configuração/prompt/credenciais externas e erro interno, 503 SERP indisponível e 502 geração indisponível conforme branches atuais. Não transformar todo erro upstream em status novo; exceções não mapeadas seguem tratamento existente. `app/investigation/router.py` preserva 404 e 409 para reserva/estado já iniciado. Erros têm mensagens seguras, sem segredo/corpos/prompts.

Timeout do briefing validado por `_resolve_briefing_timeout`, usando `settings.SEARCH_TIMEOUT_SECONDS`, repassado aos adapters SERP/LLM/serviço por tentativa. Não é SLA HTTP end-to-end; retries/execução síncrona podem levar mais que uma tentativa. Nenhum prazo novo, garantia de disponibilidade ou status de timeout inventado.

## 3. Compatibilidade legada

| Método e path externo | Contrato observado em `app/routers/research.py` |
|---|---|
| POST `/api/research` | 201, `ResearchCreate`: theme 3–300 após strip e callback_url opcional B2B; sem campo novo |
| GET `/api/research/{research_id}` | Consulta estado existente, 404 inexistente; manter payload frontend |
| POST `/api/research/{research_id}/resume` | Sem body; 200 com research_id/status; 404 ausente; 409 DONE, tarefa ativa ou briefing não aprovado |
| GET `/api/reports/{identifier}` | 200 por UUID de pesquisa ou Report; 404 ainda ausente |
| POST `/api/reports/{identifier}/retry-callback` | Sem body; 200 `{success: delivered, delivered: delivered}`; 404 pesquisa ausente; 409 sem callback ou Report |
| GET `/api/research/{research_id}/events` | SSE existente; alias `/api/research/{research_id}/stream`, `Last-Event-ID` preservado; sem novo polling obrigatório |

Criação legada retorna `research_id`, `status`, `briefing_draft`, `briefing_url` e `stream_url`, com Scout síncrono. Não confundir com `BriefingResponse`: branch legado pode retornar 201 com status FAILED e erro persistido após falha Scout; 201 sozinho não prova briefing útil. Sessão browser proíbe callback_url no payload com 422; B2B valida URL pública/anti-SSRF. Não usar callback real nos exercícios.

Resume mantém assinatura e scheduler `schedule`, que chama `run_research`. Proposta: `run_research` adapta ciclo modular compartilhado preservando dependências, eventos e callbacks; sem inventar rodada de histórico ativo não identificado. Retenção com diagnóstico é regra interna proposta, não novo status HTTP inventado. Retomada WRITE sem Report deve chegar ao Writer; DONE/Report existentes ficam intactos.

GET report retorna `report_id`, `research_id`, `content_markdown`, `citation_metrics`, `audit_findings`, `generated_at`. Até Report existir, 404 não significa aprovação nem conclusão. Unicidade de Report/CAS internos garantem entrega única proposta; callbacks somente depois de persistir Report/DONE. Falha callback mantém relatório consultável e DONE; retry-callback não gera relatório novo. Callback e segurança de outbound seguem `app/services/webhook.py` e `app/tools/outbound.py`, sem novo destino, payload ou política de retry neste plano.

## 4. Contrato interno, não API pública

Tool Jina pertence a `app/investigation/tools.py`, `JinaToolAdapter._single_attempt`. Proposta envia `q` e `num=10` no Search existente; mantém query/título/URL/corpo integral limpo no contexto, sem snippet substituto, fallback apresentado como sucesso ou corte silencioso. Nenhum endpoint público de tool/merge criado. Até três queries distintas por persona/ponto/rodada; primeira pelo modelo e obrigatória. Merge persistido das quatro personas antecede auditor, não response novo de briefing. Result/merge retêm citações verificadas além do primeiro Evidence, conforme data-delta.

Q-501: menos dez corpos/contexto insuficiente falha explicitamente sem sucesso parcial. Q-502: falha individual preserva resultados e impede merge/auditoria; não é quarta reprovação nem permite Writer prematuro. Premissas pendentes de política, não decisões humanas respondidas e não status HTTP novos.

## 5. Matriz de cobertura e provas propostas

| RF | Superfície preservada / consequência | Prova no onboarding/data-delta |
|---|---|---|
| RF-501 | Tool interna, não Scout HTTP | Dez corpos longos, parser e num=10 |
| RF-502 | Sem query budget exposto ao frontend | 1 a 3 queries distintas e primeira obrigatória |
| RF-503 | Sem novo campo de request | Persistência individual por rodada |
| RF-504 | Auditor interno após merge committed | 3/4 bloqueia; quatro da mesma rodada liberam |
| RF-505 | 202 não equivale a conclusão | Quatro reprovações, todos conclusivos |
| RF-506 | GET report aceita relatório curto honesto | Zero Evidence, Report/DONE |
| RF-507 | Markdown existente, guardrails corrigidos | Fatos sem fonte negativos em quatro formatos |
| RF-508 | Legado/resume/report/callback sem assinatura nova | Dois entrypoints até Report/DONE; falha callback |
| RF-509 | POST201/PATCH200/409 e investigate202 | Fixtures HTTP síncronas, decisão exclusiva |

Somente contrato documentado; testes novos e implementação ainda propostos até actions definir arquivos/nós. Nenhuma chamada live, migration ou gate aprovado nesta sprint.
