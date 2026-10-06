import type { Point, Event, ReportData, Research } from './types.ts'

export function canMovePoint(
  points: Point[],
  index: number,
  shift: number,
): { allowed: boolean; reason?: string } {
  const target = index + shift
  if (target < 0 || target >= points.length) {
    return { allowed: false, reason: 'Movimento fora dos limites da lista' }
  }
  const originalTitles = points.map(p => (p.title || '').trim())

  function resolveDepIndex(ref: string): number {
    const refStr = String(ref).trim()
    const m = refStr.match(/^(?:point|ponto)\s*(\d+)$/i)
    if (/^\d+$/.test(refStr)) return parseInt(refStr, 10) - 1
    if (m) return parseInt(m[1], 10) - 1
    return originalTitles.indexOf(refStr)
  }

  const pointMoving = points[index]

  // If moving UP (shift < 0): check if moving before its prerequisite
  if (shift < 0) {
    for (const dep of pointMoving.dependencies || []) {
      const depIdx = resolveDepIndex(dep)
      if (depIdx >= target && depIdx <= index) {
        return {
          allowed: false,
          reason: `Não é possível mover "${pointMoving.title || `Ponto ${index + 1}`}" antes da sua dependência "${points[depIdx]?.title || `Ponto ${depIdx + 1}`}"`,
        }
      }
    }
  }

  // If moving DOWN (shift > 0): check if moving after a dependent
  if (shift > 0) {
    for (let i = index + 1; i <= target; i++) {
      const otherPoint = points[i]
      for (const dep of otherPoint.dependencies || []) {
        const depIdx = resolveDepIndex(dep)
        if (depIdx === index) {
          return {
            allowed: false,
            reason: `Não é possível mover "${pointMoving.title || `Ponto ${index + 1}`}" após o ponto dependente "${otherPoint.title || `Ponto ${i + 1}`}"`,
          }
        }
      }
    }
  }

  return { allowed: true }
}

export function reorderBriefingPoints(points: Point[], index: number, shift: number): Point[] {
  const target = index + shift
  if (target < 0 || target >= points.length) return points

  const check = canMovePoint(points, index, shift)
  if (!check.allowed) {
    // MA-17: Do not silently remove dependencies; prevent invalid movement to preserve DAG semantics.
    return points
  }

  const next = [...points]
  ;[next[index], next[target]] = [next[target], next[index]]

  const originalTitles = points.map(p => (p.title || '').trim())

  return next.map((point, newIdx) => {
    const rawDeps = point.dependencies || []
    const cleanDeps: string[] = []

    for (const ref of rawDeps) {
      const refStr = String(ref).trim()
      const m = refStr.match(/^(?:point|ponto)\s*(\d+)$/i)
      let oldTargetIdx = -1

      if (/^\d+$/.test(refStr)) {
        oldTargetIdx = parseInt(refStr, 10) - 1
      } else if (m) {
        oldTargetIdx = parseInt(m[1], 10) - 1
      } else {
        const found = originalTitles.indexOf(refStr)
        if (found !== -1) oldTargetIdx = found
      }

      if (oldTargetIdx >= 0 && oldTargetIdx < points.length) {
        const targetPoint = points[oldTargetIdx]
        const newTargetIdx = next.indexOf(targetPoint)
        // Strict DAG contract: dependencies must reference earlier points only (newTargetIdx < newIdx)
        if (newTargetIdx >= 0 && newTargetIdx < newIdx) {
          cleanDeps.push(String(newTargetIdx + 1))
        }
      }
    }

    return {
      ...point,
      dependencies: Array.from(new Set(cleanDeps)),
    }
  })
}

export function validateBriefingApproval(points: Point[]): { valid: boolean; error?: string } {
  if (!Array.isArray(points) || points.length !== 5) {
    return { valid: false, error: 'Briefing approval requires exactly 5 points' }
  }
  const titles = points.map(p => (p.title || '').trim())
  if (new Set(titles).size !== titles.length) {
    return { valid: false, error: 'Research point titles must be unique' }
  }
  for (let idx = 0; idx < points.length; idx++) {
    const p = points[idx]
    for (const ref of p.dependencies || []) {
      const refStr = String(ref).trim()
      const m = refStr.match(/^(?:point|ponto)\s*(\d+)$/i)
      let p_idx = -1
      if (/^\d+$/.test(refStr)) {
        p_idx = parseInt(refStr, 10) - 1
      } else if (m) {
        p_idx = parseInt(m[1], 10) - 1
      } else if (titles.includes(refStr)) {
        p_idx = titles.indexOf(refStr)
      } else {
        return { valid: false, error: `Unknown point dependency: '${ref}' in point ${idx + 1}` }
      }
      if (p_idx >= idx) {
        return {
          valid: false,
          error: `Point ${idx + 1} has dependency on point ${p_idx + 1}; dependencies must reference earlier points only (p_idx < idx)`,
        }
      }
      if (p_idx < 0) {
        return { valid: false, error: `Invalid point index: ${p_idx + 1}` }
      }
    }
  }
  return { valid: true }
}

export function ingestEvent(existingEvents: Event[], newEvent: Event): Event[] {
  if (existingEvents.some(item => item.id === newEvent.id)) return existingEvents
  return [...existingEvents, newEvent].sort((a, b) => a.id - b.id)
}

export function getModelOptions(
  modelsByProvider: Record<string, string[]>,
  savedModel = '',
): { value: string; savedOnly: boolean }[] {
  const discovered = Array.from(
    new Set(
      Object.entries(modelsByProvider).flatMap(([provider, models]) =>
        (models || []).map(model => {
          // MA-19: Preserve provider identity even when model ID contains slashes (e.g. meta-llama/llama-3.1-70b from openai-compatible)
          if (model.startsWith(`${provider}/`)) {
            return model
          }
          return `${provider}/${model}`
        }),
      ),
    ),
  )
  const options = discovered.map(value => ({ value, savedOnly: false }))
  if (savedModel && !discovered.includes(savedModel)) {
    options.unshift({ value: savedModel, savedOnly: true })
  }
  return options
}

export function parseReportData(raw: unknown): ReportData {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Formato de relatório inválido: dados vazios')
  }
  const obj = raw as Record<string, any>
  if (typeof obj.report_id !== 'string' || typeof obj.content_markdown !== 'string') {
    throw new Error('Formato de relatório inválido: campos obrigatórios ausentes')
  }
  return {
    report_id: obj.report_id,
    research_id: typeof obj.research_id === 'string' ? obj.research_id : '',
    content_markdown: obj.content_markdown,
    citation_metrics: obj.citation_metrics
      ? {
          evidence_records: Number(obj.citation_metrics.evidence_records) || 0,
          source_urls_cited: Number(obj.citation_metrics.source_urls_cited) || 0,
        }
      : undefined,
    audit_findings:
      obj.audit_findings && Array.isArray(obj.audit_findings.points)
        ? {
            points: obj.audit_findings.points.map((p: any, idx: number) => {
              const position = typeof p.position === 'number' ? p.position : idx
              const point = p.point ?? p.title ?? `Ponto ${idx + 1}`
              const status =
                p.status ||
                (p.audit?.llm?.approved === true ? 'approved' : p.verdict?.toLowerCase()) ||
                'pending'
              const verdict =
                p.verdict ||
                (status === 'approved' ? 'APPROVED' : status === 'blocked' ? 'RETRY' : status.toUpperCase())
              const reason =
                p.reason ||
                p.audit?.llm?.missing_research?.join('; ') ||
                (p.audit?.deterministic?.unsupported?.length
                  ? `${p.audit.deterministic.unsupported.length} fontes com citação não sustentada`
                  : undefined)

              return {
                position,
                point,
                status,
                verdict,
                reason,
                audit: p.audit
                  ? {
                      deterministic: p.audit.deterministic
                        ? {
                            supported: Number(p.audit.deterministic.supported) || 0,
                            unsupported: Array.isArray(p.audit.deterministic.unsupported)
                              ? p.audit.deterministic.unsupported
                              : [],
                          }
                        : undefined,
                      llm: p.audit.llm
                        ? {
                            approved: Boolean(p.audit.llm.approved),
                            findings: Array.isArray(p.audit.llm.findings) ? p.audit.llm.findings : [],
                            contradictions: Array.isArray(p.audit.llm.contradictions)
                              ? p.audit.llm.contradictions
                              : [],
                            uncertainties: Array.isArray(p.audit.llm.uncertainties)
                              ? p.audit.llm.uncertainties
                              : [],
                            missing_research: Array.isArray(p.audit.llm.missing_research)
                              ? p.audit.llm.missing_research
                              : [],
                          }
                        : undefined,
                      attempt: Number(p.audit.attempt) || 1,
                    }
                  : undefined,
              }
            }),
          }
        : undefined,
    generated_at: typeof obj.generated_at === 'string' ? obj.generated_at : undefined,
  }
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    scouting: 'Scout ativo',
    pending_approval: 'Aguardando aprovação',
    approved: 'Aprovado',
    in_progress: 'Investigando',
    completed: 'Concluído',
    completed_but_callback_failed: 'Concluído · webhook pendente',
    blocked: 'Com ressalvas',
    failed: 'Falhou',
    interrupted: 'Interrompido',
  }
  return map[status] || status
}

// ----------------------------------------------------
// STATE & DRAFT CACHE (CRITERIA A11, F-08)
// Minimal, safe in-memory + sessionStorage cache without secrets
// ----------------------------------------------------
const inMemoryCache = new Map<string, string>()

function safeGet(key: string): string | null {
  try {
    if (typeof sessionStorage !== 'undefined') {
      return sessionStorage.getItem(key)
    }
  } catch {
    // fallback
  }
  return inMemoryCache.get(key) || null
}

function safeSet(key: string, val: string): void {
  try {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(key, val)
      return
    }
  } catch {
    // fallback
  }
  inMemoryCache.set(key, val)
}

function safeRemove(key: string): void {
  try {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem(key)
    }
  } catch {
    // fallback
  }
  inMemoryCache.delete(key)
}

export function getCachedResearch(id: string): Research | null {
  const key = `dr_res_${id}`
  const raw = safeGet(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && typeof parsed.research_id === 'string' ? parsed : null
  } catch {
    safeRemove(key)
    return null
  }
}

export function setCachedResearch(id: string, data: Research): void {
  const sanitized: Research = {
    research_id: data.research_id,
    theme: data.theme,
    status: data.status,
    callback_url: data.callback_url,
    callback_configured: data.callback_configured,
    callback_status: data.callback_status,
    briefing_draft: data.briefing_draft,
    points: data.points,
    error: data.error,
    created_at: data.created_at,
    updated_at: data.updated_at,
  }
  safeSet(`dr_res_${id}`, JSON.stringify(sanitized))
}

export function getCachedDraft(id: string): { points: Point[]; editNote: string } | null {
  const key = `dr_draft_${id}`
  const raw = safeGet(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && Array.isArray(parsed.points)
      ? { points: parsed.points, editNote: typeof parsed.editNote === 'string' ? parsed.editNote : '' }
      : null
  } catch {
    safeRemove(key)
    return null
  }
}

export function setCachedDraft(id: string, draft: { points: Point[]; editNote: string }): void {
  safeSet(`dr_draft_${id}`, JSON.stringify(draft))
}

export function clearCachedDraft(id: string): void {
  safeRemove(`dr_draft_${id}`)
}

export function getCachedEvents(id: string): Event[] | null {
  const key = `dr_events_${id}`
  const raw = safeGet(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : null
  } catch {
    safeRemove(key)
    return null
  }
}

export function setCachedEvents(id: string, events: Event[]): void {
  safeSet(`dr_events_${id}`, JSON.stringify(events))
}

export function getCachedReport(id: string): ReportData | null {
  const key = `dr_report_${id}`
  const raw = safeGet(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && typeof parsed.content_markdown === 'string' ? parsed : null
  } catch {
    safeRemove(key)
    return null
  }
}

export function setCachedReport(id: string, report: ReportData): void {
  safeSet(`dr_report_${id}`, JSON.stringify(report))
}

export function clearAllDrCache(): void {
  try {
    if (typeof sessionStorage !== 'undefined') {
      const keysToRemove: string[] = []
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i)
        if (k && k.startsWith('dr_')) keysToRemove.push(k)
      }
      for (const k of keysToRemove) {
        sessionStorage.removeItem(k)
      }
    }
  } catch {
    // Ignore storage errors
  }
  try {
    if (typeof localStorage !== 'undefined') {
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i)
        if (k && k.startsWith('dr_')) keysToRemove.push(k)
      }
      for (const k of keysToRemove) {
        localStorage.removeItem(k)
      }
    }
  } catch {
    // Ignore storage errors
  }
  for (const key of Array.from(inMemoryCache.keys())) {
    if (key.startsWith('dr_')) inMemoryCache.delete(key)
  }
}

export function getNextActiveTab(
  currentTab: 'plan' | 'evidence' | 'report',
  direction: 'next' | 'prev' | 'first' | 'last',
): 'plan' | 'evidence' | 'report' {
  const tabs: ('plan' | 'evidence' | 'report')[] = ['plan', 'evidence', 'report']
  const idx = tabs.indexOf(currentTab)
  if (direction === 'first') return tabs[0]
  if (direction === 'last') return tabs[tabs.length - 1]
  if (direction === 'next') return tabs[(idx + 1) % tabs.length]
  return tabs[(idx - 1 + tabs.length) % tabs.length]
}

export const STATUS_RANK: Record<string, number> = {
  scouting: 1,
  pending_approval: 2,
  approved: 3,
  in_progress: 4,
  completed: 5,
  completed_but_callback_failed: 5,
  blocked: 5,
  failed: 5,
  interrupted: 5,
}

export function canTransitionStatus(
  currentStatus: string | undefined | null,
  newStatus: string | undefined | null,
): boolean {
  if (!currentStatus || !newStatus) return true
  // Resuming from failed or interrupted to in_progress or scouting is an explicit forward recovery
  if (
    (currentStatus === 'failed' || currentStatus === 'interrupted') &&
    (newStatus === 'in_progress' || newStatus === 'scouting')
  ) {
    return true
  }
  const curRank = STATUS_RANK[currentStatus] || 0
  const newRank = STATUS_RANK[newStatus] || 0
  // MA-20: Never allow delayed responses to regress a research status from a higher rank to a lower rank
  if (curRank > newRank) return false
  return true
}

export type LatestRequestHandle = {
  signal: AbortSignal
  seq: number
  isCurrent: () => boolean
  abort: () => void
}

export function createLatestRequestGuard(): { begin: (id: string) => LatestRequestHandle } {
  let active: { id: string; controller: AbortController; seq: number } | null = null
  let seqCounter = 0

  return {
    begin(id: string): LatestRequestHandle {
      active?.controller.abort()
      const controller = new AbortController()
      const seq = ++seqCounter
      const request = { id, controller, seq }
      active = request
      return {
        signal: controller.signal,
        seq,
        isCurrent: () => active === request && !controller.signal.aborted,
        abort: () => {
          controller.abort()
          if (active === request) active = null
        },
      }
    },
  }
}

export function isCallbackRetryable(
  callbackStatus: string | null | undefined,
  researchStatus: string,
  eventTypes: string[],
): boolean {
  if (callbackStatus === 'delivered') return false
  if (callbackStatus === 'failed') return true
  for (let index = eventTypes.length - 1; index >= 0; index -= 1) {
    if (eventTypes[index] === 'callback_delivered') return false
    if (eventTypes[index] === 'callback_failed') return true
  }
  return researchStatus === 'completed_but_callback_failed'
}

export function buildSettingsPayload(
  newKeys: Record<string, string>,
  models: Record<string, string>,
  callbackUrl?: string | null,
  openaiBaseUrl?: string | null,
  jinaBaseUrl?: string | null,
): {
  provider_keys: Record<string, string>
  models: Record<string, string>
  callback_url: string | null
  openai_base_url: string | null
  jina_base_url: string | null
} {
  const provider_keys: Record<string, string> = {}
  for (const [provider, val] of Object.entries(newKeys)) {
    if (val === '') {
      provider_keys[provider] = ''
    } else if (val && val.trim()) {
      provider_keys[provider] = val.trim()
    }
  }

  const model_updates: Record<string, string> = {}
  for (const [role, val] of Object.entries(models)) {
    if (val?.trim()) {
      model_updates[role] = val.trim()
    }
  }

  return {
    provider_keys,
    models: model_updates,
    callback_url: callbackUrl ? callbackUrl.trim() : callbackUrl === '' ? '' : null,
    openai_base_url: openaiBaseUrl ? openaiBaseUrl.trim() : openaiBaseUrl === '' ? '' : null,
    jina_base_url: jinaBaseUrl ? jinaBaseUrl.trim() : jinaBaseUrl === '' ? '' : null,
  }
}
