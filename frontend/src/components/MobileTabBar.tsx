import React from 'react';
import { Compass, History, BookOpen, Settings, Plus } from 'lucide-react';

interface MobileTabBarProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  onNewResearch: () => void;
  onOpenSheet: () => void;
  sheetOpen: boolean;
  hasPlan?: boolean;
}

const TABS = [
  { id: 'research', label: 'Pesquisa', icon: Compass },
  { id: 'history', label: 'Histórico', icon: History },
  { id: 'docs', label: 'Guia', icon: BookOpen },
  { id: 'settings', label: 'Ajustes', icon: Settings },
];

/**
 * Navegação de polegar: quatro destinos fixos no rodapé e uma ação primária
 * central. Some no desktop, onde a sidebar assume.
 */
export const MobileTabBar: React.FC<MobileTabBarProps> = ({ currentRoute, onNavigate, onNewResearch, onOpenSheet, sheetOpen }) => (
  <nav className="mobile-tabbar" aria-label="Navegação principal (mobile)">
    {TABS.slice(0, 2).map((t) => {
      const Icon = t.icon;
      const active = currentRoute === t.id;
      return (
        <button
          key={t.id}
          type="button"
          className={`mobile-tab ${active ? 'is-active' : ''}`}
          aria-current={active ? 'page' : undefined}
          onClick={() => onNavigate(t.id)}
        >
          <Icon size={19} aria-hidden="true" />
          <span>{t.label}</span>
        </button>
      );
    })}

    <button type="button" className="mobile-fab" onClick={onNewResearch} aria-label="Nova pesquisa">
      <Plus size={20} aria-hidden="true" />
    </button>

    {TABS.slice(2, 3).map((t) => {
      const Icon = t.icon;
      const active = currentRoute === t.id;
      return (
        <button
          key={t.id}
          type="button"
          className={`mobile-tab ${active ? 'is-active' : ''}`}
          aria-current={active ? 'page' : undefined}
          onClick={() => onNavigate(t.id)}
        >
          <Icon size={19} aria-hidden="true" />
          <span>{t.label}</span>
        </button>
      );
    })}

    <button
      type="button"
      className={`mobile-tab ${sheetOpen ? 'is-active' : ''}`}
      aria-expanded={sheetOpen}
      aria-haspopup="dialog"
      onClick={onOpenSheet}
    >
      <Settings size={19} aria-hidden="true" />
      <span>Ajustes</span>
    </button>
  </nav>
);
