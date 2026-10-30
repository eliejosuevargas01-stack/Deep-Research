import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import './styles/main.css';
import './styles/components.css';
import './styles/planning-view.css';
import './styles/icons-scale.css';
import './styles/clean-theme.css';
import './styles/ambient-cursor.css';
import './styles/open-canvas.css';
import './styles/world.css';
import './styles/linear-timeline.css';
import './styles/gdr-refit.css';
import './styles/theme-contrast.css';
import { initReducedMotionSMIL } from './utils/reduceMotion';

// SMIL (`<animate>`/`animateTransform`/`animateMotion`) não é alcançado por
// `@media (prefers-reduced-motion: reduce)` no CSS: sem `pauseAnimations()`
// os ícones com anel animado seguem girando. Inicializa antes do render para
// que o primeiro paint já respeite a preferência.
initReducedMotionSMIL();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
