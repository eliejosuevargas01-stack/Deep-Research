# Registro de Auditoria de Segurança e Contratos Operacionais
Data: 2026-10-27
Status: Registrado para Remediação Futura

## 1. Avaliação pelas 4 Lupas

### Lupa 1: SQL Injection
- **Diagnóstico:** Mitigado. Repositórios (`ResearchRepository`, `CredentialsRepository`) usam SQLAlchemy ORM 2.0 com consultas parametrizadas (`select(Ponto)...`, `select(Credencial)...`). Migrações em `app/db/init_db.py` usam interpolação estática com tuplas fixas de nomes de tabelas/colunas da aplicação; valores utilizam binding seguro (`:pk`, `:c`).
- **Conformidade:** Conforme.

### Lupa 2: Inputs sem Limite de Entrada
- **Diagnóstico:** NÃO CONFORME.
- **Evidências:** Apenas 4 campos em todos os esquemas Pydantic possuem `max_length`: `tema` (max 500 em `app/schemas/plan.py`), `chave` (max 100 em `app/schemas/admin.py`) e `tipo` (max 30 em `app/schemas/admin.py`).
- **Campos Vulneráveis a Payloads Excessivos:**
  - `CredentialCreateRequest.valor` (`app/schemas/admin.py:23`): sem `max_length`.
  - `CredentialCreateRequest.base_url` (`app/schemas/admin.py:34`): sem `max_length`.
  - `CredentialCreateRequest.descricao` (`app/schemas/admin.py:38`): sem `max_length`.
  - `PlanoEixo.subperguntas`, `hipoteses`, `consultas_iniciais`, `fontes_primarias_desejadas`, `riscos_de_vies`, `evidencias_que_refutariam`: listas sem limite de itens ou caracteres por item.
  - `SearchRequest.id_pesquisa`, `WriterRequest.id_pesquisa`: sem `max_length`.
- **Risco:** Em SQLite (`aiosqlite`), textos gigantes são persistidos sem truncamento, gerando DoS de memória e disco. Sob PostgreSQL real, colunas tipadas `VARCHAR(30)` geram `StringDataRightTruncation` (HTTP 500).

### Lupa 3: Rate Limiting
- **Diagnóstico:** NÃO CONFORME.
- **Evidências:** Zero controle de taxa de requisições implementado na camada HTTP. Nenhum middleware de rate limit (ex: SlowAPI, Redis limiter) configurado no FastAPI (`app/main.py`).
- **Risco:** Endpoints `POST /api/v1/plan`, `POST /api/v1/search`, `POST /api/v1/audit`, `POST /api/v1/writer` e `POST /api/v1/admin/credentials` podem ser acionados em rajadas contínuas sem qualquer bloqueio por IP ou chave. O repositório possui apenas limites lógicos de tentativas por ponto (4 de busca, 3 de auditoria).

### Lupa 4: Senhas ou Credenciais Hardcoded
- **Diagnóstico:** PARCIALMENTE NÃO CONFORME.
- **Evidências:**
  - `app/config.py` e repositórios não possuem segredos reais em texto plano.
  - No entanto, `app/core/security.py:80-81` possui comportamento aberto permissivo: se `API_SECRET_KEY` não for configurada no ambiente ou no banco cifrado, `verify_api_key` retorna `True` irrestritamente, deixando todos os endpoints `/api/v1/*` abertos publicamente sem autenticação.
  - `app/main.py:36-46` contém chave mestra e segredos de teste estáticos em fallback ativados apenas sob ambiente `tests/integration/`.

---

## 2. Respostas às 10 Perguntas Operacionais

1. **Quanto cabe aí dentro?**
   - `tema`: 5 a 500 caracteres (`PlanRequest.tema` e input `Composer.tsx`).
   - `chave` de credencial: 1 a 100 caracteres.
   - `tipo` de credencial: 1 a 30 caracteres.
   - `valor` de credencial: mínimo 1 caractere, sem limite superior (não conforme).
   - `base_url`, `descricao`, listas de perguntas e hipóteses: sem limite superior (não conforme).

2. **Onde essa caixa mora?**
   - Banco de dados relacional SQLite (`DATABASE_URL`, driver `aiosqlite`) nas tabelas `pesquisa`, `pontos`, `conteudo_coletado`, `credenciais`, `generation_attempts`.
   - Credenciais: cifradas com chave simétrica Fernet (AES-128-CBC + HMAC-SHA256) na tabela `credenciais.valor_cifrado`.
   - Navegador: `localStorage` guarda histórico sob `deep_research_local_history_v1`. Cookie `dr_local_session` HttpOnly guarda token de sessão local assinado.

3. **E se eu mandar senha vazia?**
   - Bloqueado com erro 422/400. `app/schemas/admin.py` valida `validate_not_blank` e rejeita vazios e espaços. Repositório reforça checagem antes de cifrar.

4. **E se eu colocar um item negativo na quantidade?**
   - Bloqueado com erro 422. `PlanRequest.n_pontos` valida `v < 1` e `PlanPreferencias.n_pontos` exige `ge=1`.

5. **E se eu colocar 10mil letras?**
   - No `tema`: rejeitado com HTTP 422 (`max_length=500`).
   - No `valor` de credencial ou `base_url`: aceito pelo Pydantic, cifrado e armazenado no SQLite sem truncamento (não conforme).

6. **E se eu clicar duas vezes ao mesmo tempo?**
   - Frontend: bloqueado via refs síncronas (`isPlanningRef` e `activeExecutionTokenRef`) impedindo duplicidade.
   - Backend: bloqueado por concorrência atômica CAS (`reserve_point` / `reserve_point_for_audit`) retornando erro 400 `CONCURRENT_EXECUTION`.

7. **Quantas vezes posso tentar?**
   - Na API HTTP: ilimitado (sem rate limit).
   - No ciclo do pipeline: máximo 4 tentativas de busca por ponto e 3 tentativas de auditoria por ponto (`MAX_ATTEMPTS_EXCEEDED`).

8. **E se eu pedir o dado de um outro usuário que não me pertence?**
   - Retorna o dado (vulnerabilidade IDOR / single-tenant). O sistema não possui isolamento multi-tenant nem colunas `user_id` / `tenant_id`. Conhecendo o UUID `id_pesquisa`, qualquer cliente lê status, fontes e dossiê de outra pesquisa.

9. **Ele confere quem eu sou?**
   - Não confere identidade individual. Valida apenas chave de API compartilhada (`X-API-Key`) ou emite sessão com `sub: "local_user"` para clientes em loopback. Se a chave não estiver configurada no servidor, a API é aberta a qualquer solicitante.

10. **Isso é dado ou é comando?**
    - Para o sistema operacional / SQL: é estritamente dado (sem `eval`, `subprocess` ou injeção SQL).
    - Para os modelos LLM: há risco de injeção de prompt indireta, pois o tema do usuário e o conteúdo coletado entram na composição de prompts do redator e pesquisador sem barreira estrita contra instruções em linguagem natural (apenas delimitadores SERP são neutralizados).
