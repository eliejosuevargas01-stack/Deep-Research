# Spec: Módulo Integrações Externas (tools, prompts)

> Archaeologist — módulo 4 de 6  
> Confidência: 🟢 CONFIRMADO

## `app/tools/search_pipeline.py` (227 LOC) — Busca multi-provedor
- Provider chain (failover): **SerpAPI** (paid) → **Apify** (paid) → **Jina Search** (free+key) → **DuckDuckGo** (free fallback, via Jina proxy ou direct POST).
- `Source` dataclass: `url, title, excerpt`.
- `search_read(query, limit, keys)`: search → `asyncio.gather(read_source)` → fonte lida com sucesso.
- `read_source`: 1) Jina Reader (`r.jina.ai/{url}`) → 8000 chars; 2) fallback scrape HTML direto → 8000 chars, strip `<script|style|noscript>`.
- 🟢 `_safe(url)`: toda URL validada por `validate_public_url` (SSRF guard) antes de uso.
- `_get`: `PinnedResolver` (DNS pinning), `trust_env=False`, `allow_redirects=False`.
- 🟡 `read_source` trunca em 8000 chars — fonte longa pode perder trecho citável (contract verbatim_quote exige substring exata).
- **Known debt**: `excerpt` do search provider ignorado no `read_source` (sempre tenta full read); `search_read` pede `min(10, max(5, limit))`.

## `app/tools/outbound.py` (51 LOC) — SSRF Guard
- 🟢 `validate_public_url`: esquema http/https + hostname não vazio + resolução DNS onde cada IP resolvido é público (`is_forbidden_ip`), sem redirects, sem credentials na URL.
- 🟢 `is_forbidden_ip`: loopback, link-local, multicast, reserved, unspecified + cloud metadata (`169.254.169.254` etc.).
- 🟢 `PinnedResolver`: resolve hostname uma vez, valida IP, pin no connector (anti DNS-rebinding durante request).
- `SSRFSecurityViolation(ValueError)`.

## `app/prompts/__init__.py` — vazio
- 🔴 **LACUNA**: file vazio (0 bytes) mas módulo importado pelo frontend? Não — não aparece em imports do backend. Prompts vindos de `personas.json`. Ver `questions.md`.

## `app/prompts/personas.json`
- 4 personas + scout + writer + auditor + system prompts + params (temperature, max_tokens).
- 🟡 LACUNA documentada no `architecture.md` legado: "em migração para .md" — não ocorreu.

## Lacunas 🔴
1. `app/prompts/__init__.py` vazio, importado em nenhum lugar do backend — módulo morto ou residência futura dos prompts `.md`. Ver `questions.md`.
2. `read_source` trunca fonte em 8000 chars — pode perder citações verbatim de artigos longos (contract: `exact_quote` deve ser substring exata do source). Ver `questions.md`.
```
