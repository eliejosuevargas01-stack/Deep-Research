# Interface: POST /briefings/{research_id}/investigate

> Contrato HTTP pretendido da Feature 002; exemplos sintéticos.
> Fontes: [requirements](../requirements.md), §2.1, RF-02, RF-03, RF-04, RN-01, RN-02, RN-03, e deliberações Q1/Q5/Q10/Q11 e Q14–Q16 de 2026-10-14.
> Atualizado em 2026-10-14: aprovação implícita e instanciação direta dos pontos no disparo sobre rascunho em `draft`, sem exigência de endpoint `/approve` e sem HTTP 409 por status `draft`.

---

## 1. Identificação

- **Método**: `POST`
- **Caminho**: `/briefings/{research_id}/investigate`
- **Autenticação**: administrador pela dependência real `require_admin` (`app/core/security.py`); cliente deve seguir o mecanismo configurado pelo app (`Bearer`, `X-API-Key` ou sessão por cookie `dr_session` com `x-csrf-token`), sem combinar mecanismos. Ausência ou credencial inválida retorna HTTP 401/403.
- **Tipo de Execução**: Assíncrona via FastAPI `BackgroundTasks`, conforme RN-01. Resposta HTTP 202 confirma a aprovação implícita, a instanciação atômica dos pontos em `research_points` e o enfileiramento dos workers em background.

---

## 2. Parâmetros da Requisição

- **Path Parameter**:
  - `research_id` (UUID): Identificador canônico universal da pesquisa e do briefing (RFC 4122).
- **Request Body**: Vazio (`{}` ou ausente); não transporta queries, parâmetros nem lista de pontos. UUID malformado no path retorna HTTP 422 Unprocessable Entity.

---

## 3. Respostas

### 3.1 202 Accepted (Sucesso no Disparo e Aprovação Implícita)

Retornado quando a pesquisa existe e é acionado sobre o primeiro briefing válido em status `draft` (ou pesquisa já elegível):
- Opera a **aprovação implícita** do briefing na mesma operação (sem requerer endpoint `/approve`, extinto).
- Valida os pontos do briefing (3 a 7 pontos não-vazios, aceitando títulos longos em `sa.Text` sem limite de 500 caracteres, conforme Q11).
- Insere atomicamente os pontos na tabela `research_points` vinculados ao `research_id`, com status inicial `SCRAPER_IN_PROGRESS` e `attempt_count = 0`.
- Transita a pesquisa para `research.status = 'SCRAPER'`.
- Agenda o fan-out dos $N \times 4$ workers assíncronos em background.

```json
{
  "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "SCRAPER",
  "message": "Investigação iniciada em background"
}
```

### 3.2 404 Not Found

Retornado quando `research_id` não existe na tabela `research`.

```json
{
  "detail": "Pesquisa não encontrada"
}
```

### 3.3 409 Conflict (Conflito de Estado / Idempotência)

Retornado nas seguintes situações:
1. **Re-disparo**: A investigação já foi iniciada anteriormente (a pesquisa já se encontra em `SCRAPER`, `AUDIT`, `WRITE`, `DONE` ou `FAILED`, ou os pontos já estão em `SCRAPER_IN_PROGRESS` ou concluídos).
2. **Investigação já iniciada automaticamente por revisão**: O operador já executou a revisão única via `PATCH /briefings/{research_id}`, a qual aprovou e iniciou a investigação em background automaticamente.
3. **Ausência de pontos válidos**: A pesquisa ou briefing não possui pontos válidos associados (zero pontos).
4. **Concorrência**: Tentativa de disparo concorrente enquanto a operação de reserva e instanciação atômica está em andamento.

> **Regra de Ausência de 409 por status `draft`:** O status inicial `draft` do briefing e a ausência prévia de registros em `research_points` **NÃO** motivam HTTP 409 Conflict. A chamada direta sobre o rascunho inicial válido é o fluxo canônico (Caminho A), que opera a aprovação implícita e instanciação atômica na mesma chamada.

```json
{
  "detail": "Investigação já iniciada ou em andamento para esta pesquisa"
}
```

### 3.4 401 Unauthorized / 403 Forbidden

Credenciais administrativas ausentes, inválidas ou token CSRF inválido na autenticação por sessão.

---

## 4. Comportamento e Efeitos Colaterais

1. **Aprovação Implícita e Validação**:
   - O endpoint verifica se o `research_id` existe na tabela `research`.
   - Se a pesquisa estiver em `PENDING_APPROVAL` com o briefing em `draft`, o serviço valida se o briefing possui entre 3 e 7 pontos não-vazios. Títulos longos gerados pelo Scout são aceitos integralmente em coluna `sa.Text` (Q11).
   - Os pontos são persistidos diretamente na tabela `research_points` vinculados ao `research_id`, com status `SCRAPER_IN_PROGRESS` e `attempt_count = 0`.
   - A pesquisa transita atomicamente de `PENDING_APPROVAL` para `SCRAPER`.
   - O endpoint `/approve` (`POST /briefings/{research_id}/approve`) foi extinto e não deve ser invocado em nenhum momento.
2. **Fan-out Concorrente Irrestrito**:
   - Para os $N$ pontos aprovados, o orquestrador assíncrono despacha exatamente $N \times 4$ tarefas assíncronas concorrentes via `asyncio.gather(..., return_exceptions=True)`, sem enfileiramento por semáforo (conforme a Emenda da Feature 002 ao Princípio IV).
   - O despachador repassa para cada função worker a tupla explícita `(research_id, step_id, step_title, persona)`.
3. **Execução das Personas e Persistência**:
   - Cada worker executa loop de reflexão com LiteLLM e memória exclusivamente em RAM, utilizando até 3 buscas Jina Search por ponto (via POST `https://s.jina.ai/` ou proxy configurado, timeout 90s).
   - Todas as URLs retornadas pela API da Jina são capturadas pelo harness e gravadas em `read_urls` (não prova leitura integral nem citação verbatim).
   - O modelo retorna JSON estruturado `{"result": "...", "used_urls": [...]}`. Erros de formatação recebem até 3 chamadas de reparo dedicadas.
   - Cada worker bem-sucedido persiste linha imutável em `research_step_results` com status `AUDIT_PENDING`.
   - Cada worker com falha definitiva grava linha em `research_step_results` com status `FAILED`, erro sanitizado (máx 500 chars), e incrementa atomicamente o contador `attempt_count` do respectivo ponto.
4. **Finalização do Ponto e da Pesquisa**:
   - Ao concluir todos os 4 workers de um ponto: o ponto transita para `AUDIT_PENDING` (se pelo menos 1 worker concluiu com sucesso) ou para `SCRAPER_FAILED` (se todos os 4 workers falharam definitivamente).
   - Ao concluir todos os pontos da pesquisa: `research.status` transita para `AUDIT` se pelo menos 1 ponto obteve sucesso analítico; ou para `FAILED` se 100% dos pontos da pesquisa terminaram em `SCRAPER_FAILED`.
5. **Retomada Pós-Reinício**:
   - Um hook no ciclo de inicialização do FastAPI inspeciona pesquisas em `SCRAPER` cujos pontos estejam em `SCRAPER_IN_PROGRESS` e reagenda em background exclusivamente as personas que ainda não possuem linha persistida em `research_step_results`.

---

## 5. Tentativas, limites e privacidade

- **Chamadas Externas (Jina e LiteLLM)**: Até 3 tentativas totais (1 inicial + até 2 retries técnicos com backoff exponencial 2s/4s e suporte a `Retry-After`). Timeout limite por chamada individual de 90s; timeout global máximo por execução de worker de 600s.
- **Autocorreção de JSON**: Até 3 tentativas dedicadas de reparo quando o modelo emitir payload inválido; após exaustão, grava `FAILED` com `result="Invalid JSON response after 3 corrections"` e `used_urls=[]`, incrementando `attempt_count`.
- **Privacidade e Isolamento**: Prompts de sistema e raciocínio bruto (*chain-of-thought*) residem estritamente em memória RAM e nunca são gravados em banco, logs públicos ou payloads de resposta. A coluna `result` armazena exclusivamente a síntese analítica final ou mensagem de erro sanitizada de até 500 caracteres (Princípio II).
- **Rastreabilidade Factual**: Prompts instruem as personas a citar trechos literais (*verbatim*) das fontes acompanhadas de URLs em `used_urls` (Princípio I). A validação profunda dessas citações cabe à Feature 003 (Auditoria).

---

## 6. Idempotência e concorrência

A aprovação implícita e a instanciação dos pontos em `SCRAPER_IN_PROGRESS` ocorrem sob transação atômica no banco de dados antes da emissão da resposta HTTP 202 e do agendamento dos workers. Caso uma requisição concorrente tente acionar `/investigate` sobre a mesma pesquisa simultaneamente, a transação concorrente detecta a mudança de estado e responde HTTP 409 Conflict. Re-disparos subsequentes também são imediatamente rejeitados com HTTP 409 Conflict sem duplicar execuções de workers.
