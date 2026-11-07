import { useState } from 'react';
import { Menu, Moon, Plus, Search, History, Settings, Sun, X } from 'lucide-react';
import { BrandMark } from '../BrandMark';
import type { Tema } from '../../v12/useTemaV12';
import type { RotaV12 } from './SidebarV12';

interface Props {
  rota: RotaV12;
  navegar: (r: RotaV12) => void;
  novaPesquisa: () => void;
  tema: Tema;
  alternarTema: () => void;
}

/**
 * Barra superior (mobile, ≤900px): a sidebar some via CSS e esta navbar
 * assume. Desktop: escondida via CSS (.navbar display:none ≥901px).
 */
export function NavbarV12({ rota, navegar, novaPesquisa, tema, alternarTema }: Props) {
  const [aberto, setAberto] = useState(false);
  const ir = (r: RotaV12) => {
    navegar(r);
    setAberto(false);
  };
  const rotulo: Record<RotaV12, string> = {
    research: 'Pesquisa',
    history: 'Histórico',
    settings: 'Configurações',
  };
  return (
    <header className="navbar" role="banner">
      <div className="navbar-inner">
        <div className="navbar-left">
          <a
            href="#research"
            className="brand-link"
            onClick={(e) => {
              e.preventDefault();
              ir('research');
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
              novaPesquisa();
              ir('research');
            }}
            title="Iniciar uma nova pesquisa"
          >
            <Plus size={16} aria-hidden="true" />
            <span>Nova pesquisa</span>
          </button>
          <nav
            className={`nav-links${aberto ? ' mobile-open' : ''}`}
            aria-label="Navegação principal"
          >
            {(['research', 'history', 'settings'] as const).map((r) => (
              <a
                key={r}
                href={`#${r}`}
                className={`nav-link${rota === r ? ' active' : ''}`}
                aria-current={rota === r ? 'page' : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  ir(r);
                }}
              >
                <span>{r === 'research' ? 'Pesquisa' : rotulo[r]}</span>
              </a>
            ))}
          </nav>
        </div>
        <div className="navbar-right">
          <button
            type="button"
            className="theme-toggle"
            onClick={alternarTema}
            aria-label={tema === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
            aria-pressed={tema === 'dark'}
          >
            {tema === 'dark' ? (
              <Sun size={16} aria-hidden="true" />
            ) : (
              <Moon size={16} aria-hidden="true" />
            )}
          </button>
          <button
            type="button"
            className="mobile-nav-toggle"
            aria-expanded={aberto}
            aria-controls="main-nav"
            aria-label={aberto ? 'Fechar menu' : 'Abrir menu'}
            onClick={() => setAberto((v) => !v)}
          >
            {aberto ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
        </div>
      </div>
      {/* Ícones puros decorativos do menu — navegação real fica nos links acima. */}
      <span hidden aria-hidden="true">
        <Search size={1} />
        <History size={1} />
        <Settings size={1} />
      </span>
    </header>
  );
}
