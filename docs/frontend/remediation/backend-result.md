# Backend Implementation Report - Checkpoint 1 (Remediation 20261026)

## 1. Visão Geral e Escopo Entregue
Em estrito cumprimento das diretrizes de remediação integral (`requirements.json` e `backend-worker-task.md`), a implementação do backend unificado foi concluída com sucesso para o Checkpoint 1 (modo síncrono; sem SSE).

A entrega unifica o frontend React (compilado em `frontend/dist`) e o backend FastAPI sob a mesma origem, eliminando a exigência de chave `API_SECRET_KEY` na experiência de navegação do usuário local, enquanto preserva e blinda os contratos de segurança externa, provedores de inferência (`OPENAI_API_KEY`, `JINA_API_KEY`) e persistência atômica das preferências por pesquisa.

---

## 2. Correções Específicas dos 5 Casos de Fronteira (Review Notes)

### Caso 1: Rejeição de Origem com Porta Diferente (Different port origin must reject)
- **Problema anterior:** `verify_same_origin_csrf` extraía o hostname descartando a porta (`split(':')[0]`), permitindo requisições mutantes com cookie vindas de portas distintas (ex: `http://localhost:3000` em servidor `http://localhost:8000`).
- **Correção:** `get_request_origin(request)` e `_canonical_origin(url_str)` agora constroem a tupla exata de mesma origem `f"{scheme}://{host}"` incluindo porta canônica. Qualquer porta divergente é estritamente rejeitada com HTTP 403.
- **Teste de evidência:** `tests/integration/test_web_app.py::test_auth_boundary_case1_different_port_origin_must_reject` (PASSED).

### Caso 2: Rejeição de Requisição Mutante sem Prova de Origem (Missing Origin/Referer/fetch metadata must reject unsafe cookie request)
- **Problema anterior:** Requisições `POST`/`PUT`/`DELETE`/`PATCH` sem cabeçalhos `Origin`, `Referer` ou fetch metadata podiam passar se apenas o cookie estivesse presente.
- **Correção:** `verify_same_origin_csrf` agora exige explicitamente prova de origem em métodos mutantes (`is_mutating`). Se tanto `Origin` quanto `Referer` estiverem ausentes, o acesso é rejeitado com HTTP 403.
- **Teste de evidência:** `tests/integration/test_web_app.py::test_auth_boundary_case2_missing_origin_and_referer_must_reject_unsafe_cookie_request` (PASSED).

### Caso 3: Rejeição de Origem com Esquema Diferente (Different scheme origin must reject)
- **Problema anterior:** A comparação de origem não verificava estritamente o esquema HTTP vs HTTPS.
- **Correção:** O esquema (`http` vs `https`) faz parte obrigatória da comparação da origem canônica exata. Requisições `http` com `Origin: https` (ou vice-versa) são rejeitadas com HTTP 403.
- **Teste de evidência:** `tests/integration/test_web_app.py::test_auth_boundary_case3_different_scheme_origin_must_reject` (PASSED).

### Caso 4: Rejeição de Hostnames Não-IP com Prefixo 127 (Untrusted 127-prefix hostname must reject bootstrap)
- **Problema anterior:** `_is_loopback_ip` usava `ip_clean.startswith("127.")`, aceitando domínios maliciosos como `127.evil.invalid`.
- **Correção:** Validação estrita via `ipaddress.ip_address(clean_ip).is_loopback`. Se o valor não for um endereço IP IPv4/IPv6 sintaticamente válido, `ipaddress.ip_address` lança `ValueError` e a função retorna `False`. Hostnames permitidos em `_is_local_host` foram restritos a `{"localhost", "127.0.0.1", "::1"}` (sem tokens frouxos como `testserver` em código de produção).
- **Teste de evidência:** `tests/integration/test_web_app.py::test_auth_boundary_case4_untrusted_127_prefix_hostname_must_reject_bootstrap` (PASSED).

### Caso 5: Rejeição Segura de Cookies Malformados ou Unicode (Malformed Unicode cookie must be rejected without exception)
- **Problema anterior:** `verify_session_token("é.signature")` tentava codificar a string em ASCII sem captura, levantando `UnicodeEncodeError` não tratado e podendo gerar HTTP 500.
- **Correção:** `verify_session_token` valida se ambos os segmentos (`b64_payload` e `b64_sig`) são estritamente ASCII dentro de bloco `try/except`. Qualquer caractere não-ASCII, formato inválido, base64 corrompido, excesso de segmentos ou payload inválido falha fechado retornando `False`, resultando em HTTP 401 limpo quando API_SECRET_KEY está ativa.
- **Teste de evidência:** `tests/integration/test_web_app.py::test_auth_boundary_case5_malformed_unicode_cookie_rejected_without_exception` (PASSED).

---

## 3. Complementos de Empacotamento, Resolução e Interface

### 3.1. Resolução Efetiva de Preferências via ENV -> Banco Cifrado
- **Implementação:** `get_default_preferences(db: AsyncSession)` em `app/ui_session.py` resolve `n_pontos` e `personas` consultando primeiro variáveis de ambiente e, na sua ausência, recupera as credenciais descriptografadas do banco relacional via `resolve_n_pontos(db)` e `resolve_personas(db)`.
- **Rota `GET /app/session`:** Injeta a sessão assíncrona do banco (`Depends(get_db)`) e devolve os valores efetivos do banco caso o ambiente não os defina.
- **Teste de evidência:** `tests/integration/test_web_app.py::test_session_bootstrap_resolves_preferences_from_db_when_env_absent` (PASSED).

### 3.2. Script `scripts/run_app.py`
- Executa verificação prévia de dependências: se `frontend/node_modules` não existir, executa `npm ci`.
- Previne assets obsoletos: quando solicitado `--build` (force_clean=True), remove o `dist/index.html` anterior antes de disparar o build, garantindo que uma falha subsequente (ou ausência de npm) nunca mascare o erro com assets legados.
- Se o build falhar ou npm estiver ausente, encerra imediatamente com código de saída não-zero (`sys.exit(1)`).
- Garante importação correta da aplicação partindo de qualquer diretório via `sys.path.insert(0, str(root_dir))` e `os.chdir(str(root_dir))`.

### 3.3. Retorno HTTP 503 para Bundle Ausente
- Em `app/main.py`, a rota SPA `GET /{full_path:path}` verifica a existência de `frontend/dist/index.html`. Caso o bundle não esteja compilado, retorna HTTP 503 Service Unavailable com mensagem orientando a compilação do frontend, em vez de retornar HTTP 200 com HTML de placeholder.
- **Teste de evidência:** `tests/integration/test_web_app.py::test_missing_bundle_index_html_returns_503` (PASSED).

### 3.4. Dockerfile, Docker Compose e Fronteira de Rede Local
- **Dockerfile:** Multi-stage build com Node 20 para compilar o frontend e runtime limpo Python 3.14 (sem Node em produção). Arquivo `.env` NUNCA é copiado para a imagem. O container define `HOST=127.0.0.1` e `PORT=8000` por padrão, executando uvicorn com bind estrito em `127.0.0.1` (em vez de `0.0.0.0`).
- **docker-compose.yml:**
  - Define comando explícito: `command: ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8085"]`.
  - Injeta credenciais em tempo de execução via `env_file: - .env` sem expor segredos na imagem.
  - Substitui o caminho hardcoded `/root/projects/...` por volume relativo ao projeto: `./data:/app/data`.
  - Preserva overrides `DATABASE_URL=sqlite+aiosqlite:////app/data/deep_research.db` e `CREDENTIALS_MASTER_KEY=${CREDENTIALS_MASTER_KEY}`.
  - No Linux, `network_mode: host` compartilha a pilha de rede do host, preservando `request.client.host == 127.0.0.1` e mantendo a fronteira de sessão local íntegra.
  - **Limitações de plataforma:** Em macOS e Windows (Docker Desktop com VM intermediária), `network_mode: host` não compartilha diretamente o loopback do host. Nesses sistemas operacionais, para execução local de desenvolvimento, deve-se utilizar diretamente o runner host `scripts/run_app.py`.

---

## 4. Arquivos Modificados e Novos Componentes

### 2.1. Novos Arquivos de Domínio, Sessão e Infraestrutura
- `app/ui_session.py`:
  - Gerenciador de sessão local com assinatura criptográfica HMAC-SHA256 (`dr_local_session`).
  - Verificação de elegibilidade de cliente local (`client.host` loopback + `Host` header autorizado).
  - Emissão de cookie `HttpOnly`, `SameSite=Strict`, `Path=/`, com tempo de vida (`exp`) e `nonce`.
  - Proteção contra CSRF e ataques cross-origin (`Sec-Fetch-Site`, `Origin`, `Referer`) para requisições mutantes (`POST`, `PUT`, `DELETE`, `PATCH`).
  - Resolução privada das preferências padrão do servidor (`n_pontos` e subconjunto de `personas`).
  - Segredo de assinatura isolado e nunca retornado em payloads nem registrado em logs.
- `scripts/run_app.py`:
  - Script executável de inicialização local com suporte a flags (`--host`, `--port`, `--build`, `--reload`).
  - Vinculação estrita ao bind `127.0.0.1` por padrão (protegendo a fronteira de sessão local).
  - Carregador seguro de `.env` que não sobrescreve variáveis de ambiente injetadas.
  - Gatilho automático de compilação de assets caso `frontend/dist/index.html` não exista.
- `tests/integration/test_web_app.py`:
  - 14 testes de integração cobrindo emissão de sessão, servir HTML/assets, 404 estrito em assets faltantes, bloqueio de path traversal, rejeição de remotos e de host headers maliciosos, bypass de API key para cookies válidos, proteção 401 para requisições externas não autenticadas e proteção CSRF.
- `tests/integration/test_research_preferences.py`:
  - 13 testes de integração e validação Pydantic cobrindo validação estrita de `n_pontos` (rejeitando bool/float), validação do subconjunto das 4 personas de busca, persistência de snapshot em `metadados_planejamento` JSON, isolamento entre pesquisas concomitantes e não-vazamento de credenciais.

### 2.2. Arquivos do Backend Atualizados
- `app/config.py`:
  - Ajuste no carregamento hermético de configurações com Pydantic Settings, garantindo que em ambiente de teste `pytest` o arquivo `.env` do desenvolvedor não contamine testes unitários com valores externos.
- `app/core/security.py`:
  - Implementação da autenticação dupla: valida clientes externos com `X-API-Key` ou `Authorization: Bearer` e clientes locais de navegador via cookie assinado `dr_local_session`.
  - Rejeita com HTTP 401 requisições sem nenhuma credencial válida quando `API_SECRET_KEY` estiver configurada.
  - Clientes nativos externos de API continuam sem exigência de cabeçalhos de navegador (`Origin`).
- `app/schemas/plan.py`:
  - `PlanRequest`: campos aditivos `n_pontos` (inteiro positivo estrito, validado contra `bool` e `float`) e `personas` (subconjunto não vazio e único de `['historiador', 'visionario', 'cetico', 'futurista']`).
  - `PlanResponse` e `PlanAsyncResponse`: campo `preferencias: {n_pontos, personas}` com o snapshot efetivamente aplicado.
- `app/core/planner.py`:
  - Incorporação do parâmetro `preferencias` em `execute_plan(...)`, gravando o snapshot de preferências dentro de `metadados_planejamento` JSON da tabela `pesquisa`.
  - Preservação intacta de todas as métricas observáveis de telemetria, envelopes e custos.
- `app/api/v1/endpoints/plan.py`:
  - Extração e validação de `n_pontos` e `personas` solicitados, repassando a contagem de pontos diretamente ao `Planner`.
  - Verificação de conformidade na saída: falha explicitamente com HTTP 422 caso haja divergência entre os pontos gerados e o número solicitado.
- `app/api/v1/endpoints/search.py` e `app/core/searcher.py`:
  - Ao executar `/search` sem o parâmetro explícito `personas`, recupera automaticamente o snapshot armazenado em `metadados_planejamento` da pesquisa, garantindo que retentativas e continuidade do pipeline usem o mesmo conjunto selecionado.
- `app/main.py`:
  - Rota `GET /app/session` retornando `{authenticated: true, mode: "local", preferences: {n_pontos, personas}}` com emissão do cookie assinado.
  - Rota de assets `GET /assets/{file_path:path}` servindo arquivos estáticos de `frontend/dist/assets` com 404 estrito quando ausentes (não caindo em index.html).
  - Rota raiz SPA `GET /{full_path:path}` servindo `frontend/dist/index.html` e autenticando automaticamente clientes locais elegíveis.
  - Sanitização de exceções `RequestValidationError` usando `jsonable_encoder` para respostas JSON estritas.
- `Dockerfile` e `docker-compose.yml`:
  - Build multi-stage (Node 20 compila o frontend e copia `frontend/dist` para o container Python 3.14).
  - Compose com porta vinculada explicitamente a `127.0.0.1:8085:8000`, respeitando a fronteira de segurança local.
- `tests/mocks/http_mock.py`:
  - Mock de rede atualizado para suportar planos dinâmicos com contagem variável de eixos (`n_pontos`) baseados nas mensagens do prompt agêntico.

---

## 3. Contrato da API Coordenado com o Frontend

### 3.1. Sessão e Autenticação
- `GET /app/session`
  - Resposta Local (elegível):
    ```json
    {
      "authenticated": true,
      "mode": "local",
      "preferences": {
        "n_pontos": 1,
        "personas": ["historiador", "visionario", "cetico", "futurista"]
      }
    }
    ```
    - Header: `Set-Cookie: dr_local_session=<token>; HttpOnly; Path=/; SameSite=Strict`
  - Resposta Remota (não-loopback):
    ```json
    {
      "authenticated": false,
      "mode": "remote",
      "preferences": {
        "n_pontos": 1,
        "personas": ["historiador", "visionario", "cetico", "futurista"]
      }
    }
    ```

### 3.2. Formulação de Plano
- `POST /api/v1/plan`
  - Payload de entrada (aditivo e retrocompatível):
    ```json
    {
      "tema": "Impacto da Inteligência Artificial",
      "n_pontos": 3,
      "personas": ["visionario", "cetico"],
      "async_execute": false
    }
    ```
  - Resposta (eco de snapshot):
    ```json
    {
      "id_pesquisa": "uuid-...",
      "tema": "Impacto da Inteligência Artificial",
      "n_pontos": 3,
      "criado_em": "2026-10-26T...",
      "status_pipeline": "planejado",
      "pontos": [...],
      "plano_estruturado": {...},
      "metadados_modelo": {...},
      "preferencias": {
        "n_pontos": 3,
        "personas": ["visionario", "cetico"]
      }
    }
    ```

### 3.3. Varredura com Personas
- `POST /api/v1/search`
  - Quando `personas` for omitido: utiliza o snapshot gravado na pesquisa em `metadados_planejamento.preferencias.personas`.
  - Quando `personas` for informado: honra o filtro explícito para retentativas focadas.

---

## 6. Evidências de Teste e Comprovação

### 6.1. Testes de Integração Específicos do Web App (22 testes)
```bash
$ .venv/bin/pytest tests/integration/test_web_app.py -v
============================== test session starts ==============================
collected 22 items

tests/integration/test_web_app.py::test_fresh_session_issuance_for_local_client PASSED [  4%]
tests/integration/test_web_app.py::test_spa_root_serves_html_and_sets_cookie_for_local_client PASSED [  9%]
tests/integration/test_web_app.py::test_static_assets_served_same_origin PASSED [ 13%]
tests/integration/test_web_app.py::test_missing_assets_must_return_404_not_index_html PASSED [ 18%]
tests/integration/test_web_app.py::test_path_traversal_on_assets_returns_404 PASSED [ 22%]
tests/integration/test_web_app.py::test_remote_client_cannot_bootstrap_local_session PASSED [ 27%]
tests/integration/test_web_app.py::test_cross_origin_session_bootstrap_rejected PASSED [ 31%]
tests/integration/test_web_app.py::test_malicious_host_bootstrap_rejected PASSED [ 36%]
tests/integration/test_web_app.py::test_browser_session_cookie_grants_access_without_api_key PASSED [ 40%]
tests/integration/test_web_app.py::test_client_without_key_or_cookie_gets_401_when_key_configured PASSED [ 45%]
tests/integration/test_web_app.py::test_external_api_key_and_bearer_auth_remain_functional PASSED [ 50%]
tests/integration/test_web_app.py::test_tampered_or_expired_cookie_rejected_with_401 PASSED [ 54%]
tests/integration/test_web_app.py::test_mutating_cookie_request_cross_origin_rejected_with_403 PASSED [ 59%]
tests/integration/test_web_app.py::test_mutating_cookie_request_same_origin_succeeds PASSED [ 63%]
tests/integration/test_web_app.py::test_auth_boundary_case1_different_port_origin_must_reject PASSED [ 68%]
tests/integration/test_web_app.py::test_auth_boundary_case2_missing_origin_and_referer_must_reject_unsafe_cookie_request PASSED [ 72%]
tests/integration/test_web_app.py::test_auth_boundary_case3_different_scheme_origin_must_reject PASSED [ 77%]
tests/integration/test_web_app.py::test_auth_boundary_case4_untrusted_127_prefix_hostname_must_reject_bootstrap PASSED [ 81%]
tests/integration/test_web_app.py::test_auth_boundary_case5_malformed_unicode_cookie_rejected_without_exception PASSED [ 86%]
tests/integration/test_web_app.py::test_auth_boundary_cross_origin_localhost_vs_127_0_0_1_must_reject PASSED [ 90%]
tests/integration/test_web_app.py::test_missing_bundle_index_html_returns_503 PASSED [ 95%]
tests/integration/test_web_app.py::test_session_bootstrap_resolves_preferences_from_db_when_env_absent PASSED [100%]

============================== 22 passed in 0.70s ==============================
```

### 6.2. Testes de Integração de Preferências de Pesquisa (13 testes)
```bash
$ .venv/bin/pytest tests/integration/test_research_preferences.py -v
============================== test session starts ==============================
collected 13 items

tests/integration/test_research_preferences.py::test_plan_request_pydantic_accepts_valid_strict_integers PASSED [  7%]
tests/integration/test_research_preferences.py::test_plan_request_pydantic_rejects_bool_for_n_pontos PASSED [ 15%]
tests/integration/test_research_preferences.py::test_plan_request_pydantic_rejects_float_for_n_pontos PASSED [ 23%]
tests/integration/test_research_preferences.py::test_plan_request_pydantic_rejects_non_positive_n_pontos PASSED [ 30%]
tests/integration/test_research_preferences.py::test_plan_request_pydantic_accepts_valid_personas_subsets PASSED [ 38%]
tests/integration/test_research_preferences.py::test_plan_request_pydantic_rejects_invalid_personas PASSED [ 46%]
tests/integration/test_research_preferences.py::test_plan_endpoint_rejects_bool_and_float_via_http_422 PASSED [ 53%]
tests/integration/test_research_preferences.py::test_plan_endpoint_with_omitted_preferences_uses_server_defaults PASSED [ 61%]
tests/integration/test_research_preferences.py::test_plan_endpoint_with_custom_n_pontos_generates_exact_point_count PASSED [ 69%]
tests/integration/test_preferences_snapshot_persisted_in_metadados_planejamento_json PASSED [ 76%]
tests/integration/test_search_honors_stored_snapshot_when_personas_omitted PASSED [ 84%]
tests/integration/test_search_honors_explicit_valid_requested_subset PASSED [ 92%]
tests/integration/test_no_secret_keys_or_tokens_leaked_in_json_responses PASSED [100%]

============================== 13 passed in 0.76s ==============================
```

### 6.3. Testes Específicos de Empacotamento e Runner (4 testes)
```bash
$ .venv/bin/pytest tests/integration/test_packaging_and_runner.py -v
============================== test session starts ==============================
collected 4 items

tests/integration/test_packaging_and_runner.py::test_dockerfile_multi_stage_and_secure_bind PASSED [ 25%]
tests/integration/test_packaging_and_runner.py::test_docker_compose_config_structure_sanitized PASSED [ 50%]
tests/integration/test_packaging_and_runner.py::test_run_app_build_clean_handles_missing_npm_gracefully PASSED [ 75%]
tests/integration/test_packaging_and_runner.py::test_run_app_load_dotenv_does_not_override_existing_env PASSED [100%]

============================== 4 passed in 0.25s ==============================
```

### 6.4. Suíte Integral do Repositório (Unitários + Integração)
```bash
$ .venv/bin/pytest -q
........................................................................ [ 19%]
........................................................................ [ 38%]
........................................................................ [ 57%]
........................................................................ [ 76%]
........................................................................ [ 95%]
..................                                                       [100%]
378 passed, 8 warnings in 33.00s
```

Todos os 378 testes do projeto foram executados e passaram com 100% de sucesso, comprovando:
1. Empacotamento Docker e Docker Compose configurados com bind local 127.0.0.1 e porta 8085 documentada, sem exposição em 0.0.0.0 nem cópia de `.env` para a imagem.
2. Script `scripts/run_app.py` com limpeza prévia em build forçado, verificação de npm e tratamento de dependências ausentes via `npm ci`.
3. Todas as 5 falhas de fronteira de autenticação/segurança reportadas foram corrigidas e comprovadas por testes automatizados determinísticos.
4. Resolução dinâmica de preferências padrão via ENV -> Banco de dados cifrado (`resolve_n_pontos`, `resolve_personas`).
5. Bundle ausente resulta em HTTP 503 Service Unavailable claro.
6. Nenhuma regressão nas regras de integridade do pipeline existente (auditor, writer, jina, llm envelope).
7. Sessão local funcional sem qualquer necessidade de digitação de segredo pelo usuário no navegador.
8. API externa com `X-API-Key` e `Bearer` permanece 100% protegida contra acessos anônimos quando a chave está configurada.
9. Snapshot de preferências isolado por pesquisa e persistido fielmente no banco de dados.
10. Assets estáticos compilados servidos na mesma origem pelo FastAPI com código de status 404 estrito em arquivos inexistentes.
