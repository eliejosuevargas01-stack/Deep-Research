# Interface: POST /briefings/{research_id}/investigate

> Contrato HTTP da Feature 002 (Investigação Paralela por Personas).

---

## 1. Identificação

- **Método**: `POST`
- **Caminho**: `/briefings/{research_id}/investigate`
- **Autenticação**: `Depends(require_admin)` (`app/core/security.py`), mesma dependência dos demais endpoints de `/briefings`
- **Tipo de Execução**: Assíncrona (Background Tasks do FastAPI / `asyncio.create_task`)

---

## 2. Parâmetros da Requisição

- **Path Parameter**:
  - `research_id` (UUID): Identificador canônico da pesquisa (compartilhado com o briefing aprovado).
- **Request Body**: Vazio (`{}` ou ausente).

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
2. A investigação já foi disparada anteriormente (passos não estão todos em `SCRAPER_PENDING` ou já existem resultados em `research_step_results`).

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
   - `research_points.status` transita imediatamente para `SCRAPER_IN_PROGRESS`.
3. **Fan-out Concorrente**:
   - Dispara $N 	imes 4$ tarefas assíncronas em background via `asyncio.gather(..., return_exceptions=True)`.
4. **Finalização**:
   - Cada persona bem-sucedida grava em `research_step_results` com status `AUDIT_PENDING`.
   - Cada persona com falha definitiva grava com status `FAILED` e incrementa `attempt_count` do passo.
   - Ao concluir todas as tarefas do passo: passo fica `AUDIT_PENDING` (se ao menos 1 worker teve sucesso) ou `SCRAPER_FAILED` (se os 4 falharam).
   - Ao concluir todos os passos: `research.status` transita para `AUDIT` (ou `FAILED` se todos os passos forem `SCRAPER_FAILED`).
