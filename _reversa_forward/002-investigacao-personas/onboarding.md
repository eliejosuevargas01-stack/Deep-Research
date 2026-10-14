# Onboarding: Investigação Paralela por Personas (Feature 002)

> Guia executável para validação manual e automatizada da Feature 002.
> Atualizado em 2026-10-14: extinção definitiva de `/approve`, aprovação implícita no `/investigate` direto (Caminho A) e revisão única com auto-investigate em background no `PATCH` (Caminho B).

---

## 1. Pré-requisitos e Configuração

Inicie a aplicação no ambiente de teste em `http://localhost:8000`. O guard `require_admin` aceita segredo administrativo por Bearer ou `X-API-Key`; sessão por cookie `dr_session` exige `x-csrf-token` nas mutações. Exemplos abaixo usam somente `X-API-Key`, com variável `TOKEN` fornecida pelo operador localmente, sem registrar seu valor. Não combine credenciais. Configure credenciais válidas via `PUT /api/settings`:
- Chave da Jina (`provider_keys.jina`) ou URL de proxy configurada.
- Chave de LLM configurada (`provider_keys.openai` ou gateway compatível) com modelos para as personas ou fallback no `scout`.

*Nota:* Exemplos ainda não executados nesta rodada. O humano pode executá-los em ambiente de teste isolado após os gates de implementação, com credenciais fornecidas localmente; nenhum segredo deve ser colado no chat ou nos artefatos.

---

## 2. Passo a Passo do Fluxo de Teste

### Passo 1: Criar o Briefing (Scout) e Capturar `research_id`

Envie uma requisição para gerar o briefing inicial com um tema e extraia o `research_id` da resposta usando Python stdlib:

```bash
set -euo pipefail
AUTH_HEADER=$(printf '%s: %s' 'X-API-Key' "${TOKEN:?Defina TOKEN localmente}")
RESPONSE=$(curl --fail-with-body -sS -X POST http://localhost:8000/briefings \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"theme": "Impacto da IA Generativa na Medicina Diagnóstica"}')

RESEARCH_ID=$(printf '%s' "$RESPONSE" | python3 -c "import sys, json; from uuid import UUID; print(UUID(json.load(sys.stdin)['research_id']))")
echo "Research ID capturado: $RESEARCH_ID"
```

**Formato ilustrativo de resposta HTTP 201; valores não são execução observada:**
```json
{
  "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "theme": "Impacto da IA Generativa na Medicina Diagnóstica",
  "status": "draft",
  "points": [
    {"title": "Precisão em Imagens", "description": "Investigar acurácia em imagens..."},
    {"title": "Decisão Clínica", "description": "Examinar apoio à decisão..."},
    {"title": "Ponto 3", "description": "Descrição ilustrativa"},
    {"title": "Ponto 4", "description": "Descrição ilustrativa"},
    {"title": "Ponto 5", "description": "Descrição ilustrativa"}
  ],
  "version": 1,
  "error": null,
  "approved_at": null
}
```

*Nota:* O identificador retornado é `research_id`, que já foi registrado na tabela `research` com status `PENDING_APPROVAL`. O endpoint `/approve` não existe no sistema. O operador dispõe a partir daqui de duas vias exclusivas (Caminho A ou Caminho B).

---

### Caminho A: Investigação Direta com Aprovação Implícita (Sem Alterações)

Se o operador julgar o briefing inicial em `draft` satisfatório, a investigação é disparada diretamente:

#### Passo 2A: Disparar a Investigação Direta

Acione o endpoint `/investigate` sobre o briefing em `draft`:

```bash
curl --fail-with-body -sS -X POST "http://localhost:8000/briefings/$RESEARCH_ID/investigate" \
  -H "$AUTH_HEADER"
```

**Resposta esperada (HTTP 202 Accepted):**
```json
{
  "research_id": "$RESEARCH_ID",
  "status": "SCRAPER",
  "message": "Investigação iniciada em background"
}
```

**Efeitos no banco:**
- Opera a **aprovação implícita** do briefing na mesma operação. O status `draft` não retorna HTTP 409.
- Os pontos são persistidos na tabela `research_points` vinculados ao `research_id` com status inicial `SCRAPER_IN_PROGRESS` e `attempt_count = 0`.
- A pesquisa transita atomicamente para `research.status = 'SCRAPER'`.
- N $\times$ 4 workers assíncronos (4 personas por ponto) são agendados e executados em background via FastAPI `BackgroundTasks`.

#### Passo 3A: Verificar Idempotência e Bloqueio de Re-disparo

Tente disparar a investigação novamente com o mesmo ID em `$RESEARCH_ID`:

```bash
curl -sS -i -X POST "http://localhost:8000/briefings/$RESEARCH_ID/investigate" \
  -H "$AUTH_HEADER"
```

**Resposta esperada (HTTP 409 Conflict):**
```json
{
  "detail": "Investigação já iniciada ou em andamento para esta pesquisa"
}
```

---

### Caminho B: Revisão Única por Feedback com Início Automático em Background

Se o operador desejar ajustar o briefing inicial, ele envia feedback textual único via PATCH, que gera nova versão e inicia a investigação automaticamente:

#### Passo 2B: Enviar Feedback Único via PATCH

Envie o feedback textual no corpo da requisição (3 a 4000 caracteres):

```bash
RESPONSE_PATCH=$(curl --fail-with-body -sS -X PATCH "http://localhost:8000/briefings/$RESEARCH_ID" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"note": "Aprofundar riscos regulatórios e conformidade clínica"}')

echo "$RESPONSE_PATCH" | python3 -m json.tool
```

**Comportamento e Resposta esperada (HTTP 200 OK síncrono):**
- O Scout executa obrigatoriamente exatamente 1 nova consulta SERP Jina formulada pela IA a partir do tema original e do feedback.
- A IA preserva pontos não afetados e ajusta/acrescenta foco conforme as novas evidências.
- Uma nova versão revisada é gerada em `briefing_versions`.
- **Início Automático:** Na mesma operação, o sistema aprova e inicia a investigação automaticamente em background: os pontos revisados são salvos em `research_points` com status `SCRAPER_IN_PROGRESS` (`attempt_count = 0`), a pesquisa passa a `SCRAPER` e os workers são despachados em background.
- O cliente recebe a resposta síncrona HTTP 200 contendo o briefing revisado (`version: 2`), sem necessidade de chamar `/investigate` e sem confirmação intermediária.

#### Passo 3B: Verificar Bloqueio de Segunda Revisão

Tente enviar um segundo feedback para a mesma pesquisa:

```bash
curl -sS -i -X PATCH "http://localhost:8000/briefings/$RESEARCH_ID" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"note": "Tentativa de segunda revisão não permitida"}'
```

**Resposta esperada (HTTP 409 Conflict):**
O sistema rejeita com HTTP 409 Conflict, pois a revisão por feedback é estritamente única.

#### Passo 4B: Verificar Bloqueio de Chamada Redundante a `/investigate`

Como a investigação já foi iniciada automaticamente pelo PATCH, qualquer chamada subsequente a `/investigate` é recusada:

```bash
curl -sS -i -X POST "http://localhost:8000/briefings/$RESEARCH_ID/investigate" \
  -H "$AUTH_HEADER"
```

**Resposta esperada (HTTP 409 Conflict):**
```json
{
  "detail": "Investigação já iniciada ou em andamento para esta pesquisa"
}
```

---

### Passo 5: Acompanhar Execução no Banco de Dados (PostgreSQL)

Consulte os resultados inseridos na tabela `research_step_results` substituindo `$RESEARCH_ID` pelo UUID real capturado no Passo 1:

```sql
-- Dialeto: PostgreSQL (utiliza funções nativas de JSON)
SELECT step_title, worker, status, json_array_length(used_urls::json) as used_count, json_array_length(read_urls::json) as read_count, created_at
FROM research_step_results
WHERE research_id = 'SUBSTITUA_PELO_RESEARCH_ID_REAL'
ORDER BY created_at ASC;
```

**Critérios de validação:**
1. Para 3–7 pontos, são geradas 12–28 linhas de resultado (4 personas por ponto: `historian`, `skeptic`, `pragmatist`, `futurist`); falhas definitivas também geram linha com status `FAILED` e erro sanitizado (máx 500 caracteres).
2. Cada resultado de sucesso possui `status = 'AUDIT_PENDING'`.
3. `read_urls` contém todas as URLs retornadas pela Jina capturadas pelo harness.
4. `used_urls` contém exatamente as fontes citadas pelo modelo na síntese analítica.
5. Ao concluir todos os workers, se pelo menos 1 ponto teve sucesso, a pesquisa transita para `AUDIT`. Se todos os workers de todos os pontos falharem, cada ponto termina em `SCRAPER_FAILED` e a pesquisa termina em `FAILED`.

---

## 3. Validação de Regras de Borda e Falhas

- **Validação de Tema no POST (Q13)**: O tema deve ter entre 3 e 300 caracteres após strip. Submeter tema com 301 caracteres retorna HTTP 422 com mensagem explícita informando o limite de 300 antes de qualquer processamento.
- **Títulos Longos sem Teto de 500 (Q11)**: Títulos gerados pelo Scout com mais de 500 caracteres são aceitos e gravados integralmente em coluna `sa.Text` em `research_points` e `research_step_results`.
- **Falhas Terminais no PATCH (Q12, Q16)**: Se a busca SERP Jina ou a geração do briefing revisado falhar de forma terminal após esgotar retries: a API responde HTTP 500 (configuração LLM), HTTP 502 (geração LLM indisponível) ou HTTP 503 (busca Jina indisponível); a pesquisa transita para `FAILED`, o briefing para `failed`, nenhuma investigação é iniciada, e nova tentativa exige novo `POST /briefings`.
- **Tentativa de Reabertura (`/reopen`)**: Chamar `POST /briefings/{research_id}/reopen` em pesquisa já aprovada ou em `SCRAPER` retorna HTTP 409 Conflict.
- **Extinção de `/approve`**: O endpoint `POST /briefings/{research_id}/approve` não existe no sistema; qualquer chamada resulta em erro de rota inexistente (HTTP 404/405), sem nenhum impacto de negócio.
