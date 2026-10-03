import test from 'node:test'
import assert from 'node:assert/strict'

// Import REAL production modules (no copied functions, no mock implementations)
import {
  canMovePoint,
  canTransitionStatus,
  reorderBriefingPoints,
  validateBriefingApproval,
  ingestEvent,
  getModelOptions,
  parseReportData,
  statusLabel,
  getCachedResearch,
  setCachedResearch,
  getCachedDraft,
  setCachedDraft,
  clearCachedDraft,
  clearAllDrCache,
  getNextActiveTab,
  buildSettingsPayload,
  createLatestRequestGuard,
  isCallbackRetryable,
  getCachedEvents,
  setCachedEvents,
  getCachedReport,
  setCachedReport,
} from '../src/research-utils.ts'

import {
  router,
  routeTree,
  createProductionRouteTree,
} from '../src/routes.ts'

import {
  api,
  buildResearchPayload,
  prepareHeaders,
  getCsrfToken,
  setCsrfToken,
  clearSession,
  initializeSession,
  logoutUser,
} from '../src/api.ts'

// 1. Test production briefing points reordering & dependency updates (CRITERIA A3, MA-17)
test('Briefing points reordering maintains DAG (prior deps only) and conforms to real BriefingApproval contract', () => {
  const initial = [
    { title: 'Ponto 1', description: 'Desc 1', dependencies: [], is_parallelizable: true },
    { title: 'Ponto 2', description: 'Desc 2', dependencies: ['1'], is_parallelizable: false },
    { title: 'Ponto 3', description: 'Desc 3', dependencies: ['2'], is_parallelizable: false },
    { title: 'Ponto 4', description: 'Desc 4', dependencies: [], is_parallelizable: true },
    { title: 'Ponto 5', description: 'Desc 5', dependencies: ['3'], is_parallelizable: false },
  ]

  // MA-17: Moving a dependent before its base (e.g. Ponto 2 before Ponto 1) must be prevented/refused
  // rather than silently deleting dependencies.
  const invalidCheck = canMovePoint(initial, 1, -1)
  assert.equal(invalidCheck.allowed, false, 'Moving dependent point before its prerequisite must be disallowed')
  assert.ok(invalidCheck.reason?.includes('Não é possível mover'))

  const refusedMove = reorderBriefingPoints(initial, 1, -1)
  assert.deepEqual(refusedMove, initial, 'Invalid move must return points unchanged and preserve dependencies')
  assert.deepEqual(refusedMove[1].dependencies, ['1'], 'Dependencies must not be silently deleted')

  // Moving a point with valid dependencies preserved:
  // Swap Ponto 3 (index 2, deps ['2']) and Ponto 4 (index 3, deps [])
  const validCheck = canMovePoint(initial, 2, 1)
  assert.equal(validCheck.allowed, true, 'Valid reordering preserving DAG order must be allowed')

  const moved = reorderBriefingPoints(initial, 2, 1)
  assert.equal(moved[2].title, 'Ponto 4')
  assert.equal(moved[3].title, 'Ponto 3')
  // Ponto 3 still references Ponto 2 (which is at index 1 < new index 3)
  assert.deepEqual(moved[3].dependencies, ['2'])
  assert.deepEqual(moved[2].dependencies, [])

  // Conformance to real BriefingApproval contract
  const approvalValidation = validateBriefingApproval(moved)
  assert.equal(approvalValidation.valid, true, 'Reordered points must pass BriefingApproval validation')

  // Negative test: manually inject forward dependency and verify rejection
  const invalidForward = structuredClone(moved)
  invalidForward[0].dependencies = ['2']
  const invalidRes = validateBriefingApproval(invalidForward)
  assert.equal(invalidRes.valid, false)
  assert.ok(invalidRes.error?.includes('p_idx < idx'))

  // Boundary check: move index 0 up (out of bounds) should return original array unchanged
  const outOfBoundsTop = reorderBriefingPoints(initial, 0, -1)
  assert.deepEqual(outOfBoundsTop, initial)

  // Boundary check: move last index down (out of bounds) should return original array unchanged
  const outOfBoundsBottom = reorderBriefingPoints(initial, 4, 1)
  assert.deepEqual(outOfBoundsBottom, initial)
})

// 2. Test production SSE event deduplication and sorting (CRITERIA A5, A15)
test('SSE events deduplicate and maintain strict ID ordering via production module', () => {
  const events = [
    { id: 1, persona: 'scout', type: 'scout_started', summary: 'Scout started', created_at: '2026-10-02T10:00:00Z' },
    { id: 2, persona: 'scout', type: 'briefing_ready', summary: 'Briefing ready', created_at: '2026-10-02T10:01:00Z' },
  ]

  // Duplicate event with ID 2 should be rejected
  const step1 = ingestEvent(events, {
    id: 2,
    persona: 'scout',
    type: 'briefing_ready',
    summary: 'Briefing ready duplicate',
    created_at: '2026-10-02T10:01:00Z',
  })
  assert.equal(step1.length, 2)
  assert.equal(step1[1].summary, 'Briefing ready')

  // Out of order events with ID 4 and ID 3
  const step2 = ingestEvent(step1, {
    id: 4,
    persona: 'system',
    type: 'briefing_approved',
    summary: 'Approved',
    created_at: '2026-10-02T10:03:00Z',
  })
  const step3 = ingestEvent(step2, {
    id: 3,
    persona: 'system',
    type: 'worker_started',
    summary: 'Worker',
    created_at: '2026-10-02T10:02:00Z',
  })
  assert.equal(step3.length, 4)
  assert.deepEqual(step3.map(e => e.id), [1, 2, 3, 4])
  assert.equal(step3[2].summary, 'Worker')
})

// 3. Test cookie-session research payload compliance (CRITERIA A2, A4)
test('Research creation payload contains only theme and no browser credentials', () => {
  const payload = buildResearchPayload('   Impactos de computação quântica   ')
  assert.deepEqual(payload, { theme: 'Impactos de computação quântica' })
  assert.equal(Object.prototype.hasOwnProperty.call(payload, 'api_key'), false)
  assert.equal(Object.prototype.hasOwnProperty.call(payload, 'jwt_token'), false)
  assert.equal(Object.prototype.hasOwnProperty.call(payload, 'callback_url'), false)

  // Rejection check for invalid short theme (< 3 chars)
  assert.throws(() => buildResearchPayload('  ab  '), /no mínimo 3 caracteres/)

  clearSession()
})

// 4. Test Report audit metrics structure via production parseReportData (CRITERIA A6)
test('Report parsing preserves citation_metrics and audit_findings via production parseReportData', () => {
  const backendReportResponse = {
    report_id: 'rep-123',
    research_id: 'res-456',
    content_markdown: '# Relatório Completo\n\nTexto com fontes [Nature](https://nature.com).',
    citation_metrics: {
      evidence_records: 12,
      source_urls_cited: 8,
    },
    audit_findings: {
      points: [
        { position: 0, status: 'approved', verdict: 'APPROVED', reason: null },
        { position: 1, status: 'blocked', verdict: 'RETRY', reason: 'Falta fonte oficial' },
      ],
    },
    generated_at: '2026-10-02T10:15:00Z',
  }

  const parsed = parseReportData(backendReportResponse)
  assert.equal(parsed.report_id, 'rep-123')
  assert.equal(parsed.research_id, 'res-456')
  assert.ok(parsed.content_markdown.includes('https://nature.com'))
  assert.equal(parsed.citation_metrics?.evidence_records, 12)
  assert.equal(parsed.citation_metrics?.source_urls_cited, 8)
  assert.equal(parsed.audit_findings?.points?.length, 2)
  assert.equal(parsed.audit_findings?.points?.[0].verdict, 'APPROVED')
  assert.equal(parsed.audit_findings?.points?.[1].verdict, 'RETRY')
  assert.equal(parsed.audit_findings?.points?.[1].reason, 'Falta fonte oficial')

  // Validation failure checks
  assert.throws(() => parseReportData(null), /dados vazios/)
  assert.throws(() => parseReportData({ report_id: '123' }), /campos obrigatórios ausentes/)
})

// 5. Test TanStack Router configuration integrity using production router export (CRITERIA A1)
test('TanStack Router production exports and route tree initialization work cleanly', () => {
  assert.ok(router, 'Production router must be defined')
  assert.ok(routeTree, 'Production routeTree must be defined')

  const registeredPaths = Object.keys(router.routesByPath)
  assert.ok(registeredPaths.includes('/'), 'Root path "/" must be registered')
  assert.ok(registeredPaths.includes('/research/$id'), 'Research detail path "/research/$id" must be registered')
  assert.ok(registeredPaths.includes('/settings'), 'Settings path "/settings" must be registered')

  // Custom route tree factory check
  const customTree = createProductionRouteTree()
  assert.ok(customTree.router)
  assert.equal(Object.keys(customTree.router.routesByPath).length, registeredPaths.length)
})

// 6. Security guardrails: no X-Tenant-ID header and CSRF on mutating calls via production prepareHeaders (CRITERIA A4)
test('Security client policy validates HttpOnly cookie model, CSRF inclusion, and strips X-Tenant-ID', () => {
  setCsrfToken('active-csrf-token')

  // POST mutation: must include X-CSRF-Token and never include X-Tenant-ID
  const postHeaders = prepareHeaders('POST', { 'X-Tenant-ID': 'malicious-tenant', 'Custom-Header': '1' })
  assert.equal(postHeaders.get('X-CSRF-Token'), 'active-csrf-token')
  assert.equal(postHeaders.get('X-Tenant-ID'), null)
  assert.equal(postHeaders.get('x-tenant-id'), null)
  assert.equal(postHeaders.get('Custom-Header'), '1')

  // PUT and DELETE mutations: must include X-CSRF-Token
  const putHeaders = prepareHeaders('PUT')
  assert.equal(putHeaders.get('X-CSRF-Token'), 'active-csrf-token')
  const deleteHeaders = prepareHeaders('DELETE')
  assert.equal(deleteHeaders.get('X-CSRF-Token'), 'active-csrf-token')

  // GET safe method: must NOT include X-CSRF-Token
  const getHeaders = prepareHeaders('GET')
  assert.equal(getHeaders.get('X-CSRF-Token'), null)
  assert.equal(getHeaders.get('X-Tenant-ID'), null)

  clearSession()
})

// 7. Test CSRF auto-reauth and retry handling via production api (CRITERIA A4, A8)
test('API client transparently handles CSRF token expiration with auto-refresh and retry', async () => {
  const originalFetch = globalThis.fetch
  let callCount = 0
  let csrfRefreshCalled = false

  setCsrfToken('stale-csrf-token')

  globalThis.fetch = async (url, options = {}) => {
    callCount++
    if (url === '/api/test-mutation') {
      const headers = new Headers(options.headers)
      // First attempt with stale token returns 403 Forbidden
      if (headers.get('X-CSRF-Token') === 'stale-csrf-token') {
        return new Response(JSON.stringify({ detail: 'CSRF validation failed' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      // Second attempt with refreshed token succeeds
      if (headers.get('X-CSRF-Token') === 'fresh-csrf-token') {
        return new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
    }
    if (url === '/api/auth/csrf') {
      csrfRefreshCalled = true
      return new Response(JSON.stringify({ csrf_token: 'fresh-csrf-token' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(null, { status: 404 })
  }

  try {
    const res = await api('/api/test-mutation', { method: 'POST', body: JSON.stringify({ action: 'approve' }) })
    assert.deepEqual(res, { success: true })
    assert.equal(csrfRefreshCalled, true, 'CSRF token must have been refreshed via /api/auth/csrf')
    assert.equal(getCsrfToken(), 'fresh-csrf-token', 'Client csrf state must be updated to fresh token')
    assert.equal(callCount, 3, 'Initial call (403) + CSRF refresh + Retried call (200) = 3 calls')
  } finally {
    globalThis.fetch = originalFetch
    clearSession()
  }
})

// 8. Test secure logout lifecycle and session revocation via production logoutUser (CRITERIA A4, A8)
test('Logout lifecycle sends CSRF token, revokes session, and cleans local state', async () => {
  const originalFetch = globalThis.fetch
  let logoutCalled = false
  let logoutCsrfHeader = null

  setCsrfToken('session-token-to-revoke')

  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/auth/logout') {
      logoutCalled = true
      logoutCsrfHeader = new Headers(options.headers).get('X-CSRF-Token')
      return new Response(null, { status: 204 })
    }
    return new Response(null, { status: 404 })
  }

  try {
    await logoutUser()
    assert.equal(logoutCalled, true, 'Logout endpoint must be called')
    assert.equal(logoutCsrfHeader, 'session-token-to-revoke', 'Logout must send X-CSRF-Token')
    assert.equal(getCsrfToken(), '', 'CSRF token must be cleared')
  } finally {
    globalThis.fetch = originalFetch
    clearSession()
  }
})

// 9. Test statusLabel mapping
test('statusLabel correctly maps research state strings to friendly Portuguese text', () => {
  assert.equal(statusLabel('scouting'), 'Scout ativo')
  assert.equal(statusLabel('pending_approval'), 'Aguardando aprovação')
  assert.equal(statusLabel('approved'), 'Aprovado')
  assert.equal(statusLabel('in_progress'), 'Investigando')
  assert.equal(statusLabel('completed'), 'Concluído')
  assert.equal(statusLabel('completed_but_callback_failed'), 'Concluído · webhook pendente')
  assert.equal(statusLabel('blocked'), 'Com ressalvas')
  assert.equal(statusLabel('failed'), 'Falhou')
})

// 10. Test logout on 403 or network failure does not pretend revocation succeeded (F-05)
test('Logout failure (403/network error) throws and preserves local session state', async () => {
  const originalFetch = globalThis.fetch
  setCsrfToken('active-token-before-fail')

  globalThis.fetch = async (url) => {
    if (url === '/api/auth/logout') {
      return new Response(JSON.stringify({ detail: 'CSRF token missing or invalid' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(null, { status: 404 })
  }

  try {
    await assert.rejects(
      async () => {
        await logoutUser()
      },
      /CSRF token missing or invalid|403/,
      'Logout on 403 must reject and not pretend session revocation'
    )
    assert.equal(getCsrfToken(), 'active-token-before-fail', 'CSRF token must not be wiped on failed logout')
  } finally {
    globalThis.fetch = originalFetch
    clearSession()
  }
})

// 11. Logout treats 401 as already revoked and clears local CSRF state
test('Logout 401 clears local CSRF because server session is already absent', async () => {
  const originalFetch = globalThis.fetch
  setCsrfToken('expired-session-csrf')
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Not authenticated' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  })

  try {
    await logoutUser()
    assert.equal(getCsrfToken(), '')
  } finally {
    globalThis.fetch = originalFetch
    clearSession()
  }
})

// 12. Login uses same-origin HttpOnly cookie transport and accepts csrf-only browser auth contract
test('Login request uses cookie transport and csrf-only response contract', async () => {
  const originalFetch = globalThis.fetch
  let requestOptions
  globalThis.fetch = async (_url, options = {}) => {
    requestOptions = options
    return new Response(JSON.stringify({ authenticated: true, role: 'admin', csrf_token: 'login-csrf' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const result = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password: 'browser-entered-password' }),
    })
    assert.equal(requestOptions.credentials, 'same-origin')
    assert.deepEqual(Object.keys(result).sort(), ['authenticated', 'csrf_token', 'role'])
    assert.equal(Object.prototype.hasOwnProperty.call(result, 'api_key'), false)
    assert.equal(Object.prototype.hasOwnProperty.call(result, 'jwt_token'), false)
  } finally {
    globalThis.fetch = originalFetch
    clearSession()
  }
})

// 13. Test research state and draft caching (CRITERIA A11, F-08)
test('Research detail and user draft caching operates without secrets and preserves draft edits', () => {
  const dummyResearch = {
    research_id: 'res-cache-123',
    theme: 'Cache Research Test',
    status: 'pending_approval',
    briefing_draft: {
      points: [
        { title: 'P1', description: 'D1', dependencies: [], is_parallelizable: true },
        { title: 'P2', description: 'D2', dependencies: ['1'], is_parallelizable: false },
        { title: 'P3', description: 'D3', dependencies: ['2'], is_parallelizable: false },
        { title: 'P4', description: 'D4', dependencies: [], is_parallelizable: true },
        { title: 'P5', description: 'D5', dependencies: ['3'], is_parallelizable: false },
      ],
    },
  }

  setCachedResearch('res-cache-123', dummyResearch)
  const cachedRes = getCachedResearch('res-cache-123')
  assert.equal(cachedRes?.research_id, 'res-cache-123')
  assert.equal(cachedRes?.theme, 'Cache Research Test')

  // Cache user's in-progress edit draft
  const draft = {
    points: [
      { title: 'P1 Edited', description: 'D1 Edited', dependencies: [], is_parallelizable: true },
    ],
    editNote: 'Favor aprofundar custos',
  }

  setCachedDraft('res-cache-123', draft)
  const retrievedDraft = getCachedDraft('res-cache-123')
  assert.equal(retrievedDraft?.editNote, 'Favor aprofundar custos')
  assert.equal(retrievedDraft?.points[0].title, 'P1 Edited')

  // Clear draft on submission
  clearCachedDraft('res-cache-123')
  assert.equal(getCachedDraft('res-cache-123'), null)
})

// 14. Real model catalog only; preserve saved model during temporary discovery failure (CRITERIA A7)
test('Model options derive from discovered catalog and retain only a previously saved unavailable model', () => {
  const catalog = {
    openai: ['gpt-4.1', 'openai/gpt-4.1-mini'],
    anthropic: ['claude-sonnet-4'],
  }
  assert.deepEqual(getModelOptions(catalog), [
    { value: 'openai/gpt-4.1', savedOnly: false },
    { value: 'openai/gpt-4.1-mini', savedOnly: false },
    { value: 'anthropic/claude-sonnet-4', savedOnly: false },
  ])
  assert.deepEqual(getModelOptions({}, 'openai/saved-model'), [
    { value: 'openai/saved-model', savedOnly: true },
  ])
  assert.equal(
    getModelOptions(catalog, 'arbitrary/text').some(option => option.value === 'arbitrary/text' && !option.savedOnly),
    false,
  )
})

// 15. Test retry-callback contract returns { success: boolean } (UI-RE-01)
test('retry-callback handles { success: boolean } contract from backend', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/reports/res-ret-1/retry-callback' && options.method === 'POST') {
      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url === '/api/reports/res-ret-2/retry-callback' && options.method === 'POST') {
      return new Response(JSON.stringify({ success: false }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(null, { status: 404 })
  }

  try {
    const okRes = await api('/api/reports/res-ret-1/retry-callback', { method: 'POST' })
    assert.equal(okRes.success, true)
    const failRes = await api('/api/reports/res-ret-2/retry-callback', { method: 'POST' })
    assert.equal(failRes.success, false)
  } finally {
    globalThis.fetch = originalFetch
  }
})

// 16. Test research switching isolates cache state and prevents retaining research A (UI-RE-02)
test('Research switching isolates cache state between research A and research B', () => {
  const resA = {
    research_id: 'res-A',
    theme: 'Research A Theme',
    status: 'in_progress',
    briefing_draft: {
      points: [{ title: 'Point A1', description: 'Desc A1', dependencies: [], is_parallelizable: true }],
      edit_note: 'Note A',
    },
  }
  const resB = {
    research_id: 'res-B',
    theme: 'Research B Theme',
    status: 'completed',
    briefing_draft: {
      points: [{ title: 'Point B1', description: 'Desc B1', dependencies: [], is_parallelizable: false }],
      edit_note: 'Note B',
    },
  }

  setCachedResearch('res-A', resA)
  setCachedResearch('res-B', resB)
  setCachedDraft('res-A', { points: resA.briefing_draft.points, editNote: 'Draft Note A' })
  setCachedEvents('res-A', [{ id: 10, persona: 'scout', type: 'scout_started', summary: 'Scout A', created_at: '2026-10-02T10:00:00Z' }])
  setCachedReport('res-B', { report_id: 'rep-B', research_id: 'res-B', content_markdown: '# Report B' })

  // Validate state isolation
  const cachedA = getCachedResearch('res-A')
  const cachedB = getCachedResearch('res-B')
  assert.equal(cachedA?.theme, 'Research A Theme')
  assert.equal(cachedB?.theme, 'Research B Theme')
  assert.equal(getCachedEvents('res-B'), null, 'Research B must not retain events from research A')
  assert.equal(getCachedReport('res-A'), null, 'Research A must not retain report from research B')
  assert.equal(getCachedDraft('res-B'), null, 'Research B must not retain draft from research A')
  assert.equal(getCachedDraft('res-A')?.editNote, 'Draft Note A')
})

// 17. Test clearAllDrCache cleans up all dr_* cache items on logout/expiration (UI-RE-04)
test('clearAllDrCache cleans up all dr_* cache items on logout and session expiration', () => {
  setCachedResearch('res-clean-1', { research_id: 'res-clean-1', theme: 'T1', status: 'scouting' })
  setCachedDraft('res-clean-1', { points: [], editNote: 'To be wiped' })
  setCachedEvents('res-clean-1', [{ id: 1, persona: 'scout', type: 'scout_started', summary: 'S1', created_at: '2026-10-02T10:00:00Z' }])
  setCachedReport('res-clean-1', { report_id: 'rep-1', research_id: 'res-clean-1', content_markdown: '# M1' })

  assert.ok(getCachedResearch('res-clean-1'))
  assert.ok(getCachedDraft('res-clean-1'))
  assert.ok(getCachedEvents('res-clean-1'))
  assert.ok(getCachedReport('res-clean-1'))

  // Perform cache wipe
  clearAllDrCache()

  assert.equal(getCachedResearch('res-clean-1'), null)
  assert.equal(getCachedDraft('res-clean-1'), null)
  assert.equal(getCachedEvents('res-clean-1'), null)
  assert.equal(getCachedReport('res-clean-1'), null)
})

// 18. Test settings removal sends empty string ('') in payload (UI-RE-05)
test('buildSettingsPayload sends empty string for removed provider keys and reset URLs', () => {
  const newKeys = {
    openai: 'new-key-123',
    anthropic: '', // Removed provider key
    gemini: '   ',  // Whitespace only (should be ignored)
  }
  const models = {
    scout: 'openai/gpt-4.1',
    writer: '', // Deselected model
  }
  const payload = buildSettingsPayload(newKeys, models, '', '')

  assert.deepEqual(payload.provider_keys, {
    openai: 'new-key-123',
    anthropic: '', // MUST be empty string to trigger pop in backend update_settings
  })
  assert.equal(payload.models.scout, 'openai/gpt-4.1')
  assert.equal(Object.hasOwn(payload.models, 'writer'), false, 'Blank model must be omitted for backend validation')
  assert.equal(payload.callback_url, '', 'Cleared callback URL must be sent as empty string')
  assert.equal(payload.openai_base_url, '', 'Cleared base URL must be sent as empty string')
})

// 19. Tolerant JSON cache handling for corrupted stored values (UI-RE-10)
test('Tolerant JSON cache removes actually corrupted JSON without throwing', () => {
  const values = new Map([
    ['dr_res_corrupted-99', '{"research_id":'],
    ['dr_draft_corrupted-99', '{not-json'],
    ['dr_report_corrupted-99', '[broken'],
    ['dr_events_corrupted-99', 'undefined'],
  ])
  const previousStorage = globalThis.sessionStorage
  globalThis.sessionStorage = {
    get length() { return values.size },
    key: index => [...values.keys()][index] ?? null,
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
    clear: () => values.clear(),
  }

  try {
    assert.equal(getCachedResearch('corrupted-99'), null)
    assert.equal(getCachedDraft('corrupted-99'), null)
    assert.equal(getCachedReport('corrupted-99'), null)
    assert.equal(getCachedEvents('corrupted-99'), null)
    assert.equal(values.size, 0, 'Invalid cache values must be removed after parse failure')
  } finally {
    if (previousStorage === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = previousStorage
  }
})

// 20. WAI-ARIA tab keyboard navigation wrapping (UI-RE-07)
test('WAI-ARIA tab keyboard navigation helper wraps correctly across tabs', () => {
  assert.equal(getNextActiveTab('plan', 'next'), 'evidence')
  assert.equal(getNextActiveTab('evidence', 'next'), 'report')
  assert.equal(getNextActiveTab('report', 'next'), 'plan') // Wrap around

  assert.equal(getNextActiveTab('plan', 'prev'), 'report') // Wrap backwards
  assert.equal(getNextActiveTab('evidence', 'prev'), 'plan')
  assert.equal(getNextActiveTab('report', 'prev'), 'evidence')

  assert.equal(getNextActiveTab('plan', 'last'), 'report')
  assert.equal(getNextActiveTab('report', 'first'), 'plan')
})

// 21. Request race guard used by ResearchPage (AUD-02)
test('Latest research request aborts A and prevents late A result from replacing B', async () => {
  const guard = createLatestRequestGuard()
  let resolveA
  let resolveB
  const responseA = new Promise(resolve => { resolveA = resolve })
  const responseB = new Promise(resolve => { resolveB = resolve })
  const committed = []

  const requestA = guard.begin('A')
  const consumeA = responseA.then(value => {
    if (requestA.isCurrent()) committed.push(value)
  })
  const requestB = guard.begin('B')
  const consumeB = responseB.then(value => {
    if (requestB.isCurrent()) committed.push(value)
  })

  assert.equal(requestA.signal.aborted, true)
  resolveB('B')
  await consumeB
  resolveA('A')
  await consumeA
  assert.deepEqual(committed, ['B'])
})

// 22. Callback retry must only appear for confirmed failure (AUD-03)
test('Callback retry eligibility rejects pending and accepts failed states only', () => {
  assert.equal(isCallbackRetryable('pending', 'running', []), false)
  assert.equal(isCallbackRetryable(undefined, 'completed', []), false)
  assert.equal(isCallbackRetryable('delivered', 'completed', []), false)
  assert.equal(isCallbackRetryable('failed', 'completed', []), true)
  assert.equal(isCallbackRetryable('pending', 'completed_but_callback_failed', []), true)
  assert.equal(isCallbackRetryable('pending', 'completed', ['callback_failed']), true)
  assert.equal(isCallbackRetryable('pending', 'completed', ['callback_failed', 'callback_delivered']), false)
  assert.equal(isCallbackRetryable('pending', 'completed_but_callback_failed', ['callback_delivered']), false)
})

// 23. Initial auth failure must clear CSRF and dr_* cache (AUD-04)
test('initializeSession clears client session when initial auth/me fails', async () => {
  const values = new Map([
    ['dr_res_private', '{"research_id":"private"}'],
    ['unrelated', 'keep'],
  ])
  const previousStorage = globalThis.sessionStorage
  const previousFetch = globalThis.fetch
  globalThis.sessionStorage = {
    get length() { return values.size },
    key: index => [...values.keys()][index] ?? null,
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
    clear: () => values.clear(),
  }
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Unauthorized' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  })
  setCsrfToken('stale-token')

  try {
    await assert.rejects(initializeSession(), /Unauthorized/)
    assert.equal(getCsrfToken(), '')
    assert.equal(values.has('dr_res_private'), false)
    assert.equal(values.get('unrelated'), 'keep')
  } finally {
    globalThis.fetch = previousFetch
    if (previousStorage === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = previousStorage
  }
})

// 24. Test model options preserves provider prefix when model ID contains slashes (MA-19)
test('Model options retain provider identity for OpenAI-compatible vendor models with slashes', () => {
  const catalog = {
    openai: [
      'gpt-4o',
      'openai/gpt-4.1',
      'meta-llama/llama-3.1-70b-instruct',
      'qwen/qwen-2.5-72b-instruct',
    ],
    anthropic: ['claude-3-5-sonnet'],
  }
  const options = getModelOptions(catalog)
  const values = options.map(o => o.value)

  assert.ok(values.includes('openai/gpt-4o'))
  assert.ok(values.includes('openai/gpt-4.1'))
  // MA-19: Models with slashes MUST retain provider prefix so LiteLLM targets the correct provider/base_url
  assert.ok(
    values.includes('openai/meta-llama/llama-3.1-70b-instruct'),
    'Model with slash from openai catalog must have openai/ prefix',
  )
  assert.ok(
    values.includes('openai/qwen/qwen-2.5-72b-instruct'),
    'Model with slash from openai catalog must have openai/ prefix',
  )
  assert.ok(values.includes('anthropic/claude-3-5-sonnet'))
})

// 25. Test research status lifecycle transitions and regression prevention (MA-20)
test('Status transitions prevent late/delayed responses from regressing research status', () => {
  // Allowed forward progression
  assert.equal(canTransitionStatus(null, 'scouting'), true)
  assert.equal(canTransitionStatus('scouting', 'pending_approval'), true)
  assert.equal(canTransitionStatus('pending_approval', 'approved'), true)
  assert.equal(canTransitionStatus('approved', 'in_progress'), true)
  assert.equal(canTransitionStatus('in_progress', 'completed'), true)
  assert.equal(canTransitionStatus('in_progress', 'completed_but_callback_failed'), true)
  assert.equal(canTransitionStatus('in_progress', 'blocked'), true)

  // Disallowed backwards regressions
  assert.equal(canTransitionStatus('in_progress', 'pending_approval'), false)
  assert.equal(canTransitionStatus('in_progress', 'scouting'), false)
  assert.equal(canTransitionStatus('completed', 'in_progress'), false)
  assert.equal(canTransitionStatus('completed', 'scouting'), false)
  assert.equal(canTransitionStatus('blocked', 'approved'), false)
})

// 26. Test real backend audit structure preserves unsupported claims with quotes and URLs (MA-18)
test('parseReportData preserves real backend audit shape with quotes, URLs, and correct approved status', () => {
  const backendResponse = {
    report_id: 'rep-real-999',
    research_id: 'res-real-888',
    content_markdown: '# Relatório\n\n| Metodologia | Status |\n|---|---|\n| LLM Audit | OK |\n',
    citation_metrics: {
      evidence_records: 15,
      source_urls_cited: 6,
    },
    audit_findings: {
      points: [
        {
          point: 'Ponto 1: Arquitetura Quântica',
          status: 'approved',
          audit: {
            attempt: 1,
            deterministic: {
              supported: 4,
              unsupported: [],
            },
            llm: {
              approved: true,
              findings: ['Fontes de alta fidelidade confirmadas.'],
              contradictions: [],
              uncertainties: [],
            },
          },
        },
        {
          point: 'Ponto 2: Escalabilidade de Qubits',
          status: 'blocked',
          audit: {
            attempt: 2,
            deterministic: {
              supported: 1,
              unsupported: [
                {
                  url: 'https://nature.com/articles/quantum-scale',
                  claim: 'Computador opera a temperatura ambiente com 10.000 qubits',
                  excerpt: 'Experiments were conducted at cryogenic temperatures below 15mK.',
                  reason: 'Quote contradicts claim regarding operating temperature',
                },
              ],
            },
            llm: {
              approved: false,
              findings: ['Alegação de temperatura ambiente contradiz o artigo fonte.'],
              contradictions: ['Temperatura ambiente vs 15mK'],
              uncertainties: ['Persistência da coerência'],
              missing_research: ['Buscar dados oficiais de testes criogênicos'],
            },
          },
        },
      ],
    },
  }

  const parsed = parseReportData(backendResponse)
  assert.equal(parsed.report_id, 'rep-real-999')
  assert.equal(parsed.audit_findings?.points?.length, 2)

  // Point 1: Approved
  const pt1 = parsed.audit_findings?.points?.[0]
  assert.equal(pt1?.status, 'approved')
  assert.equal(pt1?.verdict, 'APPROVED')
  assert.equal(pt1?.audit?.deterministic?.supported, 4)
  assert.equal(pt1?.audit?.deterministic?.unsupported?.length, 0)
  assert.equal(pt1?.audit?.llm?.approved, true)

  // Point 2: Blocked / Unsupported quotes
  const pt2 = parsed.audit_findings?.points?.[1]
  assert.equal(pt2?.status, 'blocked')
  assert.equal(pt2?.verdict, 'RETRY')
  assert.equal(pt2?.audit?.deterministic?.supported, 1)
  assert.equal(pt2?.audit?.deterministic?.unsupported?.length, 1)
  assert.equal(pt2?.audit?.deterministic?.unsupported?.[0].url, 'https://nature.com/articles/quantum-scale')
  assert.equal(
    pt2?.audit?.deterministic?.unsupported?.[0].excerpt,
    'Experiments were conducted at cryogenic temperatures below 15mK.',
  )
  assert.equal(pt2?.audit?.llm?.approved, false)
})

// 27. Test DAG movement prevention when prerequisite would be placed after dependent (MA-17)
test('canMovePoint prevents placing dependent point before base or base point after dependent', () => {
  const points = [
    { title: 'A', description: 'Base A', dependencies: [], is_parallelizable: true },
    { title: 'B', description: 'Dep B (depends on A)', dependencies: ['1'], is_parallelizable: false },
    { title: 'C', description: 'Dep C (depends on B)', dependencies: ['2'], is_parallelizable: false },
    { title: 'D', description: 'Independent D', dependencies: [], is_parallelizable: true },
    { title: 'E', description: 'Independent E', dependencies: [], is_parallelizable: true },
  ]

  // Moving B up (swap with A): would place dependent B before base A -> MUST BE DISALLOWED
  const moveBUp = canMovePoint(points, 1, -1)
  assert.equal(moveBUp.allowed, false)
  assert.ok(moveBUp.reason?.includes('antes da sua dependência'))

  // Moving A down (swap with B): would place base A after dependent B -> MUST BE DISALLOWED
  const moveADown = canMovePoint(points, 0, 1)
  assert.equal(moveADown.allowed, false)
  assert.ok(moveADown.reason?.includes('após o ponto dependente'))

  // Moving D up (swap with C): D has no dependencies and C depends on B (which remains at index 1 < new index 3) -> ALLOWED
  const moveDUp = canMovePoint(points, 3, -1)
  assert.equal(moveDUp.allowed, true)

  const reordered = reorderBriefingPoints(points, 3, -1)
  assert.equal(reordered[2].title, 'D')
  assert.equal(reordered[3].title, 'C')
  assert.deepEqual(reordered[3].dependencies, ['2'], 'C still depends on B at index 1')
})

// 28. Test simulated E2E workflow: login -> settings with OpenAI-compatible slash model -> research -> briefing -> report (MA-22)
test('Simulated isolated frontend workflow handles login, settings, research and report verification', async () => {
  // Step 1: Login
  const fakeSession = { authenticated: true, role: 'admin', csrf_token: 'valid-csrf-token' }
  setCsrfToken(fakeSession.csrf_token)
  assert.equal(getCsrfToken(), 'valid-csrf-token')

  // Step 2: Settings payload with custom endpoint and slash model
  const catalog = {
    openai: ['meta-llama/llama-3.1-70b-instruct'],
  }
  const modelOptions = getModelOptions(catalog)
  assert.equal(modelOptions[0].value, 'openai/meta-llama/llama-3.1-70b-instruct')

  const settingsPayload = buildSettingsPayload(
    { openai: 'sk-custom-openai-compatible' },
    { scout: modelOptions[0].value },
    'https://external.webhook.com/callback',
    'https://openrouter.ai/api/v1',
  )
  assert.equal(settingsPayload.provider_keys.openai, 'sk-custom-openai-compatible')
  assert.equal(settingsPayload.models.scout, 'openai/meta-llama/llama-3.1-70b-instruct')
  assert.equal(settingsPayload.callback_url, 'https://external.webhook.com/callback')
  assert.equal(settingsPayload.openai_base_url, 'https://openrouter.ai/api/v1')

  // Step 3: Research creation payload
  const researchPayload = buildResearchPayload('Avanços em inteligência artificial multiagente')
  assert.deepEqual(researchPayload, { theme: 'Avanços em inteligência artificial multiagente' })
  assert.equal(Object.hasOwn(researchPayload, 'callback_url'), false, 'Browser creation request omits callback_url')

  // Step 4: Briefing approval validation
  const validPoints = [
    { title: 'P1', description: 'Desc 1', dependencies: [], is_parallelizable: true },
    { title: 'P2', description: 'Desc 2', dependencies: ['1'], is_parallelizable: false },
    { title: 'P3', description: 'Desc 3', dependencies: ['2'], is_parallelizable: false },
    { title: 'P4', description: 'Desc 4', dependencies: [], is_parallelizable: true },
    { title: 'P5', description: 'Desc 5', dependencies: ['3'], is_parallelizable: false },
  ]
  const valResult = validateBriefingApproval(validPoints)
  assert.equal(valResult.valid, true)

  // Step 5: Report parsing preserves markdown table and citation metrics
  const reportPayload = {
    report_id: 'rep-e2e-1',
    research_id: 'res-e2e-1',
    content_markdown: '# Relatório\n\n| Item | Val |\n|---|---|\n| A | B |\n',
    citation_metrics: { evidence_records: 5, source_urls_cited: 3 },
  }
  const report = parseReportData(reportPayload)
  assert.equal(report.report_id, 'rep-e2e-1')
  assert.equal(report.citation_metrics?.evidence_records, 5)

  clearSession()
})
