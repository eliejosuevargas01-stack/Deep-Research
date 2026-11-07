# Redação e consolidação — desenho interno

## Ordem

1. `_auditar` acumula `encerrados` e chama `_redigir` **uma vez por rodada de auditoria** (`src/orchestrator.py:458-459` no `while estado`). **CONFIRMADO**
2. `_redigir` (`:461-544`): tarefas + validadores por ponto; loop até `tentativas_por_agente` com `executor.executar` + `_registrar_orquestrador`; inválido → `_registrar` + `_corrigir`; válida → `saidas`. **CONFIRMADO**
3. Segunda passada: exige saída válida, `_registrar` + `salvar_relatorio` + `ponto.finalizado`; sem saída → `ponto.erro`, segue. **CONFIRMADO**
4. `executar`: `consolidar` dentro do try (`:149`); `run.concluido` com `avaliacao_pontos[]` (`:150-159`); webhook fora do try (`:166-173`).
5. `consolidar` sob `self._lock` com commit único (`src/db/repository.py:400-493`). **CONFIRMADO**

## Validador por tarefa vs `_executar_lote`

Redator **não usa** `_executar_lote`: validador distinto por ponto (closure allowlist). Duplicação ~20 linhas intencional. **CONFIRMADO** (`:498` comentário).

## Decisões

- COMPLETED-antes-do-webhook (D-01): banco consistente antes de efeito externo; preço = COMPLETED com callback não entregue (só log). **CONFIRMADO**.
- Ponto incompleto vira seção, não aborta; FAILED só com zero relatórios. **CONFIRMADO**.
