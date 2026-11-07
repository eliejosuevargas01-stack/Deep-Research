# Redação e consolidação — contratos

## `payload_redator` (`src/hydrator.py:105-129`)

`research_id, ponto_id, persona "redator", soul, ponto_enunciado, resultado_final_auditor, perguntas_auditoria, perguntas_nao_concluidas, erro_coleta, urls_usadas_acumuladas, informacao_coletada_acumulada_integral` (compactada D-11) + `compactacao`. **CONFIRMADO**

## `RedatorSaida` (`src/contracts.py:190-204`)

`extra="ignore"`; `relatorio_ponto` strip não-vazio; `lacunas_identificadas=""`; `urls_citadas` normalizadas. Subconjunto checado no orchestrator (corpo + lista). **CONFIRMADO**

## Retorno de `consolidar` = payload do webhook (`src/db/repository.py:495-510`)

`{research_id, relatorio_final, lacunas_finais, urls_usadas, urls_lidas, urls_lidas_nao_usadas, avaliacao_pontos{...}, pontos_falhos, metricas_tokens{prompt,completion,reasoning,total}}`. Colunas: `status='COMPLETED'`, `relatorio_final_consolidado` (+ `## Avaliação de veracidade`), `lacunas_finais_consolidadas`, `urls_*_globais`, `completed_at`. **CONFIRMADO**

## `enviar_callback(url, payload, timeout_s=15)`

`httpx.post` JSON; **5 tentativas**, esperas (1,2,4,8s); retenta só 5xx/rede; 4xx levanta; fim → `RuntimeError`. **CONFIRMADO** (`src/webhook.py`; `tests/test_webhook.py`).

## Divergências vs PRD/SDD

- Nomes payload ≠ colunas (`relatorio_final` vs `relatorio_final_consolidado`; `metricas_tokens` = `SUM` sem coluna própria). Mapear 1:1 não é possível; documentado aqui. **CONFIRMADO**.
- Webhook fora da transação de COMPLETED por decisão D-01 (COMPLETED primeiro, falha só log). **CONFIRMADO**.
