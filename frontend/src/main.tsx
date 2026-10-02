import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
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
  FileText,
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
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import './style.css'

type Point = { title: string; description: string; dependencies: string[]; is_parallelizable: boolean }
type Research = {
  research_id: string
  theme: string
  status: string
  callback_url?: string | null
  briefing_draft?: { points?: Point[]; edit_note?: string; source?: string }
  points?: { id: string; title: string; status: string; attempt_count: number; audit?: unknown }[]
  error?: string
  created_at?: string
  updated_at?: string
}
type Event = {
  id: number
  persona: string
  type: string
  summary: string
  metrics?: Record<string, number>
  created_at: string
}
type Settings = {
  provider_keys: Record<string, string | null>
  provider_configured: Record<string, boolean>
  models: Record<string, string | null>
  callback_url?: string | null
  openai_base_url?: string | null
}

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

let csrf = ''
let sessionApiKey = 'session-admin'
let sessionJwt = 'session-jwt'

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET' && csrf) headers.set('X-CSRF-Token', csrf)
  const response = await fetch(path, { ...options, credentials: 'same-origin', headers })
  if (response.status === 401 || response.status === 403) {
    if (path !== '/api/auth/me' && path !== '/api/auth/login') {
      window.dispatchEvent(new CustomEvent('auth-expired'))
    }
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : 'HTTP ' + response.status)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [password, setPassword] = useState('')
  const [view, setView] = useState<'chat' | 'settings'>('chat')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [artifactsOpen, setArtifactsOpen] = useState(true)
  const [mobileMenu, setMobileMenu] = useState(false)
  const [history, setHistory] = useState<Research[]>([])
  const [research, setResearch] = useState<Research | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [report, setReport] = useState('')
  const [topic, setTopic] = useState('')
  const [points, setPoints] = useState<Point[]>([])
  const [editNote, setEditNote] = useState('')
  const [activeTab, setActiveTab] = useState<'plan' | 'evidence' | 'report'>('plan')

  // Settings state
  const [config, setConfig] = useState<Settings | null>(null)
  const [newKeys, setNewKeys] = useState<Record<string, string>>({})
  const [models, setModels] = useState<Record<string, string>>({})
  const [callbackUrl, setCallbackUrl] = useState('')
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState('')
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({})
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({})

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const chatBottomRef = useRef<HTMLDivElement>(null)

  // Listen for auth-expired
  useEffect(() => {
    const handleExpired = () => {
      setAuthenticated(false)
      setError('Sua sessão expirou. Por favor, autentique-se novamente.')
    }
    window.addEventListener('auth-expired', handleExpired)
    return () => window.removeEventListener('auth-expired', handleExpired)
  }, [])

  const refreshHistory = () =>
    api<Research[]>('/api/research')
      .then(setHistory)
      .catch((e: Error) => setError(e.message))

  const openResearch = (id: string) => {
    setView('chat')
    setMobileMenu(false)
    setEvents([])
    setReport('')
    setError('')
    setNotice('')
    setEditNote('')
    api<Research>('/api/research/' + id)
      .then(data => {
        setResearch(data)
        setPoints(data.briefing_draft?.points || [])
        if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) {
          loadReport(id)
          setActiveTab('report')
        } else if (data.status === 'pending_approval') {
          setActiveTab('plan')
        }
      })
      .catch((e: Error) => setError(e.message))
  }

  const loadReport = (id: string) =>
    api<{ content_markdown: string }>('/api/reports/' + id)
      .then(data => setReport(data.content_markdown))
      .catch((e: Error) => setError(e.message))

  const loadSettings = async () => {
    try {
      const data = await api<Settings>('/api/settings')
      setConfig(data)
      setModels(Object.fromEntries(Object.entries(data.models).map(([key, value]) => [key, value || ''])))
      setCallbackUrl(data.callback_url || '')
      setOpenaiBaseUrl(data.openai_base_url || '')
      loadDynamicModels()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const loadDynamicModels = async () => {
    try {
      const res = await api<{ models_by_provider: Record<string, string[]> }>('/api/settings/models')
      if (res?.models_by_provider) {
        setAvailableModels(res.models_by_provider)
      }
    } catch {
      // Non-fatal
    }
  }

  const testKey = async (provider: string) => {
    const keyToTest = newKeys[provider] || ''
    if (!keyToTest && !config?.provider_configured?.[provider]) {
      setTestResults(prev => ({
        ...prev,
        [provider]: { success: false, message: 'Insira a chave antes de testar.' },
      }))
      return
    }
    setTestingProvider(provider)
    try {
      const res = await api<{ success: boolean; message: string }>('/api/settings/test', {
        method: 'POST',
        body: JSON.stringify({
          provider,
          api_key: keyToTest || 'configured-secret',
          base_url: provider === 'openai' ? openaiBaseUrl.trim() || null : null,
        }),
      })
      setTestResults(prev => ({ ...prev, [provider]: res }))
      if (res.success) {
        loadDynamicModels()
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

  // Initial authentication check
  useEffect(() => {
    api('/api/auth/me')
      .then(() => api<{ csrf_token: string; jwt_token?: string; api_key?: string }>('/api/auth/csrf'))
      .then(result => {
        csrf = result.csrf_token
        if (result.jwt_token) sessionJwt = result.jwt_token
        if (result.api_key) sessionApiKey = result.api_key
        setAuthenticated(true)
      })
      .catch(() => setAuthenticated(false))
  }, [])

  useEffect(() => {
    if (authenticated) refreshHistory()
  }, [authenticated])

  useEffect(() => {
    if (authenticated && view === 'settings') loadSettings()
  }, [authenticated, view])

  // SSE event streaming with deduplication
  useEffect(() => {
    if (!research || !authenticated) return
    const id = research.research_id
    const source = new EventSource('/api/research/' + id + '/events', { withCredentials: true })

    source.addEventListener('progress', message => {
      try {
        const event = JSON.parse((message as MessageEvent).data) as Event
        setEvents(old => {
          if (old.some(item => item.id === event.id)) return old
          return [...old, event].sort((a, b) => a.id - b.id)
        })

        if (
          ['briefing_ready', 'briefing_approved', 'research_failed', 'synthesis_completed', 'scout_failed'].includes(
            event.type,
          )
        ) {
          api<Research>('/api/research/' + id)
            .then(data => {
              setResearch(data)
              setPoints(data.briefing_draft?.points || [])
              if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) {
                loadReport(id)
                setActiveTab('report')
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
      // EventSource auto-reconnects with Last-Event-ID
    }

    return () => source.close()
  }, [research?.research_id, authenticated])

  // Periodic polling fallback
  useEffect(() => {
    if (!research || ['completed', 'completed_but_callback_failed', 'blocked', 'failed'].includes(research.status))
      return
    const timer = window.setInterval(() => {
      api<Research>('/api/research/' + research.research_id)
        .then(data => {
          setResearch(data)
          if (
            data.status === 'pending_approval' &&
            (!points.length || data.briefing_draft?.points?.length !== points.length)
          ) {
            setPoints(data.briefing_draft?.points || [])
          }
          if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) {
            loadReport(data.research_id)
            refreshHistory()
          }
        })
        .catch(() => {})
    }, 4000)
    return () => window.clearInterval(timer)
  }, [research?.research_id, research?.status])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events, research?.status])

  async function login(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api<{ csrf_token: string; jwt_token?: string; api_key?: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ password }),
      })
      csrf = result.csrf_token
      if (result.jwt_token) sessionJwt = result.jwt_token
      if (result.api_key) sessionApiKey = result.api_key
      setPassword('')
      setAuthenticated(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    try {
      await api('/api/auth/logout', { method: 'POST' })
    } catch {
      // Continue cleanup
    }
    csrf = ''
    setAuthenticated(false)
    setResearch(null)
    setConfig(null)
    setEvents([])
    setReport('')
    setHistory([])
    setMobileMenu(false)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (topic.trim().length < 3) return
    setBusy(true)
    setError('')
    try {
      // CRITERIA A: payload contains api_key, jwt_token, theme. Webhook is not sent here.
      const item = await api<Research>('/api/research', {
        method: 'POST',
        body: JSON.stringify({
          api_key: sessionApiKey,
          jwt_token: sessionJwt,
          theme: topic.trim(),
        }),
      })
      setTopic('')
      openResearch(item.research_id)
      refreshHistory()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function approve() {
    if (!research || points.some(p => p.title.trim().length < 3 || p.description.trim().length < 3)) {
      setError('Preencha o título e a descrição de cada ponto do briefing.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await api('/api/research/' + research.research_id + '/briefing/approve', {
        method: 'POST',
        body: JSON.stringify({ approved_points: points }),
      })
      openResearch(research.research_id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function sendAdjustments() {
    if (!research) return
    if (!editNote.trim()) {
      setError('Escreva uma nota detalhando os ajustes necessários para o scout refazer o plano.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await api('/api/research/' + research.research_id + '/briefing/edit', {
        method: 'POST',
        body: JSON.stringify({ note: editNote.trim(), points }),
      })
      setNotice('Ajustes enviados com sucesso! O Scout está refinando o plano e iniciará a pesquisa automaticamente.')
      openResearch(research.research_id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveSettings(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({
          provider_keys: Object.fromEntries(Object.entries(newKeys).filter(([, value]) => value.trim())),
          models: Object.fromEntries(Object.entries(models).filter(([, value]) => value.trim())),
          callback_url: callbackUrl.trim() || null,
          openai_base_url: openaiBaseUrl.trim() || null,
        }),
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

  function editPoint(index: number, key: keyof Point, value: any) {
    setPoints(old => old.map((p, i) => (i === index ? { ...p, [key]: value } : p)))
  }

  function movePoint(index: number, shift: number) {
    const next = [...points]
    const target = index + shift
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    setPoints(
      next.map(point => ({
        ...point,
        dependencies: point.dependencies.map(ref => {
          const oldIndex = Number(ref) - 1
          return Number.isInteger(oldIndex) && oldIndex >= 0 && oldIndex < points.length
            ? String(next.indexOf(points[oldIndex]) + 1)
            : ref
        }),
      })),
    )
  }

  const exportReport = () => {
    if (!report) return
    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'deep-research-' + (research?.theme.slice(0, 30).replace(/\s+/g, '-').toLowerCase() || 'report') + '.md'
    a.click()
    URL.revokeObjectURL(url)
  }

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
          <form onSubmit={login}>
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
          {error && <p role="alert" className="error">{error}</p>}
        </div>
      </main>
    )
  }

  return (
    <div className="shell">
      {/* AREA 1: LEFT SIDEBAR (COLLAPSIBLE) */}
      <aside
        className={'sidebar ' + (sidebarOpen ? 'open' : 'closed') + ' ' + (mobileMenu ? 'mobile-visible' : '')}
        aria-label="Navegação e pesquisas"
      >
        <div className="sidebar-head">
          <div className="brand-mark small">
            <Sparkles size={16} />
          </div>
          <strong>Deep Research</strong>
          <button
            className="icon-btn mobile-close"
            aria-label="Fechar menu móvel"
            onClick={() => setMobileMenu(false)}
          >
            <X size={18} />
          </button>
        </div>

        <button
          className="new-button"
          onClick={() => {
            setResearch(null)
            setReport('')
            setEvents([])
            setView('chat')
            setMobileMenu(false)
            setError('')
            setNotice('')
          }}
        >
          <Plus size={16} /> Nova pesquisa <span className="kbd">⌘N</span>
        </button>

        <button
          className={'nav-item ' + (view === 'chat' && !research ? 'selected' : '')}
          onClick={() => {
            setView('chat')
            setMobileMenu(false)
          }}
        >
          <Layers3 size={16} /> Conversas
        </button>

        <div className="nav-caption">
          RECENTES <span>{history.length}</span>
        </div>

        <div className="history">
          {history.map(item => (
            <button
              key={item.research_id}
              className={'history-item ' + (research?.research_id === item.research_id ? 'active' : '')}
              onClick={() => openResearch(item.research_id)}
            >
              <span className="history-dot" data-status={item.status} />
              <span>{item.theme}</span>
            </button>
          ))}
          {!history.length && <p className="quiet">Nenhuma pesquisa realizada ainda.</p>}
        </div>

        <div className="sidebar-bottom">
          <button
            className={'nav-item ' + (view === 'settings' ? 'selected' : '')}
            onClick={() => {
              setView('settings')
              setMobileMenu(false)
              setError('')
              setNotice('')
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

      {/* AREA 2: CENTRAL WORKSPACE / CHAT */}
      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-btn mobile-open"
              aria-label="Menu"
              onClick={() => setMobileMenu(true)}
            >
              <Menu size={18} />
            </button>
            <button
              className="icon-btn desktop-toggle"
              aria-label={sidebarOpen ? 'Recolher menu lateral' : 'Expandir menu lateral'}
              onClick={() => setSidebarOpen(s => !s)}
              title={sidebarOpen ? 'Recolher barra lateral' : 'Expandir barra lateral'}
            >
              {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
            </button>
            <div className="breadcrumbs">
              <span>Deep Research</span>
              <ChevronRight size={14} />
              <span className="current-crumb">
                {view === 'settings' ? 'Configurações' : research ? research.theme : 'Nova pesquisa'}
              </span>
            </div>
          </div>

          <div className="topbar-right">
            {research && (
              <span className={'status-pill ' + research.status}>
                {statusLabel(research.status)}
              </span>
            )}
            {view === 'chat' && research && (
              <button
                className={'icon-btn artifacts-toggle ' + (artifactsOpen ? 'active' : '')}
                aria-label={artifactsOpen ? 'Recolher painel de artefatos' : 'Abrir painel de artefatos'}
                onClick={() => setArtifactsOpen(a => !a)}
                title={artifactsOpen ? 'Ocultar artefatos' : 'Exibir artefatos'}
              >
                {artifactsOpen ? <PanelRightClose size={18} /> : <PanelRight size={18} />}
                <span className="toggle-label">Artefatos</span>
              </button>
            )}
          </div>
        </header>

        {error && (
          <div className="banner error-banner" role="alert">
            <CircleHelp size={18} />
            <span>{error}</span>
            <button className="icon-btn" onClick={() => setError('')}>
              <X size={16} />
            </button>
          </div>
        )}

        {notice && (
          <div className="banner notice-banner" role="status">
            <Check size={18} />
            <span>{notice}</span>
            <button className="icon-btn" onClick={() => setNotice('')}>
              <X size={16} />
            </button>
          </div>
        )}

        {/* SETTINGS VIEW */}
        {view === 'settings' ? (
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
                            <span className={'badge ' + (isConfigured ? 'configured' : 'not-configured')}>
                              {isConfigured ? 'Ativo no banco' : provider === 'jina' ? 'Opcional (fallback público)' : 'Não configurado'}
                            </span>
                          </div>
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
                    Defina um endpoint OpenAI-compatible personalizado (Ollama, vLLM, OpenRouter) e a URL global de callback.
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
                  {roles.map(role => {
                    const currentModel = models[role] || ''
                    // Collect options from availableModels
                    const options = Object.entries(availableModels).flatMap(([prov, mList]) =>
                      mList.map(m => (m.includes('/') ? m : prov + '/' + m)),
                    )

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
                          {options.length > 0 && (
                            <select
                              value={options.includes(currentModel) ? currentModel : ''}
                              onChange={e => {
                                if (e.target.value) {
                                  setModels(old => ({ ...old, [role]: e.target.value }))
                                }
                              }}
                            >
                              <option value="">Selecione do catálogo…</option>
                              {options.map(opt => (
                                <option key={opt} value={opt}>
                                  {opt}
                                </option>
                              ))}
                            </select>
                          )}
                          <input
                            type="text"
                            value={currentModel}
                            onChange={e => setModels(old => ({ ...old, [role]: e.target.value }))}
                            placeholder="openai/gpt-4o-mini ou gemini/gemini-1.5-flash"
                            aria-label={'Modelo ' + roleName[role]}
                          />
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
                <button className="primary" disabled={busy}>
                  {busy ? 'Salvando…' : 'Salvar configurações'}
                </button>
              </div>
            </form>
          </div>
        ) : !research ? (
          /* HOME CHAT VIEW */
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
                4 agentes investigam em paralelo com rigor acadêmico e auditoria factual.
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
                <button type="submit" className="primary" disabled={busy || topic.trim().length < 3}>
                  {busy ? (
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
                  <small>Citações reais rastreáveis</small>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ACTIVE RESEARCH WORKSPACE (3-COLUMN LAYOUT) */
          <div className={'research-workspace ' + (artifactsOpen ? 'with-artifacts' : 'full-center')}>
            {/* CENTER CONVERSATION */}
            <div className="conversation-pane">
              {/* RESEARCH TOP BAR */}
              <div className="research-banner">
                <button
                  className="back-btn"
                  onClick={() => {
                    setResearch(null)
                    setEvents([])
                    setReport('')
                  }}
                >
                  <ArrowLeft size={15} /> Nova conversa
                </button>
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
                        : ['completed', 'blocked'].includes(research.status)
                        ? 'passed'
                        : '')
                    }
                  >
                    <Layers3 size={13} /> 3. Investigação
                  </span>
                  <span className={'step-badge ' + (report ? 'passed' : '')}>
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
                            />
                            <textarea
                              className="point-desc-input"
                              rows={2}
                              value={p.description}
                              onChange={e => editPoint(i, 'description', e.target.value)}
                              placeholder="Descrição e escopo investigativo"
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
                            <button
                              type="button"
                              disabled={i === 0}
                              onClick={() => movePoint(i, -1)}
                              aria-label="Mover para cima"
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              disabled={i === points.length - 1}
                              onClick={() => movePoint(i, 1)}
                              aria-label="Mover para baixo"
                            >
                              ↓
                            </button>
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
                        onChange={e => setEditNote(e.target.value)}
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
                      <button
                        className="primary"
                        type="button"
                        disabled={busy || !points.length}
                        onClick={approve}
                      >
                        {busy ? 'Aprovando…' : <>Aprovar e iniciar pesquisa <ArrowRight size={16} /></>}
                      </button>
                    </div>
                  </div>
                )}

                {/* 4 SPECIALIST PERSONAS GRID */}
                {['approved', 'in_progress', 'completed', 'blocked'].includes(research.status) && (
                  <div className="personas-block">
                    <div className="block-header">
                      <h3>Quatro Personas Especialistas</h3>
                      <p>Execução paralela investigativa focada no viés cognitivo de cada agente.</p>
                    </div>

                    <div className="personas-cards">
                      {(['historian', 'skeptic', 'pragmatist', 'futurist'] as const).map((role, idx) => {
                        const personaEvents = events.filter(e => e.persona === role)
                        const latestEvent = personaEvents[personaEvents.length - 1]
                        const isDone = ['completed', 'blocked'].includes(research.status)

                        return (
                          <div className="persona-card" key={role}>
                            <div className="persona-header">
                              <span className="persona-num">0{idx + 1}</span>
                              <span
                                className={
                                  'persona-tag ' +
                                  (isDone ? 'done' : latestEvent ? 'active' : 'waiting')
                                }
                              >
                                {isDone ? 'Concluído' : latestEvent ? 'Pesquisando' : 'Aguardando'}
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
                              {latestEvent ? latestEvent.summary : 'Aguardando evidências…'}
                            </div>
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

                {research.status === 'failed' && (
                  <div className="agent-card error-card">
                    <CircleHelp size={20} />
                    <div>
                      <strong>A pesquisa foi interrompida</strong>
                      <p>{research.error || 'Verifique as chaves e modelos configurados na página de configurações.'}</p>
                    </div>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>
            </div>

            {/* AREA 3: RIGHT ARTIFACTS DRAWER (COLLAPSIBLE) */}
            {artifactsOpen && (
              <aside className="artifacts-drawer" aria-label="Artefatos da pesquisa">
                <div className="drawer-header">
                  <div className="drawer-title">
                    <BookOpen size={17} />
                    <span>Artefatos</span>
                  </div>
                  <button
                    className="icon-btn"
                    onClick={() => setArtifactsOpen(false)}
                    aria-label="Ocultar painel"
                  >
                    <X size={16} />
                  </button>
                </div>

                <div className="drawer-tabs">
                  <button
                    className={'tab-btn ' + (activeTab === 'plan' ? 'active' : '')}
                    onClick={() => setActiveTab('plan')}
                  >
                    Plano
                  </button>
                  <button
                    className={'tab-btn ' + (activeTab === 'evidence' ? 'active' : '')}
                    onClick={() => setActiveTab('evidence')}
                  >
                    Evidências ({events.filter(e => e.type.includes('worker') || e.type.includes('audit')).length})
                  </button>
                  <button
                    className={'tab-btn ' + (activeTab === 'report' ? 'active' : '')}
                    onClick={() => setActiveTab('report')}
                  >
                    Relatório {report ? '✓' : ''}
                  </button>
                </div>

                <div className="drawer-content">
                  {activeTab === 'plan' && (
                    <div className="plan-artifact">
                      <h4>Plano de 5 Pontos</h4>
                      <div className="points-summary">
                        {points.map((p, i) => (
                          <div className="summary-point" key={i}>
                            <span className="point-num">{i + 1}</span>
                            <div>
                              <strong>{p.title}</strong>
                              <p>{p.description}</p>
                              <div className="point-tags">
                                <span className="tag">
                                  {p.is_parallelizable ? 'Paralelo' : 'Sequencial'}
                                </span>
                                {p.dependencies.length > 0 && (
                                  <span className="tag dep">
                                    Depende de: {p.dependencies.join(', ')}
                                  </span>
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
                    <div className="evidence-artifact">
                      <h4>Verificações e Auditoria</h4>
                      <div className="evidence-list">
                        {events
                          .filter(e => ['worker_started', 'verdict_rendered', 'synthesis_completed'].includes(e.type))
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
                    <div className="report-artifact">
                      <div className="report-artifact-header">
                        <h4>Relatório Final</h4>
                        <div className="report-actions">
                          <button
                            className="icon-btn-text"
                            onClick={() => {
                              navigator.clipboard.writeText(report)
                              setNotice('Relatório copiado para a área de transferência!')
                            }}
                            disabled={!report}
                            title="Copiar Markdown"
                          >
                            <Clipboard size={14} /> Copiar
                          </button>
                          <button
                            className="icon-btn-text"
                            onClick={exportReport}
                            disabled={!report}
                            title="Exportar .md"
                          >
                            <Download size={14} /> Exportar
                          </button>
                        </div>
                      </div>

                      {report ? (
                        <div className="markdown-render">
                          <ReactMarkdown>{report}</ReactMarkdown>
                        </div>
                      ) : (
                        <div className="waiting-report">
                          <FileText size={32} className="faint-icon" />
                          <p>O relatório será sintetizado após a aprovação de todos os pontos pelo auditor.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </aside>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function statusLabel(status: string) {
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

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
