import { useEffect, useState } from 'react';

/** Chave do tema no localStorage (mesma convenção do app legado). */
export const CHAVE_TEMA = 'dr:v12:tema';

export type Tema = 'light' | 'dark';

export function lerTemaInicial(): Tema {
  try {
    return localStorage.getItem(CHAVE_TEMA) === 'dark' ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

/** Aplica data-theme no <html> e persiste. Light = sem atributo (padrão). */
export function aplicarTema(tema: Tema): void {
  if (tema === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  try {
    localStorage.setItem(CHAVE_TEMA, tema);
  } catch {
    /* segue sem persistir */
  }
}

/** Hook de tema claro/escuro para o shell V12. */
export function useTemaV12(): { tema: Tema; alternar: () => void } {
  // (ponytail: sem matchMedia; adicionar quando houver pedido de modo sistema.)
  const [tema, setTema] = useState<Tema>(() => lerTemaInicial());
  useEffect(() => {
    aplicarTema(tema);
  }, [tema]);
  return { tema, alternar: () => setTema((t) => (t === 'dark' ? 'light' : 'dark')) };
}
