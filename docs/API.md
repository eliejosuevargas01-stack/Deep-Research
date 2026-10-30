# API — Deep Research

Contrato HTTP da versão `0.1.0`. Base local: `http://127.0.0.1:8010`. Em Docker Compose: `http://127.0.0.1:8085`.

- Swagger: `GET /docs`
- OpenAPI: `GET /openapi.json`
- Prefixo de negócio: `/api/v1`

---

## 1. Convenções

### Autenticação

| Forma | Uso |
| :--- | :--- |
| Cookie `dr_local_session` | Interface web em loopback; emitido por `GET /app/session` (`HttpOnly`, `SameSite=Strict`, 24 h) |
| `X-API-Key: <chave>` | Integrações, quando `API_SECRET_KEY` está configurada |
| `Authorization: Bearer <chave>` | Equivalente ao header acima |
| `?token=<chave>` ou `?api_key=<chave>` | Apenas `GET`/`HEAD`, necessário para `EventSource` |

Sem `API_SECRET_KEY` e sem cookie válido, as rotas `/api/v1/*` ficam abertas (modo desenvolvimento). Requisições com cookie exigem `Origin`/`Referer` de mesma origem.

### Corpo e respostas

- Entrada e saída em `application/json; charset=utf-8`.
- Erros de regra: `{"detail": "mensagem"}` ou `{"detail": {"tipo": "...", ...}}`.
- Erros de validação Pydantic: `422` com `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.
- Exceção inesperada: `500` com `{"detail": "Erro interno do servidor."}`.

### Códigos comuns

| Código | Significado |
| :---: | :--- |
| `200` | Operação concluída |
| `201` | Plano criado (modo síncrono) |
| `202` | Plano criado e pipeline assíncrono agendado |
| `400` | Requisição inválida (estado ou parâmetro) |
| `401` | Chave ausente/inválida |
| `403` | Origem divergente ou sessão cross-site |
| `404` | Pesquisa/ponto não encontrado |
| `409` | Execução concorrente ou lease de outro processo |
| `422` | Validação semântica/estrutural |
| `500` | Erro interno ou configuração ausente |
| `502` | Falha do provedor LLM/Jina |
| `504` | Timeout de LLM, Jina ou estágio |

---

## 2. `POST /api/v1/plan`

Cria o plano de investigação e persiste a pesquisa. **Não executa busca.**

### Requisição

| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `tema` | string | sim | Tema/briefing; mínimo 5 caracteres, sem teto no backend |
| `id_pesquisa` | string | não | UUID pré-existente; se omitido, o servidor gera |
| `async_execute` | boolean | não | `false` (padrão). `true` agenda o pipeline completo e retorna `202` |
| `callback_url` | string | não | URL de webhook específica desta execução |
| `n_pontos` | inteiro | não | Eixos investigativos; inteiro ≥ 1, sem booleanos/float |
| `personas` | string[] | não | Subconjunto não vazio de `historiador`, `visionario`, `cetico`, `futurista` |
| `execution_mode` | string | não | `parallel` (padrão) ou `sequential` |
| `recencia` | string | não | `auto`, `recente`, `24h`, `7d`, `30d`, `12m`, `historico` |

```bash
curl -X POST http://127.0.0.1:8010/api/v1/plan \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: SUA_CHAVE' \
  -d '{
    "tema": "Impacto da IA generativa no mercado de trabalho brasileiro",
    "n_pontos": 4,
    "personas": ["historiador", "cetico", "futurista"],
    "execution_mode": "parallel",
    "recencia": "auto"
  }'
```

### Resposta `201` — `PlanResponse`

```json
{
  "id_pesquisa": "3f6c2b1a-...",
  "tema": "Impacto da IA generativa no mercado de trabalho brasileiro",
  "n_pontos": 4,
  "criado_em": "2026-10-28T20:15:03.123456Z",
  "status_pipeline": "planejado",
  "pontos": [
    {
      "ponto_id": "8a1d...",
      "ponto_n": 1,
      "ponto": "Pergunta principal do eixo",
      "status": "pendente",
      "pontos_fracos": null,
      "reasoning_planejamento": "Raciocínio operacional do planejador",
      "reasoning_auditoria": null,
      "eixo_estruturado": {
        "pergunta_principal": "...",
        "subperguntas": ["..."],
        "hipoteses": ["..."],
        "consultas_iniciais": ["..."],
        "fontes_primarias_desejadas": ["..."],
        "riscos_de_vies": ["..."],
        "evidencias_que_refutariam": ["..."],
        "criterio_de_conclusao": "...",
        "investigabilidade": "...",
        "eixo_essencial": true
      }
    }
  ],
  "plano_estruturado": {
    "pedido_original": "...",
    "pedido_normalizado": "...",
    "publico": "...",
    "formato_entrega": "...",
    "recorte_temporal": null,
    "data_referencia": "2026-10-28",
    "politica_recencia": "auto",
    "pressupostos": ["..."],
    "ambiguidades": [],
    "pergunta_de_esclarecimento": null,
    "eixos": []
  },
  "metadados_modelo": {
    "modelo": "...",
    "recencia": {"modo": "auto", "data_referencia": "2026-10-28"}
  },
  "preferencias": {
    "n_pontos": 4,
    "personas": ["historiador", "cetico", "futurista"],
    "recencia": "auto",
    "data_referencia": "2026-10-28",
    "execution_mode": "parallel"
  }
}
```

Com `async_execute: true` → **`202`** e corpo com `status: "iniciado"`, `mensagem`, `callback_url` e os mesmos campos de plano/pontos.

### Erros

| Código | `detail.tipo` / mensagem | Causa |
| :---: | :--- | :--- |
| `422` | `ambiguidade_bloqueante` | Tema ambíguo; inclui `pergunta_de_esclarecimento` |
| `422` | `PlanContractError` | Plano fora do contrato (quantidade, tipos, duplicatas) |
| `422` | mensagem | Quantidade de pontos divergente do solicitado |
| `502` | `LLMCallError` | Provedor LLM recusou/falhou |
| `502`/`504` | `JinaError` | Falha na descoberta SERP |
| `500` | `CONFIG_ERROR` | `N_PONTOS`/configuração ausente |
| `400` | mensagem | Valor de domínio inválido |

---

## 3. `GET /api/v1/plan/{id_pesquisa}/stream`

SSE com o raciocínio do planejador **durante** o `POST /plan`. O `id_pesquisa` deve ser conhecido pelo cliente antecipadamente (enviado no corpo do `POST`).

- `Content-Type: text/event-stream`
- Eventos: `agent.delta` (`kind: reasoning` ou `content`) e comentários `: keep-alive` a cada 15 s
- Sem snapshot de banco; encerra na desconexão

---

## 4. `POST /api/v1/search`

Executa a coleta web por personas nos pontos pendentes.

### Requisição

| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `id_pesquisa` | string | sim | UUID da pesquisa |
| `ponto_id` | string | não | Reprocessa somente um ponto |
| `personas` | string[] | não | Filtro de personas para retentativa focada |
| `execution_mode` | string | não | `parallel` (padrão) ou `sequential` |

```bash
curl -X POST http://127.0.0.1:8010/api/v1/search \
  -H 'Content-Type: application/json' -H 'X-API-Key: SUA_CHAVE' \
  -d '{"id_pesquisa":"3f6c2b1a-...","execution_mode":"parallel"}'
```

### Resposta `200` — `SearchResponse`

```json
{
  "id_pesquisa": "3f6c2b1a-...",
  "total_pontos_processados": 4,
  "status_pesquisa": "coletado",
  "total_falhas_coleta": 0,
  "resumo_coletas": [
    {
      "ponto_id": "8a1d...",
      "ponto_n": 1,
      "status": "coletado",
      "falha_coleta": false,
      "diagnostico": null,
      "total_urls_lidas": 9,
      "total_urls_fonte": 7,
      "tamanho_conteudo_caracteres": 48213,
      "tentativas": 1,
      "personas": [
        {
          "persona": "historiador",
          "analise": "Síntese da persona",
          "reasoning": null,
          "urls_fonte": ["https://..."],
          "queries_executadas": 3,
          "falha_coleta": false,
          "diagnostico": null,
          "conclusoes": [],
          "lacunas": [],
          "diario_acoes": [],
          "motivo_parada": null,
          "envelopes": []
        }
      ],
      "conteudo_relevante": "...",
      "fontes": {},
      "trechos": {},
      "selecao_contexto": {},
      "recencia": {}
    }
  ]
}
```

`reasoning` é sempre `null` na resposta HTTP; o raciocínio operacional aparece apenas no SSE autenticado.

### Erros

| Código | Causa |
| :---: | :--- |
| `404` | Pesquisa não encontrada ou sem pontos pendentes |
| `400` | Estado/configuração inválida para busca |
| `504` | Timeout do ponto (`TIMEOUT_ERROR`, `re_tentavel: true`) |
| `500` | Falha interna não tratada |

Falhas de persona ou de leitura não derrubam a resposta: são reportadas em `falha_coleta`, `diagnostico` e `total_falhas_coleta`.

---

## 5. `POST /api/v1/audit`

Audita os pontos coletados contra os 12 critérios.

### Requisição

| Campo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `id_pesquisa` | string | sim | UUID da pesquisa |
| `ponto_id` | string | não | Audita somente um ponto |
| `criterios_minimos` | inteiro | não | `10`, `11` (padrão) ou `12` |

```bash
curl -X POST http://127.0.0.1:8010/api/v1/audit \
  -H 'Content-Type: application/json' -H 'X-API-Key: SUA_CHAVE' \
  -d '{"id_pesquisa":"3f6c2b1a-...","criterios_minimos":11}'
```

### Resposta `200` — `AuditResponse`

```json
{
  "id_pesquisa": "3f6c2b1a-...",
  "total_pontos": 4,
  "aprovados": 3,
  "reprovados": 1,
  "status_geral": "auditado",
  "status_pesquisa": "auditado",
  "pronto_para_writer": false,
  "auditorias": [
    {
      "ponto_id": "8a1d...",
      "ponto_n": 1,
      "status": "aprovado",
      "pontuacao_percentual": 91.67,
      "criterios_aprovados": 11,
      "criterios_minimos": 11,
      "valido": true,
      "criterios": [
        {
          "id": 1,
          "aprovado": true,
          "justificativa": "...",
          "claim_ids": ["clm_..."],
          "source_ids": ["src_..."],
          "lacuna": null,
          "correcao": null,
          "personas_pertinentes": ["historiador"]
        }
      ],
      "pontos_fracos": null,
      "diagnostico": null,
      "resumo_auditoria": "...",
      "tarefas": [],
      "antes_depois": {},
      "envelope": {},
      "reasoning_auditoria": null
    }
  ]
}
```

### Erros

| Código | Causa |
| :---: | :--- |
| `404` | Pesquisa não encontrada |
| `409` | Execução concorrente do mesmo ponto |
| `502` | `AUDIT_LLM_PROVIDER_ERROR` ou JSON inválido do modelo |
| `504` | `AUDIT_TIMEOUT` — evidência preservada; repetir |
| `400` | Estado/limiar inválido |

---

## 6. `POST /api/v1/writer`

Redige, avalia e publica o dossiê final; dispara o webhook quando configurado.

### Requisição

| Campo | Tipo | Obrigatório |
| :--- | :--- | :---: |
| `id_pesquisa` | string | sim |

```bash
curl -X POST http://127.0.0.1:8010/api/v1/writer \
  -H 'Content-Type: application/json' -H 'X-API-Key: SUA_CHAVE' \
  -d '{"id_pesquisa":"3f6c2b1a-..."}'
```

### Resposta `200` — `WriterResponse`

```json
{
  "id_pesquisa": "3f6c2b1a-...",
  "tema": "...",
  "status": "concluido",
  "total_caracteres_dossier": 18234,
  "concluido_em": "2026-10-28T20:31:44.001234Z",
  "dossier_final": "# Dossiê\n\n...",
  "dossier_resumo": "# Dossiê\n\n...",
  "reasoning_dossier": null,
  "diagnostico": null,
  "qualidade_artigo": {
    "aprovado": true,
    "pontuacao_percentual": 100.0,
    "criterios_aprovados": 12,
    "criterios_minimos": 11,
    "criterios": []
  },
  "metadados": {},
  "fontes": {
    "id_pesquisa": "3f6c2b1a-...",
    "status": "completo",
    "total_consultadas": 28,
    "total_utilizadas": 19,
    "total_nao_utilizadas": 9,
    "consultadas": [{"url": "https://...", "titulo": "...", "dominio": "..."}],
    "utilizadas": [],
    "nao_utilizadas": [],
    "observacao": null,
    "artifact_hash": "sha256..."
  },
  "webhook_entrega": {
    "url": "https://...",
    "status": "entregue",
    "http_status_code": 200,
    "tentativas": 1,
    "detalhes_falha": null
  }
}
```

> **Atenção:** `200` não significa dossiê aprovado. Verifique `status == "concluido"`. Em bloqueio/reprovação o corpo pode vir com `status: "incompleto"` e `dossier_final: null`.

### Erros

| Código | Causa |
| :---: | :--- |
| `404` | Pesquisa não encontrada |
| `409` | Conflito de concorrência/lease |
| `502` | Falha do provedor LLM |
| `504` | Deadline de 600 s excedido |
| `400` | Pré-condição de prontidão não atendida (pontos não aprovados, coleta desatualizada) |
| `500` | `WRITER_PROCESSING_ERROR` |

---

## 7. `GET /api/v1/pipeline/{id_pesquisa}/status`

```json
{
  "id_pesquisa": "3f6c2b1a-...",
  "tema": "...",
  "status_pipeline": "redigindo",
  "erro_pipeline": null,
  "criado_em": "2026-10-28T20:15:03.123456Z",
  "concluido_em": null,
  "webhook_status": "pendente",
  "total_pontos": 4,
  "pontos": [
    {
      "ponto_id": "8a1d...",
      "ponto_n": 1,
      "status": "aprovado",
      "tentativas": 1,
      "tentativas_auditoria": 1,
      "pontos_fracos": null
    }
  ],
  "tem_dossier": false
}
```

`status_pipeline`: `planejado`, `buscando`, `auditando`, `redigindo`, `concluido`, `bloqueado`, `reprovado`, `parcial`, `falha`.

---

## 8. `GET /api/v1/pipeline/{id_pesquisa}/sources`

Somente leitura. Retorna `FontesResumo`:

| Campo | Descrição |
| :--- | :--- |
| `status` | Disponibilidade da contabilidade |
| `total_consultadas` / `total_utilizadas` / `total_nao_utilizadas` | Contagens |
| `consultadas[]`, `utilizadas[]`, `nao_utilizadas[]` | `{url, titulo, dominio}` |
| `observacao` | Ressalva quando a contabilidade é parcial |
| `artifact_hash` | Hash do dossiê associado, quando houver |

`404` se a pesquisa não existir.

---

## 9. `GET /api/v1/pipeline/{id_pesquisa}/stream`

SSE de progresso. Query params opcionais:

| Param | Tipo | Efeito |
| :--- | :--- | :--- |
| `snapshot_only` | boolean | Envia apenas o snapshot do banco e encerra |
| `max_events` | inteiro | Encerra após N eventos |

Sequência: snapshot (`pipeline.status`, `point.status`, `audit.result`, `search.progress`, `writer.progress`, `report.final`) → eventos ao vivo → `: keep-alive` a cada 15 s. Encerra em status terminal (`concluido`, `falha`, `reprovado`), desconexão ou limites acima.

### Catálogo de eventos

| Evento | Campos principais |
| :--- | :--- |
| `pipeline.status` | `id_pesquisa`, `status_pipeline`, `timestamp` |
| `point.status` | `id_pesquisa`, `ponto_id`, `ponto_n`, `status`, `tentativas` |
| `stage.start` / `stage.end` | `id_pesquisa`, `stage`, `agent`, `ponto_id`, extras |
| `agent.delta` | `stage`, `agent`, `ponto_id`, `kind` (`reasoning`/`content`), `text` |
| `search.progress` | `ponto_id`, `persona`, `queries_executadas`, `urls_lidas`, `falha_coleta`, `reasoning_coleta` |
| `audit.result` | `ponto_id`, `ponto_n`, `status`, `pontuacao_percentual`, `criterios_aprovados`, `reasoning_auditoria`, `pontos_fracos` |
| `writer.progress` | `status`, `reasoning_dossier`, `total_caracteres` |
| `report.final` | `status`, `dossier_final`, `total_caracteres`, `concluido_em` |
| `pipeline.error` | `id_pesquisa`, `erro` |

Deltas consecutivos do mesmo `stage`/`agent`/`ponto_id`/`kind` são agregados em um frame (até 400 deltas). Reconexão não reproduz o histórico; o snapshot inicial representa o estado persistido.

---

## 10. `POST /api/v1/admin/credentials`

Cria ou atualiza uma credencial cifrada. O valor nunca é devolvido.

### Requisição

| Campo | Tipo | Obrigatório | Limite |
| :--- | :--- | :---: | :--- |
| `chave` | string | sim | 1–100 caracteres |
| `valor` | string | sim | ≥ 1 caractere |
| `tipo` | string | sim | 1–30; `llm`, `jina`, `webhook`, `parametro` |
| `base_url` | string | não | — |
| `descricao` | string | não | — |

```bash
curl -X POST http://127.0.0.1:8010/api/v1/admin/credentials \
  -H 'Content-Type: application/json' -H 'X-API-Key: SUA_CHAVE' \
  -d '{"chave":"LLM_MODEL_STRONG","valor":"gpt-4o","tipo":"parametro"}'
```

### Resposta `200`

```json
{
  "status": "salvo",
  "chave": "LLM_MODEL_STRONG",
  "tipo": "parametro",
  "base_url": null,
  "criptografado": true,
  "algoritmo": "Fernet (AES-128-CBC + HMAC-SHA256)",
  "atualizado_em": "2026-10-28T20:40:00.000000Z"
}
```

`400` se `chave`/`valor` forem vazios ou contiverem apenas espaços.

### Chaves reconhecidas pelo pipeline

`OPENAI_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_LIGHT`, `LLM_MODEL_STRONG`, `JINA_API_KEY`, `JINA_BASE_URL`, `N_PONTOS`, `PERSONAS_CONFIG`, `CALLBACK_WEBHOOK_URL`, `WEBHOOK_HMAC_SECRET`, `API_SECRET_KEY`.

---

## 11. `GET /api/v1/admin/credentials`

Lista metadados mascarados:

```json
{
  "credenciais": [
    {
      "chave": "OPENAI_API_KEY",
      "tipo": "llm",
      "base_url": "https://api.openai.com/v1",
      "origem_ativa": "banco_cifrado",
      "mascarado": "sk-a****9f2c",
      "atualizado_em": "2026-10-28T20:40:00.000000Z"
    }
  ]
}
```

- `origem_ativa`: `banco_cifrado` ou `ambiente`.
- Valores ≤ 8 caracteres e campos vazios aparecem como `[REDACTED]`.
- A listagem não revela o valor real nem serve para repopular formulários.

---

## 12. Rotas públicas

### `GET /health`

```json
{"status": "healthy"}
```

### `GET /app/session`

- Cliente elegível (loopback + Host local + mesma origem): `200` com `authenticated: true`, `mode: "local"`, `preferences` e `Set-Cookie: dr_local_session=...`.
- Cliente não elegível: `200` com `authenticated: false`, `mode: "remote"`, `preferences`.
- Host não local: `403`. `Origin`/`Referer` divergente ou `Sec-Fetch-Site: cross-site`: `403`.

`preferences` inclui `n_pontos` e personas padrão.

### `GET /` e `GET /assets/*`

Entregam a SPA compilada. Sem `frontend/dist/index.html`, retornam `503` com instrução de build. Caminhos `api/*`, `health`, `docs*`, `openapi.json`, `app/session` não são capturados pelo fallback.

---

## 13. Contrato do webhook

Entrega apenas quando o dossiê é publicado com `status = concluido` e há URL de callback resolvida (payload > `CALLBACK_WEBHOOK_URL`).

### Requisição

```http
POST <callback_url>
Content-Type: application/json
X-Signature: sha256=<hex>
X-Event-Type: research.completed
X-Research-Id: <id_pesquisa>
```

```json
{
  "evento": "research.completed",
  "id_pesquisa": "3f6c2b1a-...",
  "tema": "...",
  "status": "concluido",
  "total_pontos": 4,
  "total_caracteres_dossier": 18234,
  "dossier_final": "# Dossiê\n\n...",
  "artifact_hash": "sha256...",
  "concluido_em": "2026-10-28T20:31:44.001234Z"
}
```

### Validação no receptor

```python
import hashlib, hmac

def assinatura_valida(secret: str, raw_body: bytes, header: str) -> bool:
    esperado = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, header)
```

A assinatura cobre os **bytes crus** do corpo. Não reserialize o JSON antes de validar.

### Política de entrega

| Situação | Resultado |
| :--- | :--- |
| `2xx` | `entregue` |
| `4xx` (exceto 429) | `falha_definitiva`, sem retry |
| `429`, `500`, `502`, `503`, `504`, erro de transporte | retry com backoff exponencial |
| Após 4 tentativas | `falha_definitiva` registrada em `pesquisa.webhook_status` |

O `WriterResponse.webhook_entrega` informa `url`, `status`, `http_status_code`, `tentativas` e `detalhes_falha`.
