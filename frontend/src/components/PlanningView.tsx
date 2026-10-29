import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { formatarTitulo } from '../utils/texto';

export interface PlanningViewProps {
  tema: string;
  iniciadoEm: number;
  raciocinio: string;
  erro?: string | null;
}

const ETAPAS = [
  'Interpretando o pedido',
  'Normalizando escopo e recência',
  'Decompondo em eixos canônicos',
  'Formulando hipóteses falseáveis',
  'Fechando o plano',
];

/** Formata segundos como m:ss, sem depender de locale. */
const formatar = (ms: number): string => {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};

/**
 * Tela intermediária do planejamento: aparece no instante em que o tema é enviado,
 * antes de `POST /plan` responder, e mostra o raciocínio do Planejador em tempo real.
 */
export const PlanningView: React.FC<PlanningViewProps> = ({ tema, iniciadoEm, raciocinio, erro }) => {
  const [agora, setAgora] = useState<number>(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setAgora(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const decorrido = agora - iniciadoEm;
  // Sem eventos do provedor ainda, mantém a primeira etapa; a barra avança devagar.
  const etapasConcluidas = raciocinio.length > 0 ? Math.min(4, 1 + Math.floor(decorrido / 12000)) : 0;
  const progresso = erro ? 0 : Math.min(96, 8 + etapasConcluidas * 22);

  return (
    <section className="planning-view" aria-labelledby="planning-title" aria-busy={!erro}>
      <div className="planning-status">
        <span className="planning-dot" aria-hidden="true" />
        <span className="planning-status-text">
          {erro ? 'O planejador parou' : 'Planejador em ação'}
        </span>
        <span className="planning-elapsed" aria-live="off">{formatar(decorrido)}</span>
      </div>

      <h1 id="planning-title" className="planning-theme">{formatarTitulo(tema)}</h1>
      <p className="planning-subtitle">
        Decompondo o tema em eixos investigativos com hipóteses falseáveis, escopo temporal e
        critérios de conclusão.
      </p>

      <div
        className="planning-progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progresso}
        aria-label="Progresso do planejamento"
      >
        <span style={{ transform: `scaleX(${Math.max(0, Math.min(100, progresso)) / 100})` }} />
      </div>

      <ol className="planning-steps">
        {ETAPAS.map((etapa, indice) => {
          const concluida = indice < etapasConcluidas;
          const ativa = indice === etapasConcluidas && !erro;
          return (
            <li key={etapa} className={`planning-step ${concluida ? 'is-done' : ''} ${ativa ? 'is-active' : ''}`}>
              <span className="planning-step-mark" aria-hidden="true">{concluida ? '✓' : indice + 1}</span>
              <span className="planning-step-label">{etapa}</span>
              {ativa && <span className="planning-step-hint">em curso</span>}
            </li>
          );
        })}
      </ol>

      <div className="planning-reasoning">
        <p className="planning-reasoning-label">Raciocínio do planejador</p>
        {raciocinio ? (
          <pre className="planning-reasoning-text">{raciocinio}</pre>
        ) : (
          <p className="planning-reasoning-empty">
            {erro ? 'Sem raciocínio registrado para esta tentativa.' : 'Aguardando o primeiro token do modelo…'}
          </p>
        )}
      </div>

      {erro && (
        <div className="planning-error" role="alert">
          <AlertTriangle size={17} aria-hidden="true" />
          <div>
            <strong>Não foi possível elaborar o plano</strong>
            <p>{erro}</p>
          </div>
        </div>
      )}
    </section>
  );
};
