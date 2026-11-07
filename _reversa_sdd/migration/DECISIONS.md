# Decisões — rodada de produto (2026-11-07)

Fonte única das decisões do usuário sobre as perguntas da documentação reversa.
Cada decisão referencia a pergunta original (`questions.md`) e o código observado.
`D-xx` = decidido; `Q-xx` = aberto.

## D-01 — Webhook: tentar várias vezes (Q-01)

- **Resposta do usuário:** "tentar várias vezes".
- **Hoje:** `src/webhook.py:13-29` faz 2 tentativas; falha final só loga e o run permanece `COMPLETED` (`src/orchestrator.py:129-136`).
- **Alvo:** 5 tentativas com espera crescente (1s, 2s, 4s, 8s) entre elas; repete em erro de rede e HTTP 5xx; erro 4xx encerra. Esgotadas as 5, levanta erro (o chamador loga) e o status continua `COMPLETED` — entrega não confirmada não é representada por novo status.
- **Aceite:** teste HTTP real com 2 falhas 500 e sucesso na 3ª; teste de esgotamento com 5 falhas.
- **Unidades afetadas:** `redacao-e-consolidacao`.

## D-02 — Auditor: exigir booleano de verdade (Q-03)

- **Resposta do usuário:** "exigir caixinha".
- **Hoje:** `src/contracts.py:163-171` já rejeita `"true"`/`"false"` como texto e exige `bool` JSON.
- **Alvo:** manter. Nenhuma mudança de código.
- **Aceite:** `tests/test_contracts_e_gate.py::test_auditor_exige_booleanos_estritos` verde.
- **Unidades afetadas:** `auditoria-e-loop`.

## D-03 — Frontend: ajustar ao servidor novo (Q-04)

- **Resposta do usuário:** "ajustar para o novo servidor".
- **Hoje:** `frontend/src/services/api.ts` chama 12 rotas antigas (`/api/v1/plan`, `/search`, `/audit`, `/writer`, `/pipeline/...`, `/settings/hermes`); nenhuma existe em `src/api.py`.
- **Alvo:** fluxo único contra a API v1.2: formulário (`tema`, `profundidade`, `veracidade_alvo`, `max_rodadas_auditoria`, `atualidade`, `callback_url`) → `POST /research` (202) → acompanhamento por `GET /research/{research_id}` → dossiê consolidado + fontes + tokens; tela de configuração via `GET/PUT /config`. Telas de plano/busca/auditoria/redação do pipeline antigo saem do fluxo ativo. Casca visual preservada.
- **Aceite:** `npm run build` verde; fluxo real contra uvicorn local com `FakeExecutor` ou API fake; nenhuma chamada às rotas antigas no bundle novo.
- **Unidades afetadas:** `ingestao-e-api` + frontend legado (declarado fora do escopo até esta decisão).

## D-04 — Auditorias: guardar todas (Q-05)

- **Resposta do usuário:** "guardar todas as auditorias, precisamos de rastreabilidade".
- **Hoje:** cada rodada já grava uma linha imutável em `agent_executions` (`agent_role='auditor'`, `raw_output_payload` com as 12 respostas), mas `research_points.ultimo_resultado_auditor` só mantém a última e `GET /research/{id}` não expõe o histórico.
- **Alvo:** expor o histórico completo em `GET /research/{research_id}` no campo `auditorias` (lista por ponto/rodada, com respostas, taxa, aprovado, modelo e tokens), derivado de `agent_executions`; não sobrescrever nada. `research_points` continua com o último resultado para leitura rápida.
- **Aceite:** teste de pipeline com 2 rodadas em 1 ponto → 2 itens em `auditorias`, ordem por `rodada`, respostas distintas.
- **Unidades afetadas:** `auditoria-e-loop`, `telemetria-e-persistencia`, `ingestao-e-api`.

## D-05 — Limite de 40: aceitar o teto de 10 pontos (Q-06)

- **Resposta do usuário:** "o planejador não pode criar mais de 10 pontos, então na teoria esse risco de pontos a mais não existe".
- **Hoje:** `ResearchRequest.profundidade` é `1..10` (`src/contracts.py:33`); o lote máximo é 10 × 4 = 40.
- **Alvo:** nenhuma trava nova no backend. O contrato de entrada já limita a 40 subagentes por rodada. Risco aceito.
- **Aceite:** `tests/test_api.py::test_api_rejeita_payload_invalido` cobre `profundidade=11` → 422.
- **Unidades afetadas:** `coleta-personas`.

## D-06 — Remover o bloco de configuração morto (Q-07)

- **Resposta do usuário:** "apagar".
- **Hoje:** `config/hermes_config.yaml:18-22` tem um bloco `delegation:` que `Config.carregar` (`src/config.py:33-51`) nunca lê; só `tests/test_settings.py` o lia.
- **Alvo:** remover o bloco e o trecho de teste que o pinava; a autoridade é `hermes_home/profiles/deep-research/config.yaml`, cujo teto continua pinado por teste.
- **Aceite:** suíte verde; nenhuma menção ao espelho em `config/hermes_config.yaml`.
- **Unidades afetadas:** `configuracao-e-execucao`.

## D-07 — Planner registra os links que leu (Q-08)

- **Resposta do usuário:** "sim, planejador não salva os links que ele leu".
- **Hoje:** `PlanoLLM` (`src/contracts.py:93-107`) só aceita `pontos`; a varredura exploratória do planner não persiste `urls_lidas`/`urls_usadas` (o `agent_executions` do planner fica com listas vazias).
- **Alvo:** o planner passa a devolver `urls_lidas` e `urls_usadas` (opcionais, listas); o backend valida/higieniza, grava na linha do planner em `agent_executions` e inclui nas listas globais da consolidação. Prompt/SOUL instruem a declarar os links da varredura.
- **Aceite:** teste com planner devolvendo 2 URLs lidas/1 usada → linha do planner com as listas e `GET /research/{id}` com as URLs globais; consolidação inclui.
- **Unidades afetadas:** `planejamento`, `redacao-e-consolidacao`, `telemetria-e-persistencia`.

## D-08 — Boletim agregado como formato oficial (Q-02)

- **Resposta do usuário:** usar `avaliacao_pontos` como formato oficial.
- **Hoje:** `src/planner.py:44-76 avaliacao_pontos` montava o objeto SDD §5.7 sem chamador no fluxo.
- **Alvo:** formato oficial incluído no dossiê (`relatorio_final_consolidado` ganha `## Avaliação de veracidade`), no payload do webhook (`avaliacao_pontos`) e no `GET /research/{id}` (omitido quando o run ainda não tem pontos).
- **Aceite:** `tests/test_pipeline.py::test_pipeline_completo_com_retentativa_e_webhook` (boletim 2 pontos 91.67/aprovado) + GET com boletim e seção; suíte verde.
- **Unidades afetadas:** `redacao-e-consolidacao`, `ingestao-e-api`.

## Q-02 — Formato agregado de avaliação (aberto)

- **Status:** decidido em D-08 (2026-11-07); pergunta reexplicada em 2026-11-07.
- **Fato:** `src/planner.py:44-76 avaliacao_pontos` monta o objeto do SDD §5.7, tem teste (`tests/test_contracts_e_gate.py:127`) e nenhum chamador no fluxo.
- **Opções:** remover a função/teste, ou plugar como formato oficial (webhook/persistência).
- **Não decidir sem resposta.**

## D-09 — Modelos por papel: forte p/ planner/auditor/redator, leve p/ buscadores (Q-09)

- **Resposta do usuário:** forte onde decide, leve onde coleta.
- **Hoje:** `src/settings.py:31-41` (`MODELO_FORTE_PADROO=ocg/deepseek-v4.1-flash`, `MODELO_LEVE_PADRAO=gemini/gemini-3.5-flash-lite`, `MODELOS_PADRAO_POR_PAPEL` com planner/auditor/redator=forte, historiador/cetico/visionario/futurista=leve); `modelo_do_papel` (`:44-55`) com `LLM_MODEL_<PAPEL>` > `LLM_MODEL` (só planner) > default do papel; `engine/entrypoint.sh:10-31` (`modelo_do_papel`, vazio nunca herda forte) + `docker-compose.yml:29-40` defaults por papel; perfil `hermes_home/profiles/deep-research/config.yaml:1-21` com os 7 papéis pinados; workspace congela via `MODELS.json` (`src/orchestrator.py:106-110`).
- **Alvo:** manter. Provedor só env (D-10).
- **Aceite:** `PYTHONPATH=src python -c "import settings"` retorna forte p/ planner/auditor/redator e lite p/ 4 buscadores; engine config com 7 papéis.
- **Unidades afetadas:** `configuracao-e-execucao`.

## D-10 — API key: header/Bearer/query-SSE, `GET /health` sempre aberto (Q-10)

- **Resposta do usuário:** chave obrigatória, saúde aberta.
- **Hoje:** `src/api.py:23-42` (`_chave_api` lê `DR_API_KEY|API_KEY`; sem chave=aberto dev; `path=/health` retorna antes de validar; `X-API-Key` + Bearer + `?api_key=` p/ SSE; 401 `API key inválida` via `hmac.compare_digest`); `GET /health` sem `Depends` (`:49-51`), demais rotas com `Depends(_exigir_chave)` (`:53,58,66,72,76-77`); `PUT /config` com `base_url/api_key` não-vazio → 422 (`src/settings.py:93-98,209-212`); `GET /config` retorna `api_key:""` + `provider_fonte:"env"` (`:141-144`).
- **Alvo:** manter. Smoke: sem chave `GET /health` 200 + `POST` 401; com chave `POST` 202, `GET` 200 com `auditorias`+`avaliacao_pontos`, `PUT api_key=x` 422, `PUT api_key=""` 200.
- **Aceite:** `tests/test_api_key.py:32-87` (aberto sem chave; 200 saúde com chave errada; 401/202/404; SSE `?api_key=` snapshot).
- **Unidades afetadas:** `ingestao-e-api`.

## D-11 — Compactação de evidências sem perda factual (Q-11)

- **Resposta do usuário:** prompt menor, fato nenhum perdido.
- **Hoje:** `src/evidencias.py:1-123` (só prompts auditor/redator; DB intacto): normaliza espaço; dedup linhas exatas (primeira vence, ordem preservada); remove só ruído da lista conservadora (`_RUIDO_EXATO` `:18-40`, prefixos `:42-48`) e **nunca** linha com dígito/URL/data/citação (`_tem_conteudo_protegido` `:51-66`); URLs/números/datas/citações intactos. `hydrator.payload_auditor` (`:90-101`) e `payload_redator` (`:115-128`) compactam e expõem `compactacao{lines/chars}`; `hidratar` (`src/db/repository.py:354-389`) segue integral (2 SELECTs + Python, `informacao_coletada NOT NULL`).
- **Alvo:** manter. DB = 100% bytes; prompt = compactado + `compactacao{}`.
- **Aceite:** `tests/test_evidencias.py:18-103` (dup some/únicas ficam; números/URLs/datas intactos; shape igual + menor; entrada original não mutada; chaves não-texto intactas).
- **Unidades afetadas:** `coleta-personas`, `auditoria-e-loop`, `redacao-e-consolidacao`, `telemetria-e-persistencia`, `planejamento` (urls do planner entram no acumulado, não mudam plano).

## D-12 — Imagem `latest` aceita (Q-12)

- **Resposta do usuário:** `latest` vale como pin.
- **Hoje:** `engine/Dockerfile:2-5` (`FROM nousresearch/hermes-agent:latest`; comentário: tag `0.22.5` não existe no registry); `docker-compose.yml` 2 serviços (api + engine `expose 8100`, engine `USER hermes`, `hermes_home:ro` na api); SDD cita `latest`.
- **Alvo:** manter `latest`; SDD registra aceite.
- **Aceite:** comentário no Dockerfile + compose com 2 serviços.
- **Unidades afetadas:** `configuracao-e-execucao`.

## Q-09..Q-12 — decididas acima

- Q-09 modelos por papel → D-09. Q-10 API key/health → D-10. Q-11 compactação → D-11. Q-12 latest → D-12.
