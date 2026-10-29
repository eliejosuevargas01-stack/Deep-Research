import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Brain, ChevronDown, ChevronUp } from 'lucide-react';
import { AgentRoleType, ReasoningFeedItem } from '../types/stream';
import { ReasoningCardItem } from './ReasoningCardItem';
import '../styles/reasoning-feed.css';

interface ReasoningFeedProps {
  items: ReasoningFeedItem[];
  isActive?: boolean;
  activeAgentName?: string | null;
  /** Mantém o feed aberto ao montar (padrão). */
  defaultExpanded?: boolean;
  /** Estágio em execução: marca o chip correspondente com pulso. */
  activeStageType?: AgentRoleType | null;
}

type Filtro = 'todos' | AgentRoleType;

const FILTROS: Array<{ id: Filtro; rotulo: string }> = [
  { id: 'todos', rotulo: 'Todos' },
  { id: 'planejador', rotulo: 'Planejador' },
  { id: 'busca', rotulo: 'Personas' },
  { id: 'auditor', rotulo: 'Auditor' },
  { id: 'redator', rotulo: 'Redator' },
];

const ROTULO_ESTAGIO: Record<string, string> = {
  plan: 'Planejamento',
  planning: 'Planejamento',
  search: 'Busca',
  searching: 'Busca',
  audit: 'Auditoria',
  auditing: 'Auditoria',
  write: 'Redação',
  writing: 'Redação',
};

/**
 * Feed de raciocínio dos agentes.
 *
 * Padrão de mercado para "thinking" (MUI X, assistant-ui, LangChain): cartão
 * recolhido por padrão, expandido só enquanto transmite, com resumo de uma
 * linha e contagem de caracteres — permite percorrer dezenas de raciocínios
 * sem rolar quilômetros de texto.
 */
export function calcularTerminados(anteriores: Set<string>, atuais: Set<string>): string[] {
  return [...anteriores].filter((id) => !atuais.has(id));
}

export const ReasoningFeed: React.FC<ReasoningFeedProps> = ({
  items,
  isActive = false,
  activeAgentName = null,
  defaultExpanded = true,
  activeStageType = null,
}) => {
  const [filtro, setFiltro] = useState<Filtro>('todos');
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [autoScroll, setAutoScroll] = useState(true);
  const [copiadoId, setCopiadoId] = useState<string | null>(null);
  const [feedRecolhido, setFeedRecolhido] = useState<boolean>(!defaultExpanded);
  const [anuncio, setAnuncio] = useState('');
  const [novosNoFim, setNovosNoFim] = useState(0);
  const totalVistoRef = useRef(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const togglesRef = useRef<Map<string, HTMLButtonElement>>(new Map());
  const totalAnteriorRef = useRef(items.length);

  const filtrados = useMemo(() => {
    const termo = '';
    return items.filter((item) => {
      if (filtro !== 'todos' && item.agentType !== filtro) return false;
      if (!termo) return true;
      return (
        item.title.toLowerCase().includes(termo) ||
        item.agentName.toLowerCase().includes(termo) ||
        item.reasoning.toLowerCase().includes(termo)
      );
    });
  }, [items, filtro]);

  const contagens = useMemo<Record<Filtro, number>>(
    () => ({
      todos: items.length,
      planejador: items.filter((i) => i.agentType === 'planejador').length,
      busca: items.filter((i) => i.agentType === 'busca').length,
      auditor: items.filter((i) => i.agentType === 'auditor').length,
      redator: items.filter((i) => i.agentType === 'redator').length,
    }),
    [items]
  );

  // Recolhido por padrão. Exceção: quando só UM agente está transmitindo, ele
  // abre sozinho — dá para ler o raciocínio ao vivo sem clicar. Com 4 personas
  // em paralelo nada abre, senão o restante do feed sai da tela.
  const idsTransmitindo = useMemo(
    () => items.filter((item) => item.streaming).map((item) => item.id),
    [items]
  );
  const estaAberto = useCallback(
    (item: ReasoningFeedItem) => {
      if (item.id in overrides) return overrides[item.id];
      // O item ao vivo troca de ID ao concluir (live-* -> definitivo). Herdar a
      // decisão do usuário evita o cartão fechar sozinho na cara dele.
      const anterior = (item.details as Record<string, unknown> | undefined)?.previous_id;
      if (typeof anterior === 'string' && anterior in overrides) return overrides[anterior];
      return idsTransmitindo.length === 1 && idsTransmitindo[0] === item.id;
    },
    [overrides, idsTransmitindo]
  );

  const manuaisRef = useRef<Set<string>>(new Set());
  const streamingAnteriorRef = useRef<Set<string>>(new Set());

  const alternar = useCallback((item: ReasoningFeedItem) => {
    manuaisRef.current.add(item.id);
    setOverrides((prev) => {
      const abertoAtual = item.id in prev ? prev[item.id] : false;
      return { ...prev, [item.id]: !abertoAtual };
    });
  }, []);

  // Etapa concluída recolhe sozinha: a tela fica curta e a leitura continua.
  useEffect(() => {
    const atuais = new Set(items.filter((i) => i.streaming).map((i) => i.id));
    const terminaram = calcularTerminados(streamingAnteriorRef.current, atuais);
    if (terminaram.length > 0) {
      setOverrides((prev) => {
        const next = { ...prev };
        for (const id of terminaram) {
          if (!manuaisRef.current.has(id)) next[id] = false;
        }
        return next;
      });
    }
    streamingAnteriorRef.current = atuais;
  }, [items]);

  // Auto-scroll só com o usuário no fim; medição dentro de rAF. Na primeira
  // renderização com conteúdo, salta para o fim (é um console ao vivo).
  const primeiraRenderizacaoRef = useRef(true);
  useEffect(() => {
    if (!autoScroll || feedRecolhido) return;
    const frame = requestAnimationFrame(() => {
      const el = containerRef.current;
      if (!el) return;
      const distancia = el.scrollHeight - el.scrollTop - el.clientHeight;
      if (primeiraRenderizacaoRef.current || distancia <= 160) {
        el.scrollTop = el.scrollHeight;
      }
      primeiraRenderizacaoRef.current = false;
    });
    return () => cancelAnimationFrame(frame);
  }, [items, autoScroll, feedRecolhido]);

  const aoRolar = () => {
    const el = containerRef.current;
    if (!el) return;
    const noFim = el.scrollHeight - el.scrollTop - el.clientHeight <= 160;
    setAutoScroll(noFim);
    if (noFim) {
      setNovosNoFim(0);
      totalVistoRef.current = items.length;
    }
  };

  useEffect(() => {
    if (autoScroll) {
      setNovosNoFim(0);
      totalVistoRef.current = items.length;
      return;
    }
    setNovosNoFim(Math.max(0, items.length - totalVistoRef.current));
  }, [items.length, autoScroll]);

  // Uma única região viva: anuncia a chegada de um novo pensamento, nunca cada
  // token (isso viraria spam para leitores de tela).
  useEffect(() => {
    if (items.length > totalAnteriorRef.current && items.length > 0) {
      const ultimo = items[items.length - 1];
      setAnuncio(`Novo raciocínio de ${ultimo.agentName}. ${items.length} no total.`);
    }
    totalAnteriorRef.current = items.length;
  }, [items]);

  // Navegação por teclado entre cartões (↑/↓, Home/End).
  const aoTeclar = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const alvoEhToggle = (event.target as HTMLElement | null)?.classList.contains('reasoning-card-toggle');
    if (!alvoEhToggle) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      // Nunca blur(): o foco iria para o <body> e a tabulação recomeçaria no topo.
      const cabecalho = containerRef.current?.querySelector<HTMLElement>('.reasoning-feed-btn');
      if (cabecalho) cabecalho.focus();
      return;
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    const ordem = filtrados
      .map((item) => togglesRef.current.get(item.id))
      .filter(Boolean) as HTMLButtonElement[];
    if (ordem.length === 0) return;
    const atual = ordem.indexOf(document.activeElement as HTMLButtonElement);
    let alvo = atual;
    if (event.key === 'ArrowDown') alvo = Math.min(ordem.length - 1, atual + 1);
    if (event.key === 'ArrowUp') alvo = Math.max(0, atual - 1);
    if (event.key === 'Home') alvo = 0;
    if (event.key === 'End') alvo = ordem.length - 1;
    if (alvo !== atual || atual === -1) {
      event.preventDefault();
      ordem[alvo]?.focus();
    }
  };

  useEffect(() => {
    const ativo = document.activeElement as HTMLElement | null;
    if (ativo && ativo.isConnected) return;
    const primeiro = filtrados[0];
    if (!primeiro) return;
    togglesRef.current.get(primeiro.id)?.focus();
  }, [filtrados]);

  const copiar = useCallback((item: ReasoningFeedItem, event: React.MouseEvent) => {
    event.stopPropagation();
    if (!navigator?.clipboard) return;
    navigator.clipboard.writeText(item.reasoning).then(() => {
      setCopiadoId(item.id);
      setTimeout(() => setCopiadoId(null), 2000);
    });
  }, []);

  // Callback estável: sem isso o `React.memo` do cartão é invalidado a cada
  // tick de 80ms do streaming e todos os cartões re-renderizam.
  const registrarToggle = useCallback((id: string, el: HTMLButtonElement | null) => {
    if (el) togglesRef.current.set(id, el);
    else togglesRef.current.delete(id);
  }, []);

  const irParaUltimo = () => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setAutoScroll(true);
    setNovosNoFim(0);
    totalVistoRef.current = items.length;
  };

  return (
    <section
      className="reasoning-feed-container"
      aria-label="Cadeia de raciocínio dos agentes em tempo real"
    >
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {anuncio}
      </div>
      <div className="sr-only" aria-live="polite">
        {copiadoId ? 'Raciocínio copiado para a área de transferência.' : ''}
      </div>

      <header className="reasoning-feed-header">
        <div className="reasoning-feed-title-group">
          <span
            className={`live-pulse-dot ${isActive ? 'pulse-violet' : 'idle'}`}
            title={isActive ? 'Agentes raciocinando em tempo real' : 'Conexão ociosa'}
            aria-hidden="true"
          />
          <h2 className="reasoning-feed-title">
            <Brain size={16} aria-hidden="true" className="reasoning-feed-title-icon" />
            <span>Raciocínio dos Agentes</span>
          </h2>
          <span className="reasoning-feed-count">
            {items.length} {items.length === 1 ? 'registro' : 'registros'}
          </span>
          {isActive && activeAgentName && (
            <span className="reasoning-feed-active-agent">{activeAgentName} pensando…</span>
          )}
        </div>

        <button
          type="button"
          className="reasoning-feed-btn"
          onClick={() => setFeedRecolhido((v) => !v)}
          aria-expanded={!feedRecolhido}
          aria-controls="reasoning-feed-body"
        >
          {feedRecolhido ? (
            <ChevronDown size={13} aria-hidden="true" />
          ) : (
            <ChevronUp size={13} aria-hidden="true" />
          )}
          <span>{feedRecolhido ? 'Mostrar painel' : 'Ocultar painel'}</span>
        </button>
      </header>

      {!feedRecolhido && (
        <div id="reasoning-feed-body">
          <div className="reasoning-toolbar">
            <div className="reasoning-filter-row" role="group" aria-label="Filtrar por agente">
              {FILTROS.map(({ id, rotulo }) => (
                <button
                  key={id}
                  type="button"
                  className={`reasoning-tab ${filtro === id ? 'is-active' : ''}`}
                  onClick={() => setFiltro(id)}
                  aria-pressed={filtro === id}
                >
                  {rotulo}
                  <span className="reasoning-tab-count">{contagens[id]}</span>
                  {activeStageType === id && <span className="reasoning-tab-live" aria-hidden="true" />}
                </button>
              ))}
            </div>
          </div>

          <div className="reasoning-stream-wrap">
          <div
            className="reasoning-feed-stream"
            ref={containerRef}
            onScroll={aoRolar}
            onKeyDown={aoTeclar}
          >
            {filtrados.length === 0 ? (
              <div className="reasoning-feed-empty">
                <Brain size={26} aria-hidden="true" className="reasoning-feed-empty-icon" />
                <span className="reasoning-feed-empty-title">
                  {isActive
                    ? 'Aguardando o primeiro pensamento dos modelos…'
                    : 'Nenhum pensamento registrado nesta categoria.'}
                </span>
              </div>
            ) : (
              filtrados.map((item, indice) => {
                const aberto = estaAberto(item);
                const estagio = String((item.details as Record<string, unknown> | undefined)?.stage || '');
                const estagioAnterior =
                  indice > 0
                    ? String(
                        (filtrados[indice - 1].details as Record<string, unknown> | undefined)?.stage || ''
                      )
                    : '';
                const mostrarDivisor = Boolean(estagio) && estagio !== estagioAnterior;
                return (
                  <React.Fragment key={item.id}>
                    {mostrarDivisor && (
                      <div className="reasoning-stage-divider">
                        <span>{ROTULO_ESTAGIO[estagio] || estagio}</span>
                      </div>
                    )}
                    <ReasoningCardItem
                      item={item}
                      aberto={aberto}
                      copiado={copiadoId === item.id}
                      onToggle={alternar}
                      onCopy={copiar}
                      registrarToggle={registrarToggle}
                    />
                  </React.Fragment>
                );
              })
            )}
          </div>
          {!autoScroll && (
            <button type="button" className="reasoning-jump-latest" onClick={irParaUltimo}>
              <ChevronDown size={13} aria-hidden="true" />
              {novosNoFim > 0 ? `${novosNoFim} novo${novosNoFim > 1 ? 's' : ''} abaixo` : 'Ir para o mais recente'}
            </button>
          )}
          </div>
        </div>
      )}
    </section>
  );
};
