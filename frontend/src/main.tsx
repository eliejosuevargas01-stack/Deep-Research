import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import { ArrowLeft, ArrowRight, BookOpen, ChevronRight, CircleHelp, Clipboard, Database, FileText, KeyRound, Layers3, LoaderCircle, LogOut, Menu, Plus, Search, Settings2, ShieldCheck, Sparkles, X } from 'lucide-react'
import './style.css'

type Point = { title: string; description: string; dependencies: string[]; is_parallelizable: boolean }
type Research = { research_id: string; theme: string; status: string; briefing_draft?: { points?: Point[] }; points?: { title: string; status: string; audit?: unknown }[]; error?: string }
type Event = { id: number; persona: string; type: string; summary: string; metrics?: Record<string, number>; created_at: string }
type Settings = { provider_keys: Record<string, string | null>; provider_configured: Record<string, boolean>; models: Record<string, string | null> }
const roles = ['scout', 'historian', 'skeptic', 'pragmatist', 'futurist', 'auditor', 'writer'] as const
const providers = ['openai', 'anthropic', 'gemini', 'litellm', 'jina', 'serpapi', 'apify'] as const
const roleName: Record<string, string> = { scout: 'Scout', historian: 'Historiador', skeptic: 'Cético', pragmatist: 'Pragmático', futurist: 'Visionário', auditor: 'Auditor', writer: 'Redator', system: 'Sistema' }
let csrf = '' // Memory-only; no credential in localStorage, URL or bundle.

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (options.method && options.method !== 'GET' && csrf) headers.set('X-CSRF-Token', csrf)
  const response = await fetch(path, { ...options, credentials: 'same-origin', headers })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `HTTP ${response.status}`)
  }
  return response.status === 204 ? undefined as T : response.json()
}

function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [password, setPassword] = useState('')
  const [view, setView] = useState<'chat' | 'settings'>('chat')
  const [menu, setMenu] = useState(false)
  const [history, setHistory] = useState<Research[]>([])
  const [research, setResearch] = useState<Research | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [report, setReport] = useState('')
  const [topic, setTopic] = useState('')
  const [callbackUrl, setCallbackUrl] = useState('')
  const [points, setPoints] = useState<Point[]>([])
  const [config, setConfig] = useState<Settings | null>(null)
  const [newKeys, setNewKeys] = useState<Record<string, string>>({})
  const [models, setModels] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refreshHistory = () => api<Research[]>('/api/research').then(setHistory).catch((e: Error) => setError(e.message))
  const openResearch = (id: string) => {
    setView('chat'); setMenu(false); setEvents([]); setReport(''); setError('')
    api<Research>(`/api/research/${id}`).then(data => { setResearch(data); setPoints(data.briefing_draft?.points || []); if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) loadReport(id) }).catch((e: Error) => setError(e.message))
  }
  const loadReport = (id: string) => api<{ content_markdown: string }>(`/api/reports/${id}`).then(data => setReport(data.content_markdown)).catch((e: Error) => setError(e.message))
  const loadSettings = () => api<Settings>('/api/settings').then(data => { setConfig(data); setModels(Object.fromEntries(Object.entries(data.models).map(([key, value]) => [key, value || '']))) }).catch((e: Error) => setError(e.message))
  useEffect(() => {
    api('/api/auth/me').then(() => api<{ csrf_token: string }>('/api/auth/csrf')).then(result => { csrf = result.csrf_token; setAuthenticated(true) }).catch(() => setAuthenticated(false))
  }, [])
  useEffect(() => { if (authenticated) refreshHistory() }, [authenticated])
  useEffect(() => { if (authenticated && view === 'settings') loadSettings() }, [authenticated, view])
  useEffect(() => {
    if (!research || !authenticated) return
    const id = research.research_id
    const source = new EventSource(`/api/research/${id}/events`, { withCredentials: true })
    source.addEventListener('progress', message => {
      try {
        const event = JSON.parse((message as MessageEvent).data) as Event
        setEvents(old => old.some(item => item.id === event.id) ? old : [...old, event].sort((a, b) => a.id - b.id))
        if (['briefing_ready', 'research_failed', 'synthesis_completed', 'scout_failed'].includes(event.type)) {
          api<Research>(`/api/research/${id}`).then(data => { setResearch(data); setPoints(data.briefing_draft?.points || []); if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) loadReport(id) }).catch(() => {})
          refreshHistory()
        }
      } catch { setError('Evento de progresso inválido. Atualize pesquisa.') }
    })
    source.onerror = () => { /* EventSource reconnects with Last-Event-ID automatically. */ }
    return () => source.close()
  }, [research?.research_id, authenticated])
  useEffect(() => {
    if (!research || ['completed', 'completed_but_callback_failed', 'blocked', 'failed'].includes(research.status)) return
    const timer = window.setInterval(() => api<Research>(`/api/research/${research.research_id}`).then(data => {
      setResearch(data)
      if (data.status === 'pending_approval') setPoints(data.briefing_draft?.points || [])
      if (['completed', 'completed_but_callback_failed', 'blocked'].includes(data.status)) { loadReport(data.research_id); refreshHistory() }
    }).catch(() => {}), 4000)
    return () => window.clearInterval(timer)
  }, [research?.research_id, research?.status])

  async function login(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const result = await api<{ csrf_token: string }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) })
      csrf = result.csrf_token; setPassword(''); setAuthenticated(true)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST' }) } catch { /* Clear visible data even if session expired. */ }
    csrf = ''; setAuthenticated(false); setResearch(null); setConfig(null); setEvents([]); setReport(''); setHistory([]); setMenu(false)
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (topic.trim().length < 3) return
    setBusy(true); setError('')
    try { const item = await api<Research>('/api/research', { method: 'POST', body: JSON.stringify({ theme: topic.trim(), callback_url: callbackUrl.trim() || null }) }); setTopic(''); setCallbackUrl(''); openResearch(item.research_id); refreshHistory() }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function approve() {
    if (!research || points.some(p => p.title.trim().length < 3 || p.description.trim().length < 3)) { setError('Preencha título e descrição de cada ponto.'); return }
    setBusy(true); setError('')
    try { await api(`/api/research/${research.research_id}/briefing/approve`, { method: 'POST', body: JSON.stringify({ approved_points: points }) }); openResearch(research.research_id) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function saveSettings(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      await api('/api/settings', { method: 'PUT', body: JSON.stringify({ provider_keys: Object.fromEntries(Object.entries(newKeys).filter(([, value]) => value.trim())), models: Object.fromEntries(Object.entries(models).filter(([, value]) => value.trim())) }) })
      setNewKeys({}); await loadSettings()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  function editPoint(index: number, key: keyof Point, value: string) { setPoints(old => old.map((p, i) => i === index ? { ...p, [key]: value } : p)) }
  function movePoint(index: number, shift: number) { const next = [...points], target = index + shift; if (target < 0 || target >= next.length) return; [next[index], next[target]] = [next[target], next[index]]; setPoints(next.map(point => ({ ...point, dependencies: point.dependencies.map(ref => { const oldIndex = Number(ref) - 1; return Number.isInteger(oldIndex) && oldIndex >= 0 && oldIndex < points.length ? String(next.indexOf(points[oldIndex]) + 1) : ref }) }))) }

  if (authenticated === null) return <main className="loading"><LoaderCircle className="spin" aria-label="Verificando sessão" /></main>
  if (!authenticated) return <main className="login-screen"><div className="login-card"><div className="brand-mark"><Sparkles size={23}/></div><p className="eyebrow">RESEARCH INTELLIGENCE</p><h1>Entre no seu espaço<br/><span>de pesquisa.</span></h1><p className="muted">Um tema. Quatro perspectivas. Um relatório fundamentado.</p><form onSubmit={login}><label htmlFor="password">Senha de administrador</label><input id="password" type="password" autoComplete="current-password" required minLength={1} value={password} onChange={e => setPassword(e.target.value)} placeholder="Insira sua senha"/><button className="primary full" disabled={busy}>{busy ? 'Entrando…' : <>Entrar <ArrowRight size={16}/></>}</button></form>{error && <p role="alert" className="error">{error}</p>}</div></main>

  return <div className="shell">
    <aside className={`sidebar ${menu ? 'open' : ''}`} aria-label="Navegação principal">
      <div className="sidebar-head"><div className="brand-mark small"><Sparkles size={17}/></div><strong>Deep Research</strong><button className="mobile-close icon" aria-label="Fechar menu" onClick={() => setMenu(false)}><X size={18}/></button></div>
      <button className="new-button" onClick={() => { setResearch(null); setReport(''); setEvents([]); setView('chat'); setMenu(false); setError('') }}><Plus size={17}/> Nova pesquisa <span>⌘ N</span></button>
      <button className={`nav-item ${view === 'chat' ? 'selected' : ''}`} onClick={() => { setView('chat'); setMenu(false) }}><Layers3 size={16}/> Pesquisas</button>
      <div className="nav-caption">RECENTES <span>{history.length}</span></div>
      <div className="history">{history.map(item => <button key={item.research_id} className={`history-item ${research?.research_id === item.research_id ? 'active' : ''}`} onClick={() => openResearch(item.research_id)}><span className="history-dot" data-status={item.status}/><span>{item.theme}</span></button>)}{!history.length && <p className="quiet">Nenhuma pesquisa ainda.</p>}</div>
      <div className="sidebar-bottom"><button className={`nav-item ${view === 'settings' ? 'selected' : ''}`} onClick={() => { setView('settings'); setMenu(false); setError('') }}><Settings2 size={16}/> Configurações</button><button className="nav-item" onClick={logout}><LogOut size={16}/> Sair</button></div>
    </aside>
    {menu && <button aria-label="Fechar menu" className="scrim" onClick={() => setMenu(false)} />}
    <main className="workspace">
      <header className="topbar"><button className="mobile-open icon" aria-label="Abrir menu" onClick={() => setMenu(true)}><Menu size={20}/></button><div className="breadcrumbs">Deep Research <ChevronRight size={14}/> <span>{view === 'settings' ? 'Configurações' : research ? 'Pesquisa' : 'Nova pesquisa'}</span></div><div className="top-indicator"><span className="live-dot"/> Ambiente de pesquisa</div></header>
      {error && <div className="error-banner" role="alert"><CircleHelp size={18}/><span>{error}</span><button className="icon" aria-label="Fechar erro" onClick={() => setError('')}><X size={16}/></button></div>}
      {view === 'settings' ? <div className="settings-page"><div className="page-intro"><p className="eyebrow">WORKSPACE / CONFIGURAÇÕES</p><h1>Motor de pesquisa<span className="accent">.</span></h1><p>Conecte provedores e atribua modelo para cada função. Chaves ficam cifradas no servidor e nunca retornam ao navegador.</p></div><form onSubmit={saveSettings} className="settings-form"><section className="settings-section"><div><div className="section-icon"><KeyRound size={19}/></div><h2>Provedores</h2><p>Preencha somente chaves que deseja atualizar. Campos vazios preservam valores existentes.</p></div><div className="settings-fields">{providers.map(provider => <label className="setting-row" key={provider}><span className="setting-label"><strong>{provider === 'serpapi' ? 'SerpAPI' : provider === 'litellm' ? 'LiteLLM' : provider.charAt(0).toUpperCase() + provider.slice(1)}</strong><small>{config?.provider_configured?.[provider] ? 'Configurado' : provider === 'jina' ? 'Opcional · leitura pública' : 'Não configurado'}</small></span><input type="password" autoComplete="off" value={newKeys[provider] || ''} onChange={e => setNewKeys(old => ({ ...old, [provider]: e.target.value }))} placeholder={config?.provider_configured?.[provider] ? '•••••••• · substituir chave' : 'Adicionar chave'} aria-label={`Chave ${provider}`}/></label>)}</div></section><section className="settings-section"><div><div className="section-icon"><Database size={19}/></div><h2>Modelos por agente</h2><p>Use identificadores aceitos pelo provedor, como <code>openai/gpt-4.1-mini</code>. Mudanças afetam a próxima execução.</p></div><div className="settings-fields">{roles.map(role => <label className="setting-row" key={role}><span className="setting-label"><strong>{roleName[role]}</strong><small>{role === 'scout' ? 'Planejamento inicial' : role === 'auditor' ? 'Validação das evidências' : role === 'writer' ? 'Relatório final' : 'Investigação especializada'}</small></span><input type="text" value={models[role] || ''} onChange={e => setModels(old => ({ ...old, [role]: e.target.value }))} placeholder="provider/model-id" aria-label={`Modelo ${roleName[role]}`}/></label>)}</div></section><div className="settings-actions"><span><ShieldCheck size={16}/> Credenciais guardadas no banco cifrado</span><button className="primary" disabled={busy}>{busy ? 'Salvando…' : 'Salvar configurações'}</button></div></form></div> :
      !research ? <div className="home"><div className="hero"><div className="hero-icon"><Sparkles size={26}/></div><p className="eyebrow">INTELIGÊNCIA COM FONTES REAIS</p><h1>Vá além da<br/><span>primeira resposta.</span></h1><p>Explore qualquer tema sob quatro perspectivas. Você aprova o plano, nós cruzamos evidências e entregamos um relatório com fontes rastreáveis.</p></div><form className="composer" onSubmit={submit}><label htmlFor="topic" className="sr-only">Tema da pesquisa</label><textarea id="topic" value={topic} onChange={e => setTopic(e.target.value)} rows={3} minLength={3} maxLength={500} placeholder="O que você quer investigar profundamente?" onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }}/><label className="callback-field" htmlFor="callback-url">Webhook opcional <input id="callback-url" type="url" value={callbackUrl} onChange={e => setCallbackUrl(e.target.value)} placeholder="https://exemplo.com/webhook"/></label><div className="composer-foot"><span><Search size={14}/> Busca, análise e auditoria</span><button type="submit" className="primary" disabled={busy || topic.trim().length < 3}>{busy ? 'Iniciando…' : <>Iniciar pesquisa <ArrowRight size={16}/></>}</button></div></form><div className="how"><span><i>01</i> Defina tema</span><ChevronRight size={15}/><span><i>02</i> Aprove plano</span><ChevronRight size={15}/><span><i>03</i> Acompanhe evidências</span><ChevronRight size={15}/><span><i>04</i> Leia relatório</span></div></div> :
      <div className="research-page"><div className="research-header"><button className="back-link" onClick={() => { setResearch(null); setEvents([]); setReport('') }}><ArrowLeft size={15}/> Todas as pesquisas</button><div className="research-title"><div><p className="eyebrow">PESQUISA / {research.research_id.slice(0, 8).toUpperCase()}</p><h1>{research.theme}</h1></div><span className={`status-pill ${research.status}`}>{statusLabel(research.status)}</span></div><div className="timeline"><span className="current"><Search size={16}/> Scout</span><span className={research.status === 'pending_approval' ? 'current' : ''}><Clipboard size={16}/> Briefing</span><span className={['approved','in_progress'].includes(research.status) ? 'current' : ''}><Layers3 size={16}/> Pesquisa</span><span className={report ? 'current' : ''}><FileText size={16}/> Relatório</span></div></div><div className="research-body"><div className="conversation"><div className="message user-message"><div className="avatar user-avatar">V</div><div><p className="message-label">VOCÊ <span>· tema inicial</span></p><p>{research.theme}</p></div></div>{research.status === 'scouting' && <div className="stage-card"><LoaderCircle size={19} className="spin accent"/><div><strong>Scout está mapeando terreno</strong><p>Buscando fontes iniciais e construindo cinco pontos de investigação.</p></div></div>}{research.status === 'pending_approval' && <div className="brief-card"><div className="brief-head"><div className="assistant-avatar"><Sparkles size={17}/></div><div><p className="message-label">SCOUT <span>· rascunho inicial</span></p><h2>Plano de investigação</h2><p>Revise os cinco pontos. Esta é a única edição antes da pesquisa começar.</p></div></div><div className="point-list">{points.map((p, i) => <div className="point-editor" key={i}><div className="point-index">{String(i + 1).padStart(2, '0')}</div><div className="point-fields"><label htmlFor={`point-title-${i}`}>Ponto de pesquisa</label><input id={`point-title-${i}`} value={p.title} onChange={e => editPoint(i, 'title', e.target.value)}/><label htmlFor={`point-description-${i}`}>Escopo</label><textarea id={`point-description-${i}`} rows={2} value={p.description} onChange={e => editPoint(i, 'description', e.target.value)}/><label className="checkbox"><input type="checkbox" checked={p.is_parallelizable} onChange={e => setPoints(old => old.map((item, j) => j === i ? { ...item, is_parallelizable: e.target.checked } : item))}/> Pode ser pesquisado em paralelo</label></div><div className="reorder"><button type="button" aria-label={`Subir ponto ${i + 1}`} disabled={i === 0} onClick={() => movePoint(i, -1)}>↑</button><button type="button" aria-label={`Descer ponto ${i + 1}`} disabled={i === points.length - 1} onClick={() => movePoint(i, 1)}>↓</button></div></div>)}</div><div className="brief-actions"><small>Aprovação única · depois não é possível editar</small><button className="primary" disabled={busy || !points.length} onClick={approve}>{busy ? 'Aprovando…' : <>Aprovar e pesquisar <ArrowRight size={16}/></>}</button></div></div>}{research.status === 'failed' && <div className="stage-card failure"><CircleHelp size={19}/><div><strong>Pesquisa interrompida</strong><p>{research.error || 'Não foi possível completar pesquisa. Verifique provedores e tente nova pesquisa.'}</p></div></div>}{research.status === 'interrupted' && <div className="stage-card failure"><CircleHelp size={19}/><div><strong>Processo interrompido</strong><p>Inicie outra pesquisa ou revise configurações.</p></div></div>}{['approved','in_progress','completed','blocked'].includes(research.status) && <><div className="section-heading"><p className="eyebrow">INVESTIGAÇÃO EM ANDAMENTO</p><h2>Quatro lentes. Uma pergunta.</h2><p>Eventos públicos da pesquisa, sem raciocínio privado dos modelos.</p></div><div className="persona-grid">{(['historian','skeptic','pragmatist','futurist'] as const).map((role, index) => { const latest = [...events].reverse().find(event => event.persona === role); return <div className="persona" key={role}><div className="persona-top"><span className="persona-index">0{index + 1}</span><span className={`persona-state ${latest ? 'active' : ''}`}>{latest ? 'Ativo' : 'Aguardando'}</span></div><h3>{roleName[role]}</h3><p>{['Contexto, origens e evolução.','Contrapontos e limitações.','Casos reais e números.','Tendências e próximos passos.'][index]}</p><div className="persona-update">{latest?.summary || 'Aguardando evidências…'}</div></div> })}</div><div className="activity"><div className="activity-title"><h3>Diário de investigação</h3><span>{events.length} eventos</span></div>{events.length ? <ol>{events.map(event => <li key={event.id}><span className="event-point"/><div><strong>{roleName[event.persona] || event.persona}</strong><p>{event.summary}</p></div><time>{new Date(event.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</time></li>)}</ol> : <p className="quiet">Aguardando primeiros eventos.</p>}</div></>}{report && <section className="report"><div className="report-heading"><div><p className="eyebrow">DOCUMENTO FINAL</p><h2>Relatório de pesquisa</h2></div><button className="secondary" onClick={() => navigator.clipboard.writeText(report)}><Clipboard size={15}/> Copiar Markdown</button></div><div className="markdown"><ReactMarkdown>{report}</ReactMarkdown></div></section>}</div><aside className="context-panel"><div className="context-title"><BookOpen size={17}/> Sobre esta pesquisa</div><div className="context-line"><span>Estado</span><strong>{statusLabel(research.status)}</strong></div><div className="context-line"><span>Pontos</span><strong>{research.briefing_draft?.points?.length ?? 0}</strong></div><div className="context-line"><span>Eventos</span><strong>{events.length}</strong></div><div className="context-note"><ShieldCheck size={17}/><p>Relatório cita fontes coletadas. Alegações incertas devem permanecer identificadas; URL não garante verdade factual.</p></div></aside></div></div>}
      {view === 'chat' && research?.status === 'pending_approval' && <section className="brief-extras" aria-label="Estrutura do briefing">
        <h2>Dependências entre pontos</h2>
        <p>Marque pontos que precisam terminar antes de cada etapa. Numeração acompanha reordenação acima.</p>
        {points.map((point, index) => <fieldset key={index}><legend>{index + 1}. {point.title}</legend>
          {points.map((dependency, parent) => parent !== index && <label key={parent}>
            <input type="checkbox" checked={point.dependencies.includes(String(parent + 1))} onChange={event => setPoints(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, dependencies: event.target.checked ? [...item.dependencies, String(parent + 1)] : item.dependencies.filter(ref => ref !== String(parent + 1)) } : item))}/>
            {parent + 1}. {dependency.title}
          </label>)}
        </fieldset>)}
        <button className="secondary" type="button" disabled={points.length >= 10} onClick={() => setPoints(current => [...current, { title: `Novo ângulo ${current.length + 1}`, description: 'Descreva o escopo deste ângulo.', dependencies: [], is_parallelizable: true }])}><Plus size={15}/> Adicionar ângulo</button>
      </section>}
      {view === 'chat' && research?.status === 'completed_but_callback_failed' && <div className="callback-retry" role="status"><span>Relatório salvo; webhook não entregue.</span><button className="secondary" type="button" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { await api(`/api/reports/${research.research_id}/retry-callback`, { method: 'POST' }); openResearch(research.research_id) } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }}>Reenviar webhook</button></div>}
    </main>
  </div>
}
function statusLabel(value: string) { return ({ scouting: 'Scout ativo', pending_approval: 'Aguardando aprovação', approved: 'Aprovado', in_progress: 'Pesquisando', completed: 'Concluído', completed_but_callback_failed: 'Concluído · callback falhou', blocked: 'Com ressalvas', failed: 'Falhou', interrupted: 'Interrompido' } as Record<string, string>)[value] || value }

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
