# Spec: Módulo Pipeline Cognitivo (services)

> Archaeologist — módulo 3 de 6  
> Confidência: 🟢 CONFIRMADO (591 LOC `research.py` lido integralmente)

## `app/services/research.py` (591 LOC) — Orquestrador

### Arquitetura
- 4 personas fixas: `historian`, `skeptic`, `pragmatist`, `futurist` (configuráveis em AppSettings).
- Worker pool limitado: `asyncio.Semaphore(20)`.
- Timeout global scout: 120s.

### Funções principais
| Função | Tipo | Responsabilidade |
|--------|------|------------------|
| `extract_site_domain` | sync | Extrai domínio de URL |
| `sanitize_audit_dict` | sync | Redige dados sensíveis via `apply_output_guardrail` |
| `point_dependencies` | sync | Valida dependências 1-based, detecta ciclos |
| `ready_point_batches` | sync | Topologically batches points (max 20) |
| `remaining_attempts` | sync | Calcula tentativas restantes |
| `add_event` | async | Persiste Event em DB com metrics sanitizados |
| `sanitize_error` | sync | 🟢 Redação de erros (regex `sk|gsk|ghp|gho` + Bearer/token patterns) |
| `scout` | async | Busca web + seleção de fontes + briefing draft |
| `run_point` | async | Worker single-point (persona pipeline) |
| `run_research` | async | Orquestrador master — agenda points, coleta evidence, gera report |

### `scout` (A2-01): Live search + source selection
1. `search_read(theme, 10, keys)` → `Source[]` (busca múltipla providers).
2. Filtra `≥ 3 fontes distintas` (exige domicílios de sites distintos).
3. `validate_public_url` cada fonte (anti-SSRF).
4. Para cada fonte: `read_source` (Jina reader proxy) → trecho.
5. Chunk texto → seleciona top chunks via LLM (`point_selection_prompt`).
6. Gera 5 points via LLM (`scout_briefing_prompt`).

### `run_research` (pipeline master):
```
briefing → approve → ready_point_batches → run_point (parallel) → evidence → run_writer → report → dispatch_callback
```
- `run_point`: persona pipeline → auditor → 3 tentativas → evidence.
- `run_writer`: WriterAgent (gemini-3.6-flash) → compila report.
- Em cada stage: `add_event` + `AuditTrail`.

### `sanitize_error` patterns (🟢 security):
- Tokens: `(sk|gsk|ghp|gho)_[A-Za-z0-9_-]{16,}`
- Credenciais: `(bearer|token|key|secret|pass...)[=:\s]+[A-Za-z0-9_-.-]{6,}`

## `app/services/llm.py` (558 LOC) — Gateway LLM

### SSRF defence (`_enforce_safe_transport`):
- 🟢 Monkey-patch LiteLLM `AsyncHTTPHandler.create_client`, `HTTPHandler.create_client`, `BaseOpenAILLM._get_*_http_client`.
- Força `follow_redirects = False` em todo client.
- Fail-closed: `RuntimeError` se transport não suportar `follow_redirects`.
- Também anula `litellm.module_level_aclient.client.follow_redirects = False`.

### Funções principais
| Função | Responsabilidade |
|--------|------------------|
| `complete` | Wrapper `litellm.acompletion` com headers de segurança |
| `parse_json` | Extract JSON de output LLM (pode vir em ```json```) |
| `apply_output_guardrail` | Redação de dados sensíveis (tokens, keys) |
| `list_provider_models` | Discovery de modelos por provider |
| `test_provider_key` | Testa credencial sem persistir |
| `ProviderConfigurationError` | Custom exception |

## `app/services/audit.py` (35 LOC) — Auditoria determinística
- `deterministic_citation_audit`: verifica `exact_quote` matches verbatim (contract enforcement).
- `audit_approves`: decide aprovação de evidence.
- `next_audit_state`: state machine para ciclo de tentativas.

## `app/services/crypto.py` (32 LOC) — Encriptação
- AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
- `encrypt_secret`/`decrypt_secret` com nonce + `b"deep-research/settings/v1"` AAD.
- `mask_secret`: `xxx****yy` (≤6 = `****`).
- Key derivada via SHA-256 fallback se base64 não for 32 bytes.

## `app/services/webhook.py` (56 LOC) — Callback delivery
- `dispatch_callback`: POST para `research.callback_url` (validada via `validate_public_url`).
- `PinnedResolver` (DNS pinning) + `trust_env=False`.
- `allow_redirects=False`.
- Status `completed` → `completed_but_callback_failed` se falhar.
- AuditTrail stage="callback".

## `app/services/settings.py` (351 LOC) — Settings runtime
- `DEFAULT_ROLE_MODELS`: mapping role → modelo default (gemini 3.1/3.6/3.8 flash).
- `PROVIDER_BASE_URLS`: base URLs fixas por provider.
- `validate_base_url`: 🟢 SSRF defense (metadata, loopback, DNS rebinding check).
- `get_record`/`runtime_settings`/`public_settings`/`update_settings` CRUD AppSettings#1.
- Chaves sensíveis: DB (encrypted) > ENV (`OPENAI_API_KEY` etc) > fallback.
- `_UNSET` sentinel para partial updates no PUT.
- `validate_public_url`: valida callback_url + base_url via DNS resolution + `is_forbidden_ip` check.
- `is_forbidden_ip`: loopback, link-local, multicast, unspecified, cloud metadata IPs (`169.254.169.254`, etc.).

## `app/services/llm.py` — Safe Transport (extraído)
🟢 SSRF defence ativo — fail-closed. LiteLLM HTTP clients forçam `follow_redirects=False`.

## Lacunas 🔴
1. Nenhuma. Cobertura completa do pipeline cognitivo.
