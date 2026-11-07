# Coleta por personas — contratos

## `payload_buscador` (`src/hydrator.py:51-78`)

`research_id, ponto_id, rodada, persona, soul, tema, atualidade, ponto_enunciado, subperguntas, hipoteses, lacunas_iniciais, perguntas_auditoria_pendentes, urls_lidas_ignoradas, max_queries`. Envelope: `## Payload da execução` + JSON + "Responda apenas com o objeto JSON" (`:43-48`); sistema = `prompts/buscador.md` p/ qualquer persona (`:41`). **CONFIRMADO**

## `BuscadorSaida` (`src/contracts.py:144-164`)

`extra="ignore"`; `informacao_coletada` strip + não-vazia; `urls_usadas/urls_lidas` normalizadas (`urls_lidas` absorve usadas); `urls_lidas_nao_usadas`. **CONFIRMADO**

## Colunas `agent_executions` (`src/db/repository.py:96-158`)

`research_id, ponto_id, rodada, agent_role, model_used, input_prompt_payload, raw_output_payload, informacao_coletada, reasoning_trace, tool_calls, urls_usadas/lidas/nao_usadas, prompt/completion/reasoning/total_tokens, latency_ms`. `total = call.total_tokens ou soma`. Totais do run por `UPDATE + ?`. **CONFIRMADO**

## Eventos de coleta (`src/orchestrator.py:262-313`)

`ponto.iniciado{ponto_id,rodada}`; `fonte.lida{ponto_id,rodada,persona,urls_lidas[],urls_usadas[]}` (arrays); `ponto.coletado{ponto_id,rodada,urls_usadas[],urls_lidas[],personas[]}`; `ponto.erro{ponto_id,erro}` se zero sucessos. **CONFIRMADO**

## Compactação D-11 (`src/evidencias.py:1-123`)

`compactar_texto` → `compactar_acumulado` (shape e chaves intactos; só valores str compactados); estatísticas `{linhas_antes/depois, chars_antes/depois}` no payload (`compactacao`). Protegidos: dígito, URL, data, citação/aspas/`fonte:`/`segundo `. **CONFIRMADO** — `tests/test_evidencias.py`.

## Divergências vs PRD/SDD

- Fan-out 40 = instrução + YAML + contrato (`le=10`), não fatiamento no backend. **CONFIRMADO** (D-05).
- Prompt auditor/redator = compactado (D-11); DB = integral. PRD "100% bytes no prompt" → v1.3 "100% bytes no DB + `compactacao{}`". **CONFIRMADO**.
