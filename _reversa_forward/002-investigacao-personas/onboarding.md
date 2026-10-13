# Onboarding: Investigação Paralela por Personas (Feature 002)

> Guia executável para validação manual e automatizada da Feature 002.

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

*Nota:* O identificador retornado é `research_id`, que já foi registrado na tabela `research` com status `PENDING_APPROVAL`.

---

### Passo 2: Aprovar o Briefing

Aprove o briefing gerado utilizando a variável `$RESEARCH_ID`:

```bash
curl --fail-with-body -sS -X POST "http://localhost:8000/briefings/$RESEARCH_ID/approve" \
  -H "$AUTH_HEADER"
```

**Resposta esperada (HTTP 200):**
Status do briefing passa para `approved`. No banco de dados:
- `research.status` transita para `SCRAPER`.
- Os pontos são instanciados em `research_points` com status `SCRAPER_PENDING` e `attempt_count = 0`.
- A aprovação **não** agenda `schedule(run_research)` nem qualquer pipeline legado (Q1). A pesquisa aguarda disparo exclusivo por `POST /briefings/{research_id}/investigate`.

---

### Passo 3: Disparar a Investigação Paralela

A aprovação não agenda investigação automaticamente, inclusive no fluxo legado/revisão: Q1 remove `schedule(run_research)`. Disparo exclusivo pelo endpoint abaixo. Com 3–7 pontos aprovados, espera-se 12–28 workers (4 personas por ponto).

Dispare os workers para investigar os pontos aprovados:

```bash
curl --fail-with-body -sS -X POST "http://localhost:8000/briefings/$RESEARCH_ID/investigate" \
  -H "$AUTH_HEADER"
```

**Formato ilustrativo da resposta HTTP 202 Accepted; `$RESEARCH_ID` representa o UUID retornado, não uma string literal enviada pela API:**
```json
{
  "research_id": "$RESEARCH_ID",
  "status": "SCRAPER",
  "message": "Investigação iniciada em background"
}
```

---

### Passo 4: Verificar Idempotência (Re-disparo)

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
1. Para 3–7 pontos, até 12–28 linhas de resultado (4 personas por ponto); falhas definitivas também geram linha.
2. Cada resultado de sucesso possui `status = 'AUDIT_PENDING'`.
3. `read_urls` contém URLs retornadas pela Jina; não prova leitura integral nem citação verbatim.
4. `used_urls` contém as fontes que o modelo citou no resultado.
5. Ao concluir todos os workers, `research.status` transita para `AUDIT` se algum ponto teve sucesso.

### Falha global esperada

Se todos os workers de todos os pontos falharem definitivamente, cada ponto termina `SCRAPER_FAILED` e `research.status` termina `FAILED` (não `AUDIT`).

### Validação de título e contrato de edição

- **Edição por feedback (`PATCH /briefings/$RESEARCH_ID`)**: Aceita exclusivamente o corpo `{"note": "texto do feedback"}` (entre 3 e 4000 caracteres). Não existe entrada manual de pontos no PATCH.
- **Comprimento de título e validação de tema**: Títulos de pontos gerados pelo Scout não possuem limite de 500 caracteres (Q11; regra Q6 revogada); o sistema aceita e persiste o título integral, e `research_points.title` / `research_step_results.step_title` passam a `sa.Text` na migração 007. O tema da pesquisa informado pelo operador possui limite de 3 a 300 caracteres (Q13); entradas acima de 300 caracteres são rejeitadas com HTTP 422 e mensagem explícita sobre o limite.
