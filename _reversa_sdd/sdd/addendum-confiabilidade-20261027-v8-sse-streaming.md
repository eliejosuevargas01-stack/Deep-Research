# Adendo v8 — Contrato de Streaming SSE e Visualização de Reasoning em Tempo Real
Data: 2026-10-27
Status: Aprovado para Implementação (Entregável 2 / Checkpoint 2)

## 1. Visão Geral

O Entregável 2 estende o pipeline contínuo do Deep Research com Server-Sent Events (SSE) nativos (`text/event-stream`), transmitindo em tempo real do backend para o frontend:
1. Transições de estado do pipeline (`status_pipeline`).
2. Progresso de busca paralela com personas e reasoning das coletas (`reasoning_coleta`).
3. Deliberações e raciocínio analítico da auditoria de 12 critérios (`reasoning_auditoria`).
4. Formulação do dossiê com o raciocínio do redator final (`reasoning_dossier`).
5. Entrega do relatório final e fontes canônicas.

## 2. Contrato da API de Streaming (Backend)

### 2.1 Endpoint
`GET /api/v1/pipeline/{id_pesquisa}/stream`
- **Cabeçalhos de Resposta:**
  - `Content-Type: text/event-stream; charset=utf-8`
  - `Cache-Control: no-cache, no-transform`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no`
- **Autenticação:**
  - Segue a regra canônica de `verify_api_key`: cookie de sessão local assinado `dr_local_session` ou header `X-API-Key` / `Authorization: Bearer <key>` ou modo aberto se `API_SECRET_KEY` não configurada.

### 2.2 Formato dos Eventos SSE
Cada evento segue a especificação W3C SSE:
```
event: <tipo_evento>
data: <payload_json_compacto>

```

### 2.3 Catálogo Canônico de Eventos

1. `pipeline.status`:
   - Emitido na inicialização e em cada mudança de estágio (`planejado`, `buscando`, `auditando`, `redigindo`, `concluido`, `falha`).
   - Payload: `{"id_pesquisa": string, "status_pipeline": string, "timestamp": string}`

2. `point.status`:
   - Emitido a cada transição de status de um ponto investigativo (`pendente`, `em_andamento`, `coletado`, `aprovado`, `reprovado`).
   - Payload: `{"id_pesquisa": string, "ponto_id": string, "ponto_n": number, "status": string, "tentativas": number}`

3. `search.progress`:
   - Emitido quando uma persona analítica conclui ou progride em sua coleta web.
   - Payload: `{"id_pesquisa": string, "ponto_id": string, "persona": string, "queries_executadas": number, "urls_lidas": number, "falha_coleta": boolean, "reasoning_coleta": Optional[str]}`

4. `audit.result`:
   - Emitido ao final da auditoria dos 12 critérios de um ponto.
   - Payload: `{"id_pesquisa": string, "ponto_id": string, "ponto_n": number, "status": "aprovado" | "reprovado", "pontuacao_percentual": number, "criterios_aprovados": number, "reasoning_auditoria": Optional[str], "pontos_fracos": Optional[str]}`

5. `writer.progress`:
   - Emitido durante e ao finalizar a redação do dossiê.
   - Payload: `{"id_pesquisa": string, "status": "redigindo" | "concluido", "reasoning_dossier": Optional[str], "total_caracteres": Optional[int]}`

6. `report.final`:
   - Emitido quando o dossiê final estiver pronto para consumo.
   - Payload: `{"id_pesquisa": string, "status": "concluido", "dossier_final": string, "total_caracteres": number, "concluido_em": string}`

7. `pipeline.error`:
   - Emitido em caso de erro fatal irrecuperável.
   - Payload: `{"id_pesquisa": string, "erro": string}`

8. `keep-alive`:
   - Linha de comentário periódica (`: keep-alive\n\n`) emitida a cada 15 segundos para evitar fechamento de conexão por proxies reversos ou timeouts de cliente.

### 2.4 Resiliência e Desconexão
- O gerador SSE monitora `await request.is_disconnected()`. Se o cliente desconectar, o canal de streaming é encerrado sem interromper a execução do pipeline em background.
- Para pesquisas em andamento ou recém-iniciadas, o endpoint envia imediatamente um snapshot de sincronização antes de transmitir novos eventos ao vivo.

---

## 3. Contrato da Interface do Usuário (Frontend)

### 3.1 Identidade Visual e Layout (Impeccable & DominusLabs)
- Preservação da identidade estética: paleta profissional de alta densidade informativa com tons de violeta/índigo (`#6D28D9` / `#4F46E5`), navy profundo e papel aquecido (`#F9FAFB`), com tipografia e espaçamentos consistentes.
- **Painel de Raciocínio dos Agentes (`ReasoningLiveFeed`):**
  - Componente colapsável e expansível, com indicador de pulso em tempo real (`.live-pulse-dot`) mostrando atividade ativa.
  - Abas/chips para alternar entre as visões de pensamento:
    - `Planejador`: Raciocínio de formulação de eixos e perguntas.
    - `Personas de Busca`: Raciocínios e decisões de coleta (Historiador, Visionário, Cético, Futurista).
    - `Auditor`: Parecer analítico e julgamento dos 12 critérios de qualidade.
    - `Redator Final`: Raciocínio de síntese e estrutura do dossiê.
  - Visualização formatada em markdown seguro, com scroll autônomo suave e opção de pausar rolagem automática.

### 3.2 Cliente SSE e Concorrência
- Utiliza `EventSource` padrão do navegador ou leitor de stream HTTP fetch compatível com autenticação de sessão.
- Gerenciamento estrito de ciclo de vida:
  - Fechamento imediato do `EventSource` ao navegar para outra pesquisa, resetar ou desmontar componente.
  - Proteção contra conexões duplicadas usando `useRef`.
