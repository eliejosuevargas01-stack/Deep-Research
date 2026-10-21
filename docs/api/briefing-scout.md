# Módulo de Briefing / Scout — Referência de API

> [!IMPORTANT]
> **Diretrizes aprovadas vigentes (2026-10-19):** Esta API reflete as diretrizes normativas do adendo `../../_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md` (DIRETRIZES APROVADAS). A implementação em código (`app/`) e sua verificação operacional permanecem **não executadas/não verificadas** nesta sprint documental. Em caso de divergência com textos legados, as diretrizes do adendo possuem precedência normativa.

> Documentação canônica da API de Briefings do Deep Research Engine.
>
> Conforme: `docs/standards/api-docs-standard.md` (v1, snake_case, RFC 9457, envelopes).

---

## 1. Visão Geral & Casos de Uso

> [!NOTE]
> O Módulo de Briefing / Scout é o **primeiro estágio** do pipeline de pesquisa: transforma um tema em um conjunto de 3 a 7 pontos de foco estruturados, que alimentam as etapas de pesquisa paralela (workers) e auditoria subsequente.

**Objetivo:** dado um tema (3 a 300 caracteres), gerar um *briefing* — lista de pontos com `title` e `description` — orientando uma pesquisa futura. Não responde ao tema nem apresenta conclusão.

**Papel do Scout:** atua como **explorador cognitivo**. Executa duas buscas em sequência:

1. **Busca SERP via Jina** (`https://s.jina.ai/`): consulta a API Jina Search e coleta resultados orgânicos para o tema informado.
2. **LLM (role `scout`):** processa os resultados SERP com um *prompt de sistema* (`app/prompts/briefing.md`) e um *prompt de usuário* estruturado, gerando **3 a 7 pontos centrais**. O modelo padrão é `gemini/gemini-3.8-flash`, resolvido em runtime via `AppSettings` (role `scout`).

**Casos de uso:**

| Caso | Descrição |
|---|---|
| Criação de briefing | `POST /briefings` — gera briefing a partir de tema (201 síncrono) |
| Revisão única por feedback | `PATCH /briefings/{research_id}` — revisa, aprova e inicia investigação (200 síncrono) |
| Aprovação implícita direta | `POST /briefings/{research_id}/investigate` — aprova e inicia investigação (202 background) |
| Consumo | Leitura do briefing aprovado por downstream |
| Auditoria | Histórico de versões (v1, v2, …) |
| Integração | Consumo via API por workers paralelos |

> [!TIP]
> A geração é **síncrona no transporte HTTP**: `POST /briefings` retorna `201` apenas após a orquestração completar (Tx1 + Tx2). Internamente o backend usa corrotinas `async/await` normais — sem background task desvinculada, sem fila, sem polling do cliente. Consulte `GET /briefings/{research_id}` apenas para ler o snapshot corrente, não para aguardar conclusão.

---

## 2. Autenticação & Headers

Todos os endpoints exigem autenticação. O mecanismo de credencial é **exclusivo** — nunca envie mais de um tipo por requisição:

| Tipo | Header / Cookie | Observação |
|---|---|---|
| Bearer Token | `Authorization: Bearer <API_AUTH_SECRET>` | Comparação constante de tempo (`hmac.compare_digest`) |
| API Key | `X-API-Key: <API_AUTH_SECRET>` | Alternativa sem `Authorization` |
| Cookie Admin | `Cookie: dr_session=<JWT>` + `X-CSRF-Token: <csrf>` | Obrigatório para mutations (`POST/PUT/PATCH/DELETE`) |

> [!WARNING]
> Headers de identidade de tenant (`x-tenant-id`) são rejeitados com `400`. Múltiplas credenciais simultaneamente retornam `400` (ambíguo).

**Headers recomendados para todas as requisições:**

```http
Accept: application/json
Content-Type: application/json
```

---

## 3. Quickstart cURL

Fluxo completo passo a passo:

### Passo 1 — Criar briefing e aguardar draft

```bash
BRIEFING_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $API_AUTH_SECRET" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  https://api.deepresearchengine.com/v1/briefings \
  -d '{"theme": "impacto da IA na medicina"}' \
  -w '\n%{http_code}' \
  | awk 'NR==1{print;}' )

echo "Briefing ID: $BRIEFING_ID"
```

### Passo 2 — Consultar status

```bash
curl -s \
  -H "Authorization: Bearer ***" \
  -H "Accept: application/json" \
  https://api.deepresearchengine.com/v1/briefings/$BRIEFING_ID | jq '.'
```

(Opcional) `GET /briefings/{research_id}` apenas para ler o snapshot — geração já concluída no `201` do POST.

### Passo 3 — ESCOLHA UMA ÚNICA VIA (não use ambas)

> [!IMPORTANT]
> **Vias exclusivas (A ou B, nunca sequência):**
> - **Via A:** `PATCH /briefings/{research_id}` — Revisar briefing via feedback único (só uma vez). Retorna **200 OK** síncrono com o briefing revisado final e **aprova e inicia a investigação automaticamente em background** na mesma operação (sem segunda chamada a `/investigate`).
> - **Via B:** `POST /briefings/{research_id}/investigate` — Aprovar implicitamente e iniciar investigação (draft → SCRAPER). Retorna **202 Accepted** e dispara a investigação em background.

#### Via A — Revisar briefing via feedback único (só uma vez)

```bash
curl -s -X PATCH \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  https://api.deepresearchengine.com/v1/briefings/$BRIEFING_ID \
  -d '{"note": "Aprofundar riscos regulatórios"}' | jq '.'
```

> [!NOTE]
> O PATCH revisa o briefing, aprova e inicia a investigação automaticamente em background na mesma operação. A resposta HTTP 200 traz o briefing revisado. Uma segunda tentativa de PATCH retorna `409 Conflict`.

#### Via B — Aprovar implicitamente e iniciar investigação

```bash
curl -s -X POST \
  -H "Authorization: Bearer ***" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  https://api.deepresearchengine.com/v1/briefings/$BRIEFING_ID/investigate \
  -d '{}' | jq '.'
```

> [!NOTE]
> Retorna HTTP 202 Accepted com `{"research_id": "...", "status": "SCRAPER", "message": "Investigação iniciada em background"}`.

> [!TIP]
> Se o `POST /briefings` (Passo 1) já retornou `status: "failed"` no corpo da resposta 201, **não prossiga para nenhuma das vias** — a geração do briefing falhou terminalmente (prompt/SERP/LLM/config). A investigação não será iniciada.

### Passo 5 — Consumir aprovado via GET /briefings/approved/{research_id}

```bash
curl -s \
  -H "Authorization: Bearer ***" \
  -H "Accept: application/json" \
  https://api.deepresearchengine.com/v1/briefings/approved/$BRIEFING_ID | jq '.'
```

---

## 4. Ciclo de Vida da Entidade

```mermaid
stateDiagram-v2
    [*] --> generating: POST /briefings
    generating --> draft: conclusão OK (geração de pontos)
    generating --> failed: erro (prompt/SERP/LLM/config)
    draft --> approved: POST /investigate
    draft --> approved: PATCH (revisão única)
    failed --> [*]: terminal
    approved --> [*]: terminal

    note right of approved
      POST /reopen proibido (409)
    end note

    note right of draft
      PATCH /briefings/{research_id}
      revisão única por feedback
    end note
```

**Regras de transição (domain.py):**

| De | Para | Trigger | Condição |
|---|---|---|---|
| `generating` | `draft` | geração concluída | 3–7 pontos válidos |
| `generating` | `failed` | erro interno/SERP/LLM | mensagem de erro fixa |
| `draft` | `approved` | `POST /briefings/{research_id}/investigate` | aprovação implícita; inicia investigação |
| `draft` | `approved` | `PATCH /briefings/{research_id}` | revisão única por feedback; aprova e inicia investigação |
| `approved` | `approved` | `POST /briefings/{research_id}/reopen` | **409**, sem mutação |
| `failed` | (qualquer) | — | **terminal**, requer nova criação |

**Controle de versão:**

- Versão inicia em `v1` (status `generating`).
- Cada transição atômica **incrementa a versão** monotonicamente: `complete_briefing`, `edit_briefing`, `approve_briefing`, `fail_briefing`. **`reopen_briefing` é proibido para briefings aprovados (409, sem mutação).**
- Histórico append-only em `briefing_versions`, ordenado por `version ASC`.
- `GET /briefings/{research_id}/versions` retorna **v2 em diante** (transições pós-criação).

**Concorrência (CAS):**

- `save_briefing_transition` usa `UPDATE ... WHERE id = ? AND version = old_version`.
- Colisão (`rowcount != 1`) eleva `BriefingVersionConflictError` → **`409 Conflict`**.
- Cliente deve reler estado/versão corrente e reconciliar; conflito não autoriza segunda revisão nem reenvios cegos.

---

## 5. Referência dos Endpoints HTTP

### `POST /briefings` — Criar briefing

Cria e orquestra a geração do briefing do tema informado.

| Campo | Tipo | Obrigatório | Default | Descrição |
|---|---|---|---|---|
| `theme` | `string` | Sim | — | Tema do briefing. **3–300 caracteres** após trim. |

**Resposta — `201 Created`:**

```json
{
  "research_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "theme": "impacto da IA na medicina",
  "status": "draft",
  "points": [
    {
      "title": "Diagnóstico assistido por IA",
      "description": "Modelos de imagem médica para detecção precoce de patologias."
    },
    {
      "title": "Eficiência hospitalar",
      "description": "Automação de triage e otimização de fluxos de pacientes."
    },
    {
      "title": "Ética e vieses algorítmicos",
      "description": "Riscos de discriminação em decisões clínicas automatizadas."
    },
    {
      "title": "Regulamentação",
      "description": "Quadros normativos internacionais para validação de IA clínica."
    },
    {
      "title": "Adoção clínica",
      "description": "Barreiras de implementação em ambientes reais de saúde."
    }
  ],
  "version": 2,
  "error": null,
  "approved_at": null
}
```

> [!NOTE]
> A geração é **síncrona no transporte HTTP**: `POST /briefings` retorna `201` apenas após a conclusão da geração (Tx1 + Tx2). Internamente usa `async/await` nativo — sem background task, sem polling. Briefing é SERP-only (sem páginas); 10 páginas integrais aplica-se apenas aos workers. Se falhar, o briefing fica com `status: "failed"` e `error` populado, retornado também com `201`.

---

### `GET /briefings/{research_id}` — Consultar snapshot corrente

Retorna o estado corrente do briefing.

| Parâmetro | Tipo | Local | Obrigatório | Descrição |
|---|---|---|---|---|
| `research_id` | `uuid` | path | Sim | UUID da pesquisa (identificador canônico compartilhado) |

**Resposta — `200 OK`:**

```json
{
  "research_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "theme": "impacto da IA na medicina",
  "status": "draft",
  "points": [
    {
      "title": "Diagnóstico assistido por IA",
      "description": "Modelos de imagem médica para detecção precoce de patologias."
    }
  ],
  "version": 2,
  "error": null,
  "approved_at": null
}
```

---

### `PATCH /briefings/{research_id}` — Revisar briefing via feedback único (só uma vez)

Revisa o briefing em status `draft` via Scout, aprovando e iniciando a investigação automaticamente na mesma operação. O agente Scout reavalia os pontos com base no feedback (`note`), gera a nova versão, persiste em `briefing_versions`, aprova o briefing e dispara a investigação em background. Uma segunda tentativa de PATCH retorna `409 Conflict`.

> [!IMPORTANT]
> **Vias exclusivas:** `PATCH /briefings/{research_id}` e `POST /briefings/{research_id}/investigate` são caminhos **exclusivos** para avançar a partir do `draft`. O cliente deve escolher uma única via; acionar ambas sobre o mesmo draft resulta em `409 Conflict`. Em `409 Conflict`, reler o estado e a versão correntes para reconciliar. Se o briefing já estiver aprovado ou revisado, a requisição não deve ser repetida. Conflito CAS não autoriza segunda revisão nem nova tentativa de criação.

| Parâmetro | Tipo | Local | Obrigatório | Descrição |
|---|---|---|---|---|
| `research_id` | `uuid` | path | Sim | UUID da pesquisa (compatível com `id` do briefing) |

| Campo | Tipo | Obrigatório | Default | Descrição |
|---|---|---|---|---|
| `note` | `string` | Sim | — | Texto de feedback para o Scout. **3–4000 caracteres** após trim. |

**Resposta — `200 OK`:**

```json
{
  "research_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "theme": "impacto da IA na medicina",
  "status": "approved",
  "points": [
    {
      "title": "Diagnóstico assistido por IA revisado",
      "description": "Modelos de imagem médica para detecção precoce com feedback incorporado."
    }
  ],
  "version": 3,
  "error": null,
  "approved_at": "2025-01-15T10:30:00Z"
}
```

> [!NOTE]
> Ilustração apenas: a resposta HTTP 200 do PATCH aprova e inicia a investigação na mesma operação. Os valores de status e approved_at neste exemplo são ilustrativos da transição efetuada.

---

### `POST /briefings/{research_id}/investigate` — Aprovar briefing e iniciar investigação

Aprova o briefing em status `draft` implicitamente e dispara a investigação em background. A pesquisa transita para `SCRAPER` e os pontos são persistidos em `SCRAPER_IN_PROGRESS`. Define `approved_at` e incrementa a versão.

> [!IMPORTANT]
> **Vias exclusivas de revisão/aprovação:** O operador deve escolher **uma única via** para avançar do draft:
> - `PATCH /briefings/{research_id}` (revisão única por feedback), **ou**
> - `POST /briefings/{research_id}/investigate` (aprovação implícita direta).
>
> Acionar ambas em sequência sobre o mesmo draft produz `409 Conflict`. Em `409 Conflict`, reler o estado e a versão correntes e reconciliar. Se o briefing já estiver aprovado ou revisado, a requisição não deve ser repetida; conflito CAS não autoriza segunda revisão nem nova tentativa de criação automática.

| Parâmetro | Tipo | Local | Obrigatório | Descrição |
|---|---|---|---|---|
| `research_id` | `uuid` | path | Sim | UUID da pesquisa (identificador canônico compartilhado) |

O corpo da requisição é **aceito vazio** (`{}`, `null` ou corpo vazio). A validação usa `_parse_empty_body` que aceita:

- Corpo vazio
- `{}` (objeto vazio)
- `null`

**Resposta — `202 Accepted`:**

```json
{
  "research_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "SCRAPER",
  "message": "Investigação iniciada em background"
}
```

---

### `POST /briefings/{research_id}/reopen` — Reabrir briefing aprovado

Reabertura de briefing aprovado **proibida**: em briefing com status `approved`, o endpoint retorna **`409 Conflict`** sem alterar `status`, `version` ou `approved_at`.

| Parâmetro | Tipo | Local | Obrigatório | Descrição |
|---|---|---|---|---|
| `research_id` | `uuid` | path | Sim | UUID da pesquisa (compatível com `id` do briefing) |

Corpo: aceito vazio (`{}`, `null` ou vazio), conforme contrato.

**Resposta — `409 Conflict` (briefing em status `approved`):**

```json
{
  "detail": "Briefing aprovado não pode ser reaberto"
}
```

> [!IMPORTANT]
> Em briefing **não aprovado** (ex.: `draft`), a operação também retorna **`409 Conflict`**, pois a reabertura apenas é inválida a partir de um briefing aprovado.

```json
{
  "detail": "Briefing não aprovado. Apenas briefings aprovados podem ser reabertos."
}
```

---

### `GET /briefings/approved/{research_id}` — Consumir aprovado (read-only)

Endpoint read-only para consumo de briefing aprovado. Retorna `409` se não estiver aprovado.

| Parâmetro | Tipo | Local | Obrigatório | Descrição |
|---|---|---|---|---|
| `research_id` | `uuid` | path | Sim | UUID da pesquisa (identificador canônico compartilhado) |

**Resposta — `200 OK`:**

```json
{
  "research_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "theme": "impacto da IA na medicina",
  "points": [
    {
      "title": "Diagnóstico assistido por IA",
      "description": "Modelos de imagem médica para detecção precoce de patologias."
    }
  ],
  "approved_at": "2025-01-15T10:30:00Z"
}
```

> [!IMPORTANT]
> Este endpoint retorna apenas briefings com `status: "approved"`. Briefings em `draft`, `generating` ou `failed` retornam `409 Conflict`.

---

### `GET /briefings/{research_id}/versions` — Listar histórico de versões

Lista o histórico append-only de versões do briefing, ordenado por `version ASC`.

| Parâmetro | Tipo | Local | Obrigatório | Descrição |
|---|---|---|---|---|
| `research_id` | `uuid` | path | Sim | UUID da pesquisa (identificador canônico compartilhado) |

**Resposta — `200 OK`:**

```json
[
  {
    "version": 2,
    "status": "draft",
    "points": [
      {
        "title": "Diagnóstico assistido por IA",
        "description": "Modelos de imagem médica para detecção precoce de patologias."
      }
    ],
    "error": null,
    "approved_at": null,
    "created_at": "2025-01-15T10:29:45Z"
  },
  {
    "version": 3,
    "status": "approved",
    "points": [
      {
        "title": "Diagnóstico assistido por IA",
        "description": "Modelos de imagem médica para detecção precoce de patologias."
      }
    ],
    "error": null,
    "approved_at": "2025-01-15T10:30:00Z",
    "created_at": "2025-01-15T10:30:01Z"
  }
]
```

> [!TIP]
> Apenas versões **v2 em diante** são retornadas. A versão `v1` (`generating`) é o ponto de origem e não aparece no histórico de transições.

---

### Sumário de Endpoints

| Método | Rota | Status sucesso | Descrição |
|---|---|---|---|
| `POST` | `/briefings` | `201` | Criar e orquestrar geração |
| `GET` | `/briefings/{research_id}` | `200` | Snapshot corrente |
| `PATCH` | `/briefings/{research_id}` | `200` | Revisar por feedback único (só uma vez) |
| `POST` | `/briefings/{research_id}/investigate` | `202` | Aprovar implicitamente e iniciar investigação (background) |
| `POST` | `/briefings/{research_id}/reopen` | `409` | Reabertura de aprovado proibida; sem mutação |
| `GET` | `/briefings/approved/{research_id}` | `200` | Consumir aprovado |
| `GET` | `/briefings/{research_id}/versions` | `200` | Histórico de versões |

---

## 6. Matriz de Tratamento de Erros

> [!NOTE]
> Todos os erros seguem **RFC 9457** (Problem Details). Corpo: `{"detail": "<mensagem segura>"}`.
>
> **Nenhum segredo** (API keys, tokens, payloads de LLM) é exposto nas mensagens de erro.

| Código | Causa | Comportamento de retry | Exemplo de payload |
|---|---|---|---|
| `400` | Header `x-tenant-id` proibido; múltiplas credenciais | Não (corrigir cliente) | `{"detail": "Client tenant headers are prohibited"}` |
| `400` | Credenciais ambíguas | Não | `{"detail": "Ambiguous authentication: multiple credential types supplied"}` |
| `401` | Bearer token inválido; API key inválida; sessão expirada/inexistente; cookie ausente | Não (reenviar credencial válida) | `{"detail": "Invalid or missing Bearer token"}` |
| `403` | CSRF token ausente ou inválido (mutations) | Não (reenviar CSRF válido) | `{"detail": "CSRF validation failed"}` |
| `404` | Briefing não encontrado | Não | `{"detail": "Briefing não encontrado"}` |
| `409` | Conflito de versão CAS (edição concorrente) | Não — reler estado/versão corrente e reconciliar; se já aprovado/revisado, não repetir | `{"detail": "Conflito de versão do briefing"}` |
| `409` | Briefing não aprovado em `GET /briefings/approved/{research_id}` | Não (aguarde aprovação) | `{"detail": "Briefing não está aprovado"}` |
| `409` | Transição inválida (ex: editar approved) | Não | `{"detail": "Briefing não pode ser editado neste estado"}` |
| `422` | Theme < 3 ou > 300 chars | Não (corrigir tema) | `{"detail": "Conteúdo de briefing inválido"}` |
| `422` | Pontos fora de 3–7; título/description vazios | Não (corrigir payload) | `{"detail": "Pontos de briefing inválidos"}` |
| `422` | Body inválido em investigate/reopen | Não | `{"detail": "Corpo inválido"}` |
| `500` | Prompt de briefing indisponível | Sim — retry exponencial (≤4 tentativas) | `{"detail": "Prompt de briefing indisponível"}` |
| `500` | Erro interno na geração (timeout de configuração) | Sim — retry exponencial (≤4 tentativas) | `{"detail": "Erro interno ao gerar briefing"}` |
| `500` | Erro de configuração de provedor LLM (auth) | Sim — verificar credenciais, retry (≤4 tentativas) | `{"detail": "Erro interno ao gerar briefing"}` |
| `503` | Busca SERP indisponível (Jina) | Sim — retry exponencial (≤4 tentativas) | `{"detail": "Busca SERP indisponível"}` |
| `503` | Geração LLM indisponível (4 tentativas esgotadas) | Sim — retry exponencial (≤4 tentativas) | `{"detail": "Geração de briefing indisponível"}` |

> [!TIP]
> **Retry recomendado:** exponencial com jitter, máximo 4 tentativas (para 500/503). Erros `409` não são retriáveis: reler estado/versão corrente e reconciliar. Se o briefing já estiver aprovado ou revisado, não repetir a requisição.

---

## 7. Guia de Configuração & Variáveis de Ambiente

### Variáveis do container `.env`

| Variável | Tipo | Obrigatório | Default | Descrição |
|---|---|---|---|---|
| `API_AUTH_SECRET` | `string` | Sim | — | Segredo para Bearer token / API key |
| `ADMIN_PASSWORD` | `string` | Sim | — | Senha do admin (hashing via `digest` HMAC-SHA256) |
| `SESSION_SECRET` | `string` | Sim | — | Segredo para JWT (`dr_session`) |
| `DATABASE_URL` | `string` | Sim | — | URL de conexão ao banco (SQLite por padrão) |
| `JINA_API_KEY` | `string` | Sim | — | Chave da API Jina Search (SERP) |
| `GEMINI_API_KEY` | `string` | Sim | — | Chave da API Gemini (role `scout`) |
| `SEARCH_TIMEOUT_SECONDS` | `float` | Não | `30` | Timeout por tentativa SERP/LLM |
| `SESSION_TTL_HOURS` | `int` | Não | `1` | TTL do cookie de sessão admin |
| `LITELLM_API_BASE` | `string` | Não | — | URL base customizada para LiteLLM |

### Configuração em runtime via `AppSettings` (`/settings`)

O modelo do Scout e as chaves de provedor são resolvidos **em runtime** a cada requisição via `runtime_settings(db)`, que lê da tabela `AppSettings`:

| Role | Modelo padrão | Provider | Chave em `AppSettings` |
|---|---|---|---|
| `scout` | `gemini/gemini-3.8-flash` | `gemini` | `GEMINI_API_KEY` |

> [!IMPORTANT]
> O modelo `gemini/gemini-3.8-flash` é o padrão para a role `scout`. Altere via rota `/settings` sem redeploy.

**Exemplo de payload de configuração runtime:**

```json
{
  "models": {
    "scout": "gemini/gemini-3.8-flash"
  },
  "keys": {
    "gemini": "GEMINI_API_KEY",
    "jina": "JINA_API_KEY"
  }
}
```

---

## 8. Exemplo Prático de Código

> [!TIP]
> Exemplo completo e testável com `httpx` assíncrono. Substitua `$API_AUTH_SECRET` e ajuste a URL base.

```python
import asyncio
import os
import httpx

BASE = "https://api.deepresearchengine.com/v1"
H = {
    "Authorization": f"Bearer {os.environ['API_AUTH_SECRET']}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        # 1. Criar briefing (síncrono: 201 já traz o draft completo)
        resp = await client.post(
            f"{BASE}/briefings",
            headers=H,
            json={"theme": "impacto da IA na medicina"},
        )
        assert resp.status_code == 201, resp.text
        briefing = resp.json()
        briefing_id = briefing["research_id"]
        print(f"Briefing criado: {briefing_id} | status: {briefing['status']}")

        # Se falhou na geração síncrona, não avança para investigação
        if briefing.get("status") == "failed":
            print(f"Falha na geração do briefing: {briefing.get('error')}")
            return

        # 3. ESCOLHA UMA ÚNICA VIA (não use ambas)
        #    A) Revisar via feedback único — aprova e inicia investigação automaticamente
        # resp = await client.patch(
        #     f"{BASE}/briefings/{briefing_id}",
        #     headers=H,
        #     json={"note": "Aprofundar riscos regulatórios"},
        # )
        # assert resp.status_code == 200, resp.text

        #    B) OU aprovar implicitamente e iniciar investigação
        resp = await client.post(
            f"{BASE}/briefings/{briefing_id}/investigate",
            headers=H,
            json={},
        )
        assert resp.status_code == 202, resp.text
        approved = resp.json()
        print(f"Investigando: {approved['status']} | {approved['message']}")

        # 4. Consumir aprovado
        resp = await client.get(
            f"{BASE}/briefings/approved/{briefing_id}",
            headers=H,
        )
        assert resp.status_code == 200, resp.text
        consumed = resp.json()
        print(f"Consumido: {consumed['theme']}")
        for p in consumed["points"]:
            print(f"  • {p['title']}")

        # 5. Listar versões
        resp = await client.get(
            f"{BASE}/briefings/{briefing_id}/versions",
            headers=H,
        )
        versions = resp.json()
        print(f"Histórico: {len(versions)} versões")


if __name__ == "__main__":
    asyncio.run(main())
```

**Saída esperada:**

```text
Briefing criado: a1b2c3d4-... | status: draft
Investigando: SCRAPER | Investigação iniciada em background
Consumido: impacto da IA na medicina
  • Diagnóstico assistido por IA
  • Eficiência hospitalar
  • Ética e vieses algoritmos
  • Regulamentação
  • Adoção clínica
Histórico: 2 versões
```

---

## Navegação

| Direção | Link |
|---|---|
| Padrão de docs | `docs/standards/api-docs-standard.md` |
| API de jobs (pipeline) | `docs/api/jobs.md` |
| Arquitetura geral | `README.md` |
