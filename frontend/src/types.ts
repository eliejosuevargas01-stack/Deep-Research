export type Point = {
  title: string
  description: string
  dependencies: string[]
  is_parallelizable: boolean
}

export type Research = {
  research_id: string
  theme: string
  status: string
  callback_url?: string | null
  callback_configured?: boolean
  callback_status?: 'pending' | 'delivered' | 'failed' | null
  briefing_draft?: { points?: Point[]; edit_note?: string; source?: string }
  points?: { id: string; title: string; status: string; attempt_count: number; audit?: unknown }[]
  error?: string
  created_at?: string
  updated_at?: string
}

export type Event = {
  id: number
  persona: string
  type: string
  summary: string
  point?: number | string
  point_id?: string
  tool?: string
  round?: number
  retry?: number
  metrics?: Record<string, number>
  created_at: string
}

export type AuditFindingPoint = {
  position?: number
  point?: string | number
  status?: string
  verdict?: string
  reason?: string
  audit?: {
    deterministic?: {
      supported?: number
      unsupported?: Array<{
        url?: string
        claim?: string
        excerpt?: string
        reason?: string
      }>
    }
    llm?: {
      approved?: boolean
      findings?: string[]
      contradictions?: string[]
      uncertainties?: string[]
      missing_research?: string[]
    }
    attempt?: number
  }
}

export type ReportData = {
  report_id: string
  research_id: string
  content_markdown: string
  citation_metrics?: {
    evidence_records?: number
    source_urls_cited?: number
  }
  audit_findings?: {
    points?: AuditFindingPoint[]
  }
  generated_at?: string
}

export type Settings = {
  provider_keys: Record<string, string | null>
  provider_configured: Record<string, boolean>
  models: Record<string, string | null>
  callback_url?: string | null
  openai_base_url?: string | null
  jina_base_url?: string | null
}
