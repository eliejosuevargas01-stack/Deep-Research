export type ConvergencePhase = 'stream' | 'audit' | 'synthesis';
export type PersonaType =
  | 'planejador'
  | 'futurista'
  | 'cetico'
  | 'visionario'
  | 'historiador'
  | 'auditor'
  | 'redator';

/**
 * Preset de Identidade Visual exportado: P1·F1·C1·V1·H1·A1·R1
 * StrokeWidth: 2.2-2.4px | ColorMode: semantic (currentColor + accents)
 */
const CONVERGENCE_PHASE_SVG: Record<ConvergencePhase, string> = {
  stream: `<!-- Convergencia - Fase 01: Investigacao em Paralelo (Stream SSE) -->
  <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1.5 2"/>
  <circle cx="12" cy="20" r="1.27" stroke="currentColor" stroke-width="2.2"/>
  <path d="M6 3.5V10.5M12 3.5V10.5M18 3.5V10.5" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="6" y1="3.5" x2="6" y2="10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="2.5 5.5">
    <animate attributeName="stroke-dashoffset" from="8" to="0" dur="0.733s" repeatCount="indefinite"/>
  </line>
  <line x1="12" y1="3.5" x2="12" y2="10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="2.5 5.5">
    <animate attributeName="stroke-dashoffset" from="8" to="0" dur="0.567s" repeatCount="indefinite"/>
  </line>
  <line x1="18" y1="3.5" x2="18" y2="10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="2.5 5.5">
    <animate attributeName="stroke-dashoffset" from="8" to="0" dur="0.867s" repeatCount="indefinite"/>
  </line>
  <circle cx="6" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="12" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="18" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="12" cy="10.5" r="0.98" fill="currentColor"><animate attributeName="r" values="0.68;1.42;0.68" dur="0.567s" repeatCount="indefinite"/></circle>`,
  audit: `<!-- Convergencia - Fase 02: Gate de Auditoria (11/12) -->
  <path d="M6 3.5V10.5M12 3.5V10.5M18 3.5V10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <circle cx="6" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="12" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="18" cy="3.5" r="0.98" fill="currentColor"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1.5 2"/>
  <circle cx="12" cy="20" r="1.27" stroke="currentColor" stroke-width="2.2"/>
  <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="#fbbf24" stroke-width="2.29" stroke-linecap="round"/>
  <line x1="3.5" y1="8.5" x2="3.5" y2="12.5" stroke="#fbbf24" stroke-width="2.2" stroke-linecap="round"><animate attributeName="x1" values="3.2;4.4;3.2" dur="0.933s" repeatCount="indefinite"/><animate attributeName="x2" values="3.2;4.4;3.2" dur="0.933s" repeatCount="indefinite"/></line>
  <line x1="20.5" y1="8.5" x2="20.5" y2="12.5" stroke="#fbbf24" stroke-width="2.2" stroke-linecap="round"><animate attributeName="x1" values="20.8;19.6;20.8" dur="0.933s" repeatCount="indefinite"/><animate attributeName="x2" values="20.8;19.6;20.8" dur="0.933s" repeatCount="indefinite"/></line>
  <circle cx="6" cy="10.5" r="1.05" fill="#fbbf24"/>
  <circle cx="12" cy="10.5" r="1.27" fill="#fbbf24"><animate attributeName="r" values="1.05;1.72;1.05" dur="0.733s" repeatCount="indefinite"/></circle>
  <circle cx="18" cy="10.5" r="1.05" fill="#fbbf24"/>
  <circle cx="6" cy="10.5" r="1.88" stroke="#fbbf24" stroke-width="1.2" fill="none">
    <animate attributeName="cx" values="6;12;18;12;6" dur="1.467s" repeatCount="indefinite"/>
  </circle>`,
  synthesis: `<!-- Convergencia - Fase 03: Sintese Final (Dossie Consolidado) -->
  <path d="M6 3.5V10.5M18 3.5V10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M12 3.5V10.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
  <circle cx="6" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="12" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="18" cy="3.5" r="0.98" fill="currentColor"/>
  <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="3.5 6.5">
    <animate attributeName="stroke-dashoffset" from="10" to="0" dur="0.733s" repeatCount="indefinite"/>
  </path>
  <circle cx="12" cy="20" r="1.80" stroke="#34d399" stroke-width="1.2" fill="none">
    <animate attributeName="r" values="1.80;3.75" dur="0.933s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.8;0" dur="0.933s" repeatCount="indefinite"/>
  </circle>
  <circle cx="12" cy="20" r="1.80" fill="#34d399"/>`
};

const PERSONA_CHOSEN_SVG: Record<PersonaType, string> = {
  planejador: `<!-- Persona: planejador (Opcao 01) -->
  <path d="M12 4V9.5M12 9.5L6 14V20M12 9.5V20M12 9.5L18 14V20" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M12 4V9.5M12 9.5L6 14V20M12 9.5V20M12 9.5L18 14V20" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4 8">
    <animate attributeName="stroke-dashoffset" from="12" to="0" dur="0.8s" repeatCount="indefinite"/>
  </path>
  <circle cx="12" cy="4" r="1.58" fill="currentColor"><animate attributeName="r" values="1.13;2.03;1.13" dur="0.8s" repeatCount="indefinite"/></circle>
  <circle cx="6" cy="20" r="1.13" fill="currentColor"/>
  <circle cx="12" cy="20" r="1.13" fill="currentColor"/>
  <circle cx="18" cy="20" r="1.13" fill="currentColor"/>`,
  futurista: `<!-- Persona: futurista (Opcao 01) -->
  <path d="M4 12L19 5M4 12L19 19" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M4 12L19 5M4 12L19 19" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="4 10"><animate attributeName="stroke-dashoffset" from="14" to="0" dur="0.733s" repeatCount="indefinite"/></path>
  <line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="1.5 2"/>
  <path d="M19 5V19" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="1.5 2"/>
  <circle cx="4" cy="12" r="1.58" fill="currentColor"/>
  <circle cx="19" cy="5" r="1.13" fill="currentColor"/>
  <circle cx="19" cy="19" r="1.13" fill="currentColor"/>`,
  cetico: `<!-- Persona: cetico (Opcao 01) -->
  <path d="M4 9H20M4 15H20" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M16.5 3.5L7.5 20.5" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M16.5 3.5L7.5 20.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="5 15"><animate attributeName="stroke-dashoffset" from="20" to="0" dur="0.7s" repeatCount="indefinite"/></path>
  <circle cx="13.6" cy="9" r="1.13" fill="currentColor"/>
  <circle cx="10.4" cy="15" r="1.13" fill="currentColor"/>`,
  visionario: `<!-- Persona: visionario (Opcao 01) -->
  <path d="M6 4V20M18 4V20" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M6 16L18 8" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M6 16L18 8" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="4 11"><animate attributeName="stroke-dashoffset" from="15" to="0" dur="0.667s" repeatCount="indefinite"/></path>
  <circle cx="6" cy="16" r="1.58" fill="currentColor"/>
  <circle cx="18" cy="8" r="1.58" fill="currentColor"/>`,
  historiador: `<!-- Persona: historiador (Opcao 01) -->
  <path d="M5 7H19M4 12H20M6 17H18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="12" y1="3.5" x2="12" y2="17" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="12" y1="3.5" x2="12" y2="17" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="4 10"><animate attributeName="stroke-dashoffset" from="14" to="0" dur="0.733s" repeatCount="indefinite"/></line>
  <circle cx="12" cy="17" r="1.58" fill="currentColor"/>`,
  auditor: `<!-- Persona: auditor (Opcao 01) -->
  <path d="M12 3.5V20.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="1.5 2"/>
  <line x1="3.5" y1="12" x2="20.5" y2="12" stroke="#fbbf24" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="7.5" y1="8.5" x2="7.5" y2="15.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><animate attributeName="x1" values="7.2;8.6;7.2" dur="0.8s" repeatCount="indefinite"/><animate attributeName="x2" values="7.2;8.6;7.2" dur="0.8s" repeatCount="indefinite"/></line>
  <line x1="16.5" y1="8.5" x2="16.5" y2="15.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><animate attributeName="x1" values="16.8;15.4;16.8" dur="0.8s" repeatCount="indefinite"/><animate attributeName="x2" values="16.8;15.4;16.8" dur="0.8s" repeatCount="indefinite"/></line>
  <circle cx="12" cy="12" r="1.58" fill="#fbbf24"/>`,
  redator: `<!-- Persona: redator (Opcao 01) -->
  <path d="M6 4L12 11.5M18 4L12 11.5M12 4V16" stroke="currentColor" stroke-opacity="0.6" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6 4L12 11.5M18 4L12 11.5M12 4V16" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4 9"><animate attributeName="stroke-dashoffset" from="13" to="0" dur="0.733s" repeatCount="indefinite"/></path>
  <circle cx="12" cy="16" r="1.58" fill="#34d399"/>
  <line x1="7" y1="20" x2="17" y2="20" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><animate attributeName="x2" values="9;17;17" dur="0.933s" repeatCount="indefinite"/></line>`
};

export function ConvergenceLogo({
  phase = 'synthesis',
  size = 20,
  className = ''
}: {
  phase?: ConvergencePhase;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      dangerouslySetInnerHTML={{ __html: CONVERGENCE_PHASE_SVG[phase] }}
    />
  );
}

export function PersonaIcon({
  persona,
  size = 16,
  className = '',
  ativo = false,
}: {
  persona: PersonaType;
  size?: number;
  className?: string;
  /** Colore e destaca só enquanto a persona está trabalhando. */
  ativo?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      data-persona={persona}
      className={`persona-icon${ativo ? ' persona-icon--ativo' : ''}${className ? ` ${className}` : ''}`}
      dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG[persona] }}
    />
  );
}
