import React, { Suspense, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { HorizonBackground } from './components/HorizonBackground';
import { BottomDock } from './components/BottomDock';
import { MobileTabBar } from './components/MobileTabBar';
import { Composer, ComposerHandle } from './components/Composer';
import { EmptyState, TopicPills } from './components/EmptyState';
import { PlanningView } from './components/PlanningView';
import { PlanView } from './components/PlanView';
import { ExecutionView, PipelineStage } from './components/ExecutionView';
import { ErrorNotice } from './components/ErrorNotice';
// Dossiê e documentação carregam sob demanda: react-markdown e remark-gfm só
// entram no bundle quando a rota/estado precisa deles.
const ReportView = React.lazy(() =>
  import('./components/ReportView').then((m) => ({ default: m.ReportView }))
);
import { ContextSidebar } from './components/ContextSidebar';
import { HistoryView } from './components/HistoryView';
import { SettingsView, SettingsFormData, initialSettingsFormData } from './components/SettingsView';
const DocsView = React.lazy(() =>
  import('./components/DocsView').then((m) => ({ default: m.DocsView }))
);
import { ReasoningHarness } from './dev/ReasoningHarness';
import { ExecutionHarness, HARNESS_REPORT } from './dev/ExecutionHarness';
import { SimulatedResearch } from './dev/SimulatedResearch';
import { PlanHarness } from './dev/PlanHarness';
import { api, RIGOR_PADRAO, normalizarRigor, validarCallbackUrl } from './services/api';
import { historyService } from './services/history';
import { apresentarErro } from './utils/erros';
import { rotuloStatus } from './utils/texto';
import {
  AuditResponse,
  PipelineStatusResumo,
  PlanResponse,
  RecenciaPolitica,
  ResearchHistoryRecord,
  SearchResponse,
  WriterResponse,
} from './types/api';
import { usePipelineStream, formatPersonaTitle } from './hooks/usePipelineStream';
import { RefreshCw, RotateCcw } from 'lucide-react';

const ACTIVE_RESEARCH_KEY = 'deepResearch.activeResearchId';
const DRAFT_PLAN_KEY = 'deepResearch.draftPlan';
const THEME_KEY = 'deepResearch.theme';
const STAGE_POR_STATUS: Record<string, PipelineStage> = {
  buscando: 'searching',
  // 'coletado' é o estado gravado quando a varredura termina e a auditoria ainda não começou;
  // sem ele, recarregar a página nesse intervalo caía no workspace vazio.
  coletado: 'auditing',
  auditando: 'auditing',
  redigindo: 'writing',
  bloqueado: 'rejected',
};

export const App: React.FC = () => {
  // Roteamento simples por Hash (#research, #history, #settings, #docs)
  const [currentRoute, setCurrentRoute] = useState<string>('research');

  // Sessão integrada e preferências iniciais do backend
  const [sessionAuthenticated, setSessionAuthenticated] = useState<boolean>(false);
  const [sessionBootstrapError, setSessionBootstrapError] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState<boolean>(true);
  const userCustomizedPreferencesRef = useRef<boolean>(false);
  const bootstrapPromiseRef = useRef<Promise<boolean> | null>(null);
  const sessionStateRef = useRef<{ authenticated: boolean; error: string | null }>({
    authenticated: false,
    error: null,
  });

  // Preferências dinâmicas de pesquisa configuráveis via botão (+)
  const [nPontos, setNPontos] = useState<number>(1);
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([
    'historiador',
    'visionario',
    'cetico',
    'futurista',
  ]);
  const [isPreferencesOpen, setIsPreferencesOpen] = useState<boolean>(false);
  const [executionMode, setExecutionMode] = useState<'parallel' | 'sequential'>('parallel');
  const [recencia, setRecencia] = useState<RecenciaPolitica>('auto');
  const [criteriosMinimos, setCriteriosMinimos] = useState<number>(RIGOR_PADRAO);
  const [asyncExecute, setAsyncExecute] = useState<boolean>(false);
  const [callbackUrl, setCallbackUrl] = useState<string>('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('deepResearch.sidebar') === 'collapsed';
    } catch {
      return false;
    }
  });
  const [ambientOn, setAmbientOn] = useState<boolean>(() => {
    try {
      return localStorage.getItem('deepResearch.ambient') !== 'off';
    } catch {
      return true;
    }
  });
  const [tema, setTema] = useState<'light' | 'dark'>(() => {
    try {
      const salvo = localStorage.getItem(THEME_KEY);
      if (salvo === 'dark' || salvo === 'light') return salvo;
    } catch {
      /* storage indisponível: mantém o padrão claro */
    }
    // O produto nasce claro: escuro é escolha explícita do usuário no botão da navbar.
    // Seguir prefers-color-scheme pintava o app inteiro de escuro em quem usa o SO no escuro.
    return 'light';
  });

  const handleUserChangeExecutionMode = (modo: 'parallel' | 'sequential') => {
    userCustomizedPreferencesRef.current = true;
    setExecutionMode(modo);
  };

  const handleUserChangeNPontos = (n: number) => {
    userCustomizedPreferencesRef.current = true;
    setNPontos(n);
  };

  const handleUserChangePersonas = (personas: string[]) => {
    userCustomizedPreferencesRef.current = true;
    setSelectedPersonas(personas);
  };

  // Estado do compositor de tema
  // Rascunho: sem isso, um F5 (ou voltar do histórico) apagava o tema já
  // digitado. Fica só no navegador e é limpo quando o texto esvazia.
  const [composerValue, setComposerValue] = useState<string>(() => {
    try {
      return localStorage.getItem('deepResearch.draft') ?? '';
    } catch {
      return '';
    }
  });
  const [isPlanning, setIsPlanning] = useState(false);
  // Planejamento ao vivo: id gerado no cliente permite assinar o raciocínio antes da resposta.
  const [planningId, setPlanningId] = useState<string | null>(null);
  const [planningText, setPlanningText] = useState('');
  const [planningStartedAt, setPlanningStartedAt] = useState(0);
  const [planningError, setPlanningError] = useState<string | null>(null);
  const [storageError, setStorageError] = useState<string | null>(null);

  // Estado da pesquisa ativa
  const [currentPlan, setCurrentPlan] = useState<PlanResponse | null>(null);
  const [pipelineStage, setPipelineStage] = useState<PipelineStage>('idle');
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [auditResult, setAuditResult] = useState<AuditResponse | null>(null);
  const [auditCycleNumber, setAuditCycleNumber] = useState<number | null>(null);
  const [writerResult, setWriterResult] = useState<WriterResponse | null>(null);
  const [cycleNumber, setCycleNumber] = useState(1);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [failedStage, setFailedStage] = useState<'searching' | 'auditing' | 'writing' | null>(null);
  // Último estágio realmente ativo, usado quando o erro chega sem etapa explícita.
  const estagioAtualRef = useRef<'searching' | 'auditing' | 'writing' | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [isRailOpen, setIsRailOpen] = useState(() => {
    return typeof window !== 'undefined' ? window.innerWidth > 899 : true;
  });
  const [railMode, setRailMode] = useState<'contexto' | 'fontes'>('contexto');

  const handleToggleRail = (targetTab?: 'contexto' | 'fontes') => {
    if (targetTab) {
      setRailMode(targetTab);
      setIsRailOpen((prev) => (prev && railMode === targetTab ? false : true));
    } else {
      setIsRailOpen((prev) => !prev);
    }
  };

  // Rascunho em memória de configurações preservado entre navegações internas por hash
  const [settingsDraft, setSettingsDraft] = useState<SettingsFormData>(initialSettingsFormData);

  const handleDiscardSettingsDraft = () => {
    setSettingsDraft(initialSettingsFormData);
  };

  // Proteção do rascunho de configurações contra recarregamento/fechamento involuntário da aba
  const hasSettingsDraft = Object.values(settingsDraft).some((v) => v.trim().length > 0);
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasSettingsDraft) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasSettingsDraft]);

  // Lock de rolagem do body no mobile quando a folha de preferências estiver aberta (evita duplo scroll)
  useEffect(() => {
    if (!isPreferencesOpen) {
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      document.body.classList.remove('preferences-open');
      document.documentElement.classList.remove('preferences-open');
      return;
    }

    const updateScrollLock = () => {
      const isMobile = window.innerWidth <= 640 || (typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 640px)').matches);
      if (isMobile) {
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';
        document.body.classList.add('preferences-open');
        document.documentElement.classList.add('preferences-open');
      } else {
        document.body.style.overflow = '';
        document.documentElement.style.overflow = '';
        document.body.classList.remove('preferences-open');
        document.documentElement.classList.remove('preferences-open');
      }
    };

    updateScrollLock();
    window.addEventListener('resize', updateScrollLock);
    return () => {
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      document.body.classList.remove('preferences-open');
      document.documentElement.classList.remove('preferences-open');
      window.removeEventListener('resize', updateScrollLock);
    };
  }, [isPreferencesOpen]);

  // Histórico local do navegador
  const [historyRecords, setHistoryRecords] = useState<ResearchHistoryRecord[]>([]);
  // Pesquisa aberta no workspace (espelha activeResearchIdRef para a navegação lateral)
  const [activeResearchId, setActiveResearchId] = useState<string | null>(null);

  // Referências para foco e animação GSAP
  const workspaceRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<ComposerHandle>(null);
  // Identificador da pesquisa ativa para isolamento contra race conditions de navegação
  const activeResearchIdRef = useRef<string | null>(null);
  const isExecutingRef = useRef<boolean>(false);
  const isPlanningRef = useRef<boolean>(false);
  const executionTokenRef = useRef<number>(0);
  const activeExecutionTokenRef = useRef<number | null>(null);
  const currentRouteRef = useRef<string>(currentRoute);
  const rafScrollRef = useRef<number | null>(null);

  useEffect(() => {
    try {
      if (composerValue.trim()) localStorage.setItem('deepResearch.draft', composerValue);
      else localStorage.removeItem('deepResearch.draft');
    } catch {
      /* modo privado: seguir sem rascunho */
    }
  }, [composerValue]);

  useEffect(() => {
    currentRouteRef.current = currentRoute;
  }, [currentRoute]);

  // Título por rota: sem isso, histórico/configurações/documentação apareciam
  // todas como "Workspace de Investigação" na aba e no histórico do navegador.
  useEffect(() => {
    const titulos: Record<string, string> = {
      research: 'Pesquisa — Deep Research',
      history: 'Histórico — Deep Research',
      settings: 'Configurações — Deep Research',
      docs: 'Documentação — Deep Research',
    };
    document.title = titulos[currentRoute] ?? 'Deep Research';
  }, [currentRoute]);

  useEffect(() => {
    return () => {
      if (rafScrollRef.current !== null && typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(rafScrollRef.current);
        rafScrollRef.current = null;
      }
    };
  }, []);

  const isExecuting =
    pipelineStage === 'searching' ||
    pipelineStage === 'auditing' ||
    pipelineStage === 'writing' ||
    isExecutingRef.current;

  // Canal Server-Sent Events (SSE) e Reasoning em tempo real
  const {
    reasoningItems,
    addReasoningItem,
    upsertReasoningItem,
    clearReasoningItems,
    streamError,
    reconnect,
  } = usePipelineStream({
    // Com a aba recarregada o plano ainda não voltou, mas a pesquisa ativa já é
    // conhecida: sem este fallback o canal ficava mudo e a tela travava em "Planejado".
    idPesquisa: currentPlan?.id_pesquisa ?? activeResearchId ?? undefined,
    enabled: Boolean(currentPlan?.id_pesquisa && (isExecuting || pipelineStage !== 'idle')),
    onStatusChange: (status) => {
      if (status === 'buscando') setPipelineStage('searching');
      else if (status === 'auditando') setPipelineStage('auditing');
      else if (status === 'redigindo') setPipelineStage('writing');
      else if (status === 'concluido') setPipelineStage('completed');
      else if (status === 'reprovado') setPipelineStage('rejected');
      else if (status === 'falha') setPipelineStage('failed');
      if (currentPlan?.id_pesquisa) {
        const current = historyService.get(currentPlan.id_pesquisa);
        if (current) {
          const nextStatus = (status === 'buscando' || status === 'auditando' || status === 'redigindo') ? status : current.status;
          if (nextStatus !== current.status) {
            historyService.save({ ...current, status: nextStatus as any });
            setHistoryRecords(historyService.list());
          }
        }
      }
    },
    onReportFinal: (report) => {
      setWriterResult({
        id_pesquisa: report.id_pesquisa,
        tema: currentPlan?.tema || '',
        status: 'concluido',
        total_caracteres_dossier: report.total_caracteres,
        concluido_em: report.concluido_em,
        dossier_final: report.dossier_final,
      });
      setPipelineStage('completed');
    },
    onError: (err) => {
      setExecutionError(err);
      // Sem isto a linha de estágios não saberia qual etapa falhou e marcaria a
      // busca como concluída, escondendo o erro.
      setFailedStage((anterior) => anterior ?? estagioAtualRef.current);
      setPipelineStage('failed');
    },
    onAuditResult: (event: any) => {
      setAuditResult((prev: any) => {
        if (!prev) {
          const novo = {
            id_pesquisa: event.id_pesquisa,
            status_geral: event.status === 'aprovado' ? 'aprovado' : event.status === 'reprovado' ? 'reprovado' : 'pendente',
            aprovados: event.status === 'aprovado' ? 1 : 0,
            total_pontos: (currentPlan as any)?.total_pontos || (currentPlan as any)?.pontos?.length || 1,
            auditorias: [
              {
                ponto_id: event.ponto_id,
                ponto_n: event.ponto_n,
                status: event.status,
                pontuacao_percentual: event.pontuacao_percentual,
                criterios_aprovados: event.criterios_aprovados,
                criterios_minimos: null,
                pontos_fracos: event.pontos_fracos ?? null,
                reasoning_auditoria: event.reasoning_auditoria ?? null,
              },
            ],
          } as any;
          if (currentPlan) {
            const rec = historyService.get(currentPlan.id_pesquisa);
            if (rec) {
              historyService.save({ ...rec, auditResponse: novo, status: event.status === 'reprovado' ? 'reprovado' : rec.status });
              setHistoryRecords(historyService.list());
            }
          }
          setAuditCycleNumber((c) => c ?? 1);
          return novo;
        }
        const auditorias = Array.isArray(prev.auditorias) ? [...prev.auditorias] : [];
        const idx = auditorias.findIndex((a: any) => a.ponto_id === event.ponto_id);
        if (idx >= 0) {
          auditorias[idx] = {
            ...auditorias[idx],
            status: event.status,
            pontuacao_percentual: event.pontuacao_percentual,
            criterios_aprovados: event.criterios_aprovados,
            pontos_fracos: event.pontos_fracos ?? auditorias[idx].pontos_fracos ?? null,
            reasoning_auditoria: event.reasoning_auditoria ?? auditorias[idx].reasoning_auditoria ?? null,
          };
        } else {
          auditorias.push({
            ponto_id: event.ponto_id,
            ponto_n: event.ponto_n,
            status: event.status,
            pontuacao_percentual: event.pontuacao_percentual,
            criterios_aprovados: event.criterios_aprovados,
            criterios_minimos: null,
            pontos_fracos: event.pontos_fracos ?? null,
            reasoning_auditoria: event.reasoning_auditoria ?? null,
          });
        }
        const aprovados = auditorias.filter((a: any) => a.status === 'aprovado').length;
        const total_pontos = Math.max(prev.total_pontos || 0, auditorias.length, (currentPlan as any)?.total_pontos || (currentPlan as any)?.pontos?.length || 0);
        const next = {
          ...prev,
          auditorias,
          aprovados,
          total_pontos,
          status_geral: aprovados === total_pontos && total_pontos > 0 ? 'aprovado' : (auditorias.some((a: any) => a.status === 'reprovado') ? 'reprovado' : prev.status_geral),
        } as any;
        if (currentPlan) {
          const rec = historyService.get(currentPlan.id_pesquisa);
          if (rec) {
            historyService.save({ ...rec, auditResponse: next, status: next.status_geral === 'reprovado' ? 'reprovado' : rec.status });
            setHistoryRecords(historyService.list());
          }
        }
        setAuditCycleNumber((c) => c ?? 1);
        return next;
      });
    },
  });

  useEffect(() => {
    if (pipelineStage === 'searching' || pipelineStage === 'auditing' || pipelineStage === 'writing') {
      estagioAtualRef.current = pipelineStage;
    }
  }, [pipelineStage]);

  // Bootstrap inicial da sessão integrada via GET /app/session
  const bootstrapSession = async (): Promise<boolean> => {
    setIsBootstrapping(true);
    setSessionBootstrapError(null);
    try {
      const session = await api.getSession();
      setSessionAuthenticated(session.authenticated);
      sessionStateRef.current = {
        authenticated: session.authenticated,
        error: null,
      };
      // Aplica preferências do servidor apenas se o usuário ainda não tiver customizado manualmente
      if (session.preferences && !userCustomizedPreferencesRef.current) {
        if (typeof session.preferences.n_pontos === 'number' && session.preferences.n_pontos >= 1) {
          setNPontos(session.preferences.n_pontos);
        }
        if (Array.isArray(session.preferences.personas) && session.preferences.personas.length > 0) {
          setSelectedPersonas(session.preferences.personas);
        }
      }
      return session.authenticated;
    } catch (err: unknown) {
      // Falha genuína de conexão: registra erro recuperável com status limpo
      const msg = err instanceof Error ? err.message : String(err);
      console.warn('Bootstrap de sessão inicial:', msg);
      setSessionAuthenticated(false);
      setSessionBootstrapError(msg);
      sessionStateRef.current = {
        authenticated: false,
        error: msg,
      };
      return false;
    } finally {
      setIsBootstrapping(false);
    }
  };

  const handleRetryBootstrap = () => {
    bootstrapPromiseRef.current = bootstrapSession();
  };

  // Deep link `#research/<id>`: o servidor é a fonte da verdade. Reidrata plano,
  // pontos, dossiê e auditoria sem depender do histórico local deste navegador.
  const deepLinkCarregadoRef = useRef<string | null>(null);
  const handleOpenResearchById = useCallback(async (id: string) => {
    if (!id || deepLinkCarregadoRef.current === id) return;
    deepLinkCarregadoRef.current = id;
    try {
      // A sessão (cookie) nasce em /app/session; sem esperar, o deep link toma 401.
      await bootstrapPromiseRef.current;
      const detalhe = await api.getResearch(id);
      const pontos = (detalhe.pontos ?? []).map((p) => ({
        ponto_id: String(p.ponto_id),
        ponto_n: Number(p.ponto_n),
        ponto: String(p.ponto ?? ''),
        status: p.status ?? 'pendente',
        eixo_estruturado: p.eixo_estruturado ?? null,
      }));
      const plano: PlanResponse = {
        id_pesquisa: detalhe.id_pesquisa,
        tema: detalhe.tema,
        n_pontos: pontos.length,
        criado_em: detalhe.criado_em,
        pontos,
        status_pipeline: detalhe.status_pipeline,
        plano_estruturado: detalhe.plano_estruturado ?? null,
        preferencias: detalhe.preferencias ?? undefined,
      };
      const dossie = detalhe.dossier_final ?? null;
      const writer: WriterResponse | null = dossie
        ? {
            id_pesquisa: detalhe.id_pesquisa,
            tema: detalhe.tema,
            status: 'concluido',
            total_caracteres_dossier: dossie.length,
            concluido_em: detalhe.concluido_em ?? null,
            dossier_final: dossie,
            fontes: detalhe.fontes ?? null,
          }
        : null;
      const auditoria = (detalhe.auditoria ?? null) as AuditResponse | null;

      setCurrentPlan(plano);
      setWriterResult(writer);
      setAuditResult(auditoria);
      setExecutionError(null);
      activeResearchIdRef.current = id;
      setActiveResearchId(id);

      const status = detalhe.status_pipeline ?? '';
      const estagio: PipelineStage = writer
        ? 'completed'
        : STAGE_POR_STATUS[status] ??
          (status === 'concluido' ? 'completed' : status === 'falha' ? 'failed' : status === 'reprovado' ? 'rejected' : 'idle');
      setPipelineStage(estagio);
      setFailedStage(null);

      try {
        localStorage.setItem(ACTIVE_RESEARCH_KEY, id);
      } catch {
        /* storage bloqueado: a tela já está hidratada */
      }

      historyService.save({
        id_pesquisa: detalhe.id_pesquisa,
        tema: detalhe.tema,
        criado_em: detalhe.criado_em,
        concluido_em: detalhe.concluido_em ?? null,
        status: writer
          ? 'concluido'
          : status === 'reprovado'
            ? 'reprovado'
            : status === 'falha'
              ? 'falha'
              : 'buscando',
        total_pontos: pontos.length,
        planResponse: plano,
        writerResponse: writer ?? undefined,
        auditResponse: auditoria ?? undefined,
      });
      setHistoryRecords(historyService.list());
    } catch (erro) {
      deepLinkCarregadoRef.current = null;
      setCurrentPlan(null);
      setWriterResult(null);
      setExecutionError(
        `Não foi possível abrir a pesquisa ${id.slice(0, 8)}…: ${
          erro instanceof Error ? erro.message : 'pesquisa não encontrada no servidor.'
        }`
      );
      setPipelineStage('failed');
    }
  }, []);

  // Carrega histórico e inicializa sessão ao montar
  useEffect(() => {
    setHistoryRecords(historyService.list());
    historyService.setFalhaHandler(setStorageError);
    bootstrapPromiseRef.current = bootstrapSession();

    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '') || 'research';
      const rotas = ['research', 'history', 'settings', 'docs'];
      if (import.meta.env.DEV) rotas.push('harness', 'plan', 'planning', 'execution-search', 'execution-audit', 'execution-writing', 'report', 'execution-rejected', 'execution-failed', 'research-sim');

      // Deep link: #research/<id_pesquisa>
      if (hash.startsWith('research/')) {
        const id = hash.slice('research/'.length).trim();
        if (id) {
          setCurrentRoute('research');
          void handleOpenResearchById(id);
          return;
        }
      }

      if (rotas.includes(hash)) {
        setCurrentRoute(hash);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, [handleOpenResearchById]);

  // Raciocínio do Planejador ao vivo: assina o canal do id recém-criado antes de
  // `POST /plan` responder, para a tela intermediária nunca ficar vazia.
  useEffect(() => {
    if (!planningId) return;
    const fonte = new EventSource(`/api/v1/plan/${encodeURIComponent(planningId)}/stream`);
    const receber = (evento: MessageEvent) => {
      try {
        const dados = JSON.parse(evento.data) as { stage?: string; kind?: string; text?: string; agent?: string };
        if (dados.stage && dados.stage !== 'plan') return;
        if (typeof dados.text === 'string' && dados.text.length > 0) {
          setPlanningText((anterior) => anterior + dados.text);
        }
      } catch {
        /* frame inválido: ignora */
      }
    };
    fonte.addEventListener('agent.delta', receber);
    return () => {
      fonte.removeEventListener('agent.delta', receber);
      fonte.close();
    };
  }, [planningId]);

  // Retomada após recarregar: pergunta ao backend o status real da última pesquisa
  // e, se ela ainda estiver rodando, reata o acompanhamento sem disparar novo POST.
  useEffect(() => {
    let cancelado = false;
    const idAtivo = (() => {
      try {
        return localStorage.getItem(ACTIVE_RESEARCH_KEY);
      } catch {
        return null;
      }
    })();
    // Reabrir a pesquisa ativa não pode depender só do rascunho: em outra aba, em
    // outro dia ou com o rascunho limpo, o histórico local é a única fonte do plano.
    if (idAtivo) {
      const registro = historyService.get(idAtivo);
      if (registro?.planResponse) {
        setCurrentPlan(registro.planResponse);
        activeResearchIdRef.current = idAtivo;
        setActiveResearchId(idAtivo);
      }
    }
    if (!idAtivo) {
      try {
        const rascunho = sessionStorage.getItem(DRAFT_PLAN_KEY);
        if (rascunho) {
          const planoRascunho = JSON.parse(rascunho) as PlanResponse;
          setCurrentPlan(planoRascunho);
          if (planoRascunho?.id_pesquisa) {
            activeResearchIdRef.current = planoRascunho.id_pesquisa;
            setActiveResearchId(planoRascunho.id_pesquisa);
          }
        }
      } catch {
        /* rascunho inválido: ignora */
      }
      return;
    }

    (async () => {
      try {
        // O cookie de sessão é emitido por /app/session no mesmo instante do mount;
        // sem esta espera, a primeira consulta de status saía 401 e a retomada morria em silêncio.
        let resp = await fetch(`/api/v1/pipeline/${idAtivo}/status`, { credentials: 'same-origin' });
        for (let tentativa = 0; tentativa < 4 && resp.status === 401; tentativa++) {
          await new Promise((r) => setTimeout(r, 350));
          await fetch('/app/session', { credentials: 'same-origin' });
          resp = await fetch(`/api/v1/pipeline/${idAtivo}/status`, { credentials: 'same-origin' });
        }
        if (cancelado) return;
        if (resp.status === 404) {
          try {
            localStorage.removeItem(ACTIVE_RESEARCH_KEY);
          } catch {
            /* ignora */
          }
          return;
        }
        if (!resp.ok) return;
        const status = (await resp.json()) as PipelineStatusResumo;
        const registro = historyService.get(idAtivo);
        if (!registro?.planResponse) return;
        setActiveResearchId(idAtivo);
        const estagio = status.status_pipeline ? STAGE_POR_STATUS[status.status_pipeline] : undefined;
        if (estagio) {
          setCurrentPlan(registro.planResponse);
          setPipelineStage(estagio);
          // Reata o canal ao vivo e a telemetria de tokens da pesquisa retomada.
          activeResearchIdRef.current = idAtivo;
          setActiveResearchId(idAtivo);
        } else if (status.status_pipeline === 'concluido' && registro.writerResponse) {
          setCurrentPlan(registro.planResponse);
          setPipelineStage('completed');
        } else if (status.status_pipeline === 'falha') {
          setCurrentPlan(registro.planResponse);
          setFailedStage(null);
          setExecutionError(status.erro_pipeline || 'A execução anterior falhou.');
          setPipelineStage('failed');
        } else if (status.status_pipeline === 'concluido') {
          try {
            localStorage.removeItem(ACTIVE_RESEARCH_KEY);
          } catch {
            /* ignora */
          }
        }
      } catch {
        /* backend offline: mantém a tela atual */
      }
    })();

    return () => {
      cancelado = true;
    };
  }, []);

  // Tema claro/escuro: os tokens já existem em :root[data-theme='dark'],
  // mas nenhum controle os ativava.
  useEffect(() => {
    if (tema === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    try {
      localStorage.setItem(THEME_KEY, tema);
    } catch {
      /* storage indisponível */
    }
  }, [tema]);

  // Rascunho do plano: F5 na tela de revisão não devolve o usuário ao estado vazio.
  useEffect(() => {
    try {
      if (currentPlan && pipelineStage === 'idle') {
        sessionStorage.setItem(DRAFT_PLAN_KEY, JSON.stringify(currentPlan));
      } else if (!currentPlan) {
        sessionStorage.removeItem(DRAFT_PLAN_KEY);
      }
    } catch {
      /* storage indisponível */
    }
  }, [currentPlan, pipelineStage]);

  const navigateTo = (route: string) => {
    window.location.hash = route;
    setCurrentRoute(route);
  };

  // Criação síncrona do plano (/api/v1/plan) com preferências de pontos e personas
  const handleCreatePlan = async () => {
    const tema = composerValue.trim();
    if (tema.length < 5 || tema.length > 500) return;
    // Lock síncrono atômico via ref antes de qualquer microtask ou await
    if (isPlanningRef.current || isExecutingRef.current) return;
    isPlanningRef.current = true;
    setIsPlanning(true);
    const planejamentoId =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `plan-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setPlanningId(planejamentoId);
    setPlanningText('');
    setPlanningStartedAt(Date.now());

    try {
      if (bootstrapPromiseRef.current) {
        await bootstrapPromiseRef.current;
      }

      if (!sessionStateRef.current.authenticated || sessionStateRef.current.error) {
        setPlanningError(
          'A sessão ainda não conectou. Nada foi enviado. Tente de novo em instantes; se continuar, abra Configurações.'
        );
        return;
      }

      setPlanningError(null);
      setExecutionError(null);
      setSearchResult(null);
      setAuditResult(null);
      setAuditCycleNumber(null);
      setWriterResult(null);
      setPipelineStage('idle');
      setCycleNumber(1);
      setAsyncStatus(null);
      setAsyncStatusErro(null);

      if (asyncExecute) {
        const check = validarCallbackUrl(callbackUrl);
        if (!check.valida) {
          setPlanningError(check.motivo ?? 'Callback inválido.');
          return;
        }
        // Localhost não é roteável pelo servidor; avisa mas deixa o operador decidir.
      }

      const plan = await api.createPlan({
        tema,
        n_pontos: nPontos,
        personas: selectedPersonas,
        idPesquisa: planejamentoId,
        recencia,
        criterios_minimos: criteriosMinimos,
        execution_mode: executionMode,
        async_execute: asyncExecute,
        callback_url: asyncExecute ? callbackUrl.trim() || null : null,
      });
      // Garante que o plano tenha o snapshot exato de preferências configuradas na criação
      if (!plan.preferencias) {
        plan.preferencias = {
          n_pontos: plan.n_pontos || nPontos,
          personas: [...selectedPersonas],
          recencia,
          execution_mode: executionMode,
          criterios_minimos: criteriosMinimos,
          async_execute: asyncExecute,
          callback_url: asyncExecute ? callbackUrl.trim() || null : null,
        };
      }
      setCurrentPlan(plan);
      // Plano recém-criado é a pesquisa aberta no workspace: o item da sidebar
      // precisa nascer ativo, antes de qualquer execução.
      activeResearchIdRef.current = plan.id_pesquisa;
      setActiveResearchId(plan.id_pesquisa);
      // Registra raciocínio inicial do Planejador
      if (plan.plano_estruturado || plan.reasoning_planejamento) {
        addReasoningItem({
          id: `plan-${plan.id_pesquisa}`,
          timestamp: plan.criado_em || new Date().toISOString(),
          agentType: 'planejador',
          agentName: 'Planejador',
          title: 'Planejamento: o tema vira pontos',
          reasoning:
            plan.reasoning_planejamento ||
            (plan.plano_estruturado
              ? `**Pedido Normalizado:** ${plan.plano_estruturado.pedido_normalizado}\n\n**Público-alvo:** ${plan.plano_estruturado.publico}\n\n**Formato de Entrega:** ${plan.plano_estruturado.formato_entrega}`
              : 'Plano estruturado pronto para revisão.'),
        });
      }
      // Limpa o compositor somente após o plano ser criado com sucesso, evitando duplicar plano
      setComposerValue('');

      // Persiste no histórico local
      const record: ResearchHistoryRecord = {
        id_pesquisa: plan.id_pesquisa,
        tema: plan.tema,
        criado_em: plan.criado_em,
        status: 'planejado',
        total_pontos: plan.n_pontos,
        planResponse: plan,
      };
      historyService.save(record);
      setHistoryRecords(historyService.list());

      // Leva usuário para a área inicial apropriada sem rolagem animada somente se na rota de pesquisa
      if (currentRouteRef.current === 'research') {
        window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
        if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
          if (rafScrollRef.current !== null) {
            cancelAnimationFrame(rafScrollRef.current);
          }
          rafScrollRef.current = window.requestAnimationFrame(() => {
            rafScrollRef.current = null;
            if (currentRouteRef.current === 'research') {
              window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
            }
          });
        }
      }

      // Entrada do plano: classe CSS (keyframe), sem biblioteca de animação no
      // bundle. `prefers-reduced-motion` desliga no próprio CSS.
      if (workspaceRef.current && currentRouteRef.current === 'research') {
        const alvo = workspaceRef.current;
        alvo.classList.remove('workspace-enter');
        void alvo.offsetWidth; // reinicia a animação
        alvo.classList.add('workspace-enter');
        window.setTimeout(() => alvo.classList.remove('workspace-enter'), 400);
      }
    } catch (err: unknown) {
      // Em caso de falha, mantém o texto do tema no compositor para permitir edição/correção
      setPlanningError(err instanceof Error ? err.message : String(err));
    } finally {
      isPlanningRef.current = false;
      setIsPlanning(false);
      setPlanningId(null);
    }
  };

  const handleEditTheme = (tema: string) => {
    setComposerValue(tema);
    composerRef.current?.focus();
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({
      top: document.body.scrollHeight,
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });
  };

  const handleReplan = async (params: {
    tema: string;
    n_pontos: number;
    personas: string[];
    execution_mode?: 'parallel' | 'sequential';
    recencia?: string;
    criterios_minimos?: number;
  }) => {
    if (!currentPlan) return;
    if (isPlanningRef.current || isExecutingRef.current) return;
    isPlanningRef.current = true;
    setIsPlanning(true);
    setPlanningId(currentPlan.id_pesquisa);
    setPlanningText('');
    setPlanningStartedAt(Date.now());

    // Atualiza estados locais de preferências
    setComposerValue(params.tema);
    setNPontos(params.n_pontos);
    setSelectedPersonas(params.personas);
    if (params.execution_mode) setExecutionMode(params.execution_mode);
    if (params.recencia) setRecencia(params.recencia as any);
    if (params.criterios_minimos) setCriteriosMinimos(params.criterios_minimos);

    try {
      const plan = await api.createPlan({
        tema: params.tema,
        n_pontos: params.n_pontos,
        personas: params.personas,
        idPesquisa: currentPlan.id_pesquisa,
        execution_mode: params.execution_mode ?? executionMode,
        recencia: (params.recencia as any) ?? recencia,
        criterios_minimos: params.criterios_minimos ?? criteriosMinimos,
        async_execute: asyncExecute,
        callback_url: asyncExecute ? callbackUrl.trim() || null : null,
      });

      if (!plan.preferencias) {
        plan.preferencias = {
          n_pontos: plan.n_pontos || params.n_pontos,
          personas: [...params.personas],
          recencia: (params.recencia as any) ?? recencia,
          execution_mode: params.execution_mode ?? executionMode,
          criterios_minimos: params.criterios_minimos ?? criteriosMinimos,
          async_execute: asyncExecute,
          callback_url: asyncExecute ? callbackUrl.trim() || null : null,
        };
      }

      setCurrentPlan(plan);
      activeResearchIdRef.current = plan.id_pesquisa;
      setActiveResearchId(plan.id_pesquisa);

      // Atualiza o registro no histórico sem duplicar
      const record: ResearchHistoryRecord = {
        id_pesquisa: plan.id_pesquisa,
        tema: plan.tema,
        criado_em: plan.criado_em,
        status: 'planejado',
        total_pontos: plan.n_pontos,
        planResponse: plan,
      };
      historyService.save(record);
      setHistoryRecords(historyService.list());
    } catch (err: unknown) {
      setPlanningError(err instanceof Error ? err.message : String(err));
    } finally {
      isPlanningRef.current = false;
      setIsPlanning(false);
      setPlanningId(null);
    }
  };

  // Pipeline unificado e sensível ao estágio com checkpoints e prevenção de concorrência
  const runPipeline = async (options?: { resumeFromStage?: 'searching' | 'auditing' | 'writing' }) => {
    if (!currentPlan) return;
    if (isExecutingRef.current || isPlanningRef.current) return;
    isExecutingRef.current = true;

    const id_pesquisa = currentPlan.id_pesquisa;
    activeResearchIdRef.current = id_pesquisa;
    setActiveResearchId(id_pesquisa);
    try {
      localStorage.setItem(ACTIVE_RESEARCH_KEY, id_pesquisa);
    } catch {
      /* storage indisponível: segue sem retomada */
    }
    const executionToken = ++executionTokenRef.current;
    activeExecutionTokenRef.current = executionToken;
    const maxCycles = 4;
    setExecutionError(null);
    setFailedStage(null);

    // Usa estritamente o snapshot de personas gravado no plano criado;
    // se o plano for legado (sem snapshot), omite explicitamente para o backend resolver seu default/snapshot
    const planPersonas =
      currentPlan.preferencias?.personas && currentPlan.preferencias.personas.length > 0
        ? currentPlan.preferencias.personas
        : undefined;

    const startStage = options?.resumeFromStage ?? 'searching';
    let currentCiclo = cycleNumber;
    if (startStage === 'searching' && !searchResult) {
      currentCiclo = 1;
      setCycleNumber(1);
    }

    // Pulso de transição plano → execução, em CSS.
    if (workspaceRef.current) {
      const alvo = workspaceRef.current;
      alvo.classList.remove('workspace-pulse');
      void alvo.offsetWidth;
      alvo.classList.add('workspace-pulse');
      window.setTimeout(() => alvo.classList.remove('workspace-pulse'), 320);
    }

    try {
      let prontoParaWriter = Boolean(auditResult?.pronto_para_writer);

      if (startStage !== 'writing' && !prontoParaWriter) {
        for (let ciclo = currentCiclo; ciclo <= maxCycles; ciclo++) {
          if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
          setCycleNumber(ciclo);

          // 1. Etapa de Busca Web Concorrente (Search) usando snapshot de personas
          // Se estamos retomando no estágio 'auditing' para este ciclo e já temos searchResult válido:
          const shouldSkipSearch =
            ciclo === currentCiclo && startStage === 'auditing' && searchResult !== null;

          if (!shouldSkipSearch) {
            setPipelineStage('searching');
            try {
              const sRes = await api.searchPoints(id_pesquisa, undefined, planPersonas, executionMode);
              if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
              setSearchResult(sRes);
              // Registra raciocínios das personas coletadas no modo síncrono
              sRes.resumo_coletas.forEach((rc) => {
                rc.personas.forEach((p) => {
                  if (p.reasoning) {
                    // Mesmo ID canônico do evento SSE: o REST só completa o item,
                    // nunca duplica o raciocínio já transmitido ao vivo.
                    upsertReasoningItem({
                      id: `search-${rc.ponto_id}-${p.persona}-${p.queries_executadas}`,
                      timestamp: new Date().toISOString(),
                      agentType: 'busca',
                      agentName: formatPersonaTitle(p.persona),
                      title: `Persona ${formatPersonaTitle(p.persona)} · Ponto ${rc.ponto_n}`,
                      reasoning: p.reasoning,
                      status: p.falha_coleta ? 'falha' : 'concluido',
                    });
                  }
                });
              });
            } catch (searchErr) {
              if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
              setFailedStage('searching');
              setPipelineStage('failed');
              setExecutionError(searchErr instanceof Error ? searchErr.message : String(searchErr));
              return;
            }
          }

          // 2. Etapa de Auditoria Cumulativa (Audit)
          setPipelineStage('auditing');
          let aRes: AuditResponse;
          try {
            aRes = await api.auditResearch(id_pesquisa, undefined, criteriosMinimos);
            if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
            setAuditResult(aRes);
            {
              const recAudit = historyService.get(id_pesquisa);
              if (recAudit) {
                historyService.save({ ...recAudit, auditResponse: aRes });
                setHistoryRecords(historyService.list());
              }
            }
            setAuditCycleNumber(ciclo);
            // Registra raciocínios das auditorias no modo síncrono
            aRes.auditorias.forEach((aud) => {
              const rText = aud.reasoning_auditoria || aud.resumo_auditoria;
              if (rText) {
                upsertReasoningItem({
                  id: `audit-${aud.ponto_id}`,
                  timestamp: new Date().toISOString(),
                  agentType: 'auditor',
                  agentName: 'Auditor Analítico',
                  title: `Auditoria · Ponto ${aud.ponto_n} (Ciclo ${ciclo})`,
                  reasoning: rText,
                  status: aud.status,
                  score: aud.pontuacao_percentual,
                });
              }
            });
          } catch (auditErr) {
            if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
            // Busca concluída com sucesso! Auditoria falhou via HTTP (ex: timeout 504, 500, falha de rede).
            // Registramos failedStage como 'auditing' para permitir retry de auditoria sem repetir a busca!
            setFailedStage('auditing');
            setPipelineStage('failed');
            setExecutionError(auditErr instanceof Error ? auditErr.message : String(auditErr));
            return;
          }

          if (aRes.pronto_para_writer === true) {
            prontoParaWriter = true;
            break;
          }

          // Se reprovado pelo backend (200 com pronto_para_writer === false):
          // Rejeição legítima pelos 12 critérios!
          // No próximo ciclo, fará nova busca para enriquecer evidências e nova auditoria.
          if (ciclo < maxCycles) {
            setSearchResult(null);
            await new Promise((r) => setTimeout(r, 600));
          }
        }

        if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;

        // Bloqueio rigoroso: se a auditoria não aprovou, NUNCA executa o Writer!
        if (!prontoParaWriter) {
          setPipelineStage('rejected');
          setFailedStage(null);
          const rec = historyService.get(id_pesquisa);
          if (rec) {
            historyService.save({ ...rec, status: 'reprovado', auditResponse: auditResult ?? rec.auditResponse });
            setHistoryRecords(historyService.list());
          }
          return;
        }
      }

      // 3. Etapa de Redação Final do Dossiê (Writer)
      // NUNCA chamado sem aprovação prévia da auditoria (prontoParaWriter === true)
      if (!prontoParaWriter) {
        setPipelineStage('rejected');
        setFailedStage(null);
        return;
      }

      setPipelineStage('writing');
      let wRes: WriterResponse;
      try {
        wRes = await api.writeDossier(id_pesquisa);
        if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
        setWriterResult(wRes);
        if (wRes.reasoning_dossier) {
          upsertReasoningItem({
            id: `writer-${id_pesquisa}`,
            timestamp: new Date().toISOString(),
            agentType: 'redator',
            agentName: 'Redator Final',
            title: 'Redação do dossiê',
            reasoning: wRes.reasoning_dossier,
            status: wRes.status,
          });
        }
      } catch (writerErr) {
        if (activeResearchIdRef.current !== id_pesquisa || activeExecutionTokenRef.current !== executionToken) return;
        setFailedStage('writing');
        setPipelineStage('failed');
        setExecutionError(writerErr instanceof Error ? writerErr.message : String(writerErr));
        return;
      }

      const hasDossier = Boolean(wRes.dossier_final && wRes.dossier_final.trim().length > 0);
      if (wRes.status === 'concluido' && hasDossier) {
        setPipelineStage('completed');
        setFailedStage(null);
        if (currentRouteRef.current === 'research') {
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      } else {
        setPipelineStage('failed');
        setFailedStage('writing');
        if (!hasDossier) {
          setExecutionError(
            wRes.diagnostico || 'O dossiê voltou vazio. Tente de novo.'
          );
        }
      }

      const existing = historyService.get(id_pesquisa);
      if (existing) {
        historyService.save({
          ...existing,
          status: wRes.status === 'concluido' && hasDossier ? 'concluido' : 'falha',
          concluido_em: wRes.concluido_em,
          writerResponse: wRes,
        });
        setHistoryRecords(historyService.list());
      }
    } finally {
      if (activeExecutionTokenRef.current === executionToken) {
        isExecutingRef.current = false;
        activeExecutionTokenRef.current = null;
        setIsRetrying(false);
      }
    }
  };

  // Início explícito da execução síncrona
  const handleStartExecution = async () => {
    if (!currentPlan || isExecutingRef.current || isPlanningRef.current) return;
    // Feedback imediato: o feed nunca abre vazio enquanto o backend não emite o primeiro delta.
    upsertReasoningItem({
      id: `planner-start-${currentPlan.id_pesquisa}`,
      timestamp: new Date().toISOString(),
      agentType: 'planejador',
      agentName: 'Planejador',
      title: 'Planejador: abrindo a varredura',
      reasoning:
        'Distribuindo os pontos entre as personas e preparando as buscas. Cada persona aparece aqui assim que começa.',
      status: 'streaming',
    });
    setCycleNumber(1);
    setSearchResult(null);
    setAuditResult(null);
    setAuditCycleNumber(null);
    setWriterResult(null);
    await runPipeline({ resumeFromStage: 'searching' });
  };

  // Recuperação e retentativa sensível ao estágio (Stage-Aware Retry)
  const handleRetryExecution = async () => {
    if (!currentPlan || isExecutingRef.current || isPlanningRef.current) return;
    setIsRetrying(true);

    if (failedStage === 'writing' || auditResult?.pronto_para_writer) {
      await runPipeline({ resumeFromStage: 'writing' });
    } else if (failedStage === 'auditing' && searchResult !== null) {
      await runPipeline({ resumeFromStage: 'auditing' });
    } else {
      await runPipeline({ resumeFromStage: 'searching' });
    }
  };

  // Passo 2: reprocessamento por ponto (busca/auditoria com ponto_id) com merge
  // no estado local — sem recarregar a página nem reiniciar o pipeline.
  const [pontoEmReprocesso, setPontoEmReprocesso] = useState<string | null>(null);

  const handleRefazerBuscaPonto = async (ponto_id: string) => {
    if (!currentPlan || pontoEmReprocesso) return;
    setPontoEmReprocesso(ponto_id);
    setExecutionError(null);
    try {
      const sRes = await api.searchPoints(
        currentPlan.id_pesquisa,
        ponto_id,
        currentPlan.preferencias?.personas?.length ? currentPlan.preferencias.personas : undefined,
        executionMode
      );
      // Merge: troca só o ponto reprocessado, preserva os demais.
      setSearchResult((anterior) => {
        if (!anterior) return sRes;
        const novos = new Map(sRes.resumo_coletas.map((c) => [c.ponto_id, c]));
        return {
          ...sRes,
          id_pesquisa: anterior.id_pesquisa,
          resumo_coletas: anterior.resumo_coletas.map((c) => novos.get(c.ponto_id) ?? c),
        };
      });
    } catch (err: unknown) {
      setExecutionError(err instanceof Error ? err.message : String(err));
    } finally {
      setPontoEmReprocesso(null);
    }
  };

  const handleReauditarPonto = async (ponto_id: string) => {
    if (!currentPlan || pontoEmReprocesso) return;
    setPontoEmReprocesso(ponto_id);
    setExecutionError(null);
    try {
      const aRes = await api.auditResearch(currentPlan.id_pesquisa, ponto_id, criteriosMinimos);
      // Merge: troca só o parecer do ponto, preserva os demais e os totais.
      setAuditResult((anterior) => {
        if (!anterior) {
          setAuditCycleNumber(cycleNumber);
          return aRes;
        }
        const novos = new Map(aRes.auditorias.map((a) => [a.ponto_id, a]));
        const auditorias = anterior.auditorias.map((a) => novos.get(a.ponto_id) ?? a);
        for (const a of aRes.auditorias) {
          if (!auditorias.some((x) => x.ponto_id === a.ponto_id)) auditorias.push(a);
        }
        const aprovados = auditorias.filter((a) => a.status === 'aprovado').length;
        return {
          ...aRes,
          id_pesquisa: anterior.id_pesquisa,
          total_pontos: auditorias.length,
          aprovados,
          reprovados: auditorias.length - aprovados,
          status_geral: aprovados === auditorias.length ? 'aprovado' : 'reprovado',
          status_pesquisa: anterior.status_pesquisa,
          pronto_para_writer: aprovados === auditorias.length,
          auditorias,
        };
      });
      setAuditCycleNumber(cycleNumber);
    } catch (err: unknown) {
      setExecutionError(err instanceof Error ? err.message : String(err));
    } finally {
      setPontoEmReprocesso(null);
    }
  };

  // Passo 5: consulta sob demanda do job assíncrono — sem abrir SSE.
  const [asyncStatus, setAsyncStatus] = useState<PipelineStatusResumo | null>(null);

  // Telemetria ao vivo: o SSE não carrega tokens, então consultamos o status
  // enquanto o pipeline roda. 3s basta para o número parecer contínuo.
  const [tokensAoVivo, setTokensAoVivo] = useState<{
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null>(null);

  const tokensEfetivos = useMemo(() => {
    if (tokensAoVivo && tokensAoVivo.total_tokens > 0) return tokensAoVivo;
    if (!isExecuting && pipelineStage === 'idle') return null;
    const chars = reasoningItems.reduce((acc, item) => acc + (item.reasoning?.length ?? 0), 0);
    if (chars === 0) return null;
    const completion = Math.round(chars / 3.8);
    const prompt = 4200 + (currentPlan?.n_pontos ?? 3) * 1800;
    return {
      prompt_tokens: prompt,
      completion_tokens: completion,
      total_tokens: prompt + completion,
    };
  }, [tokensAoVivo, isExecuting, pipelineStage, reasoningItems, currentPlan]);

  useEffect(() => {
    if (!activeResearchId) return;
    let cancelado = false;
    const consultar = async () => {
      try {
        const s = await api.getPipelineStatus(activeResearchId);
        if (cancelado) return;
        const total = Number(s.tokens_total ?? 0);
        if (total > 0) {
          setTokensAoVivo({
            prompt_tokens: Number(s.tokens_prompt ?? 0),
            completion_tokens: Number(s.tokens_completion ?? 0),
            total_tokens: total,
          });
        }
      } catch {
        /* status é acessório: falhar aqui não muda a tela */
      }
    };
    void consultar();
    // Com o pipeline rodando vale consultar de novo; parado, uma leitura basta.
    const timer = isExecuting ? setInterval(consultar, 3000) : null;
    return () => {
      cancelado = true;
      if (timer) clearInterval(timer);
    };
  }, [activeResearchId, isExecuting]);
  const [asyncConsultando, setAsyncConsultando] = useState(false);
  const [asyncStatusErro, setAsyncStatusErro] = useState<string | null>(null);

  const handleConsultarAsyncStatus = async () => {
    if (!currentPlan || asyncConsultando) return;
    setAsyncConsultando(true);
    setAsyncStatusErro(null);
    try {
      const s = await api.getPipelineStatus(currentPlan.id_pesquisa);
      setAsyncStatus(s);
    } catch (err: unknown) {
      setAsyncStatusErro(err instanceof Error ? err.message : String(err));
    } finally {
      setAsyncConsultando(false);
    }
  };

  // Carregar pesquisa salva do histórico para o workspace
  const handleSelectRecord = (record: ResearchHistoryRecord) => {
    if (isExecuting) {
      if (
        !window.confirm(
          'Existe uma pesquisa em andamento. Alternar para este registro interrompe o acompanhamento na interface, mas o processamento no servidor continua em segundo plano. Deseja abrir esta pesquisa?'
        )
      ) {
        return;
      }
    }
    activeResearchIdRef.current = record.id_pesquisa;
    setActiveResearchId(record.id_pesquisa);
    activeExecutionTokenRef.current = null;
    isExecutingRef.current = false;
    setIsRetrying(false);
    setFailedStage(null);
    setAsyncStatus(null);
    setAsyncStatusErro(null);
    setAsyncConsultando(false);

    // Restaura o plano estritamente para record.planResponse ou null em TODA seleção (elimina metadados obsoletos de plano anterior)
    setCurrentPlan(record.planResponse ?? null);

    if (record.writerResponse) {
      setWriterResult(record.writerResponse);
      const isConcluido = record.writerResponse.status === 'concluido';
      setPipelineStage(isConcluido ? 'completed' : 'failed');
      if (!isConcluido) {
        setExecutionError(
          record.writerResponse.diagnostico ||
            'A redação deste relatório não terminou. O plano e as fontes continuam salvos.'
        );
        setFailedStage('writing');
      } else {
        setExecutionError(null);
      }
    } else {
      setWriterResult(null);
      if (record.status === 'reprovado') {
        setPipelineStage('rejected');
        setExecutionError('A auditoria reprovou esta pesquisa.');
      } else if (record.status === 'falha') {
        setPipelineStage('failed');
        setExecutionError('Falha registrada no histórico.');
      } else {
        setPipelineStage('idle');
        setExecutionError(null);
        // Se a pesquisa ainda estiver rodando no servidor, reata o acompanhamento
        // em vez de mostrar o plano como se nada tivesse começado.
        void (async () => {
          try {
            const resp = await fetch(`/api/v1/pipeline/${record.id_pesquisa}/status`, {
              credentials: 'same-origin',
            });
            if (!resp.ok) return;
            const status = (await resp.json()) as PipelineStatusResumo;
            const estagio = status.status_pipeline ? STAGE_POR_STATUS[status.status_pipeline] : undefined;
            if (estagio) {
              setPipelineStage(estagio);
              try {
                localStorage.setItem(ACTIVE_RESEARCH_KEY, record.id_pesquisa);
              } catch {
                /* ignora */
              }
            }
          } catch {
            /* offline: mantém o plano */
          }
        })();
      }
    }
    setSearchResult(null);
    setAuditResult(record.auditResponse ?? null);
    setAuditCycleNumber(record.auditResponse ? 1 : null);
    navigateTo('research');
  };

  // Excluir do histórico
  const handleDeleteRecord = (id: string) => {
    const registro = historyService.get(id);
    const rotulo = registro?.tema ? `“${registro.tema}”` : 'esta pesquisa';
    if (!window.confirm(`Apagar ${rotulo} do histórico deste navegador? Esta ação não pode ser desfeita.`)) {
      return;
    }
    historyService.remove(id);
    setHistoryRecords(historyService.list());
  };

  // Limpar todo o histórico
  const handleClearHistory = () => {
    if (window.confirm('Tem certeza de que deseja apagar todo o histórico salvo neste navegador?')) {
      historyService.clear();
      setHistoryRecords([]);
    }
  };

  // Resetar para nova pesquisa
  const handleResetResearch = () => {
    if (isExecuting || isPlanningRef.current) {
      if (!window.confirm('Uma pesquisa está em andamento. Tem certeza de que deseja descartar?')) {
        return;
      }
    }
    activeResearchIdRef.current = null;
    setActiveResearchId(null);
    activeExecutionTokenRef.current = null;
    isExecutingRef.current = false;
    setIsRetrying(false);
    clearReasoningItems();
    setCurrentPlan(null);
    try {
      localStorage.removeItem(ACTIVE_RESEARCH_KEY);
    } catch {
      /* ignora */
    }
    setPipelineStage('idle');
    setFailedStage(null);
    setSearchResult(null);
    setAuditResult(null);
    setAuditCycleNumber(null);
    setWriterResult(null);
    setCycleNumber(1);
    setComposerValue('');
    try {
      localStorage.removeItem('deepResearch.draft');
    } catch {
      /* storage bloqueado */
    }
    setPlanningError(null);
    setExecutionError(null);

    // Sair de histórico/configurações/documentação e devolver o foco ao tema.
    navigateTo('research');
    window.setTimeout(() => {
      composerRef.current?.focus();
      const anchor = document.querySelector<HTMLElement>('.composer-anchor');
      if (anchor) {
        anchor.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }, 80);
  };

  // Preencher sugestão no compositor e focar editor (correção do defeito apontado)
  const handleSelectTopicSuggestion = (topic: string) => {
    setComposerValue(topic);
    // Transfere o foco para a caixa de edição
    composerRef.current?.focus();
    // Rolagem suave até o compositor respeitando acessibilidade
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({
      top: document.body.scrollHeight,
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });
  };

  return (
    <div className={`app-shell ${ambientOn ? 'has-ambient' : ''}`}>
      {ambientOn && <HorizonBackground theme={tema} />}
      <a className="skip-link" href="#conteudo">
        Pular para o conteúdo
      </a>

      <Sidebar
        currentRoute={currentRoute}
        onNavigate={navigateTo}
        onNewResearch={handleResetResearch}
        hasPlan={Boolean(currentPlan)}
        sessionAuthenticated={sessionAuthenticated}
        theme={tema}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => {
          setSidebarCollapsed((atual) => {
            try {
              localStorage.setItem('deepResearch.sidebar', atual ? 'expanded' : 'collapsed');
            } catch { /* storage bloqueado */ }
            return !atual;
          });
        }}
        onToggleTheme={() => setTema((atual) => (atual === 'dark' ? 'light' : 'dark'))}
        history={historyRecords}
        activeResearchId={activeResearchId}
        onOpenRecord={handleSelectRecord}
        onOpenHistory={() => navigateTo('history')}
      />
      <div className="app-main">
      <div className="app-container">
      {/* Barra de Navegação Superior com identidade visual DominusLabs */}
      <Navbar
        currentRoute={currentRoute}
        onNavigate={navigateTo}
        onNewResearch={handleResetResearch}
        sessionAuthenticated={sessionAuthenticated}
        isBootstrapping={isBootstrapping}
        theme={tema}
        onToggleTheme={() => setTema((atual) => (atual === 'dark' ? 'light' : 'dark'))}
        hasActiveContext={Boolean(currentPlan) || currentRoute === 'research-sim' || currentRoute.startsWith('execution-')}
        isRailOpen={isRailOpen}
        onToggleRail={() => handleToggleRail()}
        sourcesCount={
          currentRoute === 'research-sim' || currentRoute.startsWith('execution-')
            ? 4
            : searchResult?.resumo_coletas?.length ?? 0
        }
      />

      {/* Falha ao abrir a sessão: diz o que aconteceu, o que sobrou e o próximo passo */}
      {sessionBootstrapError && (
        <div className="app-error-slot">
          <ErrorNotice
            falha={apresentarErro(sessionBootstrapError, { acao: 'abrir a sessão' })}
            onRetry={handleRetryBootstrap}
            retrying={isBootstrapping}
            acaoExtra={{ rotulo: 'Abrir Configurações', onClick: () => navigateTo('settings') }}
          />
        </div>
      )}

      {/* Histórico local indisponível: a lista some ao recarregar, avise antes */}
      {storageError && (
        <div className="app-error-slot">
          <ErrorNotice
            falha={{
              titulo: 'O histórico deste navegador não está funcionando',
              mensagem: `${storageError} O armazenamento local pode estar bloqueado ou cheio. A pesquisa continua no servidor.`,
              tom: 'aviso',
            }}
            onDismiss={() => setStorageError(null)}
          />
        </div>
      )}

      {/* Conteúdo Principal por Rota */}
      <main className="workspace-main" id="conteudo">
        {currentRoute === 'research' && (
          <>
            {/* Falha no planejamento: mesmo aviso em qualquer rota, com repetição da ação */}
            {planningError && (
              <div className="app-error-slot app-error-slot--inline">
                <ErrorNotice
                  compact
                  falha={apresentarErro(planningError, { acao: 'elaborar o plano' })}
                  onRetry={() => void handleCreatePlan()}
                  retrying={isPlanning}
                  retryLabel="Tentar de novo"
                />
              </div>
            )}

            {isPlanning && !currentPlan ? (
              /* Tela intermediária: raciocínio do Planejador ao vivo */
              <PlanningView
                tema={composerValue.trim()}
                iniciadoEm={planningStartedAt}
                raciocinio={planningText}
                erro={planningError}
                onRetry={() => void handleCreatePlan()}
              />
            ) : !currentPlan && !writerResult && pipelineStage === 'idle' ? (
              /* Estado Vazio de Nova Pesquisa */
              <EmptyState tema={tema} rascunho={composerValue} />
            ) : (
              /* Grid de Trabalho: 2 colunas com Sidebar quando há plano real; 1 coluna quando sem plano */
              <div className={`workspace-grid ${!currentPlan ? 'single-column' : ''}`} ref={workspaceRef}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {pipelineStage === 'idle' && currentPlan && currentPlan.preferencias?.async_execute ? (
                    /* Passo 5: job agendado no servidor — sem SSE, com pipeline_id e status sob demanda. */
                    <div className="card" role="status" aria-live="polite">
                      <div className="card-header">
                        <h2 className="card-title">Job agendado no servidor</h2>
                      </div>
                      <p className="card-copy">
                        O plano foi criado e a pesquisa roda no servidor. O dossiê vai para o webhook
                        configurado. Esta tela não acompanha o progresso ao vivo.
                      </p>
                      <dl className="async-confirm-list">
                        <div>
                          <dt>ID da pesquisa</dt>
                          <dd><code>{currentPlan.id_pesquisa}</code></dd>
                        </div>
                        <div>
                          <dt>Entrega</dt>
                          <dd><code>{currentPlan.preferencias?.callback_url || '—'}</code></dd>
                        </div>
                        {asyncStatus && (
                          <div>
                            <dt>Andamento</dt>
                            <dd>{`● ${rotuloStatus(asyncStatus.status_pipeline)} · ${asyncStatus.pontos.filter((p) => p.status === 'aprovado' || p.status === 'coletado').length}/${asyncStatus.total_pontos}`}</dd>
                          </div>
                        )}
                      </dl>
                      <div className="execution-banner-actions">
                        <button
                          type="button"
                          className="btn-secondary btn-compact"
                          onClick={handleConsultarAsyncStatus}
                          disabled={asyncConsultando}
                        >
                          <RefreshCw size={14} className={asyncConsultando ? 'spinner' : ''} aria-hidden="true" />
                          <span>{asyncConsultando ? 'Consultando…' : 'Checar andamento'}</span>
                        </button>
                        <button
                          type="button"
                          className="btn-secondary btn-compact"
                          onClick={handleResetResearch}
                        >
                          <RotateCcw size={14} aria-hidden="true" />
                          <span>Formular novo tema</span>
                        </button>
                      </div>
                      {asyncStatusErro && (
                        <ErrorNotice
                          compact
                          falha={apresentarErro(asyncStatusErro, { acao: 'consultar o andamento' })}
                          onRetry={handleConsultarAsyncStatus}
                          retrying={asyncConsultando}
                          retryLabel="Consultar de novo"
                        />
                      )}
                    </div>
                  ) : pipelineStage === 'idle' && currentPlan ? (
                    <PlanView
                      plan={currentPlan}
                      onStartExecution={handleStartExecution}
                      onReset={handleResetResearch}
                      onEditTheme={handleEditTheme}
                      onReplan={handleReplan}
                      isStarting={isExecutingRef.current || isPlanning}
                    />
                  ) : null}

                  {(pipelineStage === 'searching' ||
                    pipelineStage === 'auditing' ||
                    pipelineStage === 'writing' ||
                    pipelineStage === 'rejected' ||
                    pipelineStage === 'failed') && (
                    <ExecutionView
                      stage={pipelineStage}
                      plan={currentPlan}
                      searchResult={searchResult}
                      auditResult={auditResult}
                      cycleNumber={cycleNumber}
                      maxCycles={4}
                      errorMessage={executionError}
                      streamError={streamError}
                      onReconnect={reconnect}
                      failedStage={failedStage}
                      isRetrying={isRetrying}
                      onRetry={currentPlan ? handleRetryExecution : undefined}
                      onReset={handleResetResearch}
                      reasoningItems={reasoningItems}
                      onRefazerBuscaPonto={currentPlan ? handleRefazerBuscaPonto : undefined}
                      onReauditarPonto={currentPlan ? handleReauditarPonto : undefined}
                      pontoEmReprocesso={pontoEmReprocesso}
                      tokensAoVivo={tokensAoVivo ?? tokensEfetivos}
                      sourcesCount={searchResult?.resumo_coletas?.length ?? 0}
                      isRailOpen={isRailOpen}
                      onToggleRail={handleToggleRail}
                    />
                  )}

                  {pipelineStage === 'completed' && writerResult && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                      <Suspense
                        fallback={
                          <div className="route-loading" role="status" aria-live="polite">
                            Carregando dossiê…
                          </div>
                        }
                      >
                        <ReportView report={writerResult} onReset={handleResetResearch} />
                      </Suspense>
                    </div>
                  )}
                </div>

                {/* Coluna Contextual Direita (Status e Escopo de Comp C) exibida apenas quando há plano real */}
                {currentPlan && (
                  <ContextSidebar
                    plan={currentPlan}
                    isCollapsed={!isRailOpen}
                    onToggleCollapse={() => setIsRailOpen(false)}
                    initialMode={railMode}
                    mode={railMode}
                    pipelineStatus={pipelineStage !== 'idle' ? pipelineStage : currentPlan.status_pipeline}
                    cycleNumber={cycleNumber}
                    maxCycles={4}
                    collectedPoints={
                      searchResult?.resumo_coletas?.filter((c) => c.status !== 'em_andamento').length
                    }
                    auditAoVivo={pipelineStage === 'auditing' && !auditResult}
                    auditSummary={
                      auditResult
                        ? {
                            aprovados: auditResult.aprovados,
                            total: auditResult.total_pontos,
                            ciclo: auditCycleNumber,
                            criteriosMinimos: auditResult.auditorias?.[0]?.criterios_minimos ?? null,
                          }
                        : null
                    }
                    metadadosModelo={currentPlan.metadados_modelo ?? null}
                    tokensAoVivo={tokensAoVivo ?? tokensEfetivos}
                    searchResult={searchResult}
                    fontesAtivas={pipelineStage === 'searching' || pipelineStage === 'auditing'}
                    reasoningItems={reasoningItems}
                    pontosReprovados={
                      auditResult
                        ? new Set(auditResult.auditorias.filter((a) => a.status === 'reprovado').map((a) => a.ponto_id))
                        : null
                    }
                  />
                )}
              </div>
            )}

            {/* Pílulas de temas recomendados: posicionadas acima do card de input, entre o card e a animação */}
            {!isPlanning && !isExecuting && !currentPlan && !writerResult && pipelineStage === 'idle' && (
              <TopicPills onSelect={handleSelectTopicSuggestion} />
            )}

            {/* Compositor só fora de execução e sem plano ativo: durante a revisão do plano
                o card de plano assume o foco total sem input ocioso no rodapé. */}
            {!isPlanning && !isExecuting && !currentPlan && (
            <Composer
              ref={composerRef}
              value={composerValue}
              onChange={setComposerValue}
              onSubmit={handleCreatePlan}
              isSubmitting={isPlanning}
              disabled={
                Boolean(sessionBootstrapError) ||
                isExecuting
              }
              currentPlanActive={Boolean(currentPlan)}
              preferencesProps={{
                isOpen: isPreferencesOpen,
                onToggle: () => setIsPreferencesOpen(!isPreferencesOpen),
                onClose: () => setIsPreferencesOpen(false),
                nPontos,
                onChangeNPontos: handleUserChangeNPontos,
                selectedPersonas,
                onChangePersonas: handleUserChangePersonas,
                disabled: isExecuting || Boolean(sessionBootstrapError),
                currentPlanActive: Boolean(currentPlan),
                executionMode,
                onChangeExecutionMode: handleUserChangeExecutionMode,
                recencia,
                onChangeRecencia: setRecencia,
                criteriosMinimos,
                onChangeCriteriosMinimos: (n) => setCriteriosMinimos(normalizarRigor(n)),
                asyncExecute,
                onChangeAsyncExecute: setAsyncExecute,
                callbackUrl,
                onChangeCallbackUrl: setCallbackUrl,
              }}
              placeholder={
                sessionBootstrapError
                  ? 'A sessão precisa conectar antes de descrever um tema.'
                  : currentPlan || writerResult
                  ? 'Descreva um novo tema de pesquisa para formular outro plano...'
                  : 'Descreva um novo tema de pesquisa (ex: O futuro da matriz energética no Brasil)...'
              }
            />
            )}

            {!isPlanning && !isExecuting && (
              <BottomDock
                theme={tema}
                onToggleTheme={() => setTema((atual) => (atual === 'dark' ? 'light' : 'dark'))}
                ambientOn={ambientOn}
                onToggleAmbient={() => setAmbientOn((on) => {
                  const next = !on;
                  try { localStorage.setItem('deepResearch.ambient', next ? 'on' : 'off'); } catch { /* storage bloqueado */ }
                  return next;
                })}
                nPontos={nPontos}
                onChangeNPontos={handleUserChangeNPontos}
                personas={[
                  { id: 'historiador', label: 'Historiador' },
                  { id: 'visionario', label: 'Visionário' },
                  { id: 'cetico', label: 'Cético' },
                  { id: 'futurista', label: 'Futurista' },
                ]}
                selectedPersonas={selectedPersonas}
                onChangePersonas={handleUserChangePersonas}
                executionMode={executionMode}
                onChangeExecutionMode={handleUserChangeExecutionMode}
                disabled={Boolean(sessionBootstrapError)}
                sessionAuthenticated={sessionAuthenticated}
                onOpenSettings={() => navigateTo('settings')}
              />
            )}
          </>
        )}

        {currentRoute === 'history' && (
          <HistoryView
            records={historyRecords}
            onSelectRecord={handleSelectRecord}
            onDeleteRecord={handleDeleteRecord}
            onClearAll={handleClearHistory}
          />
        )}

        {currentRoute === 'settings' && (
          <SettingsView
            draft={settingsDraft}
            onDraftChange={setSettingsDraft}
            onDiscardDraft={handleDiscardSettingsDraft}
            sessionError={sessionBootstrapError}
            onRetrySession={handleRetryBootstrap}
            theme={tema}
            onToggleTheme={() => setTema((atual) => (atual === 'dark' ? 'light' : 'dark'))}
            ambientOn={ambientOn}
            onToggleAmbient={() =>
              setAmbientOn((on) => {
                const next = !on;
                try {
                  localStorage.setItem('deepResearch.ambient', next ? 'on' : 'off');
                } catch {
                  /* storage bloqueado */
                }
                return next;
              })
            }
          />
        )}

        {currentRoute === 'docs' && (
          <Suspense
            fallback={
              <div className="route-loading" role="status" aria-live="polite">
                Carregando documentação…
              </div>
            }
          >
            <DocsView />
          </Suspense>
        )}

        {import.meta.env.DEV && currentRoute === 'harness' && <ReasoningHarness />}
        {import.meta.env.DEV && currentRoute === 'plan' && <PlanHarness />}
        {import.meta.env.DEV && currentRoute === 'planning' && (
          <PlanningView
            tema="Automação bancária no Brasil: impactos no emprego e na requalificação profissional entre 2010 e 2026"
            iniciadoEm={Date.now() - 15000}
            raciocinio='{"objetivo": "Analisar a transição digital dos bancos", "escopo": "2010 a 2026", "pontos": ["Fechamento de agências físicas", "Programas de requalificação"]}'
          />
        )}
        {import.meta.env.DEV && currentRoute === 'execution-search' && (
          <ExecutionHarness stage="searching" />
        )}
        {import.meta.env.DEV && currentRoute === 'execution-audit' && (
          <ExecutionHarness stage="auditing" />
        )}
        {import.meta.env.DEV && currentRoute === 'execution-writing' && (
          <ExecutionHarness stage="writing" />
        )}
        {import.meta.env.DEV && currentRoute === 'research-sim' && (
          <SimulatedResearch />
        )}
        {import.meta.env.DEV && currentRoute === 'report' && (
          <Suspense fallback={<div className="route-loading">Carregando dossiê…</div>}>
            <ReportView report={HARNESS_REPORT} onReset={() => { window.location.hash = '#research'; }} />
          </Suspense>
        )}
        {import.meta.env.DEV && currentRoute === 'execution-failed' && (
          <ExecutionHarness stage="failed" />
        )}
        {import.meta.env.DEV && currentRoute === 'execution-rejected' && (
          <ExecutionHarness stage="rejected" />
        )}
      </main>
      </div>
    </div>
      <MobileTabBar
        currentRoute={currentRoute}
        onNavigate={navigateTo}
        onNewResearch={handleResetResearch}
      />
    </div>
  );
};
