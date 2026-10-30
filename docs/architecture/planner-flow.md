# Fluxo do Planejador (Planner)

## Como funciona hoje

1. **Pre-coleta SERP antes do modelo**: `app/core/planner.py` usa `JinaClient.search(...)` / ferramentas SERP integradas (via `JinaClient`) para obter resultados SERP da consulta do tema antes de montar o contexto enviado ao LLM. O código busca links/resultados web com antecedência e os incorpora ao prompt/contexto.
2. **Contexto construído pelo harness**: o harness (planner/orquestração) executa essa busca SERP programaticamente (sem delegar ao modelo decidir chamadas). Os resultados são formatados e passados na mensagem/prompt enviado ao modelo.
3. **Modelo não faz tool calling própria**: o planejamento usa o cliente LLM (`LLMClient`) com prompt já enriquecido pelos resultados SERP. Não há loop de tool calling autônomo por parte do modelo; toda recuperação SERP é realizada pelo harness antes da inferência.
4. **Geração do plano**: o modelo retorna o plano estruturado (eixos/pontos) a partir desse contexto. O repositório persiste `plano_estruturado`/`metadados_planejamento` e gera pontos.

## Onde isso acontece

- `app/core/planner.py`: lógica de planejamento; invoca busca SERP/Jina e monta contexto antes de chamar LLM.
- `app/tools/jina_client.py`: cliente Jina/SERP usado pelo planner/harness para obter resultados web.
- `app/services/credential_resolver.py`: resolução de credenciais para Jina/LLM.
- Integração com `ResearchRepository.create_research(...)` para persistir plano/pontos.

## Por que economiza tokens

- Evita tool schema e múltiplos turnos de tool calling (menos overhead de instruções + menos chamadas).
- Reduz chance de alucinações ao dar fontes concretas no contexto inicial.
- Permite controlar quais resultados entram (filtragem/deduplicação pelo harness) antes de gastar tokens com raciocínio do modelo.
- Respostas mais determinísticas e menor custo/latência.

## O que mudaria se fosse tool calling

- Modelo decidiria quando/como buscar (pode chamar SERP em turnos distintos), exigindo loop de tool calling no planner.
- Maior uso de tokens (schemas + histórico + turnos) e potencialmente mais latência.
- Mais flexível para perguntas abertas, mas precisa de guardrails (limites de chamadas, allowlist, deduplicação).
- Requer mudanças em `planner.py` para suportar function/tool calls, tratamento de tool results e possivelmente maior complexidade de erros/retries.
