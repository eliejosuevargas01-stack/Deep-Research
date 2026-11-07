import React from 'react';
import { Plus, ArrowRight, History, Settings, BookOpen, Moon, Sun, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { BrandMark } from './BrandMark';
import type { ResearchHistoryRecord } from '../types/api';

interface SidebarProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  onNewResearch: () => void;
  hasPlan?: boolean;
  sessionAuthenticated?: boolean;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  /** Pesquisas salvas no navegador, já ordenadas da mais nova para a mais antiga. */
  history?: ResearchHistoryRecord[];
  activeResearchId?: string | null;
  onOpenRecord?: (record: ResearchHistoryRecord) => void;
  onOpenHistory?: () => void;
}

interface ItemProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  collapsed?: boolean;
}

const Item: React.FC<ItemProps> = ({ active, onClick, icon, label, collapsed = false }) => (
  <button
    type="button"
    className={`sidebar-item ${active ? 'is-active' : ''}`}
    onClick={onClick}
    aria-current={active ? 'page' : undefined}
    title={collapsed ? label : undefined}
  >
    <span className="sidebar-item-icon" aria-hidden="true">{icon}</span>
    {!collapsed && <span>{label}</span>}
  </button>
);

const STATUS_LABEL: Record<ResearchHistoryRecord['status'], string> = {
  planejado: 'Planejado',
  buscando: 'Em pesquisa',
  auditando: 'Em pesquisa',
  redigindo: 'Em pesquisa',
  concluido: 'Concluída',
  reprovado: 'Reprovada',
  falha: 'Falha',
};

const MESES_CURTOS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

/**
 * Data curta e legível: "agora", "há 2 h", "ontem", "há 3 d" ou "12 out".
 * Retorna string vazia para datas inválidas para não imprimir "Invalid Date".
 */
const formatRelativeDate = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (diffMs <= 0) return 'agora';
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'agora';
  if (minutes < 60) return `há ${minutes} min`;

  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const dayDiff = Math.round((startOfToday - startOfDate) / 86400000);
  if (dayDiff <= 0) return `há ${Math.floor(minutes / 60)} h`;
  if (dayDiff === 1) return 'ontem';
  if (dayDiff < 7) return `há ${dayDiff} d`;
  return `${date.getDate()} ${MESES_CURTOS[date.getMonth()]}`;
};

const recordMeta = (record: ResearchHistoryRecord): string => {
  const parts = [STATUS_LABEL[record.status], formatRelativeDate(record.criado_em)].filter(Boolean);
  return parts.join(' · ');
};

/**
 * Navegação lateral fixa e recolhível: libera a altura da tela para a
 * investigação e substitui a topbar cheia de botões fortes.
 * Recolhida vira trilho de ícones (64px) com tooltip por item.
 */
export const Sidebar: React.FC<SidebarProps> = ({
  currentRoute,
  onNavigate,
  onNewResearch,
  hasPlan = false,
  sessionAuthenticated = false,
  theme = 'light',
  onToggleTheme,
  collapsed = false,
  onToggleCollapse,
  history = [],
  activeResearchId = null,
  onOpenRecord,
  onOpenHistory,
}) => {
  return (
    <aside
      className={`app-sidebar ${collapsed ? 'is-collapsed' : ''}`}
      aria-label="Navegação do workspace"
      aria-expanded={!collapsed}
    >
      <div className="sidebar-top">
        <a
          href="#research"
          className="sidebar-brand"
          onClick={(e) => {
            e.preventDefault();
            onNavigate('research');
          }}
          title={collapsed ? 'Deep Research: ir para pesquisa' : undefined}
        >
          <BrandMark size={26} />
          {!collapsed && (
            <span className="sidebar-brand-word">
              Deep<b>Research</b>
            </span>
          )}
        </a>
        {onToggleCollapse && (
          <button
            type="button"
            className="sidebar-collapse"
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
            title={collapsed ? 'Expandir menu lateral' : 'Recolher menu lateral'}
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        )}
      </div>

      <span className={`sidebar-mode ${sessionAuthenticated ? 'is-ok' : 'is-warn'}`} title={collapsed ? (sessionAuthenticated ? 'Sessão ativa' : 'Sessão pendente') : undefined}>
        <span className="sidebar-mode-dot" aria-hidden="true" />
        {!collapsed && (sessionAuthenticated ? 'Sessão ativa' : 'Sessão pendente')}
      </span>

      <nav className="sidebar-nav" aria-label="Navegação principal">
        {!collapsed && <p className="sidebar-group">Investigação</p>}
        <Item
          active={currentRoute === 'research' && !hasPlan}
          onClick={onNewResearch}
          icon={<Plus size={16} />}
          label="Nova pesquisa"
          collapsed={collapsed}
        />
        <Item
          active={currentRoute === 'research' && hasPlan}
          onClick={() => onNavigate('research')}
          icon={<ArrowRight size={16} />}
          label="Pesquisa atual"
          collapsed={collapsed}
        />
        <Item
          active={currentRoute === 'history'}
          onClick={() => onNavigate('history')}
          icon={<History size={16} />}
          label="Histórico"
          collapsed={collapsed}
        />

        {!collapsed && <p className="sidebar-group">Sistema</p>}
        <Item
          active={currentRoute === 'settings'}
          onClick={() => onNavigate('settings')}
          icon={<Settings size={16} />}
          label="Configurações"
          collapsed={collapsed}
        />
        <Item
          active={currentRoute === 'docs'}
          onClick={() => onNavigate('docs')}
          icon={<BookOpen size={16} />}
          label="Documentação"
          collapsed={collapsed}
        />
      </nav>

      {!collapsed && (
        <section className="sidebar-conversations" aria-labelledby="sidebar-conversations-heading">
          <p className="sidebar-group" id="sidebar-conversations-heading">Conversas</p>
          {history.length === 0 ? (
            <p className="sidebar-conversations-empty">Nenhuma pesquisa ainda</p>
          ) : (
            <ul className="sidebar-conversation-list">
              {history.slice(0, 6).map((record) => {
                const active = activeResearchId === record.id_pesquisa;
                return (
                  <li key={record.id_pesquisa}>
                    <button
                      type="button"
                      className={`sidebar-conversation ${active ? 'is-active' : ''}`}
                      onClick={() => onOpenRecord?.(record)}
                      aria-current={active ? 'page' : undefined}
                      title={record.tema}
                    >
                      <span className="sidebar-conversation-title">{record.tema}</span>
                      <span className="sidebar-conversation-meta">{recordMeta(record)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <button type="button" className="sidebar-history-link" onClick={() => onOpenHistory?.()}>
            Ver histórico
          </button>
        </section>
      )}

      <div className="sidebar-footer">
        <button
          type="button"
          className="sidebar-theme"
          onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'}
          title={collapsed ? (theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro') : undefined}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {!collapsed && <span>{theme === 'dark' ? 'Tema claro' : 'Tema escuro'}</span>}
        </button>
      </div>
    </aside>
  );
};
