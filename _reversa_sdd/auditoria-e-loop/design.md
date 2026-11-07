# Auditoria e loop — desenho interno

## Ordem (`Pipeline._auditar`, `src/orchestrator.py:324-459`)

1. Por ponto: `hidratar` → `payload_auditor` (acumulado compactado) → tarefa `auditor_p{id}_r{rodada}` (`:331-355`).
2. `_executar_lote(..., AuditorSaida.model_validate)` — uma chamada, retentativa por tarefa (`:357`).
3. Por ponto: sem saída → redator com 12 false + evento `auditoria.executada` com `auditor_ausente:true` (`:363-401`); com saída → `_registrar`, `avaliar`, `salvar_auditoria` (só última p/ leitura rápida), evento com detalhe (`:402-434`).
4. `aprovado` → evento `ponto.aprovado`; `!=NOVA_RODADA` → `ponto.reprovado` (`:435-442`).
5. `NOVA_RODADA` → `pendentes/ignoradas/rodada`, `continue`; senão acumula `encerrados` + `del estado` (`:443-457`); `encerrados` → `_redigir` (`:458-459`).
Loop externo: `while estado: coletar → auditar` (`:146-148`). **CONFIRMADO**

## Estados do ponto (implícitos)

`pendente-coleta → auditado → {nova-rodada | encerrado-redigido}`; vive no dict `estado` em memória; persistido: `rodada_atual, aprovado, porcentagem_aprovacao, ultimo_resultado_auditor` + histórico imutável em `agent_executions`. **CONFIRMADO**

## `avaliar` (`src/planner.py:25-41`)

| condição | `proxima_acao` |
|---|---|
| `taxa >= alvo` | `chamar_subagente_redator` |
| `tentativa_atual >= max_rodadas` | `encerrar_buscas_por_limite_e_chamar_redator` |
| senão | `chamar_subagentes_buscadores_rodada_seguinte` |

**CONFIRMADO**

## Decisões

- Auditor ausente não aborta: redige com 12 false + lacunas documentadas. **CONFIRMADO** (`:363-401`, `:470-484`).
- Limite estourado redige com o que há; dossiê parcial > nada. **CONFIRMADO** (`:439-442` + `_redigir`).
