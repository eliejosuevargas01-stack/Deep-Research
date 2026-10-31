# Spec — Streaming SSE em Tempo Real

**Versão:** v1.0 (2026-10-28)
**Status:** Implementada
**Substitui:** o canal SSE baseado apenas em snapshots do banco (eventos emitidos só ao fim de cada estágio)
**Referências:** PRD v2 (I-2, I-6), `endpoint-busca-com-personas.md` v1.1, `endpoint-auditoria-de-qualidade.md` v1.1, `endpoint-redacao-do-dossier.md` v1.1

---

## 1. Objetivo

O provedor LLM (9Router) já devolve `reasoning_content` e `content` em chunks
(`stream=True`). Este contrato garante que esses deltas cheguem ao frontend **ao
vivo**, sem esperar o fim do estágio, e sem acoplar o cliente LLM ao endpoint HTTP.

O canal anterior transmitia apenas snapshots: o raciocínio de uma persona só
aparecia depois que a coleta inteira terminava. Para o usuário, isso é
indistinguível de uma simulação.

---

## 2. Arquitetura

```
LLMClient (stream)  ->  stream_context.publish_delta()
                              |
                              v
                     PipelineEventHub (global, in-process)
                              |
                              v
        GET /api/v1/pipeline/{id}/stream  ->  EventSource (frontend)
```

### 2.1 `app/core/stream_context.py`

- `stream_scope(id_pesquisa, stage, agent=None, ponto_id=None)`: context manager
  baseado em `contextvars.ContextVar`. Propaga-se para `asyncio.create_task`
  criados dentro do bloco (cada persona/ponto herda o escopo do seu task).
- `publish_delta(kind, text)`: publica `agent.delta` no hub quando há escopo
  ativo. **Fora de escopo é no-op** — chamadas HTTP avulsas (`/plan`, `/search`,
  `/audit`, `/writer`) e testes não publicam nada.
- `publish_stage_event(...)`: publica `stage.start` / `stage.end`.

### 2.2 Instrumentação

| Estágio | Onde o escopo é aberto | `agent` | `ponto_id` |
|---|---|---|---|
| `plan` | `endpoints/plan.py` em volta de `Planner.execute_plan` | `planejador` | — |
| `search` | `searcher.py`, um escopo por task de persona | persona (`historiador`, `visionario`, `cetico`, `futurista`) | ponto corrente |
| `audit` | `auditor.py`, um escopo por task de ponto | `auditor` | ponto corrente |
| `writer` | `writer.py`, em volta de `_execute_writer_concreto` | `redator final` | — |

`pipeline_runner.py` publica `stage.start`/`stage.end` para `audit` e `writer`
(estágios sequenciais); no `search`, o ciclo de vida é derivado dos eventos
`point.status`/`search.progress` já existentes.

---

## 3. Eventos

### 3.1 `agent.delta` (novo)

```
event: agent.delta
data: {"id_pesquisa":"...","stage":"search","agent":"historiador","ponto_id":"...","kind":"reasoning","text":"trecho"}
```

- `kind = "reasoning"`: `delta.reasoning_content` do provedor.
- `kind = "content"`: `delta.content` (resposta bruta do agente).
- `text` é sempre o delta incremental, nunca o acumulado.
- O frontend concatena por chave estável `(stage, agent, ponto_id)`.

### 3.2 `stage.start` / `stage.end` (novos)

```
event: stage.end
data: {"id_pesquisa":"...","stage":"audit","agent":"auditor","ponto_id":null}
```

Fecham o indicador de "pensando" no frontend.

### 3.3 Eventos preservados

`pipeline.status`, `point.status`, `search.progress`, `audit.result`,
`writer.progress`, `report.final`, `pipeline.error` continuam com o mesmo
contrato (snapshot inicial + marcos de estágio).

---

## 4. Coalescência (obrigatória)

Cada token do provedor **não** vira um frame SSE. O endpoint agrupa deltas
consecutivos com a mesma chave `(stage, agent, ponto_id, kind)` em um único
evento, até 400 deltas por frame.

- Um evento de tipo diferente encontrado na fila é devolvido para a próxima
  iteração (`asyncio.Queue` não tem `put_front`) — **nunca é descartado**.
- A coalescência não reordena nem perde texto: `text` do frame é a concatenação
  exata, na ordem de chegada.

---

## 5. Frontend (`usePipelineStream`)

- `agent.delta` com `kind="reasoning"` cria/atualiza um item ao vivo com
  `id = live-{stage}-{agent}-{ponto_id}` e `streaming: true`.
- `stage.end` marca os itens daquele estágio como `streaming: false`.
- Quando chega o evento final do estágio (`search.progress`, `audit.result`,
  `writer.progress`), o item ao vivo correspondente é removido e substituído
  pelo parecer consolidado — sem duplicar conteúdo no feed.
- `kind="content"` é repassado via callback (`onAgentDelta`) e não entra no feed
  de raciocínio.

---

## 6. Invariantes

- **SSE-1**: nenhum delta é truncado. O `text` do frame é a soma exata dos
  deltas recebidos do provedor (PRD v2, I-2).
- **SSE-2**: nenhum evento de outro tipo é descartado durante a coalescência.
- **SSE-3**: `publish_delta` nunca levanta exceção — streaming não pode derrubar
  a chamada ao LLM.
- **SSE-4**: sem escopo ativo não há publicação (isolamento entre pesquisas e
  entre execuções síncronas).
- **SSE-5**: o canal é somente leitura sobre o estado; a verdade continua no
  banco (snapshot inicial + eventos de marco).

---

## 7. Limitações conhecidas

- O hub é **in-process**: múltiplos workers Uvicorn não compartilham eventos
  (o deploy atual usa 1 processo). Escalar horizontalmente exige Redis/pub-sub.
- O snapshot inicial cobre apenas o histórico já persistido; deltas emitidos
  antes da conexão do cliente não são reproduzidos (não há replay).
