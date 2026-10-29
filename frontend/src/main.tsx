import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './styles/main.css';
import './styles/components.css';
import './styles/planning-view.css';
import './styles/clean-theme.css';
import './styles/open-canvas.css';
import './styles/world.css';
import './styles/linear-timeline.css';
import './styles/gdr-refit.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
