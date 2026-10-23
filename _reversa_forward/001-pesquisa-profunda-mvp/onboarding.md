# Onboarding: Guia de Teste e Operação Ponta a Ponta MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Contexto: Guia Executável para Teste da Primeira Versão do Pipeline Deep Research
> Referências: `_reversa_forward/001-pesquisa-profunda-mvp/requirements.md` e `_reversa_sdd/prd.md`

---

## 1. Pré-Requisitos do Ambiente

- **Linguagem:** Python 3.11 ou superior
- **Gerenciador:** pip / venv
- **Banco de Dados:** SQLite 3 (embutido)
- **Acesso de Rede:** Conectividade com a internet para as APIs do Jina e OpenAI-compatible

---

## 2. Configuração de Variáveis de Ambiente

Crie o arquivo `.env` na raiz do projeto contendo as definições obrigatórias (sem fallback hardcoded):

```bash
# 1. Configuração do Pipeline
N_PONTOS=1
PERSONAS_CONFIG="planejador,historiador,visionario,cetico,futurista,auditor,redator final"

# 2. Segurança e Criptografia
# Gerar chave com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIALS_MASTER_KEY="SUA_CHAVE_FERNET_BASE64_32_BYTES="
WEBHOOK_HMAC_SECRET="segredo_super_seguro_para_assinatura_do_webhook"
CALLBACK_WEBHOOK_URL="https://webhook.site/seu-identificador-de-teste"

# 3. Provedores Externos
OPENAI_API_KEY="sk-proj-..."
LLM_BASE_URL="https://api.openai.com/v1"
LLM_MODEL_LIGHT="gpt-4o-mini"
LLM_MODEL_STRONG="gpt-4o"
JINA_API_KEY="jina_..."
JINA_BASE_URL="https://s.jina.ai"

# 4. Persistência
DATABASE_URL="sqlite+aiosqlite:///./data/deep_research.db"
```

---

## 3. Inicialização do Serviço

1. Crie o diretório de dados persistentes:
   ```bash
   mkdir -p ./data
   ```

2. Instale as dependências:
   ```bash
   pip install fastapi uvicorn sqlalchemy aiosqlite httpx tenacity cryptography pydantic
   ```

3. Suba o servidor ASGI FastAPI:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. Verifique a saúde do serviço:
   ```bash
   curl -s http://localhost:8000/health
   # Retorno esperado: {"status": "ok", "banco": "conectado", "modo": "greenfield"}
   ```

---

## 4. Roteiro de Teste do Ciclo Completo (4 Etapas)

### Etapa 1: Planejamento de Investigação (`POST /api/v1/plan`)
Dispara a consulta SERP e gera exatamente N pontos temáticos:

```bash
curl -X POST "http://localhost:8000/api/v1/plan" \
  -H "Content-Type: application/json" \
  -d '{"tema": "Impacto da Inteligência Artificial Generativa na Educação Básica"}'
```
**O que verificar:**
- Código HTTP 201 Created retornado.
- `id_pesquisa` retornado em formato UUID.
- Exatamente 5 pontos listados com status `pendente`.
- Guarde o `id_pesquisa` retornado na variável de shell:
  ```bash
  export ID_PESQUISA="<UUID_RETORNADO>"
  ```

---

### Etapa 2: Busca Aprofundada com Personas (`POST /api/v1/search`)
Executa a raspagem paralela aplicando as 4 personas analíticas e descartando URLs repetidas:

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d "{\"id_pesquisa\": \"$ID_PESQUISA\"}"
```
**O que verificar:**
- Código HTTP 200 OK retornado em menos de 300 segundos.
- Status da pesquisa atualizado para `coletado`.
- Quantidade de URLs lidas e URLs fonte registradas na tabela `conteudo_coletado`.

---

### Etapa 3: Auditoria Crítica de Qualidade (`POST /api/v1/audit`)
Submete cada ponto ao checklist de 12 perguntas de qualidade via LLM forte:

```bash
curl -X POST "http://localhost:8000/api/v1/audit" \
  -H "Content-Type: application/json" \
  -d "{\"id_pesquisa\": \"$ID_PESQUISA\"}"
```
**O que verificar:**
- Código HTTP 200 OK retornado.
- Cada ponto na resposta possui status `aprovado` ou `reprovado`.
- Se houver reprovação, o campo `pontos_fracos` detalha a lacuna factual identificada.

---

### Etapa 4: Redação do Dossiê e Despacho via Webhook (`POST /api/v1/writer`)
Gera o dossiê consolidado com 100% de fontes canônicas e despacha para o callback webhook:

```bash
curl -X POST "http://localhost:8000/api/v1/writer" \
  -H "Content-Type: application/json" \
  -d "{\"id_pesquisa\": \"$ID_PESQUISA\"}"
```
**O que verificar:**
- Código HTTP 200 OK retornado.
- Resposta contém o texto em Markdown com Sumário Executivo, Desenvolvimento dos Eixos, Ressalvas e Referências Canônicas.
- Objeto `webhook_entrega` reporta status `entregue`.
- No receptor do webhook (ex: webhook.site), verifique se o cabeçalho `X-Signature: sha256=...` foi recebido e se o payload JSON do dossiê confere.

---

## 5. Verificação da Persistência Relacional

Inspecione o banco SQLite permanente via terminal:

```bash
sqlite3 ./data/deep_research.db ".mode table" \
  "SELECT id_pesquisa, tema, webhook_status, concluido_em FROM pesquisa;" \
  "SELECT ponto_n, status, substr(ponto, 1, 40) AS ponto, substr(pontos_fracos, 1, 30) AS fraco FROM pontos WHERE id_pesquisa = '$ID_PESQUISA';" \
  "SELECT ponto_id, length(conteudo_coletado) AS bytes, urls_fonte FROM conteudo_coletado WHERE id_pesquisa = '$ID_PESQUISA';"
```

---

## 6. Testes de Casos Negativos e Robustez (Edge Cases)

1. **Tentativa de Redação com Pontos Pendentes:**
   - Crie novo plano com `POST /api/v1/plan`.
   - Tente chamar imediatamente `POST /api/v1/writer` sem antes rodar search e audit.
   - **Resultado esperado:** HTTP 400 Bad Request informando que todos os pontos devem ser previamente auditados.

2. **Tentativa de Boot sem Variável N_PONTOS:**
   - Inicie o serviço sem a variável `N_PONTOS` e sem registro no banco.
   - Chame `POST /api/v1/plan`.
   - **Resultado esperado:** HTTP 500 informando ausência de configuração explícita (sem fallback hardcoded).

3. **Tentativa de Auditoria sem Coleta:**
   - Crie plano com `POST /api/v1/plan` e chame imediatamente `POST /api/v1/audit`.
   - **Resultado esperado:** HTTP 400 Bad Request informando que a etapa de busca deve ser concluída antes da auditoria.