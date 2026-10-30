# Plano de Implementação: Checkpoint 2 — Streaming SSE e Reasoning em Tempo Real
Data: 2026-10-27
Orquestrador: Hermes Orchestrator

## 1. Objetivo
Implementar o Entregável 2 do Deep Research:
1. Backend: canal SSE (`GET /api/v1/pipeline/{id_pesquisa}/stream`) e despacho de eventos ao vivo a partir do `PipelineRunner` (buscas, personas, auditorias, redação e relatório final com seus respectivos reasonings).
2. Frontend: consumo do stream SSE via cliente resiliente, renderização do progresso em tempo real e visualização rica dos pensamentos dos modelos (`ReasoningLiveFeed`) com estilo profissional Impeccable (identidade DominusLabs).
3. Testes e Auditoria: testes unitários e de integração de streaming no backend, testes reais no navegador e auditoria de qualidade rigorosa via subagentes Hermes.

---

## 2. Fases de Execução

### Fase 1: Backend SSE & Event Bus (Worker Backend)
- Implementar barramento em memória / fila de eventos para pesquisas ativas (`PipelineEventHub` ou fila por pesquisa).
- Adicionar hook de notificação no `PipelineRunner` para emitir eventos `pipeline.status`, `search.progress` (com reasoning das personas), `audit.result` (com reasoning da auditoria) e `writer.progress` / `report.final` (com reasoning do dossiê).
- Criar endpoint `GET /api/v1/pipeline/{id_pesquisa}/stream` em `app/api/v1/endpoints/pipeline.py` com `StreamingResponse`, autenticação por sessão/API key, snapshot inicial do banco e keep-alive periódico.
- Testes unitários (`tests/unit/test_sse_stream_acceptance.py`) validando formatação SSE, headers, autorização e término limpo na desconexão.

### Fase 2: Frontend SSE Client & Componente de Reasoning (Worker Frontend)
- Criar serviço/hook de conexão SSE (`usePipelineStream.ts` ou `streamService.ts`) com reconexão segura e fechamento no unmount.
- Criar componente `ReasoningFeed.tsx` estilizado com o design system do projeto (violeta/índigo DominusLabs, tipografia limpa, tags e cards expansíveis de pensamento dos modelos).
- Integrar `ExecutionView.tsx` e `App.tsx` para exibir os eventos e raciocínios à medida que chegam pelo stream, mantendo compatibilidade com modo síncrono.
- Compilar frontend e verificar build limpo (`npm run build`).

### Fase 3: Auditoria Independente de Qualidade (Auditor Hermes)
- Subagente auditor (Gemini 3.8 Flash High com reasoning high) avalia:
  - Isolamento de conexões e vazamento de memória em streams.
  - Segurança de headers SSE e autenticação de mesma origem.
  - UX e a11y do painel de reasoning (contraste, foco, redução de movimento).
  - Veredito (SHIP/FIX).

### Fase 4: Cenários Gherkin Cucumber & Validação Visual
- Cenários de teste Cucumber cobrindo conexão SSE, exibição de cards de raciocínio, finalização fluida e tratamento de interrupção de rede.
- Execução de suíte visual e fechamento do Checkpoint 2.
