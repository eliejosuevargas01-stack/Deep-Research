import { useState } from 'react';
import { History, Plus, Search, Settings } from 'lucide-react';
import type { RotaV12 } from './SidebarV12';

interface Props {
  rota: RotaV12;
  navegar: (r: RotaV12) => void;
  novaPesquisa: () => void;
}

/** Tab bar inferior (mobile, ≤640px via .mobile-tabbar). */
export function MobileTabBarV12({ rota, navegar, novaPesquisa }: Props) {
  return (
    <nav className="mobile-tabbar" aria-label="Navegação móvel">
      <button
        type="button"
        className={`mobile-tab${rota === 'research' ? ' is-active' : ''}`}
        aria-current={rota === 'research' ? 'page' : undefined}
        onClick={() => navegar('research')}
      >
        <Search size={20} aria-hidden="true" />
        <span>Pesquisa</span>
      </button>
      <button
        type="button"
        className={`mobile-tab${rota === 'history' ? ' is-active' : ''}`}
        aria-current={rota === 'history' ? 'page' : undefined}
        onClick={() => navegar('history')}
      >
        <History size={20} aria-hidden="true" />
        <span>Histórico</span>
      </button>
      <button
        type="button"
        className="mobile-fab"
        onClick={() => {
          novaPesquisa();
          navegar('research');
        }}
        aria-label="Nova pesquisa"
        title="Nova pesquisa"
      >
        <Plus size={22} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={`mobile-tab${rota === 'settings' ? ' is-active' : ''}`}
        aria-current={rota === 'settings' ? 'page' : undefined}
        onClick={() => navegar('settings')}
      >
        <Settings size={20} aria-hidden="true" />
        <span>Ajustes</span>
      </button>
      <span className="mobile-tab" aria-hidden="true" style={{ visibility: 'hidden' }}>
        ·
      </span>
    </nav>
  );
}

/** Hook simples para a sidebar recolhível (persistido por sessão). */
export function useSidebarRecolhida(): { recolhida: boolean; alternar: () => void } {
  const [recolhida, setRecolhida] = useState<boolean>(() => {
    try {
      return localStorage.getItem('dr:v12:sidebar') === 'colapsada';
    } catch {
      return false;
    }
  });
  return {
    recolhida,
    alternar: () =>
      setRecolhida((v) => {
        const proxima = !v;
        try {
          localStorage.setItem('dr:v12:sidebar', proxima ? 'colapsada' : 'aberta');
        } catch {
          /* segue sem persistir */
        }
        return proxima;
      }),
  };
}

export function DummyIcon() {
  return null;
}
