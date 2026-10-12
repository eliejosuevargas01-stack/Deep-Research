# Política de execução da feature 001-modulo-briefing

## Autorização do usuário

Em 2026-10-10, usuário solicitou delegação contínua após plan e to-do: coding, auditorias, sync, reversa-audit e quality. Não exigir CONTINUAR entre essas fases. Autorização se limita ao módulo backend de briefing e requisitos aprovados.

## Sequência

Esta sequência substitui a política anterior de micro-sprints com auditoria entre tarefas. Decisão explícita do usuário, 2026-10-11: delegação em lotes por capacidade e revisão independente ao final da implementação da feature.

1. Reutilizar plan e to-do já aprovados; não reiniciar etapas comprovadas.
2. Delegar `/reversa-coding` em lotes coerentes: high recebe várias ações sequenciais, preferencialmente 5–10 quando existirem ações prontas nesse recorte; low recebe várias ações simples. Informar IDs exatos, arquivos permitidos, dependências, critérios e checks. Não inventar tarefas para atingir uma quantidade.
3. Depois de cada lote, Orchestrator confere entrega, escopo, diff, artefatos e comandos/exit codes. Workers executam testes relevantes durante implementação. Essa verificação não inicia auditoria/QA independente por tarefa.
4. Entregar os próximos lotes até finalizar a implementação da lista. Registrar implementação entregue separadamente de aprovação final; checkbox não substitui evidência de aceite.
5. Com a implementação estável, executar auditoria independente, `/reversa-audit`, `/reversa-quality` e QA aplicável da feature. Cobrir a feature com recortes definidos por módulo/fluxo/diff e relatórios próprios, sem pedido irrestrito de revisão do projeto inteiro. Implementador não aprova seu trabalho; auditor e QA não corrigem código.
6. Agrupar findings confirmados em lotes de correção para os workers apropriados. Depois das correções, verificar e revisar os recortes afetados, sem repetir etapas aprovadas e inalteradas. Falha que comprometa segurança, integridade ou execução bloqueia o caminho afetado.
7. Após conformidade comprovada e auditoria/quality/QA aprovados, executar `/reversa-sync`, conferir seus artefatos e atualizar a feature para DONE. Divergência no sync volta aos workers antes de DONE.

## Limites

Não alterar frontend, corrigir testes antigos sem relação direta, recriar requisitos antigos, fazer commit/push/deploy ou usar banco externo. Não executar migração em ambiente real sem autorização. Respeitar `.reversa/reversa-config.json`; não editá-la. Falhas técnicas ou decisões funcionais não resolvidas bloqueiam avanço, sem inventar evidências. Documentação/código antigos não são verdade de produto.

## Pendências de pré-checagem

Validar âncora nova requerida pelo coding após chegada do plano; não reaproveitar specs excluídas ou presumir que requisitos substituem automaticamente essa pré-condição. Confirmar contrato Jina SERP sem leitura de páginas antes de implementar integração.

## Paralelismo e perfis por complexidade

Decisão do usuário, 2026-10-11: executar tarefas paralelizáveis em paralelo; usar perfis high quando houver alto reasoning e low quando trabalho for repetitivo com pouco ou nenhum reasoning.
Decisão do usuário, 2026-10-11 (lotes por capacidade cognitiva e auditoria no final):
- Workers high têm alta capacidade cognitiva e executam lotes de 5 a 10 tarefas em sequência em uma única delegação.
- Workers low executam tarefas mecânicas ou repetitivas (testes simples, updates de doc, configs, etc.) sem micro-delegação unitária.
- Não fazer auditoria ou QA a cada micro-tarefa entregue. A delegação de código segue em lotes até concluir a lista de tarefas da feature.
- Auditoria (/reversa-audit) e Quality (/reversa-quality) rodam no final de todas as tarefas de implementação da feature inteira, contra a documentação/specs aprovadas.
- Se a auditoria/quality encontrar divergência documental ou defeito real, o Orchestrator cria tarefa de correção pontual para os workers.
- Se todas as tarefas estiverem conformes à documentação: avança para /reversa-sync, atualiza a feature para DONE e finaliza.
