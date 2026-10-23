# Interface: POST /api/v1/plan (Plano de Investigação)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Exposto pelo sistema)
> Protocolo: HTTP/1.1 ou HTTP/2 sobre TLS
> Referência SDD: `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md`

---

## 1. Visão Geral
Endpoint da Etapa 1 do pipeline Deep Research. Recebe o tema proposto pelo usuário, persiste a pesquisa no SQLite permanente, invoca o modelo LLM com a persona `planejador` com ferramenta Jina restrita a metadados da SERP, formulando exatamente N pontos de foco para posterior investigação.

---

## 2. Detalhes da Requisição

- **Método HTTP:** `POST`
- **Caminho:** `/api/v1/plan`
- **Cabeçalhos Exigidos:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <API_BEARER_TOKEN>` (quando autenticação ativada)
- **Timeout:** 120 segundos

### Payload da Requisição (Request Body)
```json
{
  "tema": "Impacto da Inteligência Artificial Generativa na Educação Básica",
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `tema` | String (5 a 500 caracteres) | Sim | Tema central ou briefing para investigação |
| `id_pesquisa` | String (UUID v4) | Não | Identificador opcional caso criado previamente em rotina administrativa |

---

## 3. Respostas da API (Response)

### 3.1 Sucesso: HTTP 201 Created
```json
{
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
  "tema": "Impacto da Inteligência Artificial Generativa na Educação Básica",
  "n_pontos": 5,
  "criado_em": "2026-10-21T18:30:00Z",
  "pontos": [
    {
      "ponto_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      "ponto_n": 1,
      "ponto": "Adoção de tutores inteligentes baseados em IA e impactos no letramento",
      "status": "pendente"
    },
    {
      "ponto_id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
      "ponto_n": 2,
      "ponto": "Desafios de plágio, integridade acadêmica e novas diretrizes de avaliação",
      "status": "pendente"
    },
    {
      "ponto_id": "c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f",
      "ponto_n": 3,
      "ponto": "Desigualdade no acesso digital e assimetrias regionais de infraestrutura",
      "status": "pendente"
    },
    {
      "ponto_id": "d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a",
      "ponto_n": 4,
      "ponto": "Formação continuada e capacitação do corpo docente para uso pedagógico de IA",
      "status": "pendente"
    },
    {
      "ponto_id": "e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9a0b",
      "ponto_n": 5,
      "ponto": "Marcos regulatórios internacionais e políticas públicas de proteção à infância",
      "status": "pendente"
    }
  ]
}
```

---

## 4. Códigos de Erro e Tratamento

| Código HTTP | Erro | Causa / Comportamento |
|-------------|------|-----------------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Tema com menos de 5 caracteres ou campo malformatado |
| `422 Unprocessable Entity` | `UNPROCESSABLE_ENTITY` | Payload JSON sintaticamente inválido ou campos ausentes |
| `500 Internal Server Error` | `CONFIG_ERROR` | Variável de ambiente `N_PONTOS` ausente e sem valor configurado no banco |
| `502 Bad Gateway` | `SERP_UNAVAILABLE` | Falha persistente de conexão com o motor Jina SERP após 1+3 retentativas |
| `504 Gateway Timeout` | `LLM_TIMEOUT` | Chamada ao modelo OpenAI-compatible ultrapassou 120s |

---

## 5. Idempotência e Concorrência
- O envio de um `id_pesquisa` pré-existente sem pontos cadastrados reaproveita a pesquisa existente.
- A geração dos pontos e a inserção no banco são executadas sob transação atômica única no SQLite permanente.