import React from 'react';
import { Plus, ArrowRight, History, Settings, BookOpen, Moon, Sun, ShieldCheck, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { BrandMark } from './BrandMark';

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
          title={collapsed ? 'DeepResearch — ir para pesquisa' : undefined}
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

      <nav className="sidebar-nav">
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

      <div className="sidebar-footer">
        {!collapsed && (
          <span className="sidebar-footer-note">
            <ShieldCheck size={14} aria-hidden="true" /> Dados ficam neste navegador
          </span>
        )}
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
