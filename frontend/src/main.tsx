import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppV12 } from './v12/AppV12';
import { ErrorBoundary } from './components/ErrorBoundary';
import './styles/main.css';
import './styles/components.css';
import './styles/mobile-shell.css';
import './styles/theme-contrast.css';
import './v12/v12.css';

// Fluxo ativo: API v1.2 (POST/GET /research, GET/PUT /config). O app legado
// vive em frontend/legacy/ (fora de src, fora do tsconfig/vitest) e não entra no bundle.

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppV12 />
    </ErrorBoundary>
  </React.StrictMode>,
);
