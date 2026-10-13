# Interface: POST /briefings/{research_id}/investigate

> Contrato HTTP pretendido da Feature 002; exemplos sintéticos. Inspeção estática de `app/investigation/router.py` não equivale a execução/aceite.

---

## 1. Identificação

- **Método**: `POST`
- **Caminho**: `/briefings/{research_id}/investigate`
- **Autenticação**: administrador pela dependência real `require_admin` (`app/core/security.py`); cliente deve seguir o mecanismo configurado pelo app, sem presumir esquema Bearer.
- **Tipo de Execução**: Assíncrona com FastAPI `BackgroundTasks`, conforme RN-01. HTTP 202 confirma a reserva, não o sucesso dos workers.

---

## 2. Parâmetros da Requisição

- **Path Parameter**:
  - `research_id` (UUID): Identificador canônico da pesquisa (compartilhado com o briefing aprovado).
- **Request Body**: Vazio (`{}` ou ausente); não transporta query nem lista de pontos. UUID inválido no path retorna HTTP 422.

---

## 3. Respostas

### 3.1 202 Accepted (Sucesso no Disparo)

Retornado quando a pesquisa existe, está aprovada e os passos são enfileirados para investigação em background.

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
1. O briefing associado à pesquisa ainda não foi aprovado (status diferente de `SCRAPER`).
2. A pesquisa não possui nenhum ponto aprovado associado em `research_points` (zero pontos).
3. Pelo menos um ponto não está em `SCRAPER_PENDING`, inclusive execução/finalização anterior; ou a reserva concorrente não altera todos os pontos esperados. O router valida estados e contagem de linhas reservadas, não consulta `research_step_results` para aceitar o disparo.

```json
{
  "detail": "Investigação já iniciada ou em andamento para esta pesquisa"
}
```

### 3.4 401 Unauthorized / 403 Forbidden

Credenciais inválidas ou ausentes.

---

## 4. Comportamento e Efeitos Colaterais

1. **Validação**: Verifica se `research.status == 'SCRAPER'` e se todos os `research_points` correspondentes possuem `status == 'SCRAPER_PENDING'`.
2. **Transição de Estado**:
   - `research_points.status` transita imediatamente para `SCRAPER_IN_PROGRESS`; `research.status` permanece `SCRAPER`.
   - `SCRAPER_IN_PROGRESS` é estado de ponto, não de pesquisa.
3. **Fan-out Concorrente**:
   - Dispara $N 	imes 4$ tarefas assíncronas em background via `asyncio.gather(..., return_exceptions=True)`.
4. **Finalização**:
   - Cada persona bem-sucedida grava em `research_step_results` com status `AUDIT_PENDING`.
   - Cada persona com falha definitiva grava com status `FAILED` e incrementa atomicamente `attempt_count` do ponto.
   - `attempt_count` nasce em 0 ao persistir pontos após aprovação.
   - Ao concluir todas as tarefas do ponto: ponto fica `AUDIT_PENDING` (se ao menos 1 worker teve sucesso) ou `SCRAPER_FAILED` (se os 4 falharam).
   - Ao concluir todos os pontos: `research.status` transita para `AUDIT` se algum ponto teve sucesso; `FAILED` apenas se todos os pontos forem `SCRAPER_FAILED`.
5. **Retomada**: No startup, pesquisa permanece `SCRAPER`; só despacha personas sem linha correspondente em `research_step_results` para ponto `SCRAPER_IN_PROGRESS`.

## 5. Tentativas, resultado e privacidade

- Cada chamada externa: até 3 tentativas totais (inicial + até 2 retries), espera 2s e 4s; timeout de 90s por chamada e 600s por worker. `Retry-After` é respeitado quando presente, sujeito ao limite total acordado.
- Reparos de JSON: resposta inicial e até 3 correções. Após exaustão, grava `FAILED`, `result="Invalid JSON response after 3 corrections"`, `used_urls=[]`; incremento atômico de `attempt_count` por falha definitiva.
- Prompts e CoT ficam apenas em RAM; `result` guarda análise final ou erro sanitizado, nunca segredo.
- `read_urls` significa URLs retornadas pela Jina, não prova leitura integral ou citação verbatim.

## 6. Idempotência e timeout HTTP

A reserva muda todos os pontos esperados de `SCRAPER_PENDING` para `SCRAPER_IN_PROGRESS` antes do commit e do agendamento. Conflito de contagem provoca rollback e HTTP 409; re-disparo não deve duplicar workers. Isso é proteção por estado/reserva, não uma chave de idempotência de cliente nem lease distribuído.

HTTP 202 não espera o término dos workers. Nenhum timeout total de request foi aprovado; limites 90s I/O e 600s worker referem-se à execução background. Leituras de resultados/status ficam fora deste contrato.
