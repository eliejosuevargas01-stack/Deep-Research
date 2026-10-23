# Interface: Endpoints Administrativos (Credenciais e Configurações)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Exposto pelo sistema)
> Protocolo: HTTP/1.1 ou HTTP/2 sobre TLS
> Referência SDD: `_reversa_sdd/prd.md#7-requisitos-funcionais` (RF-007, RF-008)

---

## 1. Visão Geral
Endpoints administrativos auxiliares para cadastrar, atualizar e inspecionar configurações operacionais, chaves de API externas (OpenAI, Jina, Callback Webhook) e URLs base personalizadas. Todos os segredos gravados são cifrados automaticamente com o algoritmo Fernet (`cryptography.fernet`) utilizando a chave `CREDENTIALS_MASTER_KEY`. Variáveis de ambiente configuradas no contêiner possuem precedência de leitura sobre os registros salvos nesta tabela.

---

## 2. Rotas Disponibilizadas

### 2.1 Cadastro / Atualização de Credencial
- **Método HTTP:** `POST`
- **Caminho:** `/api/v1/admin/credentials`
- **Headers:** `Content-Type: application/json`, `Authorization: Bearer <ADMIN_TOKEN>`
- **Timeout:** 30 segundos

#### Payload da Requisição
```json
{
  "chave": "OPENAI_API_KEY",
  "valor": "sk-proj-abc123xyz...",
  "base_url": "https://api.openai.com/v1",
  "tipo": "llm",
  "descricao": "Chave de acesso primária ao modelo OpenAI"
}
```

#### Resposta de Sucesso: HTTP 200 OK
```json
{
  "status": "salvo",
  "chave": "OPENAI_API_KEY",
  "tipo": "llm",
  "base_url": "https://api.openai.com/v1",
  "criptografado": true,
  "algoritmo": "Fernet (AES-128-CBC + HMAC-SHA256)",
  "atualizado_em": "2026-10-21T18:25:00Z"
}
```

---

### 2.2 Consulta de Configurações Ativas (Sanitizada)
- **Método HTTP:** `GET`
- **Caminho:** `/api/v1/admin/credentials`
- **Headers:** `Authorization: Bearer <ADMIN_TOKEN>`
- **Comportamento de Segurança:** Valores de segredos e chaves NUNCA são expostos em texto claro nas respostas de consulta; apenas metadados, status de mascaramento e indicação de precedência de ambiente são retornados.

#### Resposta de Sucesso: HTTP 200 OK
```json
{
  "credenciais": [
    {
      "chave": "OPENAI_API_KEY",
      "tipo": "llm",
      "base_url": "https://api.openai.com/v1",
      "origem_ativa": "ambiente",
      "mascarado": "sk-proj-****-xyz",
      "atualizado_em": "2026-10-21T18:25:00Z"
    },
    {
      "chave": "CALLBACK_WEBHOOK_URL",
      "tipo": "webhook",
      "base_url": null,
      "origem_ativa": "banco_cifrado",
      "mascarado": "https://meu-servico.exemplo.com/webhooks/pesquisa",
      "atualizado_em": "2026-10-21T18:20:00Z"
    }
  ]
}
```

---

## 3. Códigos de Erro

| Código HTTP | Erro | Causa / Comportamento |
|-------------|------|-----------------------|
| `400 Bad Request` | `INVALID_CREDENTIAL_DATA` | Campo `chave` ou `valor` nulos ou com formato inválido |
| `401 Unauthorized` | `UNAUTHORIZED` | Token administrativo ausente ou inválido |
| `500 Internal Server Error` | `ENCRYPTION_KEY_MISSING` | Variável `CREDENTIALS_MASTER_KEY` ausente no ambiente do contêiner |