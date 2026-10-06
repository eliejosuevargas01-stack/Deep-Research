import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Outlet,
  RouterProvider,
  useNavigate,
  useParams,
} from '@tanstack/react-router'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Clipboard,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderGit2,
  KeyRound,
  Layers3,
  LoaderCircle,
  LogOut,
  Menu,
  PanelLeft,
  PanelLeftClose,
  PanelRight,
  PanelRightClose,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  User,
  X,
} from 'lucide-react'
import './style.css'
import './tokens.css'
import './components.css'
import type { Point, Research, Event, ReportData, Settings } from './types.ts'
export type { Point, Research, Event, ReportData, Settings }

import {
  api,
  buildResearchPayload,
  clearSession,
  initializeSession,
  logoutUser,
  setCsrfToken,
} from './api.ts'
export { api }

import {
  canMovePoint,
  canTransitionStatus,
  ingestEvent,
  getModelOptions,
  parseReportData,
  reorderBriefingPoints,
  statusLabel,
  getCachedResearch,
  setCachedResearch,
  getCachedDraft,
  setCachedDraft,
  clearCachedDraft,
  getCachedEvents,
  setCachedEvents,
  getCachedReport,
  setCachedReport,
  clearAllDrCache,
  getNextActiveTab,
  buildSettingsPayload,
  createLatestRequestGuard,
  isCallbackRetryable,
  type LatestRequestHandle,
} from './research-utils.ts'

import { createProductionRouteTree } from './routes.ts'

const roles = ['scout', 'historian', 'skeptic', 'pragmatist', 'futurist', 'auditor', 'writer'] as const
const providers = ['openai', 'anthropic', 'gemini', 'litellm', 'jina', 'serpapi', 'apify'] as const
const roleName: Record<string, string> = {
  scout: 'Scout',
  historian: 'Historiador',
  skeptic: 'Cético',
  pragmatist: 'Pragmático',
  futurist: 'Visionário',
  auditor: 'Auditor',
  writer: 'Redator',
  system: 'Sistema',
}

type AppContextType = {
  authenticated: boolean | null
  history: Research[]
  refreshHistory: () => Promise<void>
  sidebarOpen: boolean
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>
  artifactsOpen: boolean
  setArtifactsOpen: React.Dispatch<React.SetStateAction<boolean>>
  mobileMenu: boolean
  setMobileMenu: React.Dispatch<React.SetStateAction<boolean>>
  error: string
  setError: React.Dispatch<React.SetStateAction<string>>
  notice: string
  setNotice: React.Dispatch<React.SetStateAction<string>>
  login: (password: string) => Promise<void>
  logout: () => Promise<void>
  busy: boolean
}

const AppContext = createContext<AppContextType | null>(null)

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}

// ----------------------------------------------------
// ROOT LAYOUT COMPONENT
// ----------------------------------------------------
function RootLayout() {
  const {
    authenticated,
    history,
    sidebarOpen,
    setSidebarOpen,
    mobileMenu,
    setMobileMenu,
    error,
    setError,
    notice,
    setNotice,
    login,
    logout,
    busy,
  } = useApp()

  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const mobileMenuOpenBtnRef = useRef<HTMLButtonElement>(null)
  const mobileMenuCloseBtnRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!authenticated) {
      setPassword('')
    }
  }, [authenticated])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!mobileMenu) return
      if (e.key === 'Escape') {
        setMobileMenu(false)
        mobileMenuOpenBtnRef.current?.focus()
        return
      }
      if (e.key === 'Tab') {
        const sidebar = document.getElementById('sidebar-navigation')
        if (!sidebar) return
        const focusable = sidebar.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (!focusable.length) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault()
            last.focus()
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault()
            first.focus()
          }
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [mobileMenu, setMobileMenu])

  useEffect(() => {
    if (mobileMenu) {
      mobileMenuCloseBtnRef.current?.focus()
    }
  }, [mobileMenu])

  if (authenticated === null) {
    return (
      <main className="loading">
        <LoaderCircle className="spin" size={28} aria-label="Verificando sessão" />
      </main>
    )
  }

  if (!authenticated) {
    return (
      <main className="login-screen">
        <div className="login-card">
          <div className="brand-mark">
            <Sparkles size={22} />
          </div>
          <p className="eyebrow">DEEP RESEARCH INTELLIGENCE</p>
          <h1>
            Espaço de pesquisa<span>.</span>
          </h1>
          <p className="muted">
            Motor autônomo multiagente com exploração cognitiva, rigor factual e quatro lentes especializadas.
          </p>
          <form
            onSubmit={e => {
              e.preventDefault()
              const pwd = password
              setPassword('')
              login(pwd)
            }}
          >
            <label htmlFor="password">Senha de administrador</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              minLength={1}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Insira sua senha de acesso"
            />
            <button className="primary full" disabled={busy}>
              {busy ? 'Entrando…' : <>Entrar <ArrowRight size={16} /></>}
            </button>
          </form>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </div>
      </main>
    )
  }

  return (
    <div className="shell">
      <a className="skip-link" href="#workspace-main">
        Ir para o conteúdo principal
      </a>
      {/* AREA 1: LEFT SIDEBAR (COLLAPSIBLE) */}
      <aside
        id="sidebar-navigation"
        className={'sidebar ' + (sidebarOpen ? 'open' : 'closed') + ' ' + (mobileMenu ? 'mobile-visible' : '')}
        aria-label="Navegação e pesquisas"
      >
        <div className="sidebar-head">
          <div className="brand-mark small">
            <Sparkles size={16} />
          </div>
          <strong>Deep Research</strong>
          <button
            ref={mobileMenuCloseBtnRef}
            className="icon-btn mobile-close"
            aria-label="Fechar menu móvel"
            onClick={() => {
              setMobileMenu(false)
              mobileMenuOpenBtnRef.current?.focus()
            }}
          >
            <X size={18} />
          </button>
        </div>

        <button
          className="new-button"
          onClick={() => {
            setMobileMenu(false)
            setError('')
            setNotice('')
            navigate({ to: '/' })
          }}
        >
          <Plus size={16} /> Nova pesquisa <span className="kbd">⌘N</span>
        </button>

        <button
          className="nav-item"
          onClick={() => {
            setMobileMenu(false)
            navigate({ to: '/' })
          }}
        >
          <Layers3 size={16} /> Conversas
        </button>

        <button
          className="nav-item"
          onClick={() => {
            setMobileMenu(false)
            setNotice('Seção de Projetos: organização por pastas e workspaces em breve.')
          }}
          title="Acessar Projetos"
        >
          <FolderGit2 size={16} /> Projetos
        </button>

        <div className="nav-caption">
          RECENTES <span>{history.length}</span>
        </div>

        <div className="history">
          {history.map(item => (
            <button
              key={item.research_id}
              className="history-item"
              onClick={() => {
                setMobileMenu(false)
                setError('')
                setNotice('')
                navigate({ to: '/research/$id', params: { id: item.research_id } })
              }}
            >
              <span className="history-dot" data-status={item.status} />
              <span>{item.theme}</span>
            </button>
          ))}
          {!history.length && <p className="quiet">Nenhuma pesquisa realizada ainda.</p>}
        </div>

        <div className="sidebar-bottom">
          <div className="user-profile-badge" title="Perfil do Usuário Autenticado">
            <div className="user-avatar">
              <User size={15} />
            </div>
            <div className="user-info">
              <span className="user-name">Administrador</span>
              <span className="user-role">Sessão Segura</span>
            </div>
          </div>
          <button
            className="nav-item"
            onClick={() => {
              setMobileMenu(false)
              setError('')
              setNotice('')
              navigate({ to: '/settings' })
            }}
          >
            <Settings2 size={16} /> Configurações
          </button>
          <button className="nav-item danger-text" onClick={logout}>
            <LogOut size={16} /> Sair
          </button>
        </div>
      </aside>

      {mobileMenu && <div className="scrim" onClick={() => setMobileMenu(false)} />}

      {/* AREA 2: CENTRAL WORKSPACE */}
      <main className="workspace" id="workspace-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              ref={mobileMenuOpenBtnRef}
              className="icon-btn mobile-open"
              aria-label="Menu"
              onClick={() => setMobileMenu(true)}
            >
              <Menu size={18} />
            </button>
            <button
              className="icon-btn desktop-toggle"
              aria-label={sidebarOpen ? 'Recolher menu lateral' : 'Expandir menu lateral'}
              aria-expanded={sidebarOpen}
              aria-controls="sidebar-navigation"
              onClick={() => setSidebarOpen(s => !s)}
              title={sidebarOpen ? 'Recolher barra lateral' : 'Expandir barra lateral'}
            >
              {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
            </button>
            <nav className="breadcrumbs" aria-label="Navegação estrutural">
              <ol className="breadcrumb-list">
                <li className="breadcrumb-item">
                  <button
                    type="button"
                    className="breadcrumb-link"
                    onClick={() => {
                      setError('')
                      setNotice('')
                      navigate({ to: '/' })
                    }}
                  >
                    Deep Research
                  </button>
                </li>
                <li className="breadcrumb-separator" aria-hidden="true">
                  <ChevronRight size={14} />
                </li>
                <li className="breadcrumb-item" aria-current="page">
                  <span className="current-crumb">Painel Principal</span>
                </li>
              </ol>
            </nav>
          </div>
        </header>

        {error && (
          <div className="banner error-banner" role="alert">
            <CircleHelp size={18} />
            <span>{error}</span>
            <button className="icon-btn" onClick={() => setError('')} aria-label="Fechar erro">
              <X size={16} />
            </button>
          </div>
        )}

        {notice && (
          <div className="banner notice-banner" role="status">
            <Check size={18} />
            <span>{notice}</span>
            <button className="icon-btn" onClick={() => setNotice('')} aria-label="Fechar aviso">
              <X size={16} />
            </button>
          </div>
        )}

        <Outlet />
      </main>
    </div>
  )
}

// ----------------------------------------------------
// HOME PAGE COMPONENT (CHAT COMPOSER & 4-STEP GUIDE)
// ----------------------------------------------------
function HomePage() {
  const { refreshHistory, setError } = useApp()
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (topic.trim().length < 3) return
    setSubmitting(true)
    setError('')
    try {
      // CRITERIA A2 & A4: payload contains theme. Browser uses HttpOnly session cookie; no secrets sent.
      const payload = buildResearchPayload(topic)
      const item = await api<Research>('/api/research', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setTopic('')
      await refreshHistory()
      navigate({ to: '/research/$id', params: { id: item.research_id } })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="home-chat">
      <div className="hero">
        <div className="hero-icon">
          <Sparkles size={28} />
        </div>
        <p className="eyebrow">PESQUISA PROFUNDA MULTIAGENTE</p>
        <h1>
          O que você quer<br />
          <span>investigar profundamente?</span>
        </h1>
        <p className="hero-sub">
          Submeta um tema complexo. Nosso Scout fará a varredura preliminar, você aprova ou ajusta os 5 pontos, e
          4 agentes investigam em paralelo com diferentes perspectivas e auditoria de fontes.
        </p>
      </div>

      <form className="composer-card" onSubmit={submit}>
        <label htmlFor="topic" className="sr-only">
          Tema da pesquisa
        </label>
        <textarea
          id="topic"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          rows={3}
          minLength={3}
          maxLength={500}
          placeholder="Ex: Impactos econômicos e gargalos de produção de chips semicondutores na Ásia em 2026…"
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              e.currentTarget.form?.requestSubmit()
            }
          }}
        />
        <div className="composer-footer">
          <span className="hint-text">
            <Search size={14} /> 5-10 fontes reais por agente · 4 perspectivas simultâneas
          </span>
          <button type="submit" className="primary" disabled={submitting || topic.trim().length < 3}>
            {submitting ? (
              <>
                <LoaderCircle size={16} className="spin" /> Iniciando…
              </>
            ) : (
              <>
                Iniciar pesquisa <Send size={15} />
              </>
            )}
          </button>
        </div>
      </form>

      <div className="process-steps">
        <div className="step-item">
          <span className="step-num">01</span>
          <div>
            <strong>Scout Preliminar</strong>
            <small>Reconhecimento rápido de fontes</small>
          </div>
        </div>
        <ChevronRight size={16} className="step-arrow" />
        <div className="step-item">
          <span className="step-num">02</span>
          <div>
            <strong>Briefing em 5 Pontos</strong>
            <small>Aprovação ou ajuste único</small>
          </div>
        </div>
        <ChevronRight size={16} className="step-arrow" />
        <div className="step-item">
          <span className="step-num">03</span>
          <div>
            <strong>4 Personas Especialistas</strong>
            <small>Até 20 workers simultâneos</small>
          </div>
        </div>
        <ChevronRight size={16} className="step-arrow" />
        <div className="step-item">
          <span className="step-num">04</span>
          <div>
            <strong>Auditoria & Relatório</strong>
            <small>Fontes auditadas e rastreáveis</small>
          </div>
        </div>
      </div>
    </div>
  )
}

// ----------------------------------------------------
// RESEARCH DETAIL PAGE (CHAT + PERSONAS + ARTIFACTS)
// ----------------------------------------------------
function ResearchPage() {
  const { id } = useParams({ from: '/research/$id' })
  const navigate = useNavigate()
  const {
    artifactsOpen,
    setArtifactsOpen,
    setError,
    setNotice,
    refreshHistory,
  } = useApp()

  const [research, setResearch] = useState<Research | null>(() => getCachedResearch(id))
  const [loadError, setLoadError] = useState<string>('')
  const [events, setEvents] = useState<Event[]>(() => getCachedEvents(id) || [])
  const [reportData, setReportData] = useState<ReportData | null>(() => getCachedReport(id))
  const [points, setPoints] = useState<Point[]>(() => {
    const draft = getCachedDraft(id)
    if (draft?.points?.length) return draft.points
    const cached = getCachedResearch(id)
    return cached?.briefing_draft?.points || []
  })
  const [editNote, setEditNote] = useState<string>(() => {
    const draft = getCachedDraft(id)
    return draft?.editNote || ''
  })
  const [activeTab, setActiveTab] = useState<'plan' | 'evidence' | 'report'>('plan')
  const [busy, setBusy] = useState(false)
  const [retryingCallback, setRetryingCallback] = useState(false)
  const [resuming, setResuming] = useState(false)
  const [sseState, setSseState] = useState<'connecting' | 'connected' | 'reconnecting' | 'error' | 'closed'>('connecting')
  const [reconnectCount, setReconnectCount] = useState(0)
  const chatBottomRef = useRef<HTMLDivElement>(null)
  const artifactsToggleBtnRef = useRef<HTMLButtonElement>(null)
  const artifactsCloseBtnRef = useRef<HTMLButtonElement>(null)
  const artifactsDrawerRef = useRef<HTMLElement>(null)
  const requestGuardRef = useRef(createLatestRequestGuard())
  const activeRequestRef = useRef<LatestRequestHandle | null>(null)
  const seenEventIdsRef = useRef<Set<number>>(new Set())
  const [artifactsModal, setArtifactsModal] = useState(() => window.matchMedia('(max-width: 1080px)').matches)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1080px)')
    const updateMode = () => setArtifactsModal(media.matches)
    media.addEventListener('change', updateMode)
    return () => media.removeEventListener('change', updateMode)
  }, [])

  useEffect(() => {
    if (!artifactsOpen || !artifactsModal) return

    const drawer = artifactsDrawerRef.current
    artifactsCloseBtnRef.current?.focus()
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        setArtifactsOpen(false)
        artifactsToggleBtnRef.current?.focus()
        return
      }
      if (e.key !== 'Tab' || !drawer) return
      const focusable = Array.from(
        drawer.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'),
      ).filter(element => !element.hasAttribute('hidden'))
      if (focusable.length === 0) {
        e.preventDefault()
        drawer.focus()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [artifactsModal, artifactsOpen, setArtifactsOpen])

  const loadReport = (resId: string, request: LatestRequestHandle) => {
    api<unknown>('/api/reports/' + resId, { signal: request.signal })
      .then(data => {
        if (!request.isCurrent()) return
        const parsed = parseReportData(data)
        setReportData(parsed)
        setCachedReport(resId, parsed)
      })
      .catch((e: Error) => {
        if (!request.isCurrent()) return
        setError(e.message)
      })
  }

  const loadResearch = (resId: string, request: LatestRequestHandle) => {
    setLoadError('')
    api<Research>('/api/research/' + resId, { signal: request.signal })
      .then(data => {
        if (!request.isCurrent()) return
        setResearch(prev => {
          // MA-20: Prevent delayed responses from regressing status
          if (prev && !canTransitionStatus(prev.status, data.status)) {
            return prev
          }
          setCachedResearch(resId, data)
          return data
        })
        const draft = getCachedDraft(resId)
        if (draft?.points?.length) {
          setPoints(draft.points)
          setEditNote(draft.editNote)
        } else {
          setPoints(data.briefing_draft?.points || [])
          setEditNote(data.briefing_draft?.edit_note || '')
        }
        if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) {
          loadReport(resId, request)
          setActiveTab('report')
        } else if (data.status === 'pending_approval') {
          setActiveTab('plan')
        }
      })
      .catch((e: Error) => {
        if (!request.isCurrent()) return
        setLoadError(e.message)
        setError(e.message)
      })
  }

  const retryLoadResearch = () => {
    const request = requestGuardRef.current.begin(id)
    activeRequestRef.current = request
    loadResearch(id, request)
  }

  // Synchronize and reset state immediately on id change so research A is never retained
  useEffect(() => {
    const cachedRes = getCachedResearch(id)
    const cachedDraft = getCachedDraft(id)
    const cachedEv = getCachedEvents(id) || []
    const cachedRep = getCachedReport(id)

    setResearch(cachedRes)
    setLoadError('')
    setEvents(cachedEv)
    seenEventIdsRef.current = new Set((cachedEv || []).map(e => e.id))
    setReportData(cachedRep)
    setPoints(cachedDraft?.points?.length ? cachedDraft.points : (cachedRes?.briefing_draft?.points || []))
    setEditNote(cachedDraft?.editNote || (cachedRes?.briefing_draft?.edit_note || ''))
    setActiveTab(cachedRes && ['completed', 'completed_but_callback_failed', 'blocked'].includes(cachedRes.status) ? 'report' : 'plan')
    setBusy(false)
    setRetryingCallback(false)
    setError('')
    setNotice('')

    const request = requestGuardRef.current.begin(id)
    activeRequestRef.current = request
    loadResearch(id, request)
    return () => activeRequestRef.current?.abort()
  }, [id])

  // SSE event streaming with deduplication, callback tracking, and reconnection state (F-03, F-07)
  useEffect(() => {
    if (!id) return
    const request = activeRequestRef.current
    if (!request?.isCurrent()) return
    setSseState('connecting')
    const source = new EventSource('/api/research/' + id + '/events', { withCredentials: true })

    source.onopen = () => {
      if (request.isCurrent()) setSseState('connected')
    }

    source.addEventListener('progress', message => {
      if (!request.isCurrent()) return
      try {
        const event = JSON.parse((message as MessageEvent).data) as Event
        const isDuplicate = seenEventIdsRef.current.has(event.id)
        if (isDuplicate) {
          // MA-20: Repeated events must not re-apply effects or re-close stream
          return
        }
        seenEventIdsRef.current.add(event.id)

        setEvents(old => {
          const updated = ingestEvent(old, event)
          setCachedEvents(id, updated)
          return updated
        })

        if (event.type === 'synthesis_completed') {
          loadReport(id, request)
          setActiveTab('report')
          api<Research>('/api/research/' + id, { signal: request.signal })
            .then(data => {
              if (!request.isCurrent()) return
              setResearch(data)
              setCachedResearch(id, data)
              if (data.status === 'completed' && data.callback_configured === false) {
                source.close()
                setSseState('closed')
              }
            })
            .catch(() => {})
          refreshHistory()
          return
        }

        if (event.type === 'callback_delivered') {
          setNotice('Relatório entregue com sucesso via webhook de callback.')
          api<Research>('/api/research/' + id, { signal: request.signal })
            .then(data => {
              if (!request.isCurrent()) return
              setResearch(data)
              setCachedResearch(id, data)
            })
            .catch(() => {})
          refreshHistory()
          source.close()
          setSseState('closed')
          return
        }

        if (event.type === 'callback_failed') {
          setError('A entrega do relatório ao webhook falhou. Você pode acionar o reenvio.')
          api<Research>('/api/research/' + id, { signal: request.signal })
            .then(data => {
              if (!request.isCurrent()) return
              setResearch(data)
              setCachedResearch(id, data)
            })
            .catch(() => {})
          refreshHistory()
          source.close()
          setSseState('closed')
          return
        }

        if (['research_failed', 'scout_failed'].includes(event.type)) {
          api<Research>('/api/research/' + id, { signal: request.signal })
            .then(data => {
              if (!request.isCurrent()) return
              setResearch(data)
              setCachedResearch(id, data)
            })
            .catch(() => {})
          refreshHistory()
          source.close()
          setSseState('closed')
          return
        }

        if (['briefing_ready', 'briefing_approved'].includes(event.type)) {
          api<Research>('/api/research/' + id, { signal: request.signal })
            .then(data => {
              if (!request.isCurrent()) return
              setResearch(data)
              setCachedResearch(id, data)
              if (!getCachedDraft(id)) {
                setPoints(data.briefing_draft?.points || [])
              }
            })
            .catch(() => {})
          refreshHistory()
        }
      } catch {
        setError('Evento de progresso recebido em formato inválido.')
      }
    })

    source.onerror = () => {
      if (!request.isCurrent()) return
      // F-07: Inform user and attempt reconnection unless already terminal
      if (
        research &&
        ['completed', 'completed_but_callback_failed', 'blocked', 'failed'].includes(research.status)
      ) {
        source.close()
        setSseState('closed')
      } else {
        setSseState('reconnecting')
      }
    }

    return () => {
      source.close()
      setSseState('closed')
    }
  }, [id, research?.status, reconnectCount])

  // Periodic polling fallback for in-flight jobs
  useEffect(() => {
    if (
      !research ||
      ['completed', 'completed_but_callback_failed', 'blocked', 'failed'].includes(research.status)
    )
      return

    const request = activeRequestRef.current
    if (!request?.isCurrent()) return
    const timer = window.setInterval(() => {
      api<Research>('/api/research/' + id, { signal: request.signal })
        .then(data => {
          if (!request.isCurrent()) return
          setResearch(prev => {
            if (prev && !canTransitionStatus(prev.status, data.status)) {
              return prev
            }
            setCachedResearch(id, data)
            return data
          })
          if (
            data.status === 'pending_approval' &&
            (!points.length || data.briefing_draft?.points?.length !== points.length)
          ) {
            if (!getCachedDraft(id)) {
              setPoints(data.briefing_draft?.points || [])
            }
          }
          if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) {
            loadReport(id, request)
            refreshHistory()
          }
        })
        .catch(() => {})
    }, 4000)

    return () => window.clearInterval(timer)
  }, [id, research?.status, points.length])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events, research?.status])

  async function approve() {
    if (!research || points.some(p => p.title.trim().length < 3 || p.description.trim().length < 3)) {
      setError('Preencha o título e a descrição de cada ponto do briefing.')
      return
    }
    const request = activeRequestRef.current
    if (!request?.isCurrent()) return
    setBusy(true)
    setError('')
    try {
      await api('/api/research/' + id + '/briefing/approve', {
        method: 'POST',
        body: JSON.stringify({ approved_points: points }),
        signal: request.signal,
      })
      if (!request.isCurrent()) return
      clearCachedDraft(id)
      const refreshed = await api<Research>('/api/research/' + id, { signal: request.signal })
      if (!request.isCurrent()) return
      setResearch(refreshed)
      setCachedResearch(id, refreshed)
      await refreshHistory()
    } catch (e) {
      if (request.isCurrent()) setError((e as Error).message)
    } finally {
      if (request.isCurrent()) setBusy(false)
    }
  }

  async function sendAdjustments() {
    if (!research) return
    if (!editNote.trim()) {
      setError('Escreva uma nota detalhando os ajustes necessários para o scout refazer o plano.')
      return
    }
    const request = activeRequestRef.current
    if (!request?.isCurrent()) return
    setBusy(true)
    setError('')
    try {
      await api('/api/research/' + id + '/briefing/edit', {
        method: 'POST',
        body: JSON.stringify({ note: editNote.trim(), points }),
        signal: request.signal,
      })
      if (!request.isCurrent()) return
      clearCachedDraft(id)
      setNotice('Ajustes enviados com sucesso! O Scout está refinando o plano e iniciará a pesquisa automaticamente.')
      const refreshed = await api<Research>('/api/research/' + id, { signal: request.signal })
      if (!request.isCurrent()) return
      setResearch(refreshed)
      setCachedResearch(id, refreshed)
      await refreshHistory()
    } catch (e) {
      if (request.isCurrent()) setError((e as Error).message)
    } finally {
      if (request.isCurrent()) setBusy(false)
    }
  }

  async function handleRetryCallback() {
    if (!id) return
    const request = activeRequestRef.current
    if (!request?.isCurrent()) return
    setRetryingCallback(true)
    setError('')
    try {
      const res = await api<{ success?: boolean; delivered?: boolean }>('/api/reports/' + id + '/retry-callback', {
        method: 'POST',
        signal: request.signal,
      })
      if (!request.isCurrent()) return
      const delivered = Boolean(res.success ?? res.delivered)
      if (delivered) {
        setNotice('Webhook reenviado e entregue com sucesso!')
      } else {
        setError('Tentativa de reenvio falhou: o webhook destino não retornou confirmação.')
      }
      const refreshed = await api<Research>('/api/research/' + id, { signal: request.signal })
      if (!request.isCurrent()) return
      setResearch(refreshed)
      setCachedResearch(id, refreshed)
      await refreshHistory()
    } catch (e) {
      if (request.isCurrent()) setError('Erro ao acionar reenvio do callback: ' + (e as Error).message)
    } finally {
      if (request.isCurrent()) setRetryingCallback(false)
    }
  }

  async function handleResume() {
    if (!id || busy || resuming) return
    const request = activeRequestRef.current
    if (!request?.isCurrent()) return
    setResuming(true)
    setError('')
    try {
      await api('/api/research/' + id + '/resume', {
        method: 'POST',
        signal: request.signal,
      })
      if (!request.isCurrent()) return
      const refreshed = await api<Research>('/api/research/' + id, { signal: request.signal })
      if (!request.isCurrent()) return
      setResearch(refreshed)
      setCachedResearch(id, refreshed)
      setNotice('Pesquisa retomada com sucesso! Acompanhando execução…')
      setReconnectCount(c => c + 1)
      await refreshHistory()
    } catch (e) {
      if (request.isCurrent()) setError('Erro ao retomar pesquisa: ' + (e as Error).message)
    } finally {
      if (request.isCurrent()) setResuming(false)
    }
  }

  function editPoint(index: number, key: keyof Point, value: any) {
    setPoints(old => {
      const updated = old.map((p, i) => (i === index ? { ...p, [key]: value } : p))
      setCachedDraft(id, { points: updated, editNote })
      return updated
    })
  }

  function movePoint(index: number, shift: number) {
    const check = canMovePoint(points, index, shift)
    if (!check.allowed) {
      setError(check.reason || 'Movimento inválido: viola dependências entre os pontos do plano')
      return
    }
    setPoints(old => {
      const updated = reorderBriefingPoints(old, index, shift)
      setCachedDraft(id, { points: updated, editNote })
      return updated
    })
  }

  const exportReport = () => {
    if (!reportData?.content_markdown) return
    const blob = new Blob([reportData.content_markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download =
      'deep-research-' + (research?.theme.slice(0, 30).replace(/\s+/g, '-').toLowerCase() || 'report') + '.md'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleTabKeyDown = (e: React.KeyboardEvent, tab: 'plan' | 'evidence' | 'report') => {
    let nextTab: 'plan' | 'evidence' | 'report' | null = null
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault()
      nextTab = getNextActiveTab(tab, 'next')
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault()
      nextTab = getNextActiveTab(tab, 'prev')
    } else if (e.key === 'Home') {
      e.preventDefault()
      nextTab = getNextActiveTab(tab, 'first')
    } else if (e.key === 'End') {
      e.preventDefault()
      nextTab = getNextActiveTab(tab, 'last')
    }
    if (nextTab) {
      setActiveTab(nextTab)
      const el = document.getElementById(`tab-${nextTab}`)
      el?.focus()
    }
  }

  if (!research) {
    if (loadError) {
      return (
        <div className="error-state-card" role="alert">
          <CircleHelp size={32} color="#f87171" />
          <h3>Não foi possível carregar a pesquisa</h3>
          <p>{loadError}</p>
          <div className="error-actions">
            <button className="primary" onClick={retryLoadResearch}>
              Tentar carregar novamente
            </button>
            <button className="secondary" onClick={() => navigate({ to: '/' })}>
              Voltar ao painel
            </button>
          </div>
        </div>
      )
    }
    return (
      <div className="research-skeleton" role="status" aria-label="Carregando pesquisa">
        <div className="skeleton" style={{ width: '40%', height: '20px', marginBottom: '18px' }} />
        <div className="skeleton" style={{ width: '70%', height: '14px', marginBottom: '12px' }} />
        <div className="skeleton" style={{ width: '100%', height: '120px', marginBottom: '18px', borderRadius: '12px' }} />
        <div className="skeleton" style={{ width: '100%', height: '80px', borderRadius: '12px' }} />
      </div>
    )
  }

  const isCompleted = ['completed', 'completed_but_callback_failed', 'blocked'].includes(research.status)
  const isBlocked = research.status === 'blocked'
  const isCallbackFailed = isCallbackRetryable(research.callback_status, research.status, events.map(event => event.type))
  const isCallbackDelivered = research.callback_status === 'delivered' || events.some(e => e.type === 'callback_delivered')
  const hasCallback = Boolean(research.callback_configured || isCallbackFailed || isCallbackDelivered)

  return (
    <div className={'research-workspace ' + (artifactsOpen ? 'with-artifacts' : 'full-center')}>
      {/* CENTER CONVERSATION */}
      <div className="conversation-pane">
        {/* RESEARCH TOP BAR */}
        <div className="research-banner">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <button className="back-btn" onClick={() => navigate({ to: '/' })}>
              <ArrowLeft size={15} /> Nova conversa
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {sseState === 'connected' && (
                <span className="sse-indicator live" title="Conexão ao vivo de eventos ativa">
                  <span className="pulse-dot" /> Ao vivo
                </span>
              )}
              {sseState === 'reconnecting' && (
                <span className="sse-indicator reconnecting" title="Tentando reconectar stream…">
                  <LoaderCircle size={11} className="spin" /> Reconectando
                  <button
                    type="button"
                    style={{ background: 'transparent', border: 0, color: 'inherit', textDecoration: 'underline', cursor: 'pointer', padding: 0, fontSize: '10px' }}
                    onClick={() => setReconnectCount(c => c + 1)}
                  >
                    Tentar agora
                  </button>
                </span>
              )}
              <span className={'status-pill ' + research.status}>{statusLabel(research.status)}</span>
              {research.status === 'failed' && (
                <button
                  type="button"
                  className="secondary"
                  style={{ padding: '3px 8px', fontSize: '11px', gap: '4px', height: '24px', display: 'inline-flex', alignItems: 'center' }}
                  disabled={resuming || busy}
                  onClick={handleResume}
                  title="Retomar execução da pesquisa"
                >
                  <RefreshCw size={11} className={resuming ? 'spin' : ''} />
                  {resuming ? 'Retomando…' : 'Retomar'}
                </button>
              )}
              <button
                ref={artifactsToggleBtnRef}
                className={'icon-btn artifacts-toggle ' + (artifactsOpen ? 'active' : '')}
                aria-label={artifactsOpen ? 'Recolher painel de artefatos' : 'Abrir painel de artefatos'}
                aria-expanded={artifactsOpen}
                aria-controls="artifacts-drawer"
                onClick={() => setArtifactsOpen(a => !a)}
                title={artifactsOpen ? 'Ocultar artefatos' : 'Exibir artefatos'}
              >
                {artifactsOpen ? <PanelRightClose size={18} /> : <PanelRight size={18} />}
                <span className="toggle-label" style={{ fontSize: '12px', marginLeft: '4px' }}>Artefatos</span>
              </button>
            </div>
          </div>
          <h2>{research.theme}</h2>
          <div className="pipeline-flow">
            <span className={'step-badge ' + (research.status === 'scouting' ? 'active' : 'passed')}>
              <Search size={13} /> 1. Scout
            </span>
            <span
              className={
                'step-badge ' +
                (research.status === 'pending_approval'
                  ? 'active'
                  : ['approved', 'in_progress', 'completed', 'blocked'].includes(research.status)
                  ? 'passed'
                  : '')
              }
            >
              <Clipboard size={13} /> 2. Briefing
            </span>
            <span
              className={
                'step-badge ' +
                (['approved', 'in_progress'].includes(research.status)
                  ? 'active'
                  : isCompleted
                  ? 'passed'
                  : '')
              }
            >
              <Layers3 size={13} /> 3. Investigação
            </span>
            <span className={'step-badge ' + (reportData ? 'passed' : '')}>
              <FileText size={13} /> 4. Relatório
            </span>
          </div>
        </div>

        {/* MESSAGES & INTERACTIVE CARDS */}
        <div className="conversation-thread">
          {/* USER INITIAL MESSAGE */}
          <div className="chat-bubble user">
            <div className="bubble-header">
              <span className="sender-tag">VOCÊ</span>
              <span className="time-tag">
                {research.created_at ? new Date(research.created_at).toLocaleTimeString('pt-BR') : ''}
              </span>
            </div>
            <p className="bubble-content">{research.theme}</p>
          </div>

          {/* SCOUT PHASE CARD */}
          {research.status === 'scouting' && (
            <div className="agent-card scout-card">
              <div className="card-avatar">
                <LoaderCircle size={20} className="spin" />
              </div>
              <div className="card-content">
                <strong>Scout explorando a web…</strong>
                <p>
                  Mapeando o estado da arte e conceitos centrais em 5 fontes independentes para construir o
                  plano de 5 pontos de investigação.
                </p>
              </div>
            </div>
          )}

          {/* BRIEFING APPROVAL / EDIT CARD (CRITERIA A3) */}
          {research.status === 'pending_approval' && (
            <div className="agent-card brief-card">
              <div className="brief-title-bar">
                <div className="agent-avatar">
                  <Sparkles size={18} />
                </div>
                <div>
                  <strong>Scout & Briefing · Rascunho Inicial</strong>
                  <p>
                    Revise os 5 pontos de investigação propostos. Esta é sua oportunidade única de aprovar ou
                    enviar ajustes.
                  </p>
                </div>
              </div>

              <div className="points-container">
                {points.map((p, i) => (
                  <div className="point-item" key={i}>
                    <div className="point-badge">{String(i + 1).padStart(2, '0')}</div>
                    <div className="point-inputs">
                      <input
                        className="point-title-input"
                        value={p.title}
                        onChange={e => editPoint(i, 'title', e.target.value)}
                        placeholder="Título do ponto"
                        aria-label={'Título do ponto ' + (i + 1)}
                      />
                      <textarea
                        className="point-desc-input"
                        rows={2}
                        value={p.description}
                        onChange={e => editPoint(i, 'description', e.target.value)}
                        placeholder="Descrição e escopo investigativo"
                        aria-label={'Descrição do ponto ' + (i + 1)}
                      />
                      <label className="checkbox-row">
                        <input
                          type="checkbox"
                          checked={p.is_parallelizable}
                          onChange={e => editPoint(i, 'is_parallelizable', e.target.checked)}
                        />
                        <span>Pode ser executado em paralelo</span>
                      </label>
                    </div>
                    <div className="point-order-controls">
                      {(() => {
                        const canUp = canMovePoint(points, i, -1)
                        const canDown = canMovePoint(points, i, 1)
                        return (
                          <>
                            <button
                              type="button"
                              disabled={i === 0 || !canUp.allowed}
                              onClick={() => movePoint(i, -1)}
                              aria-label="Mover ponto para cima"
                              title={!canUp.allowed ? canUp.reason : 'Mover ponto para cima'}
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              disabled={i === points.length - 1 || !canDown.allowed}
                              onClick={() => movePoint(i, 1)}
                              aria-label="Mover ponto para baixo"
                              title={!canDown.allowed ? canDown.reason : 'Mover ponto para baixo'}
                            >
                              ↓
                            </button>
                          </>
                        )
                      })()}
                    </div>
                  </div>
                ))}
              </div>

              {/* EDIT NOTE INPUT FOR BRIEFING ADJUSTMENTS */}
              <div className="brief-adjustment-box">
                <label htmlFor="edit-note">
                  <strong>Instruções de Ajuste (Opcional caso queira refazer o rascunho)</strong>
                  <small>
                    Se desejar que o Scout refine o plano, descreva o que alterar e clique em "Enviar ajustes".
                  </small>
                </label>
                <textarea
                  id="edit-note"
                  rows={2}
                  value={editNote}
                  onChange={e => {
                    const nextVal = e.target.value
                    setEditNote(nextVal)
                    setCachedDraft(id, { points, editNote: nextVal })
                  }}
                  placeholder="Ex: Foque mais no cenário de 2026 e adicione um ponto sobre custos operacionais…"
                />
              </div>

              <div className="brief-footer-actions">
                <button
                  className="secondary"
                  type="button"
                  disabled={busy || !editNote.trim()}
                  onClick={sendAdjustments}
                  title="Devolve as instruções ao Scout para refazer o rascunho e iniciar a pesquisa"
                >
                  {busy ? 'Enviando…' : 'Enviar ajustes'}
                </button>
                <button className="primary" type="button" disabled={busy || !points.length} onClick={approve}>
                  {busy ? 'Aprovando…' : <>Aprovar e iniciar pesquisa <ArrowRight size={16} /></>}
                </button>
              </div>
            </div>
          )}

          {/* 4 SPECIALIST PERSONAS GRID (MA-16: Não sumir em completed_but_callback_failed) */}
          {(isCompleted || ['approved', 'in_progress', 'completed_but_callback_failed'].includes(research.status)) && (
            <div className="personas-block">
              <div className="block-header">
                <h3>Quatro Personas Especialistas</h3>
                <p>Execução paralela investigativa focada no viés cognitivo de cada agente.</p>
              </div>

              <div className="personas-cards">
                {(['historian', 'skeptic', 'pragmatist', 'futurist'] as const).map((role, idx) => {
                  const personaEvents = events.filter(e => e.persona === role)
                  const latestEvent = personaEvents[personaEvents.length - 1]
                  const isDone = isCompleted
                  const isFailed = research.status === 'failed'

                  let personaStatusClass = 'waiting'
                  let personaStatusText = 'Aguardando'
                  if (isFailed) {
                    personaStatusClass = 'failed'
                    personaStatusText = 'Interrompido'
                  } else if (isDone) {
                    personaStatusClass = 'done'
                    personaStatusText = 'Concluído'
                  } else if (latestEvent) {
                    personaStatusClass = 'active'
                    personaStatusText = 'Pesquisando'
                  }

                  return (
                    <div className="persona-card" key={role}>
                      <div className="persona-header">
                        <span className="persona-num">0{idx + 1}</span>
                        <span className={'persona-tag ' + personaStatusClass}>
                          {personaStatusText}
                        </span>
                      </div>
                      <h4>{roleName[role]}</h4>
                      <p className="persona-focus">
                        {
                          [
                            'Base conceitual, histórico e estado da arte.',
                            'Contraponto crítico, falhas e limitações.',
                            'Métricas reais, casos de uso e dados empíricos.',
                            'Tendências futuras, patentes e projeções.',
                          ][idx]
                        }
                      </p>
                      <div className="persona-latest">
                        {latestEvent
                          ? latestEvent.summary
                          : isFailed
                          ? 'Investigação interrompida.'
                          : 'Aguardando evidências…'}
                      </div>
                      {personaEvents.length > 0 && (
                        <div className="persona-meta-footer" style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-tertiary)', display: 'flex', gap: '6px', alignItems: 'center' }}>
                          <span>{personaEvents.length} eventos</span>
                          {latestEvent?.point && <span>· Ponto {latestEvent.point}</span>}
                          {latestEvent?.tool && <span>· Ferramenta: <code>{latestEvent.tool}</code></span>}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* EXECUTION TIMELINE (A5, A15) */}
          {events.length > 0 && (
            <div className="execution-timeline">
              <div className="timeline-title">
                <h3>Linha do Tempo da Investigação</h3>
                <span>{events.length} eventos registrados</span>
              </div>

              <div className="timeline-events">
                {events.map(ev => (
                  <div className="timeline-item" key={ev.id}>
                    <div className="item-marker" />
                    <div className="item-body">
                      <div className="item-top">
                        <strong>{roleName[ev.persona] || ev.persona}</strong>
                        <time>
                          {new Date(ev.created_at).toLocaleTimeString('pt-BR', {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                          })}
                        </time>
                      </div>
                      <p>{ev.summary}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* RESEARCH COMPLETION CHAT CARD */}
          {isCompleted && reportData && (
            <div className={'completed-chat-card ' + (isBlocked ? 'with-caveats' : '')}>
              <div className="completed-header">
                {isBlocked ? (
                  <ShieldAlert size={20} color="#f59e0b" />
                ) : (
                  <FileCheck2 size={20} color="#10b981" />
                )}
                <strong>
                  {isBlocked
                    ? 'Pesquisa Concluída com Ressalvas de Auditoria'
                    : 'Pesquisa Concluída com Auditoria de Fontes'}
                </strong>
              </div>
              <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)' }}>
                Relatório consolidado com base em fontes auditadas e múltiplas perspectivas investigativas (
                <strong>{reportData.citation_metrics?.source_urls_cited || 0} fontes citadas</strong> e{' '}
                <strong>{reportData.citation_metrics?.evidence_records || 0} evidências consolidadas</strong>).
              </p>

              {/* CALLBACK STATUS & RETRY (F-03) */}
              {hasCallback && (
                <div
                  className={
                    'callback-status-card ' +
                    (isCallbackFailed
                      ? 'failed'
                      : isCallbackDelivered
                      ? 'delivered'
                      : '')
                  }
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <ExternalLink size={14} />
                    <span>
                      {isCallbackFailed
                        ? 'Falha na entrega do webhook de callback'
                        : isCallbackDelivered
                        ? 'Webhook entregue com sucesso'
                        : 'Webhook de callback configurado'}
                    </span>
                  </div>
                  {isCallbackFailed && (
                    <button
                      type="button"
                      className="secondary btn-retry-callback"
                      disabled={retryingCallback}
                      onClick={handleRetryCallback}
                      title="Acionar POST /api/reports/{id}/retry-callback"
                    >
                      {retryingCallback ? (
                        <>
                          <LoaderCircle size={12} className="spin" /> Reenviando…
                        </>
                      ) : (
                        <>
                          <RefreshCw size={12} /> Reenviar Webhook
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}

              <div className="completed-actions">
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    setArtifactsOpen(true)
                    setActiveTab('report')
                  }}
                >
                  <BookOpen size={14} /> Abrir Relatório no Painel
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    navigator.clipboard
                      .writeText(reportData.content_markdown)
                      .then(() => setNotice('Relatório copiado para a área de transferência!'))
                      .catch(err =>
                        setError('Falha ao copiar para a área de transferência: ' + (err?.message || 'Permissão negada')),
                      )
                  }}
                >
                  <Clipboard size={14} /> Copiar Markdown
                </button>
                <button type="button" className="secondary" onClick={exportReport}>
                  <Download size={14} /> Exportar .md
                </button>
              </div>
            </div>
          )}

          {research.status === 'failed' && (
            <div className="agent-card error-card" role="alert">
              <CircleHelp size={20} />
              <div>
                <strong>A pesquisa foi interrompida</strong>
                <p>
                  {research.error || 'Verifique as chaves e modelos configurados na página de configurações.'}
                </p>
                <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={resuming || busy}
                    onClick={handleResume}
                  >
                    <RefreshCw size={14} className={resuming ? 'spin' : ''} />
                    {resuming ? 'Retomando…' : 'Retomar Pesquisa'}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => navigate({ to: '/settings' })}
                  >
                    Verificar Configurações
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => navigate({ to: '/' })}
                  >
                    Nova Pesquisa
                  </button>
                </div>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* BOTTOM AI CHAT COMPOSER (CRITERIA A12, A14, MA-23) */}
        <div className="chat-composer-bar">
          {research.status === 'pending_approval' ? (
            <form
              className="composer-form"
              onSubmit={e => {
                e.preventDefault()
                if (editNote.trim() && !busy) sendAdjustments()
              }}
            >
              <textarea
                className="composer-input"
                rows={1}
                placeholder="Descreva ajustes para o Scout refinar o plano de pesquisa…"
                value={editNote}
                onChange={e => {
                  const nextVal = e.target.value
                  setEditNote(nextVal)
                  setCachedDraft(id, { points, editNote: nextVal })
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (editNote.trim() && !busy) sendAdjustments()
                  }
                }}
              />
              <button
                type="submit"
                className="composer-send-btn"
                disabled={busy || !editNote.trim()}
                title="Enviar ajustes ao Scout"
              >
                <Send size={15} />
              </button>
            </form>
          ) : isCompleted ? (
            <div className="composer-status-bar">
              <span className="composer-status-text">
                ✓ Pesquisa concluída com sucesso.
              </span>
              <button
                type="button"
                className="secondary small"
                onClick={() => navigate({ to: '/' })}
              >
                Nova Pesquisa <ArrowRight size={13} />
              </button>
            </div>
          ) : (
            <div className="composer-status-bar">
              <LoaderCircle size={14} className="spin" />
              <span className="composer-status-text">
                Pesquisa autônoma em andamento. Os agentes estão investigando os 5 pontos.
              </span>
            </div>
          )}
        </div>
      </div>

      {/* AREA 3: RIGHT ARTIFACTS DRAWER (COLLAPSIBLE) */}
      {artifactsOpen && (
        <>
          <aside
            ref={artifactsDrawerRef}
            id="artifacts-drawer"
            className="artifacts-drawer"
            aria-label="Painel de artefatos da pesquisa"
            role={artifactsModal ? 'dialog' : undefined}
            aria-modal={artifactsModal ? true : undefined}
            aria-labelledby="drawer-title"
            tabIndex={artifactsModal ? -1 : undefined}
          >
            <div className="drawer-header">
              <div className="drawer-title" id="drawer-title">
                <BookOpen size={17} />
                <span>Artefatos</span>
              </div>
              <button
                ref={artifactsCloseBtnRef}
                className="icon-btn"
                onClick={() => {
                  setArtifactsOpen(false)
                  artifactsToggleBtnRef.current?.focus()
                }}
                aria-label="Ocultar painel de artefatos"
              >
                <X size={16} />
              </button>
            </div>

            <div className="drawer-tabs" role="tablist" aria-label="Abas de artefatos da pesquisa">
              <button
                role="tab"
                id="tab-plan"
                aria-controls="panel-plan"
                aria-selected={activeTab === 'plan'}
                tabIndex={activeTab === 'plan' ? 0 : -1}
                className={'tab-btn ' + (activeTab === 'plan' ? 'active' : '')}
                onClick={() => setActiveTab('plan')}
                onKeyDown={e => handleTabKeyDown(e, 'plan')}
              >
                Plano
              </button>
              <button
                role="tab"
                id="tab-evidence"
                aria-controls="panel-evidence"
                aria-selected={activeTab === 'evidence'}
                tabIndex={activeTab === 'evidence' ? 0 : -1}
                className={'tab-btn ' + (activeTab === 'evidence' ? 'active' : '')}
                onClick={() => setActiveTab('evidence')}
                onKeyDown={e => handleTabKeyDown(e, 'evidence')}
              >
                Evidências ({events.filter(e => e.type.includes('worker') || e.type.includes('audit')).length})
              </button>
              <button
                role="tab"
                id="tab-report"
                aria-controls="panel-report"
                aria-selected={activeTab === 'report'}
                tabIndex={activeTab === 'report' ? 0 : -1}
                className={'tab-btn ' + (activeTab === 'report' ? 'active' : '')}
                onClick={() => setActiveTab('report')}
                onKeyDown={e => handleTabKeyDown(e, 'report')}
              >
                Relatório {reportData ? '✓' : ''}
              </button>
            </div>

          <div className="drawer-content">
            {activeTab === 'plan' && (
              <div role="tabpanel" id="panel-plan" aria-labelledby="tab-plan" tabIndex={0} className="plan-artifact">
                <h4>Plano de 5 Pontos</h4>
                <div className="points-summary">
                  {points.map((p, i) => (
                    <div className="summary-point" key={i}>
                      <span className="point-num">{i + 1}</span>
                      <div>
                        <strong>{p.title}</strong>
                        <p>{p.description}</p>
                        <div className="point-tags">
                          <span className="tag">{p.is_parallelizable ? 'Paralelo' : 'Sequencial'}</span>
                          {(p.dependencies || []).length > 0 && (
                            <span className="tag dep">Depende de: {p.dependencies.join(', ')}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  {!points.length && <p className="quiet">Aguardando geração do plano pelo Scout…</p>}
                </div>
              </div>
            )}

            {activeTab === 'evidence' && (
              <div role="tabpanel" id="panel-evidence" aria-labelledby="tab-evidence" tabIndex={0} className="evidence-artifact">
                <h4>Verificações e Auditoria</h4>
                <div className="evidence-list">
                  {events
                    .filter(e =>
                      ['worker_started', 'verdict_rendered', 'synthesis_completed'].includes(e.type),
                    )
                    .map(ev => (
                      <div className="evidence-item" key={ev.id}>
                        <strong>{roleName[ev.persona] || ev.persona}</strong>
                        <p>{ev.summary}</p>
                        {ev.metrics && (
                          <div className="metrics-row">
                            {Object.entries(ev.metrics).map(([k, v]) => (
                              <span key={k} className="metric-pill">
                                {k}: {v}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  {!events.length && <p className="quiet">Nenhuma evidência coletada ainda.</p>}
                </div>
              </div>
            )}

            {activeTab === 'report' && (
              <div role="tabpanel" id="panel-report" aria-labelledby="tab-report" tabIndex={0} className="report-artifact">
                <div className="report-artifact-header">
                  <h4>Relatório Final</h4>
                  <div className="report-actions">
                    <button
                      className="icon-btn-text"
                      onClick={() => {
                        if (reportData?.content_markdown) {
                          navigator.clipboard
                            .writeText(reportData.content_markdown)
                            .then(() => setNotice('Relatório copiado para a área de transferência!'))
                            .catch(err =>
                              setError('Falha ao copiar para a área de transferência: ' + (err?.message || 'Permissão negada')),
                            )
                        }
                      }}
                      disabled={!reportData?.content_markdown}
                      title="Copiar Markdown"
                    >
                      <Clipboard size={14} /> Copiar
                    </button>
                    <button
                      className="icon-btn-text"
                      onClick={exportReport}
                      disabled={!reportData?.content_markdown}
                      title="Exportar .md"
                    >
                      <Download size={14} /> Exportar
                    </button>
                  </div>
                </div>

                {/* AUDIT BADGES (CRITERIA A6, F-10) */}
                {reportData && (
                  <div className="audit-badges-bar">
                    <span className={'audit-pill ' + (isBlocked ? 'warning' : 'success')}>
                      {isBlocked ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />}
                      {isBlocked ? 'Auditado com Ressalvas' : 'Fontes e Evidências Auditadas'}
                    </span>
                    {typeof reportData.citation_metrics?.source_urls_cited === 'number' && (
                      <span className="audit-pill indigo">
                        <Search size={13} />
                        {reportData.citation_metrics.source_urls_cited} fontes citadas
                      </span>
                    )}
                    {typeof reportData.citation_metrics?.evidence_records === 'number' && (
                      <span className="audit-pill indigo">
                        <Layers3 size={13} />
                        {reportData.citation_metrics.evidence_records} evidências
                      </span>
                    )}
                  </div>
                )}

                {/* CALLBACK STATUS IN REPORT TAB (F-03) */}
                {hasCallback && (
                  <div
                    className={
                      'callback-status-card ' +
                      (isCallbackFailed
                        ? 'failed'
                        : isCallbackDelivered
                        ? 'delivered'
                        : '')
                    }
                  >
                    <span>
                      {isCallbackFailed
                        ? 'Falha no callback webhook'
                        : isCallbackDelivered
                        ? 'Callback entregue'
                        : 'Webhook de callback configurado'}
                    </span>
                    {isCallbackFailed && (
                      <button
                        type="button"
                        className="secondary btn-retry-callback"
                        disabled={retryingCallback}
                        onClick={handleRetryCallback}
                        title="Acionar POST /api/reports/{id}/retry-callback"
                      >
                        {retryingCallback ? (
                          <LoaderCircle size={11} className="spin" />
                        ) : (
                          <RefreshCw size={11} />
                        )}
                        Reenviar
                      </button>
                    )}
                  </div>
                )}

                {reportData?.audit_findings?.points && reportData.audit_findings.points.length > 0 && (
                  <div className="audit-findings-summary">
                    <div className="findings-title">Auditoria por ponto de investigação:</div>
                    <div className="findings-chips">
                      {reportData.audit_findings.points.map((pt, pIdx) => {
                        const isApproved =
                          pt.status === 'approved' ||
                          pt.verdict === 'APPROVED' ||
                          pt.audit?.llm?.approved === true
                        return (
                          <span
                            key={pIdx}
                            className={'finding-chip ' + (isApproved ? 'approved' : 'retry')}
                            title={pt.reason || undefined}
                          >
                            {pt.point ? (typeof pt.point === 'string' ? pt.point : `Ponto ${pt.point}`) : `Ponto ${(pt.position ?? pIdx) + 1}`}: {isApproved ? 'Aprovado' : pt.verdict || pt.status || 'Com ressalvas'}
                            {pt.reason ? ` — ${pt.reason}` : ''}
                          </span>
                        )
                      })}
                    </div>

                    {/* DETAILED CITATION & AUDIT EVIDENCE (CRITERIA A6, MA-18) */}
                    {reportData.audit_findings.points.some(
                      pt => pt.audit?.deterministic?.unsupported?.length || pt.audit?.llm?.findings?.length,
                    ) && (
                      <div className="audit-details-accordion" style={{ marginTop: '12px', fontSize: '12px' }}>
                        {reportData.audit_findings.points.map((pt, pIdx) => {
                          const unsList = pt.audit?.deterministic?.unsupported || []
                          const findings = pt.audit?.llm?.findings || []
                          const uncertainties = pt.audit?.llm?.uncertainties || []
                          if (!unsList.length && !findings.length && !uncertainties.length) return null

                          return (
                            <div
                              key={pIdx}
                              className="audit-point-detail-card"
                              style={{
                                padding: '8px 10px',
                                background: 'var(--bg-surface)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: '6px',
                                marginBottom: '8px',
                              }}
                            >
                              <strong>
                                {pt.point ? (typeof pt.point === 'string' ? pt.point : `Ponto ${pt.point}`) : `Ponto ${(pt.position ?? pIdx) + 1}`}
                              </strong>
                              {pt.audit?.deterministic?.supported ? (
                                <p style={{ margin: '4px 0', color: 'var(--status-emerald)' }}>
                                  ✓ {pt.audit.deterministic.supported} fontes com citação confirmada
                                </p>
                              ) : null}
                              {unsList.length > 0 && (
                                <div style={{ marginTop: '6px' }}>
                                  <span style={{ color: 'var(--status-amber)', fontWeight: 500 }}>
                                    Ressalvas de citação ({unsList.length}):
                                  </span>
                                  {unsList.map((uns, uIdx) => (
                                    <div
                                      key={uIdx}
                                      style={{
                                        marginTop: '4px',
                                        paddingLeft: '8px',
                                        borderLeft: '2px solid var(--status-amber)',
                                      }}
                                    >
                                      {uns.url && (
                                        <a
                                          href={uns.url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="report-source-link"
                                          style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                                        >
                                          <ExternalLink size={11} /> {uns.url}
                                        </a>
                                      )}
                                      {uns.claim && (
                                        <p style={{ margin: '2px 0' }}>
                                          <strong>Alegação:</strong> {uns.claim}
                                        </p>
                                      )}
                                      {uns.excerpt && (
                                        <p style={{ margin: '2px 0', fontStyle: 'italic', color: 'var(--text-tertiary)' }}>
                                          "{uns.excerpt}"
                                        </p>
                                      )}
                                      {uns.reason && (
                                        <p style={{ margin: '2px 0', color: 'var(--text-quaternary)', fontSize: '11px' }}>
                                          {uns.reason}
                                        </p>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {uncertainties.length > 0 && (
                                <div style={{ marginTop: '6px' }}>
                                  <span style={{ color: 'var(--text-tertiary)', fontWeight: 500 }}>
                                    Incertezas identificadas:
                                  </span>
                                  <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                                    {uncertainties.map((unc, uncIdx) => (
                                      <li key={uncIdx}>{unc}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )}

                {reportData?.content_markdown ? (
                  <div className="markdown-render">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ node: _node, ...props }) => (
                          <a
                            {...props}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="report-source-link"
                          />
                        ),
                      }}
                    >
                      {reportData.content_markdown}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="waiting-report">
                    <FileText size={32} className="faint-icon" />
                    <p>
                      {research.status === 'failed'
                        ? 'A pesquisa falhou antes da geração do relatório.'
                        : 'O relatório será sintetizado após a aprovação de todos os pontos pelo auditor.'}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
        <div
          className="scrim artifacts-scrim"
          onClick={() => {
            setArtifactsOpen(false)
            artifactsToggleBtnRef.current?.focus()
          }}
          aria-hidden="true"
        />
      </>
      )}
    </div>
  )
}

// ----------------------------------------------------
// SETTINGS PAGE COMPONENT (A7, F1, F2, F3)
// ----------------------------------------------------
function SettingsPage() {
  const { setError, setNotice } = useApp()
  const [config, setConfig] = useState<Settings | null>(null)
  const [loadingSettings, setLoadingSettings] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [newKeys, setNewKeys] = useState<Record<string, string>>({})
  const [models, setModels] = useState<Record<string, string>>({})
  const [callbackUrl, setCallbackUrl] = useState('')
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState('')
  const [jinaBaseUrl, setJinaBaseUrl] = useState('')
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({})
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({})
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState('')
  const [busy, setBusy] = useState(false)

  const loadSettings = async () => {
    setLoadingSettings(true)
    setLoadError('')
    try {
      const data = await api<Settings>('/api/settings')
      setConfig(data)
      setModels(Object.fromEntries(Object.entries(data.models).map(([k, v]) => [k, v || ''])))
      setCallbackUrl(data.callback_url || '')
      setOpenaiBaseUrl(data.openai_base_url || '')
      setJinaBaseUrl(data.jina_base_url || '')
      loadDynamicModels()
    } catch (e) {
      const msg = (e as Error).message
      setLoadError(msg)
      setError(msg)
    } finally {
      setLoadingSettings(false)
    }
  }

  const loadDynamicModels = async () => {
    setCatalogLoading(true)
    setCatalogError('')
    try {
      const res = await api<{ models_by_provider: Record<string, string[]> }>('/api/settings/models')
      if (res?.models_by_provider) {
        setAvailableModels(prev => ({ ...prev, ...res.models_by_provider }))
      }
    } catch (e) {
      setCatalogError((e as Error).message)
    } finally {
      setCatalogLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const testKey = async (provider: string) => {
    const keyToTest = (newKeys[provider] || '').trim()
    if (!keyToTest) {
      setTestResults(prev => ({
        ...prev,
        [provider]: { success: false, message: 'Insira uma chave no campo antes de testar.' },
      }))
      return
    }
    setTestingProvider(provider)
    try {
      const res = await api<{ success: boolean; message: string; models?: string[] }>('/api/settings/test', {
        method: 'POST',
        body: JSON.stringify({
          provider,
          api_key: keyToTest,
          base_url: provider === 'openai' ? openaiBaseUrl.trim() || null : null,
        }),
      })
      setTestResults(prev => ({ ...prev, [provider]: res }))
      if (res.success) {
        if (Array.isArray(res.models) && res.models.length > 0) {
          setAvailableModels(prev => ({ ...prev, [provider]: res.models || [] }))
        } else {
          await loadDynamicModels()
        }
      }
    } catch (e) {
      setTestResults(prev => ({
        ...prev,
        [provider]: { success: false, message: (e as Error).message },
      }))
    } finally {
      setTestingProvider(null)
    }
  }

  async function saveSettings(event: React.FormEvent) {
    event.preventDefault()
    if (!config || loadingSettings) {
      setError('Aguarde o carregamento das configurações do servidor antes de salvar.')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const payload = buildSettingsPayload(newKeys, models, callbackUrl, openaiBaseUrl, jinaBaseUrl)
      await api('/api/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setNewKeys({})
      setNotice('Configurações e credenciais salvas com sucesso!')
      await loadSettings()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (loadingSettings && !config) {
    return (
      <div className="settings-page">
        <div className="page-intro">
          <p className="eyebrow">SISTEMA / CONFIGURAÇÕES</p>
          <h1>Motor de inferência & Provedores<span>.</span></h1>
        </div>
        <div className="loading" style={{ height: '40vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <LoaderCircle className="spin" size={28} />
          <p style={{ marginTop: '14px', color: 'var(--text-secondary)' }}>Carregando configurações do servidor…</p>
        </div>
      </div>
    )
  }

  if (loadError && !config) {
    return (
      <div className="settings-page">
        <div className="page-intro">
          <p className="eyebrow">SISTEMA / CONFIGURAÇÕES</p>
          <h1>Motor de inferência & Provedores<span>.</span></h1>
        </div>
        <div className="agent-card error-card" role="alert" style={{ maxWidth: '600px', margin: '40px auto' }}>
          <CircleHelp size={24} />
          <div>
            <strong>Falha ao carregar configurações</strong>
            <p>
              Não foi possível carregar as configurações do servidor ({loadError}). O formulário foi bloqueado para proteger e preservar suas credenciais e URLs salvas.
            </p>
            <div style={{ marginTop: '14px' }}>
              <button type="button" className="primary" onClick={loadSettings}>
                <RefreshCw size={14} /> Tentar novamente
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="settings-page">
      <div className="page-intro">
        <p className="eyebrow">SISTEMA / CONFIGURAÇÕES</p>
        <h1>
          Motor de inferência & Provedores<span>.</span>
        </h1>
        <p>
          Configure chaves de API, teste conexões em tempo real, selecione modelos dinâmicos por agente e
          defina endpoints compatíveis. As chaves são criptografadas com AES-256-GCM e nunca retornam ao cliente.
        </p>
      </div>

      <form onSubmit={saveSettings} className="settings-form">
        {/* SECTION: PROVIDER KEYS & TESTING */}
        <section className="settings-section">
          <div className="section-meta">
            <div className="section-icon">
              <KeyRound size={20} />
            </div>
            <h2>Chaves de Provedores</h2>
            <p>
              Teste sua chave antes de salvar para garantir que as permissões e o saldo estejam ativos no provedor.
            </p>
          </div>

          <div className="settings-fields">
            {providers.map(provider => {
              const isConfigured = config?.provider_configured?.[provider]
              const testState = testResults[provider]
              const isTesting = testingProvider === provider

              return (
                <div className="setting-card" key={provider}>
                  <div className="setting-header">
                    <div className="provider-info">
                      <strong>
                        {provider === 'serpapi'
                          ? 'SerpAPI'
                          : provider === 'litellm'
                          ? 'LiteLLM Gateway'
                          : provider.charAt(0).toUpperCase() + provider.slice(1)}
                      </strong>
                      <span className={'badge ' + (newKeys[provider] === '' ? 'not-configured' : isConfigured ? 'configured' : 'not-configured')}>
                        {newKeys[provider] === ''
                          ? 'Marcada para remoção'
                          : isConfigured
                          ? 'Ativo no banco'
                          : provider === 'jina'
                          ? 'Opcional (fallback público)'
                          : 'Não configurado'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {isConfigured && newKeys[provider] !== '' && (
                        <button
                          type="button"
                          className="secondary btn-remove-key"
                          onClick={() => {
                            setNewKeys(old => ({ ...old, [provider]: '' }))
                            setNotice(`Chave de ${provider} marcada para remoção. Clique em Salvar configurações para confirmar.`)
                          }}
                          title="Remover chave salva deste provedor"
                        >
                          Remover
                        </button>
                      )}
                      <button
                        type="button"
                        className="secondary btn-test"
                        disabled={isTesting}
                        onClick={() => testKey(provider)}
                      >
                        {isTesting ? (
                          <>
                            <LoaderCircle size={14} className="spin" /> Testando…
                          </>
                        ) : (
                          'Testar chave'
                        )}
                      </button>
                    </div>
                  </div>

                  <input
                    type="password"
                    autoComplete="off"
                    value={newKeys[provider] || ''}
                    onChange={e => setNewKeys(old => ({ ...old, [provider]: e.target.value }))}
                    placeholder={isConfigured ? '•••••••••••••••• · alterar chave' : 'Inserir chave secreta'}
                    aria-label={'Chave ' + provider}
                  />

                  {testState && (
                    <div className={'test-feedback ' + (testState.success ? 'success' : 'failure')}>
                      {testState.success ? <Check size={14} /> : <CircleHelp size={14} />}
                      <span>{testState.message}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>

        {/* SECTION: OPENAI BASE URL & WEBHOOK */}
        <section className="settings-section">
          <div className="section-meta">
            <div className="section-icon">
              <ExternalLink size={20} />
            </div>
            <h2>Endpoints & Webhooks</h2>
            <p>
              Defina endpoints personalizados (OpenAI-compatible, proxy Jina) e a URL global de callback.
            </p>
          </div>

          <div className="settings-fields">
            <div className="setting-card">
              <label htmlFor="openai-base-url">
                <strong>OpenAI Compatible Base URL (Opcional)</strong>
                <small>Ex: https://openrouter.ai/api/v1 ou http://localhost:11434/v1</small>
              </label>
              <input
                id="openai-base-url"
                type="url"
                value={openaiBaseUrl}
                onChange={e => setOpenaiBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1"
              />
            </div>

            <div className="setting-card">
              <label htmlFor="jina-base-url">
                <strong>Proxy Jina via Cloudflare Worker (Opcional)</strong>
                <small>Ex: https://meu-worker.workers.dev — envia Authorization: Bearer com a chave Jina quando configurada.</small>
              </label>
              <input
                id="jina-base-url"
                type="url"
                value={jinaBaseUrl}
                onChange={e => setJinaBaseUrl(e.target.value)}
                placeholder="https://r.jina.ai"
              />
            </div>

            <div className="setting-card">
              <label htmlFor="callback-url">
                <strong>Webhook de Callback Global (Opcional)</strong>
                <small>Ao concluir a pesquisa, o relatório final é despachado via POST HTTP para esta URL.</small>
              </label>
              <input
                id="callback-url"
                type="url"
                value={callbackUrl}
                onChange={e => setCallbackUrl(e.target.value)}
                placeholder="https://meuservico.com/webhook/deep-research"
              />
            </div>
          </div>
        </section>

        {/* SECTION: DYNAMIC MODEL ASSIGNMENT */}
        <section className="settings-section">
          <div className="section-meta">
            <div className="section-icon">
              <Database size={20} />
            </div>
            <h2>Modelos por Especialidade</h2>
            <p>
              Atribua modelos de inferência a cada agente. A lista de modelos é descoberta dinamicamente pelo catálogo dos provedores.
            </p>
          </div>

          <div className="settings-fields">
            {catalogError && (
              <div className="test-feedback failure" role="alert" style={{ marginBottom: '14px', width: '100%', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CircleHelp size={14} />
                <span>Erro ao carregar catálogo de modelos: {catalogError}</span>
                <button
                  type="button"
                  className="secondary"
                  style={{ marginLeft: 'auto', padding: '3px 8px', fontSize: '11px' }}
                  onClick={loadDynamicModels}
                  disabled={catalogLoading}
                >
                  {catalogLoading ? <LoaderCircle size={12} className="spin" /> : <RefreshCw size={12} />}
                  Tentar novamente
                </button>
              </div>
            )}
            {roles.map(role => {
              const currentModel = models[role] || ''
              const modelOptions = getModelOptions(availableModels, currentModel)

              return (
                <div className="setting-card model-card" key={role}>
                  <div className="model-label">
                    <strong>{roleName[role]}</strong>
                    <small>
                      {role === 'scout'
                        ? 'Exploração inicial e 5 pontos'
                        : role === 'auditor'
                        ? 'Auditoria de fatos e outline'
                        : role === 'writer'
                        ? 'Redação e síntese de relatório'
                        : 'Investigação especializada com viés'}
                    </small>
                  </div>

                  <div className="model-inputs">
                    <select
                      id={'model-select-' + role}
                      aria-label={'Modelo ' + roleName[role]}
                      value={currentModel}
                      disabled={modelOptions.length === 0}
                      onChange={e => {
                        const val = e.target.value
                        setModels(old => ({ ...old, [role]: val }))
                      }}
                    >
                      {!currentModel && <option value="">Selecione do catálogo…</option>}
                      {modelOptions.map(option => (
                        <option key={option.value} value={option.value}>
                          {option.value}{option.savedOnly ? ' (salvo atualmente · catálogo indisponível)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        <div className="settings-actions">
          <span className="vault-notice">
            <ShieldCheck size={16} /> Credenciais criptografadas em repouso
          </span>
          <button className="primary" disabled={busy || loadingSettings || !config}>
            {busy ? 'Salvando…' : 'Salvar configurações'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ----------------------------------------------------
// TANSTACK ROUTER SETUP
// ----------------------------------------------------
const { router } = createProductionRouteTree({
  Root: RootLayout,
  Home: HomePage,
  Research: ResearchPage,
  Settings: SettingsPage,
})

export { router }

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

// ----------------------------------------------------
// ERROR BOUNDARY
// ----------------------------------------------------
interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback: React.ReactNode
}
interface ErrorBoundaryState {
  hasError: boolean
}
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info)
  }
  render() {
    if (this.state.hasError) return this.props.fallback
    return this.props.children
  }
}

// ----------------------------------------------------
// APP PROVIDER & ROOT RENDER
// ----------------------------------------------------
function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [artifactsOpen, setArtifactsOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth > 1080
    }
    return true
  })
  const [mobileMenu, setMobileMenu] = useState(false)
  const [history, setHistory] = useState<Research[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  // Listen for auth-expired event
  useEffect(() => {
    const handleExpired = () => {
      clearSession()
      clearAllDrCache()
      setAuthenticated(false)
      setError('Sua sessão expirou. Por favor, autentique-se novamente.')
    }
    window.addEventListener('auth-expired', handleExpired)
    return () => window.removeEventListener('auth-expired', handleExpired)
  }, [])

  const refreshHistory = async () => {
    try {
      const data = await api<Research[]>('/api/research')
      setHistory(data)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  // Initial authentication check
  useEffect(() => {
    initializeSession()
      .then(() => setAuthenticated(true))
      .catch(() => {
        setHistory([])
        setAuthenticated(false)
      })
  }, [])

  useEffect(() => {
    if (authenticated) {
      refreshHistory()
    }
  }, [authenticated])

  async function login(password: string) {
    setBusy(true)
    setError('')
    try {
      const result = await api<{ authenticated: boolean; role: string; csrf_token: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ password }),
      })
      if (result?.csrf_token) {
        setCsrfToken(result.csrf_token)
      }
      setAuthenticated(true)
      await refreshHistory()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    setBusy(true)
    setError('')
    try {
      await logoutUser()
      clearAllDrCache()
      setAuthenticated(false)
      setHistory([])
      setMobileMenu(false)
    } catch (e) {
      setError('Falha ao revogar sessão no servidor: ' + (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppContext.Provider
      value={{
        authenticated,
        history,
        refreshHistory,
        sidebarOpen,
        setSidebarOpen,
        artifactsOpen,
        setArtifactsOpen,
        mobileMenu,
        setMobileMenu,
        error,
        setError,
        notice,
        setNotice,
        login,
        logout,
        busy,
      }}
    >
      <RouterProvider router={router} />
    </AppContext.Provider>
  )
}

if (typeof document !== 'undefined') {
  const rootEl = document.getElementById('root')
  if (rootEl) {
    createRoot(rootEl).render(
      <React.StrictMode>
        <ErrorBoundary
          fallback={
            <div className="error-state-card" role="alert">
              <h3>Algo falhou</h3>
              <p>Erro inesperado na interface. Recarregue a página ou volte ao painel.</p>
              <div className="error-actions">
                <button className="primary" onClick={() => window.location.reload()}>
                  Recarregar
                </button>
                <button className="secondary" onClick={() => (window.location.href = '/')}>
                  Voltar ao painel
                </button>
              </div>
            </div>
          }
        >
          <App />
        </ErrorBoundary>
      </React.StrictMode>,
    )
  }
}
