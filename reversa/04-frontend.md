# S4 — Frontend (spec auditável)

**Escopo:** `frontend/**` — `src/`, `tests/`, config, `package.json`. `dist/` é build gerado (só registrado, conteúdo não auditado).
**Nível:** 2 Completo (sem C4/ERD/ADR profundos).
**Docs referência (só leitura):** `GOAL.md` §4 item 9, `plan.md` §7, `contracts.md` §7/§9.
**Verificação:** cada rota/componente citado lido direto em `src/`. `wc -l` executado em `frontend/src`.

## 1. Propósito

UI chat centrada em pesquisa multiagente: submissão de tema, review/edição one-time do briefing 5 pontos, acompanhamento live de personas, timeline de eventos, relatório markdown auditado, settings de provedores/modelos, resume de falhas, retry de callback. Layout 3 áreas: sidebar (histórico) + workspace central (chat) + drawer artefatos (Plano/Evidências/Relatório).

## 2. Arquivos + LOC (wc -l real)

`src/` total: **6304 linhas**.

| Arquivo | LOC | O que é |
|---|---|---|
| `src/main.tsx` | 2697 | **Monolito**: RootLayout (login+sidebar+topbar), HomePage, ResearchPage, SettingsPage, App provider, ErrorBoundary, router setup. Toda UI funcional mora aqui |
| `src/style.css` | 2090 | **Monolito CSS**: layout shell/workspace/drawer/chat/briefing/personas/timeline/report/settings/login/responsivo |
| `src/research-utils.ts` | 561 | Lógica pura: DAG briefing, ingestEvent, parseReportData, cache sessionStorage, status rank/guard, tabs, settings payload, callback retry rule |
| `src/components.css` | 347 | Primitivos CSS (.btn-*, .input, .card, .badge-*, .tabs, .drawer, tooltip, toast) |
| `src/tokens.css` | 272 | Design tokens Linear dark (cores, spacing, radius, z-index, tipografia, focus-ring) |
| `src/api.ts` | 132 | Client fetch: ApiError, CSRF, HttpOnly cookie transport, auto-reauth, login/logout helpers |
| `src/types.ts` | 87 | Tipos: Point, Research, Event, AuditFindingPoint, ReportData, Settings |
| `src/ui.tsx` | 85 | Primitivos React: Button, Input, Card, Badge, Tabs, Drawer |
| `src/routes.ts` | 33 | TanStack Router code-based: `/`, `/research/$id`, `/settings` + factory `createProductionRouteTree` |
| **Config raiz** | — | `package.json`, `vite.config.ts` (20), `tsconfig.json` (strict, noUnusedLocals), `tailwind.config.js` (21, preflight:false), `eslint.config.js` (28), `index.html` (root pt-BR), `nginx.conf` (25) |
| `tests/frontend.test.mjs` | 892 | 28 testes node:test contra módulos reais (`research-utils.ts`, `routes.ts`, `api.ts`) |
| `dist/` | — | Build gerado: `index.html` + `assets/` (vendor-react, vendor-router, vendor-markdown, vendor-lucide, index JS/CSS). **Não auditado** |

Arquivos monolíticos >500 LOC: `main.tsx` (2697 — 4 páginas + provider + router + error boundary + toda interação research/settings), `style.css` (2090 — todo CSS app), `research-utils.ts` (561 — DAG + cache + parse + guards).

## 3. Stack (package.json real)

- React 19 + react-dom 19, TypeScript 5.5.4 (strict), Vite 5.4.2 + @vitejs/plugin-react 5.0.7
- Router: `@tanstack/react-router` 1.52.0 (code-based, **não** file-based — ver §7)
- Styling: `tailwindcss` 3.4.1 (preflight desligado) + CSS custom (`style.css` legado + `tokens.css` + `components.css`)
- Ícones: `lucide-react`; Markdown: `react-markdown` + `remark-gfm` (links externos `target=_blank rel=noopener`, classe `report-source-link`)
- Validação/teste: `zod`, `node --test tests/*.test.mjs`; lint `eslint src`, build `tsc && vite build`
- **Sem Zustand**: estado via React Context (`AppContext`) + `useState`/`useRef` + `sessionStorage` (ver §6)
- Dev proxy Vite: `/api` e `/health` → `127.0.0.1:8000`. Prod: nginx `proxy_pass backend:8000` em `/api/` e `/health`, `proxy_read/send_timeout 300s`, `proxy_buffering off` em `/api/`, SPA fallback `try_files ... /index.html`

## 4. Rotas (routes.ts + main.tsx)

| Rota | Componente (main.tsx) | Função |
|---|---|---|
| `/` | `HomePage` (l.445) | Hero + composer textarea (min 3/max 500) + Enter-envia + 4-step guide; `POST /api/research` → navega `/research/$id` |
| `/research/$id` | `ResearchPage` (l.567) | Chat + briefing + personas + timeline + completion card + composer inferior + drawer artefatos (tabs Plano/Evidências/Relatório) |
| `/settings` | `SettingsPage` (l.2021) | Provider keys + test + endpoints/webhooks + modelos por papel + save |
| (layout) | `RootLayout` (l.131) | Login screen se `!authenticated`; senão sidebar + topbar + `<Outlet/>`; banners error/notice; skip-link, focus trap mobile |

Sem rota dedicada `/login`: login é estado dentro de `RootLayout` (form password → `login(pwd)`).

## 5. Componentes principais (todos dentro de main.tsx)

- **Chat (HomePage composer + ResearchPage thread):** `HomePage` submit (l.451-471); thread `conversation-thread` (l.1200): bolha usuário + scout card (`scouting`) + briefing card (`pending_approval`) + personas grid + timeline + completion card + failed card + `chatBottomRef` auto-scroll. Composer inferior varia por status: textarea ajustes (`pending_approval`), status concluído, spinner em andamento.
- **Briefing review (l.1229-1341):** inputs título/descrição por ponto, checkbox `is_parallelizable`, botões ↑/↓ com `canMovePoint` (bloqueia violação DAG), `editNote` textarea, ações `approve()` (`POST .../briefing/approve` + `{approved_points}`) e `sendAdjustments()` (`POST .../briefing/edit` + `{note, points}`). Validação local: título/descrição ≥3 chars.
- **Stream SSE + timeline:** `EventSource('/api/research/'+id+'/events', {withCredentials:true})` (l.736), listener único `progress` (l.742), dedupe por `seenEventIdsRef` + `ingestEvent` (ordena por id), `sseState` connecting/connected/reconnecting/closed + indicador UI + botão "Tentar agora". Tipos tratados: `synthesis_completed` (carrega report), `callback_delivered/failed`, `research_failed/scout_failed`, `briefing_ready/briefing_approved` (recarrega research). Timeline renderiza `events` (persona, hora pt-BR, summary). Polling fallback 4s para jobs in-flight (l.860-897) + guard anti-regressão `canTransitionStatus` + `createLatestRequestGuard` (abort request antiga).
- **Personas grid (l.1344-1409):** 4 cards fixos historian/skeptic/pragmatist/futurist com status waiting/active/done/failed, último summary, contagem eventos, ponto/ferramenta. Visível em approved/in_progress/completed/completed_but_callback_failed/blocked.
- **Relatório (drawer tab + completion card):** `parseReportData` (research-utils) exige `report_id` + `content_markdown`; `citation_metrics`, `audit_findings.points` (status/verdict/reason, deterministic supported/unsupported com url/claim/excerpt/reason, llm findings/contradictions/uncertainties/missing_research). UI: audit badges, chips por ponto, accordion ressalvas, `ReactMarkdown`, copiar clipboard, export `.md` via Blob, retry callback (`POST /api/reports/{id}/retry-callback`, elegível só via `isCallbackRetryable`).
- **Settings (l.2021-2507):** `GET /api/settings` (bloqueia form se falhar), `PUT /api/settings` via `buildSettingsPayload`, `GET /api/settings/models` catálogo dinâmico, `POST /api/settings/test` por provider + proxy. Campos: 7 providers (openai/anthropic/gemini/litellm/jina/serpapi/apify), openai_base_url, jina_proxy_url, jina_proxy_auth_key (só envia se preenchido), jina_base_url, callback_url, jina_proxy_timeout; modelos por 7 papéis via `getModelOptions` (preserva prefixo provider, mantém `savedOnly` se catálogo indisponível). Chaves nunca retornam (placeholder `••••`); remoção = string vazia.
- **Login/logout:** `RootLayout` form password; `App.login` → `POST /api/auth/login {password}` → guarda `csrf_token`; `logoutUser` (api.ts) → `POST /api/auth/logout` (401 = já revogado, limpa local; 403/erro rede = throw, preserva sessão). `auth-expired` event em 401/403 → limpa sessão + cache.
- **Primitivos (ui.tsx, 85 LOC):** Button/Input/Card/Badge/Tabs/Drawer — **quase não usados** pelo monolito (main.tsx usa classNames diretas de style.css).

## 6. API client + auth (api.ts, 132 LOC)

- `fetch(path, {...options, credentials:'same-origin'})`, `Content-Type: application/json` auto em body.
- CSRF: `X-CSRF-Token` em mutações (não-GET/HEAD) se token presente; em 403 de mutação (exceto auth/csrf/login/logout) busca `GET /api/auth/csrf` e retry 1x.
- `prepareHeaders` **remove `X-Tenant-ID`** (qualquer case).
- `buildResearchPayload`: só `{theme}` trimado, exige ≥3 chars; sem api_key/jwt/callback_url no payload browser.
- `initializeSession`: `GET /api/auth/me` → `GET /api/auth/csrf`; falha limpa csrf + `dr_*` cache.
- Erros: `ApiError(message=detail, status)`; 401/403 dispara `auth-expired` (exceto me/login/logout).
- Endpoints chamados pelo frontend: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET /api/auth/csrf`, `GET /api/research` (histórico), `POST /api/research`, `GET /api/research/{id}`, `POST .../briefing/approve`, `POST .../briefing/edit` (extra, fora contracts), `POST .../resume`, SSE `GET .../events` (ver gap G2), `GET /api/reports/{id}`, `POST /api/reports/{id}/retry-callback`, `GET/PUT /api/settings`, `GET /api/settings/models`, `POST /api/settings/test`.

## 7. Estado

Sem Zustand. `AppContext` (authenticated, history, sidebarOpen, artifactsOpen, mobileMenu, error, notice, login, logout, busy) + estados locais por página. Cache `research-utils.ts`: `sessionStorage` (fallback Map memória) chaves `dr_res_{id}`, `dr_draft_{id}`, `dr_events_{id}`, `dr_report_{id}`; sanitiza research (sem segredos); `clearAllDrCache` no logout/expiração (varre `dr_*` em session+localStorage+memória). Guards: `STATUS_RANK` + `canTransitionStatus` (impede regressão; failed/interrupted → in_progress/scouting permitido), `createLatestRequestGuard` (abort request obsoleta).

## 8. Doc-vs-código etiquetado

### GOAL §4 item 9
- 🟢 CONFIRMADO — React 19 + TanStack Router + Tailwind, chat-centered (`main.tsx` l.1-10, `package.json`, `style.css` shell/workspace).
- 🟢 CONFIRMADO — Submissão tema (HomePage l.451-471, min 3/max 500).
- 🟢 CONFIRMADO — Briefing 5 pontos review/edit (l.1229-1341, reorder com DAG, approve + edit note).
- 🟢 CONFIRMADO — Atividade personas realtime (grid l.1352 + timeline l.1412 + SSE l.731).
- 🟡 INFERIDO — "public learning/next-step summaries": UI exibe `event.summary` + `metrics/tool/point`, sem campo explícito `next_step`; assume summary cobre.
- 🟢 CONFIRMADO — Resume flow (`handleResume` l.993 + botão failed l.1137 + polling).
- 🟢 CONFIRMADO — Markdown report view (ReactMarkdown l.1974 + copy/export).
- 🟢 CONFIRMADO — Settings com free default + `jina_proxy` (url + auth key) sem pedir pool interno Jina (SettingsPage l.2331-2405; jina badge "Opcional (fallback público)").
- 🟢 CONFIRMADO — JWT HttpOnly cookie + CSRF, sem expor JWT/segredos (`api.ts` l.35-37,72; credentials same-origin; chaves só `••••`).

### contracts §7
- 🟢 CONFIRMADO — `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` (api.ts + App l.2584-2643).
- 🟢 CONFIRMADO — `POST /api/research {theme}` 201, `GET /api/research/{id}`, `POST .../briefing/approve {approved_points}`.
- 🔴 LACUNA — G2: SSE em `GET /api/research/{id}/events` (l.736) vs contrato `GET /api/research/{id}/stream`; listener único `progress` vs eventos `progress/brief_ready/worker_progress/audit_decision/report_ready`.
- 🟢 CONFIRMADO — `GET /api/reports/{id}`, `POST /api/reports/{id}/retry-callback {success}`.
- 🟡 INFERIDO — Settings mascarado: frontend recebe `provider_configured/models/callback_url/...` sem segredos; criptografia AES é server-side, frontend só não exibe.
- 🟡 INFERIDO — Webhook POST com research_id/theme/content: frontend só mostra status delivered/failed + retry; payload é backend.

### contracts §9
- 🟢 CONFIRMADO — Gate one-time: briefing card só em `pending_approval`; workers/personas só após approve.
- 🟢 CONFIRMADO — Sem bypass no client (approve é único caminho; polling não avança status).
- 🟢 CONFIRMADO — Full editability: título/descrição/reorder/paralelo + edit note.
- 🟡 INFERIDO — "Authorized local implementation sem gates artificiais": N/A ao frontend.

### plan §7
- 🟢 CONFIRMADO — React 19, Vite, TS, TanStack Router, Tailwind + tokens Linear (`#0d0e11`-like, `#5e6ad2`, `#7170ff`), SSE consumer, provider keys + model selectors por papel.
- 🔴 LACUNA — G1: sem `routes/`, `components/chat|report|settings/`, `stores/*.zustand`; tudo em `main.tsx`. Sem `research.store.ts`/`settings.store.ts` (Zustand ausente do package.json).
- 🔴 LACUNA — G3: `PLAN.md` (frontend) prevê salvar settings em localStorage e enviar no payload research — código atual faz oposto (sessionStorage sem segredos, payload só `{theme}`); doc local desatualizado.

## 9. Gaps (6)

- **G1 — Arquitetura real ≠ plan §7:** monólito `main.tsx` 2697 + `style.css` 2090; sem `routes/`, `components/`, `stores/` Zustand. Risco: manutenção/teste UI (só lógica pura tem teste). 🔴 LACUNA
- **G2 — SSE path/evento diverge do contrato:** client usa `/events` + evento único `progress` com `event.type` interno; contrato diz `/stream` + múltiplos `event:` nomeados. Se backend só expõe `/stream`, live quebra. Confirmar backend. 🔴 LACUNA
- **G3 — `frontend/PLAN.md` desatualizado:** manda settings em localStorage + payload research; código usa HttpOnly cookie + sessionStorage sanitizado. Doc induz erro. 🔴 LACUNA
- **G4 — `briefing/edit` sem contrato:** `POST .../briefing/edit {note, points}` não existe em contracts §7/plan fluxos. Funcional, mas sem spec. 🟡 INFERIDO
- **G5 — `ui.tsx` não adotado:** primitivos Button/Input/Card/Badge/Tabs/Drawer existem mas main.tsx usa classes diretas; dois sistemas convivem. Dívida (DESIGN.md já registra). 🟡 INFERIDO
- **G6 — Polling 4s sem spec:** fallback além do SSE (l.860) não consta nos contratos; ajuda resiliência mas gera carga; sem Last-Event-ID/resume explícito no client (dedupe é por id em memória/cache). 🟡 INFERIDO

Verificado por leitura direta: `main.tsx` (RootLayout/Home/Research/Settings/SSE 731-857/polling 860-897/approve 903/edit 932/retry 963/resume 993/router 2512), `api.ts` (tudo), `routes.ts` (tudo), `types.ts`, `research-utils.ts`, `ui.tsx`, `vite.config.ts`, `nginx.conf`, `package.json`, `tests/frontend.test.mjs` (28 testes), `DESIGN.md`/`PLAN.md` (frontend).
