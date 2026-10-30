import React, { Suspense } from 'react';
import { InlineMarkdown } from './InlineMarkdown';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Layers,
  PenTool,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { AgentRoleType, ReasoningFeedItem } from '../types/stream';
import { PersonaIcon, PersonaType } from './ResearchIcons';

/**
 * Corpo markdown sob demanda: react-markdown + remark-gfm pesam ~35 KB gzip e
 * antes entravam no primeiro paint de qualquer rota. O fallback já mostra o
 * texto com negrito e código enquanto o chunk carrega.
 */
const MarkdownBody = React.lazy(() => import('./ReasoningMarkdownBody'));

function formatTime(iso: string): string {
  try {
    // O backend envia ISO sem fuso; sem o sufixo o navegador trataria como
    // hora local e o carimbo apareceria 3h atrasado em America/Sao_Paulo.
    const comFuso = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
    return new Date(comFuso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function formatDuration(ms?: number | null): string {
  if (!ms || ms < 0) return '';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${String(s % 60).padStart(2, '0')}s`;
}

function limparMarkdown(texto: string): string {
  return texto
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[*_`>#]/g, '')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

function extrairTakeaway(texto: string): string | null {
  if (!texto) return null;
  const linhas = texto.split('\n');
  for (let i = linhas.length - 1; i >= 0; i--) {
    const l = linhas[i].trim();
    if (!l) continue;
    if (/^Conclusão:|^Takeaway:|^Key takeaway:/i.test(l)) {
      return l.replace(/^Conclusão:|^Takeaway:|^Key takeaway:/i, '').trim() || null;
    }
  }
  if (/(pontos_fracos|resumo_auditoria)/i.test(texto)) {
    const m = texto.match(/(?:pontos_fracos|resumo_auditoria)[^\n]*\n?(.{20,280})/i);
    if (m && m[1]) return m[1].replace(/\n/g, ' ').trim();
  }
  return null;
}

function normalizarTexto(s: string): string {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function derivarPersonaDeTexto(texto: string): PersonaType | null {
  const p = normalizarTexto(texto);
  if (p.includes('planejador')) return 'planejador';
  if (p.includes('historiador')) return 'historiador';
  if (p.includes('cetico') || p.includes('cético')) return 'cetico';
  if (p.includes('visionario') || p.includes('visionário')) return 'visionario';
  if (p.includes('futurista')) return 'futurista';
  if (p.includes('auditor')) return 'auditor';
  if (p.includes('redator')) return 'redator';
  return null;
}

/** Resumo do cartão recolhido. Em streaming mostra a cauda: é o progresso. */
function resumo(texto: string, limite = 120, cauda = false): string {
  const limpo = limparMarkdown(texto);
  if (limpo.length <= limite) return limpo;
  return cauda ? `…${limpo.slice(-limite)}` : `${limpo.slice(0, limite)}…`;
}

function getAgentIcon(type: AgentRoleType) {
  switch (type) {
    case 'planejador':
      return <Layers size={12} aria-hidden="true" />;
    case 'busca':
      return <Search size={12} aria-hidden="true" />;
    case 'auditor':
      return <ShieldCheck size={12} aria-hidden="true" />;
    case 'redator':
      return <PenTool size={12} aria-hidden="true" />;
    default:
      return <Sparkles size={12} aria-hidden="true" />;
  }
}

/** Relógio de 1s enquanto o cartão transmite: "pensando há 14s". */
function useDecorrido(ativo: boolean, inicio?: number | null): number | null {
  const [agora, setAgora] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!ativo) return;
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, [ativo]);
  if (!inicio) return null;
  return Math.max(0, Math.round((agora - inicio) / 1000));
}

export interface ReasoningCardItemProps {
  item: ReasoningFeedItem;
  aberto: boolean;
  copiado: boolean;
  onToggle: (item: ReasoningFeedItem) => void;
  onCopy: (item: ReasoningFeedItem, event: React.MouseEvent) => void;
  registrarToggle: (id: string, el: HTMLButtonElement | null) => void;
}

/** Remove a query repetida da linha de telemetria: ela já aparece na pílula. */
function normalizarTelemetria(texto: string): string {
  const consultas = new Set<string>();
  const saida = texto.replace(
    /(\*\*Ferramenta · SERP\*\*)\s*`([^`]+)`\s*→\s*(\d+)\s*resultados/g,
    (_m, rotulo: string, consulta: string, total: string) => {
      consultas.add(consulta.trim());
      return `${rotulo} · ${total} resultados`;
    }
  );
  const linhas = saida.split('\n').filter((linha) => {
    if (consultas.size > 0 && consultas.has(linha.trim().replace(/^\*+|\*+$/g, '').trim())) {
      return false;
    }
    // Vazamento de meta-instrução/estilo não é raciocínio analítico: não vai para a UI.
    return !/(caveman|brain buster|system prompt|prompt do sistema|system message|minhas instruções|my instructions)/i.test(linha);
  });
  return linhas.join('\n');
}

/**
 * Cartão do feed. Memoizado: durante o streaming o array de itens muda a cada
 * 80ms, mas apenas o cartão em execução precisa reconciliar — os concluídos
 * ficam parados.
 */
export const ReasoningCardItem = React.memo(function ReasoningCardItem({
  item,
  aberto,
  onToggle,
  registrarToggle,
}: ReasoningCardItemProps) {
  const corpoId = `reasoning-body-${item.id}`;
  // O backend usa 'concluido'/'falha' na busca e 'aprovado'/'reprovado' na
  // auditoria: sem normalizar, cartão de auditoria nunca mostra desfecho.
  const falhou = item.status === 'falha' || item.status === 'reprovado';
  const concluiu = !item.streaming && (item.status === 'concluido' || item.status === 'aprovado');
  // O título do SSE já repete o nome do agente ("Varredura Web — Cético").
  // O badge ao lado diz o mesmo; repetir polui a linha.
  const sufixo = new RegExp(`\\s*[—–-]\\s*${item.agentName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`, 'i');
  const titulo = item.title.replace(sufixo, '').trim() || item.title;
  const detalhes = (item.details || {}) as Record<string, unknown>;
  const duracao = formatDuration(
    typeof detalhes.duration_ms === 'number' ? (detalhes.duration_ms as number) : null
  );
  const personaExplicita = (detalhes.persona as string) || (item as unknown as { persona?: string }).persona;
  const fontePersona = `${personaExplicita || ''} ${item.agentName} ${item.title}`;
  const personaTipo: PersonaType =
    derivarPersonaDeTexto(fontePersona) ??
    derivarPersonaDeTexto(item.agentType) ??
    (item.agentType === 'auditor' ? 'auditor' : item.agentType === 'redator' ? 'redator' : 'planejador');
  // Pílulas de domínio/consulta extraídas da telemetria real do agente
  // (`Ferramenta · SERP` e URLs citadas no raciocínio). Sem fabricar fontes.
  const consultas = Array.from(item.reasoning.matchAll(/Ferramenta · SERP\*\*\s*`([^`]+)`/g))
    .map((m) => m[1])
    .slice(0, 3);
  const dominios = Array.from(
    new Set([
      ...Array.from(item.reasoning.matchAll(/https?:\/\/([^\s"')\]>]+)/g)).map((m) =>
        m[1].replace(/^www\./, '').replace(/\/.*$/, '')
      ),
      ...Array.from(item.reasoning.matchAll(/`([a-z0-9.-]+\.[a-z]{2,})`/gi)).map((m) =>
        m[1].replace(/^www\./, '')
      ),
    ])
  ).slice(0, 6);
  const paginasLidas = item.reasoning.match(/Ferramenta · Reader\*\*\s*(\d+)\s*páginas/);

  const decorrido = useDecorrido(
    Boolean(item.streaming),
    typeof detalhes.started_at === 'number' ? (detalhes.started_at as number) : null
  );

  return (
    <article
      className={`reasoning-card role-${personaTipo} ${aberto ? 'is-open' : 'is-collapsed'} ${
        item.streaming ? 'is-streaming' : ''
      } ${falhou ? 'is-failed' : ''}`}
    >
      <div className="reasoning-card-header">
        <button
          type="button"
          className="reasoning-card-toggle"
          aria-expanded={aberto}
          aria-controls={aberto ? corpoId : undefined}
          onClick={() => onToggle(item)}
          ref={(el) => registrarToggle(item.id, el)}
        >
          <span className={`reasoning-avatar role-${personaTipo}`} aria-hidden="true">
            <PersonaIcon persona={personaTipo} size={16} />
          </span>
          <span className="reasoning-card-line">
            <span className="sr-only">
              {falhou ? 'Falhou. ' : item.streaming ? 'Em execução. ' : 'Concluído. '}
            </span>
            {concluiu && (
              <Check size={13} aria-hidden="true" className="reasoning-status-icon is-done" />
            )}
            {falhou && (
              <AlertTriangle size={13} aria-hidden="true" className="reasoning-status-icon is-fail" />
            )}
            <span className={`reasoning-agent-badge agent-badge-${item.agentType}`}>
              {getAgentIcon(item.agentType)}
              <span>{item.agentName}</span>
            </span>
            <span className="reasoning-card-title">{titulo}</span>
            <span className="reasoning-card-stats">
              {item.streaming && (
                <span className="reasoning-live-tag">
                  {decorrido !== null ? `pensando há ${decorrido}s` : 'ao vivo'}
                </span>
              )}
              {/* Métricas secundárias só no cartão aberto: recolhido precisa
                  caber badge + título + estado sem competir por espaço. */}
              {aberto && <span>{item.reasoning.length.toLocaleString('pt-BR')} caracteres</span>}
              {aberto && <span>{formatTime(item.timestamp)}</span>}
              {aberto && duracao && <span>{duracao}</span>}
              {aberto ? (
                <ChevronUp size={13} aria-hidden="true" />
              ) : (
                <ChevronDown size={13} aria-hidden="true" />
              )}
            </span>
            {!aberto && (
              <span className="reasoning-card-preview">
                {resumo(item.reasoning, 120, Boolean(item.streaming))}
              </span>
            )}
          </span>
        </button>
      </div>

      {falhou && (
        <p className="reasoning-card-alert">
          <AlertTriangle size={12} aria-hidden="true" /> Coleta falhou neste agente.
        </p>
      )}

      {aberto && (
        <div id={corpoId} className="reasoning-card-body">
          {item.streaming ? (
            <div className="reasoning-streaming-text">
              <InlineMarkdown text={normalizarTelemetria(item.reasoning)} />
            </div>
          ) : (
            <Suspense fallback={<InlineMarkdown text={normalizarTelemetria(item.reasoning)} />}>
              <MarkdownBody text={normalizarTelemetria(item.reasoning)} />
            </Suspense>
          )}

          {(() => {
            const takeaway = extrairTakeaway(item.reasoning);
            if (!takeaway || item.streaming) return null;
            return (
              <aside className="reasoning-takeaway">
                <strong>Key takeaway</strong>
                <p>{takeaway.length > 280 ? `${takeaway.slice(0, 277)}…` : takeaway}</p>
              </aside>
            );
          })()}
        </div>
      )}

      {(consultas.length > 0 || dominios.length > 0 || paginasLidas) && (
        <div className="reasoning-sources" aria-label="Ferramentas e fontes desta etapa">
          {consultas.map((consulta) => (
            <span key={`q-${consulta}`} className="reasoning-source-pill is-query">
              <span aria-hidden="true">⌕</span> {consulta}
            </span>
          ))}
          {paginasLidas && (
            <span className="reasoning-source-pill is-count">
              {paginasLidas[1]} páginas lidas
            </span>
          )}
          {dominios.map((dominio) => (
            <span key={`d-${dominio}`} className="reasoning-source-pill">
              <span aria-hidden="true">◍</span> {dominio}
            </span>
          ))}
        </div>
      )}
    </article>
  );
});
