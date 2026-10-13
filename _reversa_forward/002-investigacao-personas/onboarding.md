# Onboarding: Investigação Paralela por Personas (Feature 002)

> Guia executável para validação manual e automatizada da Feature 002.

---

## 1. Pré-requisitos e Configuração

Certifique-se de que a aplicação possui credenciais válidas configuradas via `PUT /api/settings`:
- Chave da Jina (`provider_keys.jina`) ou URL de proxy configurada.
- Chave de LLM configurada (`provider_keys.openai` ou gateway compatível) com modelos para as personas ou fallback no `scout`.

---

## 2. Passo a Passo do Fluxo de Teste

### Passo 1: Criar o Briefing (Scout)

Envie uma requisição para gerar o briefing inicial com um tema:

```bash
curl -s -X POST https://research.dominuslabs.online/briefings \
  -H "Authorization: Bearer $API_AUTH_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"theme": "Impacto da IA Generativa na Medicina Diagnóstica"}'
```

**Resposta esperada (HTTP 201):**
```json
{
  "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "theme": "Impacto da IA Generativa na Medicina Diagnóstica",
  "status": "draft",
  "points": [
    {"title": "Precisão em Imagens", "description": "Investigar acurácia em imagens..."},
    {"title": "Decisão Clínica", "description": "Examinar apoio à decisão..."}
  ],
  "version": 1,
  "error": null,
  "approved_at": null
}
```

*Nota:* O identificador retornado é `research_id`, que já foi registrado na tabela `research` com status `PENDING_APPROVAL`.

---

### Passo 2: Aprovar o Briefing

Aprove o briefing gerado:

```bash
curl -s -X POST https://research.dominuslabs.online/briefings/3fa85f64-5717-4562-b3fc-2c963f66afa6/approve \
  -H "Authorization: Bearer $API_AUTH_SECRET"
```

**Resposta esperada (HTTP 200):**
Status do briefing passa para `approved`. No banco de dados:
- `research.status` transita para `SCRAPER`.
- Os pontos são instanciados em `research_points` com status `SCRAPER_PENDING`.

---

### Passo 3: Disparar a Investigação Paralela

Dispare os workers para investigar os passos aprovados:

```bash
curl -s -X POST https://research.dominuslabs.online/briefings/3fa85f64-5717-4562-b3fc-2c963f66afa6/investigate \
  -H "Authorization: Bearer $API_AUTH_SECRET"
```

**Resposta esperada (HTTP 202 Accepted):**
```json
{
  "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "SCRAPER",
  "message": "Investigação iniciada em background"
}
```

---

### Passo 4: Verificar Idempotência (Re-disparo)

Tente disparar a investigação novamente com o mesmo ID:

```bash
curl -s -i -X POST https://research.dominuslabs.online/briefings/3fa85f64-5717-4562-b3fc-2c963f66afa6/investigate \
  -H "Authorization: Bearer $API_AUTH_SECRET"
```

**Resposta esperada (HTTP 409 Conflict):**
```json
{
  "detail": "Investigação já iniciada ou em andamento para esta pesquisa"
}
```

---

### Passo 5: Acompanhar Execução no Banco de Dados

Consulte os resultados inseridos na tabela `research_step_results`:

```sql
SELECT step_title, worker, status, json_array_length(used_urls::json) as used_count, json_array_length(read_urls::json) as read_count, created_at
FROM research_step_results
WHERE research_id = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
ORDER BY created_at ASC;
```

**Critérios de validação:**
1. Para 5 passos, existem até 20 registros produzidos (4 por passo: `historian`, `skeptic`, `pragmatist`, `futurist`).
2. Cada resultado de sucesso possui `status = 'AUDIT_PENDING'`.
3. `read_urls` contém todas as fontes retornadas pela Jina (capturadas pelo harness).
4. `used_urls` contém as fontes que o modelo citou no resultado.
5. Ao concluir todos os workers, `research.status` transita para `AUDIT`.
