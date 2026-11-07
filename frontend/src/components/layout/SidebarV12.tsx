import {
  History,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Sun,
} from 'lucide-react';
import { BrandMark } from '../BrandMark';
import type { HistoricoItem } from '../../v12/ResearchViews';
import type { Tema } from '../../v12/useTemaV12';

export type RotaV12 = 'research' | 'history' | 'settings';

interface Props {
  rota: RotaV12;
  navegar: (r: RotaV12) => void;
  novaPesquisa: () => void;
  tema: Tema;
  alternarTema: () => void;
  recolhida: boolean;
  alternarRecolher: () => void;
  historico: HistoricoItem[];
  pesquisaAtivaId: string | null;
  abrirPesquisa: (id: string) => void;
}

const ROTAS: Array<{ id: RotaV12; rotulo: string; icone: React.ReactNode }> = [
  { id: 'research', rotulo: 'Pesquisa', icone: <Search size={16} aria-hidden="true" /> },
  { id: 'history', rotulo: 'Histórico', icone: <History size={16} aria-hidden="true" /> },
  { id: 'settings', rotulo: 'Configurações', icone: <Settings size={16} aria-hidden="true" /> },
];

/**
 * Navegação lateral fixa (desktop): rotas + recentes do histórico local.
 * Versão mínima para o V12 — usa só tipos locais, sem o types/api legado.
 */
export function SidebarV12({
  rota,
  navegar,
  novaPesquisa,
  tema,
  alternarTema,
  recolhida,
  alternarRecolher,
  historico,
  pesquisaAtivaId,
  abrirPesquisa,
}: Props) {
  return (
    <aside
      className={`app-sidebar${recolhida ? ' is-collapsed' : ''}`}
      aria-label="Navegação lateral"
    >
      <div className="sidebar-top">
        <a
          href="#research"
          className="sidebar-brand"
          onClick={(e) => {
            e.preventDefault();
            navegar('research');
          }}
          title={recolhida ? 'Deep Research' : undefined}
        >
          <BrandMark size={22} />
          {!recolhida && (
            <span>
              Deep <b>Research</b>
            </span>
          )}
        </a>
        <button
          type="button"
          className="sidebar-collapse"
          onClick={alternarRecolher}
          aria-label={recolhida ? 'Expandir barra lateral' : 'Recolher barra lateral'}
          aria-expanded={!recolhida}
          title={recolhida ? 'Expandir' : 'Recolher'}
        >
          {recolhida ? (
            <PanelLeftOpen size={16} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={16} aria-hidden="true" />
          )}
        </button>
      </div>
      {!recolhida && <span className="sidebar-mode"><span className="sidebar-mode-dot" aria-hidden="true" />v1.2 ao vivo</span>}
      <button
        type="button"
        className="btn-new-research"
        onClick={() => {
          novaPesquisa();
          navegar('research');
        }}
        title={recolhida ? 'Nova pesquisa' : 'Iniciar uma nova pesquisa'}
      >
        <Plus size={16} aria-hidden="true" />
        {!recolhida && <span>Nova pesquisa</span>}
      </button>
      <nav className="sidebar-nav" aria-label="Rotas">
        {ROTAS.map((r) => (
          <button
            key={r.id}
            type="button"
            className={`sidebar-item${rota === r.id ? ' is-active' : ''}`}
            aria-current={rota === r.id ? 'page' : undefined}
            onClick={() => navegar(r.id)}
            title={recolhida ? r.rotulo : undefined}
          >
            <span className="sidebar-item-icon" aria-hidden="true">{r.icone}</span>
            {!recolhida && <span>{r.rotulo}</span>}
          </button>
        ))}
      </nav>
      {!recolhida && (
        <div className="sidebar-conversations" aria-label="Pesquisas recentes">
          <p className="sidebar-group">Recentes</p>
          {historico.length === 0 ? (
            <p className="sidebar-conversations-empty">Nenhuma pesquisa ainda.</p>
          ) : (
            <ul className="sidebar-conversation-list">
              {historico.slice(0, 8).map((h) => (
                <li key={h.research_id}>
                  <button
                    type="button"
                    className={`sidebar-conversation${h.research_id === pesquisaAtivaId ? ' is-active' : ''}`}
                    onClick={() => abrirPesquisa(h.research_id)}
                    title={h.tema || h.research_id}
                  >
                    <span className="sidebar-conversation-title">{h.tema || h.research_id}</span>
                    <span className="sidebar-conversation-meta">{h.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            className="sidebar-history-link"
            onClick={() => navegar('history')}
          >
            Ver todo o histórico
          </button>
        </div>
      )}
      <div className="sidebar-footer">
        <button
          type="button"
          className="sidebar-theme"
          onClick={alternarTema}
          aria-label={tema === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
          aria-pressed={tema === 'dark'}
          title={recolhida ? (tema === 'dark' ? 'Tema claro' : 'Tema escuro') : undefined}
        >
          {tema === 'dark' ? (
            <Sun size={16} aria-hidden="true" />
          ) : (
            <Moon size={16} aria-hidden="true" />
          )}
          {!recolhida && <span>{tema === 'dark' ? 'Tema claro' : 'Tema escuro'}</span>}
        </button>
      </div>
    </aside>
  );
}
