import React, { useState, useEffect } from 'react';
import { Plus, BookOpen, Settings, History, Search, Menu, X, ShieldAlert, PanelRight } from 'lucide-react';
import { BrandMark } from './BrandMark';

interface NavbarProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  onNewResearch: () => void;
  sessionAuthenticated?: boolean;
  isBootstrapping?: boolean;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
  hasActiveContext?: boolean;
  isRailOpen?: boolean;
  onToggleRail?: () => void;
  sourcesCount?: number;
}

const NavbarBase: React.FC<NavbarProps> = ({
  currentRoute,
  onNavigate,
  onNewResearch,
  sessionAuthenticated = false,
  isBootstrapping = false,
  hasActiveContext = false,
  isRailOpen = false,
  onToggleRail,
  sourcesCount = 0,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleNav = (route: string) => {
    onNavigate(route);
    setMobileMenuOpen(false);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  return (
    <header className="navbar" role="banner">
      <div className="navbar-inner">
        <div className="navbar-left">
          <a
            href="#research"
            className="brand-link"
            onClick={(e) => {
              e.preventDefault();
              handleNav('research');
            }}
          >
            <BrandMark size={26} />
            <span className="brand-title">
              Deep <b>Research</b>
            </span>
          </a>

          <button
            type="button"
            className="btn-new-research"
            onClick={() => {
              onNewResearch();
              handleNav('research');
            }}
            title="Iniciar uma nova pesquisa"
          >
            <Plus size={16} aria-hidden="true" />
            <span>Nova pesquisa</span>
          </button>

          <nav
            id="main-nav"
            className={`nav-links ${mobileMenuOpen ? 'mobile-open' : ''}`}
            aria-label="Navegação principal"
          >
            <a
              href="#research"
              className={`nav-link ${currentRoute === 'research' ? 'active' : ''}`}
              onClick={(e) => {
                e.preventDefault();
                handleNav('research');
              }}
            >
              <Search size={16} aria-hidden="true" />
              <span>Pesquisa</span>
            </a>
            <a
              href="#history"
              className={`nav-link ${currentRoute === 'history' ? 'active' : ''}`}
              onClick={(e) => {
                e.preventDefault();
                handleNav('history');
              }}
            >
              <History size={16} aria-hidden="true" />
              <span>Histórico</span>
            </a>
            <a
              href="#settings"
              className={`nav-link ${currentRoute === 'settings' ? 'active' : ''}`}
              onClick={(e) => {
                e.preventDefault();
                handleNav('settings');
              }}
            >
              <Settings size={16} aria-hidden="true" />
              <span>Configurações</span>
            </a>
            <a
              href="#docs"
              className={`nav-link ${currentRoute === 'docs' ? 'active' : ''}`}
              onClick={(e) => {
                e.preventDefault();
                handleNav('docs');
              }}
            >
              <BookOpen size={16} aria-hidden="true" />
              <span>Documentação</span>
            </a>
          </nav>
        </div>

        <div className="navbar-right">
          {/* Status da Sessão Integrada (DominusLabs Pill Pattern) */}
          {isBootstrapping ? (
            <div className="pill pill-violet session-badge" title="Conectando a sessão…">
              <span className="spinner spinner--xs" aria-hidden="true" />
              <span>Conectando...</span>
            </div>
          ) : sessionAuthenticated ? (
            <div
              className="pill pill-green session-badge"
              title="Sessão conectada"
            >
              <span className="dot" aria-hidden="true" />
              <span>{sessionAuthenticated ? 'Sessão ativa' : 'Sessão pendente'}</span>
            </div>
          ) : (
            <button
              type="button"
              className="pill pill-amber session-badge btn-pill-action"
              onClick={() => handleNav('settings')}
              title="A sessão não conectou. Abra Configurações."
            >
              <ShieldAlert size={12} aria-hidden="true" />
              <span>Sessão pendente</span>
            </button>
          )}

          {/* Alternador fixo no Header da Janela Lateral de Fontes & Contexto */}
          {hasActiveContext && onToggleRail && (
            <button
              type="button"
              className={`btn-header-rail ${isRailOpen ? 'is-active' : ''}`}
              onClick={onToggleRail}
              aria-label={isRailOpen ? 'Recolher painel lateral de fontes' : 'Abrir painel lateral de fontes'}
              title={isRailOpen ? 'Recolher painel lateral' : 'Abrir painel lateral'}
            >
              <PanelRight size={17} aria-hidden="true" />
              <span className="btn-header-rail-text">Painel</span>
              {sourcesCount > 0 && (
                <span className="btn-header-rail-badge">{sourcesCount}</span>
              )}
            </button>
          )}

          <button
            type="button"
            className="mobile-nav-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Alternar menu de navegação"
            aria-expanded={mobileMenuOpen}
            aria-controls="main-nav"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  );
};

export const Navbar = React.memo(NavbarBase);

