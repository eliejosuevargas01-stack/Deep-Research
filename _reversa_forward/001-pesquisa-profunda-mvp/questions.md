# Questões resolvidas no modo autônomo

Feature: `001-pesquisa-profunda-mvp`
Data: 2026-10-21

Este arquivo registra as dúvidas que o modo autônomo resolveu por conta própria ou que foram respondidas no chat (modo "parar e perguntar" escolhido na entrevista).

## Dúvidas originais do requirements.md

### 1. Teto de consumo de tokens ou custo por pesquisa

- **Estado original:** 🔴 `[DÚVIDA]`
- **Como foi resolvida:** respondida pelo usuário no chat, no modo "parar e perguntar".
- **Resposta:** "não" — não existe teto.
- **Decisão adotada:** nenhum mecanismo de corte orçamentário automático nesta feature. O custo fica limitado pelas restrições já presentes no PRD: no máximo 3 queries por ponto no `search` e no máximo 10 URLs lidas por query.
- **Registro:** premissa 🟡 explícita na seção "Lacunas" do `requirements.md`.
- **Ação para o usuário:** nenhuma pendente, a menos que se queira adicionar teto orçamentário em feature futura.

### 2. Mecanismo de criptografia em repouso da tabela `credenciais`

- **Estado original:** 🔴 `[DÚVIDA]`
- **Como foi resolvida:** respondida pelo usuário no chat, com correção técnica de segurança aplicada pelo orquestrador.
- **Resposta literal do usuário:** "hmac sha256 basico".
- **Correção aplicada:** HMAC-SHA256 é código de autenticação de mensagem, não cifra, e não é reversível. Gravar as chaves como digest HMAC tornaria impossível recuperá-las para as chamadas HTTP a Jina e aos modelos, quebrando os endpoints em tempo de execução.
- **Decisão adotada:** cifra reversível Fernet (AES-128-CBC com etiqueta HMAC-SHA256 de integridade), pacote `cryptography`, chave mestra na variável de ambiente `CREDENTIALS_MASTER_KEY`. O padrão HMAC-SHA256 foi mantido onde é correto, na assinatura do webhook.
- **Registro:** premissa 🟡 explícita na seção "Lacunas" do `requirements.md`.
- **Ação para o usuário:** fornecer `CREDENTIALS_MASTER_KEY` no ambiente antes de subir o serviço. Sem ela, a tabela de credenciais não opera.

### 3. Padrão de autenticação e assinatura do webhook de callback

- **Estado original:** 🔴 `[DÚVIDA]`
- **Como foi resolvida:** respondida pelo usuário no chat.
- **Resposta:** "hmac sha256 basico".
- **Decisão adotada:** cabeçalho `X-Signature: sha256=<hmac hexadecimal>` calculado sobre o corpo cru com o segredo da variável de ambiente `WEBHOOK_HMAC_SECRET`, comparação timing-safe via `hmac.compare_digest`.
- **Registro:** premissa 🟡 explícita na seção "Lacunas" do `requirements.md`.
- **Ação para o usuário:** fornecer `WEBHOOK_HMAC_SECRET` e `CALLBACK_WEBHOOK_URL` no ambiente.

---
Gerado por `/reversa-forward-autonomous` em 2026-10-21
