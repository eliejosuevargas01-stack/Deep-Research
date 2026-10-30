# Operações — Deep Research

Guia de instalação, configuração, execução, testes e diagnóstico. Para o desenho técnico, consulte [`ARCHITECTURE.md`](ARCHITECTURE.md); para os contratos HTTP, [`API.md`](API.md).

---

## 1. Requisitos

| Item | Versão / observação |
| :--- | :--- |
| Python | ≥ 3.11 (`pyproject.toml`); ambiente de desenvolvimento atual em 3.14.7 |
| Node.js / npm | Node 20+ (build do frontend; não é necessário em produção) |
| SQLite | Embutido no Python via `aiosqlite` |
| Rede | Acesso HTTPS a `s.jina.ai`, `r.jina.ai` e ao provedor LLM |
| Docker | Opcional; compose usa `network_mode: host` (Linux) |

### Instalação

```bash
cd Deep-Research
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

O `uv.lock` existe, mas os comandos documentados usam `pip`/`venv`. Se preferir `uv`:

```bash
uv sync
```

---

## 2. Variáveis de ambiente

### 2.1 Obrigatórias na prática

| Variável | Exemplo | Observação |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/deep_research.db` | Sem default no código; erro explícito se ausente |
| `CREDENTIALS_MASTER_KEY` | chave Fernet | Somente via ambiente; decifra a tabela `credenciais` |
| `OPENAI_API_KEY` | `sk-...` | Pode vir do banco cifrado |
| `JINA_API_KEY` | `jina_...` | Pode vir do banco cifrado |
| `N_PONTOS` | `4` | Sem default no código; configurável pela interface |
| `PERSONAS_CONFIG` | `planejador,historiador,visionario,cetico,futurista,auditor,redator final` | 7 personas; a última contém espaço |

Gere a chave mestra com:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> Guarde a `CREDENTIALS_MASTER_KEY` fora do repositório. Sem ela, os valores da tabela `credenciais` não podem ser decifrados. Não há rotação automática de chave.

### 2.2 Opcionais e de ajuste

| Variável | Default | Efeito |
| :--- | :--- | :--- |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Base compatível com OpenAI; a rota usada é `/chat/completions` |
| `LLM_MODEL_LIGHT` | `gpt-4o-mini` | Coleta com personas |
| `LLM_MODEL_STRONG` | `gpt-4o` | Plano, auditoria, redação e avaliação do artigo |
| `LLM_TIMEOUT` | `1800` (s) | Timeout HTTP do cliente LLM |
| `LLM_REASONING_EFFORT` | `high` | Enviado quando o provedor suporta reasoning |
| `JINA_BASE_URL` | `https://s.jina.ai` | Base de descoberta; o Reader usa `r.jina.ai` |
| `JINA_SEARCH_BASE_URL` | — | Override explícito da descoberta |
| `JINA_READER_BASE_URL` | — | Override explícito da leitura |
| `JINA_HTTP_TIMEOUT_SECONDS` | `45` | Timeout por requisição Jina |
| `SEARCH_POINT_TIMEOUT_SECONDS` | `480` | Deadline por ponto na busca |
| `SEARCH_READER_TIMEOUT_SECONDS` | `45` | Deadline por leitura de URL |
| `SEARCH_MAX_URLS_PER_TURN` | `4` | URLs lidas por turno da persona |
| `AUDIT_POINT_TIMEOUT_SECONDS` | `600` | Deadline da decisão por ponto |
| `AUDIT_EVIDENCE_PASS_TIMEOUT_SECONDS` | `300` | Deadline por passe de evidência |
| `AUDIT_POINT_LEASE_SECONDS` | `1800` | Validade da reserva do ponto |
| `AUDIT_EVIDENCE_BUDGET_CHARS` | `320000` | Evidência por passe |
| `AUDIT_JSON_BUDGET_CHARS` | `1200000` | Teto do JSON de decisão |
| `RESEARCH_REFERENCE_DATE` | calculado | Fixa a data de referência (`YYYY-MM-DD`) para testes |
| `RESEARCH_REFERENCE_TIMEZONE` | `America/Sao_Paulo` | Fuso da data de referência |
| `CALLBACK_WEBHOOK_URL` | — | URL padrão de callback |
| `WEBHOOK_HMAC_SECRET` | — | Sem ele, o `Writer` não cria cliente de webhook |
| `API_SECRET_KEY` | — | Ativa autenticação por chave; sem ela, API aberta |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Usadas pelo comando do Dockerfile |
| `BACKEND_PORT` | `8010` | Alvo do proxy do Vite |
| `BASE_URL` | `http://localhost:8011` | Base dos testes Cucumber |

### 2.3 Precedência

1. Banco cifrado (`credenciais`) — prioridade.
2. Variáveis de ambiente / `.env` — fallback.
3. Erro explícito — sem fallback hardcoded.

Exceções: `CREDENTIALS_MASTER_KEY` só existe no ambiente; `API_SECRET_KEY` é lida primeiro do ambiente e depois do banco.

---

## 3. Modos de execução

### 3.1 Servidor integrado (recomendado)

```bash
python scripts/run_app.py --port 8010
```

- compila o frontend automaticamente se `frontend/dist/index.html` não existir;
- `--build` força nova compilação;
- `--reload` habilita auto-reload;
- bind padrão `127.0.0.1`;
- serve SPA, assets, `/health` e `/api/v1/*` na mesma origem.

### 3.2 Desenvolvimento separado

```bash
# API
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# Frontend
cd frontend
npm ci
npm run dev        # http://127.0.0.1:3000
```

O Vite faz proxy de `/app`, `/api` e `/health` para `http://127.0.0.1:8010` com `changeOrigin: false`, preservando o `Host` e a validação de mesma origem.

### 3.3 Docker Compose

```bash
docker compose up --build
```

- container: `deep-research`;
- porta: `8085` (`uvicorn app.main:app --host 127.0.0.1 --port 8085`);
- `network_mode: host` — necessário para o cliente aparecer como loopback e receber sessão local;
- volume: `./data:/app/data`;
- banco: `/app/data/deep_research.db`;
- `restart: unless-stopped`.

Em macOS/Windows, `network_mode: host` não tem o mesmo comportamento; use `scripts/run_app.py` no host.

Build manual da imagem:

```bash
docker build -t deep-research .
docker run --rm --network host --env-file .env -v "$PWD/data:/app/data" deep-research
```

### 3.4 Portas de referência

| Porta | Uso |
| :---: | :--- |
| `3000` | Vite dev/preview |
| `8000` | `run_app.py` e Dockerfile (default) |
| `8010` | API de desenvolvimento e alvo do proxy Vite |
| `8085` | docker compose |
| `8111` | `run_test.sh` e testes Cucumber |

---

## 4. Banco de dados

### 4.1 Arquivo e pragmas

- Default do exemplo: `./data/deep_research.db`.
- No boot, `init_db()` cria tabelas, aplica migrações aditivas idempotentes e valida os pragmas.
- Pragmas aplicados em cada conexão: `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=30000`.
- Arquivos auxiliares `-wal` e `-shm` aparecem ao lado do banco; não os remova com a aplicação em execução.

### 4.2 Backup

Com a aplicação parada (ou usando o backup online do SQLite):

```bash
sqlite3 data/deep_research.db ".backup 'backup-deep-research-$(date +%F).db'"
```

Preserve também a `CREDENTIALS_MASTER_KEY`: o backup do banco sem a chave não permite decifrar credenciais.

### 4.3 Inspeção rápida

```bash
sqlite3 data/deep_research.db \
  "select id_pesquisa, status_pipeline, substr(tema,1,60) from pesquisa order by criado_em desc limit 10;"

sqlite3 data/deep_research.db \
  "select etapa, persona, model_used, latency_seconds, criado_em from generation_attempts order by criado_em desc limit 20;"
```

### 4.4 Limpeza

Não existem endpoints de deleção de pesquisas ou credenciais. Se for indispensável remover dados, faça backup antes e opere via SQL manual, respeitando as FKs em cascata (`pontos` e `conteudo_coletado` acompanham a `pesquisa`).

---

## 5. Verificação de saúde

```bash
curl -s http://127.0.0.1:8010/health
# {"status":"healthy"}
```

```bash
curl -s http://127.0.0.1:8010/api/v1/pipeline/<id>/status \
  -H "X-API-Key: $API_SECRET_KEY"
```

Checklist pós-deploy:

1. `/health` responde `200`.
2. `/` entrega o `index.html`.
3. `/docs` abre o Swagger.
4. `GET /app/session` retorna `authenticated: true` em acesso loopback.
5. `POST /api/v1/plan` com tema curto retorna `201` e pontos persistidos.
6. `GET /api/v1/pipeline/<id>/stream` emite `pipeline.status` e keep-alives.

---

## 6. Testes

```bash
# Backend: 509 testes coletados
.venv/bin/python -m pytest

# Falha rápida e verbosa
.venv/bin/python -m pytest -x -q

# Apenas unitários
.venv/bin/python -m pytest tests/unit -q

# Apenas integração
.venv/bin/python -m pytest tests/integration -q

# Frontend: typecheck + build
cd frontend && npm run build

# E2E Cucumber/Playwright
cd frontend && npm run test:e2e
```

Observações:

- Os testes de integração usam banco isolado e mock transport; não exigem provedores reais.
- Os testes E2E esperam a aplicação em `BASE_URL` (default `http://localhost:8011`).
- `run_test.sh` sobe a aplicação na `8111` com `.env.test`.
- Em ambiente de teste, `app/config.py` ignora o `.env` e `app/main.py` injeta defaults apenas para `tests/integration/`.

---

## 7. Diagnóstico

| Sintoma | Causa provável | Ação |
| :--- | :--- | :--- |
| `503` "Frontend bundle não compilado ou ausente" | `frontend/dist/index.html` não existe | `cd frontend && npm ci && npm run build` |
| `403` em `/app/session` | Host não local, `Origin`/`Referer` divergente ou acesso por IP de LAN | Acesse `http://127.0.0.1:...` ou `http://localhost:...`; atrás de proxy, preserve Host/Origin |
| `401` "Chave de API ausente ou inválida" | `API_SECRET_KEY` configurada e requisição sem chave | Envie `X-API-Key`/`Bearer` ou use a sessão do navegador |
| API responde sem autenticação | `API_SECRET_KEY` não configurada (modo aberto) | Defina a chave em produção e reinicie |
| `500 CONFIG_ERROR: N_PONTOS...` | `N_PONTOS` ausente no banco e no ambiente | Defina no `.env` ou no painel de configurações |
| `500 CONFIG_ERROR: ...` | `CREDENTIALS_MASTER_KEY`/`DATABASE_URL` ausente | Preencha o `.env` |
| `500 CONFIG_ERROR: OPENAI_API_KEY...` (ou `400` em search/audit/writer) | Chave do provedor não cadastrada no banco nem no ambiente | Cadastre em `/api/v1/admin/credentials` ou no `.env` e reinicie |
| `400` em `/admin/credentials` | `chave`/`valor` vazios ou só espaços | Preencha os campos obrigatórios |
| `502 LLM_PROVIDER_ERROR` / `AUDIT_LLM_PROVIDER_ERROR` | Provedor recusou, filtro de conteúdo ou JSON inválido | Verifique modelo, prompt e limites; reduza fontes por ponto |
| `504 TIMEOUT_ERROR` na busca | Ponto excedeu `SEARCH_POINT_TIMEOUT_SECONDS` | Repita o ponto; aumente o timeout se a rede for lenta |
| `504 AUDIT_TIMEOUT` | Decisão excedeu 600 s | Repita a auditoria; a evidência foi preservada |
| `504` na redação | Deadline de 600 s | Reduza o volume de evidência por ponto |
| `409` conflito/lease | Outro processo possui a reserva | Aguarde a expiração do lease (`AUDIT_POINT_LEASE_SECONDS`) e repita |
| `200` com `status: "incompleto"` | Artigo não aprovado ou dossiê não publicado | Trate como falha; verifique `diagnostico` e `qualidade_artigo` |
| SSE sem eventos | `id_pesquisa` errado, pipeline já terminal ou múltiplos workers | Confirme o ID; use um único processo ou um hub externo |
| SSE atrás de proxy trava | Buffering do proxy | Desative buffering; os headers já enviam `X-Accel-Buffering: no` |
| Webhook `falha_definitiva` | URL inválida, 4xx, TLS ou 4 tentativas esgotadas | Verifique `pesquisa.webhook_status`/`webhook_resposta` e o segredo HMAC |
| `database is locked` | Transação longa concorrente | Verifique WAL, `busy_timeout` e evite chamadas externas dentro de transações |
| Docker sem sessão local | `network_mode: host` ausente ou plataforma não-Linux | Use o compose no Linux ou `run_app.py` no host |

---

## 8. Observabilidade

- **Status consolidado:** `GET /api/v1/pipeline/{id}/status`.
- **Progresso ao vivo:** `GET /api/v1/pipeline/{id}/stream` (SSE).
- **Telemetria de LLM:** tabela `generation_attempts` (etapa, persona, modelo, prompt hash, uso, custo, latência, erros).
- **Entrega:** `pesquisa.webhook_status`, `pesquisa.webhook_resposta` e `WriterResponse.webhook_entrega`.
- **Fontes:** `GET /api/v1/pipeline/{id}/sources` e `WriterResponse.fontes`.
- **Logs:** `uvicorn` no stdout; o runner registra início/fim por pesquisa. Não há integração OTel configurada.

Consultas úteis:

```sql
-- pesquisas travadas em estágio não terminal
select id_pesquisa, status_pipeline, criado_em
from pesquisa
where status_pipeline in ('buscando','auditando','redigindo');

-- custo/latência por etapa
select etapa, count(*), avg(latency_seconds)
from generation_attempts
group by etapa;
```

---

## 9. Segurança operacional

Checklist mínimo para exposição remota:

1. **Feche a API:** defina `API_SECRET_KEY` e reinicie. Sem isso, `/api/v1/*` aceita requisições anônimas.
2. **Não exponha `127.0.0.1` diretamente:** use reverse proxy com TLS e repasse `Host`, `Origin` e `X-Forwarded-*` corretamente. A sessão local só é emitida para loopback; acesso remoto deve usar chave de API.
3. **Proteja o `.env`:** permissões restritas, fora do Git. O `.gitignore` já exclui `.env` e `data/`.
4. **Backup da chave mestra:** sem ela, credenciais cifradas são irrecuperáveis.
5. **Rotação:** não há endpoint de rotação de `CREDENTIALS_MASTER_KEY`; planeje recriptografia manual antes de trocar a chave.
6. **Rate limit:** não implementado. Coloque limite no proxy (nginx, Traefik, Cloudflare) se houver exposição pública.
7. **Uploads/entradas:** o tema não tem teto no backend; limite o tamanho no proxy para evitar payloads excessivos.
8. **Webhook:** valide `X-Signature` sobre os bytes crus e rejeite assinaturas inválidas.
9. **Logs:** evite registrar corpos de requisição com credenciais; a aplicação mascara valores em respostas administrativas.

Itens já conhecidos e registrados: [`security_audit_findings.md`](security_audit_findings.md).

---

## 10. Manutenção

- **Crescimento do banco:** `conteudo_coletado` e `generation_attempts` crescem por pesquisa. Monitore o tamanho de `data/deep_research.db`.
- **Coleta acumulada:** cada rodada gera uma linha em `conteudo_coletado` (chave `id_pesquisa + ponto_id + rodada`), preservada para auditoria.
- **Reexecução segura:** repetir `/search` cria nova rodada; repetir `/writer` com artefato íntegro e avaliação ≥ 11 usa cache e não reenvia webhook.
- **Atualização de dependências:** `pip install -e ".[dev]"` e `npm ci`; valide com `pytest` e `npm run build`.
- **Migrações:** aditivas e idempotentes no boot; não há ferramenta de rollback. Faça backup antes de atualizar versões que alterem schema.
