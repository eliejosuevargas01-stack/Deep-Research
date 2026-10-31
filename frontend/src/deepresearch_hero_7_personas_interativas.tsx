// @ts-nocheck
// Componente de referência visual (hero das 7 personas). Fora da árvore do app.
import React, { useState, useEffect, useRef, useMemo } from 'react';

/**
 * ============================================================================
 * PRESET ORIGINAL DO SISTEMA (P1·F1·C1·V1·H1·A1·R1)
 * ============================================================================
 */
const CONVERGENCE_PHASE_SVG = {
  stream: `<!-- Convergencia - Fase 01: Investigacao em Paralelo (Stream SSE) -->
  <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="#52525b" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="#52525b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1.5 2"/>
  <circle cx="12" cy="20" r="1.27" stroke="#52525b" stroke-width="1.5"/>
  <path d="M6 3.5V10.5M12 3.5V10.5M18 3.5V10.5" stroke="#71717a" stroke-opacity="0.45" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="6" y1="3.5" x2="6" y2="10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2.5 5.5">
    <animate attributeName="stroke-dashoffset" from="8" to="0" dur="1.10s" repeatCount="indefinite"/>
  </line>
  <line x1="12" y1="3.5" x2="12" y2="10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2.5 5.5">
    <animate attributeName="stroke-dashoffset" from="8" to="0" dur="0.85s" repeatCount="indefinite"/>
  </line>
  <line x1="18" y1="3.5" x2="18" y2="10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2.5 5.5">
    <animate attributeName="stroke-dashoffset" from="8" to="0" dur="1.30s" repeatCount="indefinite"/>
  </line>
  <circle cx="6" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="12" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="18" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="12" cy="10.5" r="0.98" fill="currentColor"><animate attributeName="r" values="0.68;1.42;0.68" dur="0.85s" repeatCount="indefinite"/></circle>`,
  audit: `<!-- Convergencia - Fase 02: Gate de Auditoria (11/12) -->
  <path d="M6 3.5V10.5M12 3.5V10.5M18 3.5V10.5" stroke="#71717a" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="6" cy="3.5" r="0.98" fill="#71717a"/>
  <circle cx="12" cy="3.5" r="0.98" fill="#71717a"/>
  <circle cx="18" cy="3.5" r="0.98" fill="#71717a"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="#52525b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1.5 2"/>
  <circle cx="12" cy="20" r="1.27" stroke="#52525b" stroke-width="1.5"/>
  <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="#fbbf24" stroke-width="1.72" stroke-linecap="round"/>
  <line x1="3.5" y1="8.5" x2="3.5" y2="12.5" stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round"><animate attributeName="x1" values="3.2;4.4;3.2" dur="1.40s" repeatCount="indefinite"/><animate attributeName="x2" values="3.2;4.4;3.2" dur="1.40s" repeatCount="indefinite"/></line>
  <line x1="20.5" y1="8.5" x2="20.5" y2="12.5" stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round"><animate attributeName="x1" values="20.8;19.6;20.8" dur="1.40s" repeatCount="indefinite"/><animate attributeName="x2" values="20.8;19.6;20.8" dur="1.40s" repeatCount="indefinite"/></line>
  <circle cx="6" cy="10.5" r="1.05" fill="#fbbf24"/>
  <circle cx="12" cy="10.5" r="1.27" fill="#fbbf24"><animate attributeName="r" values="1.05;1.72;1.05" dur="1.10s" repeatCount="indefinite"/></circle>
  <circle cx="18" cy="10.5" r="1.05" fill="#fbbf24"/>
  <circle cx="6" cy="10.5" r="1.88" stroke="#fbbf24" stroke-width="0.9" fill="none">
    <animate attributeName="cx" values="6;12;18;12;6" dur="2.20s" repeatCount="indefinite"/>
  </circle>`,
  synthesis: `<!-- Convergencia - Fase 03: Sintese Final (Dossie Consolidado) -->
  <path d="M6 3.5V10.5M18 3.5V10.5" stroke="#71717a" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M12 3.5V10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="6" cy="3.5" r="0.98" fill="#71717a"/>
  <circle cx="12" cy="3.5" r="0.98" fill="currentColor"/>
  <circle cx="18" cy="3.5" r="0.98" fill="#71717a"/>
  <line x1="3.5" y1="10.5" x2="20.5" y2="10.5" stroke="#71717a" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="#71717a" stroke-opacity="0.45" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6 10.5L12 16.5M18 10.5L12 16.5M12 10.5V19.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="3.5 6.5">
    <animate attributeName="stroke-dashoffset" from="10" to="0" dur="1.10s" repeatCount="indefinite"/>
  </path>
  <circle cx="12" cy="20" r="1.80" stroke="#34d399" stroke-width="0.9" fill="none">
    <animate attributeName="r" values="1.80;3.75" dur="1.40s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.8;0" dur="1.40s" repeatCount="indefinite"/>
  </circle>
  <circle cx="12" cy="20" r="1.80" fill="#34d399"/>`
};

const PERSONA_CHOSEN_SVG = {
  planejador: `<!-- Persona: planejador (Opcao 01) -->
  <path d="M12 4V9.5M12 9.5L6 14V20M12 9.5V20M12 9.5L18 14V20" stroke="#71717a" stroke-opacity="0.45" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M12 4V9.5M12 9.5L6 14V20M12 9.5V20M12 9.5L18 14V20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4 8">
    <animate attributeName="stroke-dashoffset" from="12" to="0" dur="1.20s" repeatCount="indefinite"/>
  </path>
  <circle cx="12" cy="4" r="1.58" fill="currentColor"><animate attributeName="r" values="1.13;2.03;1.13" dur="1.20s" repeatCount="indefinite"/></circle>
  <circle cx="6" cy="20" r="1.13" fill="#71717a"/>
  <circle cx="12" cy="20" r="1.13" fill="currentColor"/>
  <circle cx="18" cy="20" r="1.13" fill="#71717a"/>`,
  futurista: `<!-- Persona: futurista (Opcao 01) -->
  <path d="M4 12L19 5M4 12L19 19" stroke="#71717a" stroke-opacity="0.45" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M4 12L19 5M4 12L19 19" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="4 10"><animate attributeName="stroke-dashoffset" from="14" to="0" dur="1.10s" repeatCount="indefinite"/></path>
  <line x1="4" y1="12" x2="20" y2="12" stroke="#71717a" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.5 2"/>
  <path d="M19 5V19" stroke="#71717a" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.5 2"/>
  <circle cx="4" cy="12" r="1.58" fill="currentColor"/>
  <circle cx="19" cy="5" r="1.13" fill="currentColor"/>
  <circle cx="19" cy="19" r="1.13" fill="currentColor"/>`,
  cetico: `<!-- Persona: cetico (Opcao 01) -->
  <path d="M4 9H20M4 15H20" stroke="#71717a" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M16.5 3.5L7.5 20.5" stroke="#71717a" stroke-opacity="0.4" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M16.5 3.5L7.5 20.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="5 15"><animate attributeName="stroke-dashoffset" from="20" to="0" dur="1.05s" repeatCount="indefinite"/></path>
  <circle cx="13.6" cy="9" r="1.13" fill="currentColor"/>
  <circle cx="10.4" cy="15" r="1.13" fill="currentColor"/>`,
  visionario: `<!-- Persona: visionario (Opcao 01) -->
  <path d="M6 4V20M18 4V20" stroke="#71717a" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M6 16L18 8" stroke="#71717a" stroke-opacity="0.4" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M6 16L18 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="4 11"><animate attributeName="stroke-dashoffset" from="15" to="0" dur="1.00s" repeatCount="indefinite"/></path>
  <circle cx="6" cy="16" r="1.58" fill="currentColor"/>
  <circle cx="18" cy="8" r="1.58" fill="currentColor"/>`,
  historiador: `<!-- Persona: historiador (Opcao 01) -->
  <path d="M5 7H19M4 12H20M6 17H18" stroke="#71717a" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="12" y1="3.5" x2="12" y2="17" stroke="#71717a" stroke-opacity="0.4" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="12" y1="3.5" x2="12" y2="17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="4 10"><animate attributeName="stroke-dashoffset" from="14" to="0" dur="1.10s" repeatCount="indefinite"/></line>
  <circle cx="12" cy="17" r="1.58" fill="currentColor"/>`,
  auditor: `<!-- Persona: auditor (Opcao 01) -->
  <path d="M12 3.5V20.5" stroke="#71717a" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.5 2"/>
  <line x1="3.5" y1="12" x2="20.5" y2="12" stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="7.5" y1="8.5" x2="7.5" y2="15.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><animate attributeName="x1" values="7.2;8.6;7.2" dur="1.20s" repeatCount="indefinite"/><animate attributeName="x2" values="7.2;8.6;7.2" dur="1.20s" repeatCount="indefinite"/></line>
  <line x1="16.5" y1="8.5" x2="16.5" y2="15.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><animate attributeName="x1" values="16.8;15.4;16.8" dur="1.20s" repeatCount="indefinite"/><animate attributeName="x2" values="16.8;15.4;16.8" dur="1.20s" repeatCount="indefinite"/></line>
  <circle cx="12" cy="12" r="1.58" fill="#fbbf24"/>`,
  redator: `<!-- Persona: redator (Opcao 01) -->
  <path d="M6 4L12 11.5M18 4L12 11.5M12 4V16" stroke="#71717a" stroke-opacity="0.4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6 4L12 11.5M18 4L12 11.5M12 4V16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4 9"><animate attributeName="stroke-dashoffset" from="13" to="0" dur="1.10s" repeatCount="indefinite"/></path>
  <circle cx="12" cy="16" r="1.58" fill="#34d399"/>
  <line x1="7" y1="20" x2="17" y2="20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><animate attributeName="x2" values="9;17;17" dur="1.40s" repeatCount="indefinite"/></line>`
};

export function ConvergenceLogo({ phase = 'synthesis', size = 20, className = '' }) {
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

export function PersonaIcon({ persona, size = 16, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG[persona] }}
    />
  );
}

/**
 * ============================================================================
 * POSICIONAMENTO DOS 7 PERSONAGENS NO PALCO SVG (1040 x 290)
 * Estrutura:
 * '[planejador]' - '[historiador][visionario][futurista]' - '[cetico]' --- '[auditor]' - '[redator]'
 * ============================================================================
 */
const PERSONAS_META = [
  {
    id: 'planejador',
    name: 'Planejador',
    x: 105,
    y: 185,
    color: '#a855f7'
  },
  {
    id: 'historiador',
    name: 'Historiador',
    x: 262,
    y: 192,
    color: '#d97706'
  },
  {
    id: 'visionario',
    name: 'Visionário',
    x: 326,
    y: 178,
    color: '#38bdf8'
  },
  {
    id: 'futurista',
    name: 'Futurista',
    x: 390,
    y: 190,
    color: '#818cf8'
  },
  {
    id: 'cetico',
    name: 'Cético',
    x: 472, // Mais próximo do Futurista (gap curto '-')
    y: 192,
    color: '#f43f5e'
  },
  {
    id: 'auditor',
    name: 'Auditor',
    x: 765, // Separado pelo grande vão '---'
    y: 196,
    color: '#fbbf24'
  },
  {
    id: 'redator',
    name: 'Redator',
    x: 895, // Nas costas do Auditor
    y: 186,
    color: '#34d399'
  }
];

function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

/**
 * ============================================================================
 * COMPONENTE PURO E EXPORTÁVEL DA ANIMAÇÃO DAS 7 PERSONAS
 * Pode ser importado diretamente na tela inicial do DeepResearch
 * ============================================================================
 */
export function DeepResearchCharacters({
  phase = 'interactive', // 'interactive' | 'planning' | 'searching' | 'audit_fail' | 'synthesis'
  isTyping = false,
  typingProgress = 0.5,
  theme = 'dark',
  showCeticoRadius = true,
  className = ''
}) {
  const isDark = theme === 'dark';
  const [hoveredPersona, setHoveredPersona] = useState(null);
  const [whistleActive, setWhistleActive] = useState(false);
  const [hatTipActive, setHatTipActive] = useState(false);
  const [ceticoGlareActive, setCeticoGlareActive] = useState(false);
  const [redatorWaveActive, setRedatorWaveActive] = useState(false);

  const svgRef = useRef(null);
  const targetMouse = useRef({ x: 520, y: 140, inside: false });
  const smoothMouse = useRef({ x: 520, y: 140 });
  const [renderState, setRenderState] = useState({
    mx: 520,
    my: 140,
    time: 0
  });

  // Loop de física: suave a 60fps, com animações contínuas de respiração e rastreamento de mouse
  const fisicaRef = useRef({ mx: 520, my: 140, start: performance.now(), userInteracted: false });
  useEffect(() => {
    let rafId: number;
    fisicaRef.current.start = performance.now();

    const tick = (now: number) => {
      const elapsed = (now - fisicaRef.current.start) / 1000;

      let targetX = targetMouse.current.x;
      let targetY = targetMouse.current.y;

      if (phase === 'planning') {
        targetX = 150 + Math.sin(elapsed * 2.2) * 60;
        targetY = 160;
      } else if (phase === 'searching') {
        targetX = 620 + Math.sin(elapsed * 3.5) * 80;
        targetY = 175 + Math.cos(elapsed * 2.5) * 25;
      } else if (phase === 'audit_fail') {
        targetX = 472;
        targetY = 185;
      } else if (phase === 'synthesis') {
        targetX = 895;
        targetY = 175;
      } else if (isTyping && !fisicaRef.current.userInteracted) {
        targetX = 260 + clamp(typingProgress, 0, 1) * 520;
        targetY = 320;
      }

      // Interpolação responsiva e fluida (lerp 0.28 para resposta imediata)
      smoothMouse.current.x += (targetX - smoothMouse.current.x) * 0.28;
      smoothMouse.current.y += (targetY - smoothMouse.current.y) * 0.28;

      // Atualiza sempre para manter vivas as micro-animações ociosas (respiração/bobbing)
      setRenderState({
        mx: smoothMouse.current.x,
        my: smoothMouse.current.y,
        time: elapsed
      });

      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [isTyping, typingProgress, phase]);

  // Rastreamento confiável do mouse/toque em qualquer ponto da janela
  useEffect(() => {
    const aoMover = (e: MouseEvent | PointerEvent | Touch) => {
      if (!svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x = (e.clientX - rect.left) * (1020 / rect.width);
      const y = (e.clientY - rect.top) * (290 / rect.height);
      fisicaRef.current.userInteracted = true;
      targetMouse.current = {
        x: clamp(x, -350, 1370),
        y: clamp(y, -250, 540),
        inside: true,
      };
    };

    const handlePointer = (e: PointerEvent) => aoMover(e);
    const handleMouse = (e: MouseEvent) => aoMover(e);
    const handleTouch = (e: TouchEvent) => {
      if (e.touches && e.touches[0]) aoMover(e.touches[0]);
    };

    window.addEventListener('pointermove', handlePointer, { passive: true });
    window.addEventListener('mousemove', handleMouse, { passive: true });
    window.addEventListener('touchmove', handleTouch, { passive: true });
    window.addEventListener('touchstart', handleTouch, { passive: true });

    return () => {
      window.removeEventListener('pointermove', handlePointer);
      window.removeEventListener('mousemove', handleMouse);
      window.removeEventListener('touchmove', handleTouch);
      window.removeEventListener('touchstart', handleTouch);
    };
  }, []);

  const handlePointerMove = () => undefined;

  const handlePointerLeave = () => {
    // Mantém o olhar suave na última direção
  };

  const handleCharacterClick = (id: string) => {
    if (id === 'auditor') {
      setWhistleActive(true);
      setTimeout(() => setWhistleActive(false), 2200);
    } else if (id === 'planejador') {
      setHatTipActive(true);
      setTimeout(() => setHatTipActive(false), 1600);
    } else if (id === 'cetico') {
      setCeticoGlareActive(true);
      setTimeout(() => setCeticoGlareActive(false), 2000);
    } else if (id === 'redator') {
      setRedatorWaveActive(true);
      setTimeout(() => setRedatorWaveActive(false), 1800);
    }
  };

  /**
   * Círculo (invisível) onde os olhos se movem livremente em 360° com liberdade ampliada,
   * garantindo que a pupila nunca escape da órbita nem desça até a boca.
   */
  const getOrbitalEye = (ox: number, oy: number, maxRx = 4.2, maxRy = 2.1) => {
    const nx = ox / maxRx;
    const ny = oy / maxRy;
    const mag = Math.hypot(nx, ny);
    if (mag > 1) {
      return {
        x: (nx / mag) * maxRx,
        y: (ny / mag) * maxRy
      };
    }
    return { x: ox, y: oy };
  };

  const getLookVector = (charX: number, charY: number, maxDx = 9, maxDy = 3.5) => {
    const dx = renderState.mx - charX;
    const dy = renderState.my - charY;
    const dist = Math.hypot(dx, dy) || 1;
    const factor = clamp(dist / 40, 0, 1);

    // Vetor base em direção ao cursor
    const rawOx = (dx / dist) * maxDx * factor;
    const rawOy = (dy / dist) * maxDy * factor;

    // ============================================================
    // CAMPO DE NÃO-REAÇÃO / OLHAR FRONTAL PARA A CÂMERA (PONTO CENTRAL)
    // Cada especialista tem seu ponto central (charX, charY).
    // Quando o mouse está logo acima dele no eixo central (dy < 20 e |dx| < 45)
    // ou na proximidade imediata da cabeça (dist < 34),
    // ele não deve seguir o mouse para cima, e sim olhar
    // diretamente para a câmera (olhar neutro centralizado ox: 0, oy: 0).
    // O mesmo vale para o Planejador (x: 105), Redator (x: 890) e todos os 7.
    // ============================================================
    let cameraBlend = 0;

    // Cone vertical acima do especialista (estrito ao eixo do personagem)
    if (dy < 20 && Math.abs(dx) < 45) {
      const xRatio = Math.abs(dx) / 45;
      const xWeight = 1 - Math.pow(xRatio, 1.4);
      const yWeight = dy <= 0 ? 1 : Math.max(0, (20 - dy) / 20);
      cameraBlend = Math.max(cameraBlend, xWeight * yWeight);
    }

    // Raio de proximidade imediata ao redor do ponto central
    if (dist < 34) {
      cameraBlend = Math.max(cameraBlend, 1 - Math.pow(dist / 34, 1.4));
    }

    // Suaviza transição para o ponto central (ox: 0, oy: 0)
    const ox = rawOx * (1 - cameraBlend);
    const oy = rawOy * (1 - cameraBlend);

    return {
      ox,
      oy,
      angle: Math.atan2(dy, dx) * (180 / Math.PI),
      dist,
      cameraBlend
    };
  };

  const { mx, my, time } = renderState;

  // Zona de 15cm do Cético (raio = 44px centrado entre o rosto e o livro em x=492, y=155)
  const CETICO_RADIUS = 44;
  const ceticoDist = Math.hypot(mx - 492, my - 155);
  const ceticoCares =
    ceticoDist < CETICO_RADIUS ||
    ceticoGlareActive ||
    hoveredPersona === 'cetico' ||
    phase === 'audit_fail';

  const isAuditorBlowingWhistle =
    whistleActive || phase === 'audit_fail' || hoveredPersona === 'auditor';

  const ui = isDark
    ? {
        strokeMain: '#f4f4f5',
        strokeSecondary: '#a1a1aa',
        headFill: '#18181b',
        stageFloor: '#27272a'
      }
    : {
        strokeMain: '#272522',
        strokeSecondary: '#57534e',
        headFill: '#F7F5F0',
        stageFloor: '#CFC9BC'
      };

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 1020 290"
      className={`w-full h-auto overflow-visible select-none ${className}`}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <defs>
        <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="3.5" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>

        <linearGradient id="fedoraGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#92400e" />
          <stop offset="100%" stopColor="#5b2606" />
        </linearGradient>

        <linearGradient id="brownBookGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7c2d12" />
          <stop offset="100%" stopColor="#431407" />
        </linearGradient>

        <linearGradient id="policeCapGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e293b" />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>
      </defs>

      {/* ============================================================
          LINHA DE SOLO E ESPAÇAMENTOS ARQUITETURAIS
          [planejador] - [historiador][visionario][futurista] - [cetico] --- [auditor] - [redator]
      ============================================================ */}
      <g className="opacity-85">
        <line
          x1="35"
          y1="242"
          x2="975"
          y2="242"
          stroke={ui.stageFloor}
          strokeWidth="2"
          strokeLinecap="round"
        />

        {/* Traço curto '-' entre Planejador e Trio */}
        <line
          x1="168"
          y1="200"
          x2="196"
          y2="200"
          stroke={ui.strokeSecondary}
          strokeWidth="2"
          strokeDasharray="4 4"
          opacity="0.45"
        />

        {/* Traço curto '-' entre Futurista (390) e Cético (472) */}
        <line
          x1="422"
          y1="200"
          x2="442"
          y2="200"
          stroke={ui.strokeSecondary}
          strokeWidth="2"
          strokeDasharray="4 4"
          opacity="0.45"
        />

        {/* GRANDE VÃO DE CONFRONTO '---' ENTRE CÉTICO (472) E AUDITOR (765) */}
        <g>
          <line
            x1="538"
            y1="196"
            x2="695"
            y2="196"
            stroke={isAuditorBlowingWhistle ? '#ef4444' : '#fbbf24'}
            strokeWidth="2"
            strokeDasharray="8 6"
            opacity={isAuditorBlowingWhistle ? '0.9' : '0.45'}
          />

          {/* Partículas de evidências viajando dos buscadores para o Auditor no vão '---' */}
          <g>
            {[0, 1, 2].map((idx) => {
              const progress = (time * 0.65 + idx * 0.33) % 1;
              const px =
                isAuditorBlowingWhistle && progress > 0.75
                  ? 538 + (1 - progress) * 180
                  : 538 + progress * 150;
              const py = 175 + Math.sin(progress * Math.PI * 2 + idx) * 12;
              return (
                <g key={idx} transform={`translate(${px}, ${py})`}>
                  <circle
                    r="3"
                    fill={isAuditorBlowingWhistle && progress > 0.7 ? '#ef4444' : '#38bdf8'}
                  />
                  <circle
                    r="5.5"
                    stroke={isAuditorBlowingWhistle && progress > 0.7 ? '#ef4444' : '#38bdf8'}
                    strokeWidth="1"
                    fill="none"
                    opacity="0.4"
                  />
                </g>
              );
            })}
          </g>
        </g>
      </g>

      {/* ============================================================
          1. PLANEJADOR (x: 105, y: 185) — Ponto Central: (105, 141)
      ============================================================ */}
      {(() => {
        const look = getLookVector(105, 141, 9, 3.5);
        const bob = Math.sin(time * 2.1) * 2.2;
        const isHovered = hoveredPersona === 'planejador';
        // Cabeça firme: micro-inclinação anatômica de no máx 3.5°
        const headTilt = clamp(look.ox * 0.25, -3.5, 3.5);
        const hatLift = hatTipActive || isHovered ? -7 : 0;
        const hatRotate = hatTipActive ? -14 : isHovered ? -5 : -2;

        return (
          <g
            transform="translate(105, 185)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('planejador')}
            onMouseEnter={() => setHoveredPersona('planejador')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            <ellipse cx="0" cy="57" rx="26" ry="5" fill={ui.strokeMain} opacity="0.12" />

            <path
              d="M -4 16 L -12 56 M 5 16 L 13 56"
              stroke={ui.strokeMain}
              strokeWidth="3.2"
              strokeLinecap="round"
            />
            <path
              d="M -12 56 L -19 56 M 13 56 L 20 56"
              stroke="#78350f"
              strokeWidth="4.5"
              strokeLinecap="round"
            />

            <g transform={`translate(0, ${bob})`}>
              <path
                d="M -11 -18 L -14 16 L 14 16 L 11 -18 Z"
                fill="#78350f"
                fillOpacity="0.25"
                stroke="#92400e"
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
              <line
                x1="0"
                y1="-22"
                x2="0"
                y2="17"
                stroke={ui.strokeMain}
                strokeWidth="3.4"
                strokeLinecap="round"
              />

              <path
                d="M -8 -14 C -24 -4, -26 10, -14 14"
                stroke={ui.strokeMain}
                strokeWidth="3"
                fill="none"
                strokeLinecap="round"
              />
              <g transform="translate(-20, 12) rotate(-25)">
                <rect
                  x="-12"
                  y="-4"
                  width="24"
                  height="8"
                  rx="3"
                  fill="#fef3c7"
                  stroke="#d97706"
                  strokeWidth="1.5"
                />
                <line x1="-4" y1="-4" x2="-4" y2="4" stroke="#ef4444" strokeWidth="1.5" />
              </g>

              <path
                d={
                  isHovered || hatTipActive || phase === 'planning'
                    ? 'M 8 -14 C 24 -22, 26 -42, 13 -48'
                    : 'M 8 -14 C 22 -6, 22 8, 10 12'
                }
                stroke={ui.strokeMain}
                strokeWidth="3"
                fill="none"
                strokeLinecap="round"
              />

              {/* Cabeça firme no pescoço (sem translação flutuante) */}
              <g transform={`translate(0, -44) rotate(${headTilt})`}>
                <circle
                  cx="0"
                  cy="0"
                  r="22"
                  fill={ui.headFill}
                  stroke={ui.strokeMain}
                  strokeWidth="3"
                />

                <path
                  d={`M -11 -8 Q -6 ${-11 + clamp(look.oy * 0.2, -1.5, 1.5)} -2 -8`}
                  stroke={ui.strokeMain}
                  strokeWidth="2"
                  fill="none"
                  strokeLinecap="round"
                />
                <path
                  d={`M 3 -9 Q 8 ${-15 + clamp(look.oy * 0.2, -1.5, 1.5)} 13 -10`}
                  stroke={ui.strokeMain}
                  strokeWidth="2.2"
                  fill="none"
                  strokeLinecap="round"
                />

                <g transform="translate(0, 0)">
                  <circle
                    cx="-6.5"
                    cy="-2"
                    r="6.2"
                    fill="#38bdf8"
                    fillOpacity="0.12"
                    stroke="#d97706"
                    strokeWidth="2"
                  />
                  <circle
                    cx="7.5"
                    cy="-2"
                    r="6.2"
                    fill="#38bdf8"
                    fillOpacity="0.12"
                    stroke="#d97706"
                    strokeWidth="2"
                  />
                  <line x1="-0.3" y1="-2" x2="1.3" y2="-2" stroke="#d97706" strokeWidth="2" />
                  <line x1="-9" y1="-5" x2="-6" y2="-6" stroke="#ffffff" strokeWidth="1.2" strokeLinecap="round" opacity="0.8" />
                  <line x1="5" y1="-5" x2="8" y2="-6" stroke="#ffffff" strokeWidth="1.2" strokeLinecap="round" opacity="0.8" />

                  {/* Círculo orbital onde os olhos se movem livremente */}
                  {(() => {
                    const eye = getOrbitalEye(look.ox * 0.65, look.oy * 0.5, 3.8, 1.8);
                    return (
                      <>
                        <circle cx={-6.5 + eye.x} cy={-2 + eye.y} r="2.4" fill={ui.strokeMain} />
                        <circle cx={7.5 + eye.x} cy={-2 + eye.y} r="2.4" fill={ui.strokeMain} />
                      </>
                    );
                  })()}

                  <line x1="-12" y1="-5.5" x2="-1" y2="-5.5" stroke={ui.headFill} strokeWidth="2.2" />
                </g>

                <path
                  d={`M ${-4 + look.ox * 0.3} ${9 + look.oy * 0.2} Q ${3 + look.ox * 0.3} ${12 + look.oy * 0.2} ${9 + look.ox * 0.3} ${6 + look.oy * 0.2}`}
                  stroke={ui.strokeMain}
                  strokeWidth="2"
                  fill="none"
                  strokeLinecap="round"
                />

                <g transform={`translate(0, ${-17 + hatLift}) rotate(${hatRotate})`}>
                  <path
                    d="M -18 2 L -14 -14 Q -7 -18 0 -13 Q 7 -18 14 -14 L 18 2 Z"
                    fill="url(#fedoraGrad)"
                    stroke="#451a03"
                    strokeWidth="1.8"
                    strokeLinejoin="round"
                  />
                  <path d="M -17 -1 L 17 -1 L 18 2 L -18 2 Z" fill="#290f02" />
                  <rect x="6" y="-2.5" width="4" height="4" rx="0.5" fill="#fbbf24" />
                  <path
                    d="M -31 3 Q -15 -2 0 2 Q 16 6 32 0"
                    stroke="#78350f"
                    strokeWidth="4.5"
                    fill="none"
                    strokeLinecap="round"
                  />
                </g>
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 68)">
              <rect
                x="-34"
                y="-8.5"
                width="68"
                height="17"
                rx="4.5"
                fill={isHovered ? '#a855f7' : ui.headFill}
                fillOpacity={isHovered ? '0.25' : '0.85'}
                stroke={isHovered ? '#a855f7' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-28, -6) scale(0.5)" className="text-purple-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.planejador }} />
              </g>
              <text
                x="4.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="9"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Planejador
              </text>
            </g>
            <title>Planejador</title>
          </g>
        );
      })()}

      {/* ============================================================
          2. HISTORIADOR (x: 262, y: 192) — Ponto Central: (262, 152)
      ============================================================ */}
      {(() => {
        const look = getLookVector(262, 152, 9, 3.5);
        const bob = Math.sin(time * 2.4 + 1) * 2;
        const isHovered = hoveredPersona === 'historiador';
        // Cabeça firme: micro-inclinação anatômica de no máx 3.5°
        const histHeadTilt = clamp(look.ox * 0.25, -3.5, 3.5);

        return (
          <g
            transform="translate(262, 192)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('historiador')}
            onMouseEnter={() => setHoveredPersona('historiador')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            <ellipse cx="0" cy="50" rx="22" ry="4.5" fill={ui.strokeMain} opacity="0.12" />

            <path
              d="M -5 14 L -9 49 M 5 14 L 9 49"
              stroke={ui.strokeMain}
              strokeWidth="3"
              strokeLinecap="round"
            />

            <g transform={`translate(0, ${bob})`}>
              <line x1="0" y1="-20" x2="0" y2="15" stroke={ui.strokeMain} strokeWidth="3.2" strokeLinecap="round" />
              <polygon points="-5,-18 5,-14 5,-18 -5,-14" fill="#d97706" />

              <path d="M -3 -12 C -18 -5, -20 6, -11 10" stroke={ui.strokeMain} strokeWidth="2.8" fill="none" strokeLinecap="round" />
              <rect x="-22" y="2" width="12" height="15" rx="2" fill="#fde68a" stroke="#b45309" strokeWidth="1.4" />

              <path
                d={`M 3 -12 C 16 -16, 22 -24, ${19 + look.ox * 0.3} ${-28 + look.oy * 0.3}`}
                stroke={ui.strokeMain}
                strokeWidth="2.8"
                fill="none"
                strokeLinecap="round"
              />
              <g transform={`translate(${22 + look.ox * 0.4}, ${-34 + look.oy * 0.4}) rotate(${15 + look.ox * 0.4})`}>
                <line x1="0" y1="6" x2="4" y2="14" stroke="#92400e" strokeWidth="3" strokeLinecap="round" />
                <circle cx="0" cy="0" r="7.5" fill="#38bdf8" fillOpacity="0.2" stroke="#f59e0b" strokeWidth="2.2" />
              </g>

              {/* Cabeça firme no tronco, olhos reativos com monóculo */}
              <g transform={`translate(0, -40) rotate(${histHeadTilt})`}>
                <circle cx="0" cy="0" r="20" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="3" />
                <path d="M -18 -12 Q 0 -24 19 -11 Z" fill="#78350f" stroke="#451a03" strokeWidth="1.5" />

                {/* Círculo orbital onde os olhos se movem livremente */}
                {(() => {
                  const eye = getOrbitalEye(look.ox * 0.7, look.oy * 0.5, 3.8, 1.8);
                  return (
                    <>
                      <circle cx={-6 + eye.x} cy={-2 + eye.y} r="2.3" fill={ui.strokeMain} />
                      <circle cx={6 + eye.x} cy={-2 + eye.y} r="2.5" fill={ui.strokeMain} />
                    </>
                  );
                })()}
                <circle cx={6} cy={-2} r="6.2" fill="none" stroke="#fbbf24" strokeWidth="1.8" />
                <path d="M 11 2 Q 14 12 8 18" stroke="#fbbf24" strokeWidth="1.2" fill="none" strokeDasharray="1.5 1.5" />

                <path d="M -11 -8 L -2 -6" stroke={ui.strokeMain} strokeWidth="2.5" strokeLinecap="round" />
                <path d="M 2 -8 L 12 -9" stroke={ui.strokeMain} strokeWidth="2.5" strokeLinecap="round" />

                <path
                  d="M -11 7 Q 0 2 11 7 Q 5 11 0 8 Q -5 11 -11 7 Z"
                  fill={ui.strokeSecondary}
                />
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 63)">
              <rect
                x="-26"
                y="-8.5"
                width="52"
                height="17"
                rx="4.5"
                fill={isHovered ? '#d97706' : ui.headFill}
                fillOpacity={isHovered ? '0.25' : '0.85'}
                stroke={isHovered ? '#d97706' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-21, -6) scale(0.5)" className="text-amber-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.historiador }} />
              </g>
              <text
                x="3.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="8"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Historiador
              </text>
            </g>
            <title>Historiador</title>
          </g>
        );
      })()}

      {/* ============================================================
          3. VISIONÁRIO (x: 326, y: 178) — Ponto Central: (326, 136)
      ============================================================ */}
      {(() => {
        const look = getLookVector(326, 136, 9, 3.5);
        const bounce = Math.abs(Math.sin(time * 3.2)) * -5;
        const isHovered = hoveredPersona === 'visionario';
        // Cabeça firme: micro-inclinação anatômica de no máx 3.5°
        const visHeadTilt = clamp(look.ox * 0.25, -3.5, 3.5);

        return (
          <g
            transform="translate(326, 178)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('visionario')}
            onMouseEnter={() => setHoveredPersona('visionario')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            <ellipse cx="0" cy="64" rx="20" ry="4" fill={ui.strokeMain} opacity="0.12" />

            <path
              d="M -4 22 L -7 62 M 4 22 L 7 62"
              stroke={ui.strokeMain}
              strokeWidth="3"
              strokeLinecap="round"
            />

            <g transform={`translate(0, ${bounce})`}>
              <line x1="0" y1="-20" x2="0" y2="22" stroke={ui.strokeMain} strokeWidth="3.2" strokeLinecap="round" />

              <path d="M 0 -12 L -16 -24" stroke={ui.strokeMain} strokeWidth="2.8" strokeLinecap="round" />
              <path d="M 0 -12 L 18 -26" stroke={ui.strokeMain} strokeWidth="2.8" strokeLinecap="round" />

              {/* Cabeça firme no tronco, olhos grandes bem expressivos */}
              <g transform={`translate(0, -42) rotate(${visHeadTilt})`}>
                <circle cx="0" cy="0" r="20.5" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="3" />

                <path d="M -19 -9 Q 0 -14 19 -9" stroke="#0284c7" strokeWidth="2.5" fill="none" />
                <circle cx="-7" cy="-12" r="5.5" fill="#38bdf8" fillOpacity="0.35" stroke="#0284c7" strokeWidth="2" />
                <circle cx="7" cy="-12" r="5.5" fill="#38bdf8" fillOpacity="0.35" stroke="#0284c7" strokeWidth="2" />

                {/* Círculo orbital onde os olhos se movem livremente */}
                {(() => {
                  const eye = getOrbitalEye(look.ox * 0.7, look.oy * 0.5, 4.0, 1.8);
                  return (
                    <>
                      <circle cx={-6 + eye.x} cy={-2.5 + eye.y} r="3" fill={ui.strokeMain} />
                      <circle cx={6 + eye.x} cy={-2.5 + eye.y} r="3" fill={ui.strokeMain} />
                      <circle cx={-7 + eye.x} cy={-4 + eye.y} r="1.1" fill="#ffffff" />
                      <circle cx={5 + eye.x} cy={-4 + eye.y} r="1.1" fill="#ffffff" />
                    </>
                  );
                })()}

                <path
                  d="M -5 9 Q 0 15 6 9"
                  stroke={ui.strokeMain}
                  strokeWidth="2.2"
                  fill="none"
                  strokeLinecap="round"
                />

                <g transform={`translate(0, ${-31 + Math.sin(time * 5) * 3})`} filter="url(#softGlow)">
                  <circle cx="-7" cy="2" r="2" fill="#38bdf8" />
                  <circle cx="8" cy="-3" r="2.4" fill="#a855f7" />
                  <line x1="-7" y1="2" x2="8" y2="-3" stroke="#38bdf8" strokeWidth="1.2" strokeDasharray="2 2" />
                </g>
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 77)">
              <rect
                x="-25"
                y="-8.5"
                width="50"
                height="17"
                rx="4.5"
                fill={isHovered ? '#0284c7' : ui.headFill}
                fillOpacity={isHovered ? '0.25' : '0.85'}
                stroke={isHovered ? '#0284c7' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-20, -6) scale(0.5)" className="text-sky-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.visionario }} />
              </g>
              <text
                x="3.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="8"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Visionário
              </text>
            </g>
            <title>Visionário</title>
          </g>
        );
      })()}

      {/* ============================================================
          4. FUTURISTA (x: 390, y: 190) — Ponto Central: (392, 150)
      ============================================================ */}
      {(() => {
        const look = getLookVector(392, 150, 9, 3.5);
        const bob = Math.sin(time * 2.7 + 2) * 2;
        const isHovered = hoveredPersona === 'futurista';
        // Cabeça firme: micro-inclinação anatômica de no máx 3°
        const futHeadTilt = clamp(look.ox * 0.2, -3, 3);

        return (
          <g
            transform="translate(390, 190)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('futurista')}
            onMouseEnter={() => setHoveredPersona('futurista')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            <ellipse cx="0" cy="52" rx="22" ry="4.5" fill={ui.strokeMain} opacity="0.12" />

            <path
              d="M -3 15 L -11 51 M 4 15 L 12 51"
              stroke={ui.strokeMain}
              strokeWidth="3"
              strokeLinecap="round"
            />

            <g transform={`translate(0, ${bob})`}>
              <line x1="2" y1="-20" x2="-1" y2="15" stroke={ui.strokeMain} strokeWidth="3.2" strokeLinecap="round" />

              <path d="M 1 -10 L 17 -4" stroke={ui.strokeMain} strokeWidth="2.8" strokeLinecap="round" />
              <g transform={`translate(21, -8) rotate(${time * 35})`}>
                <polygon
                  points="0,-6 5,4 -5,4"
                  fill="none"
                  stroke="#818cf8"
                  strokeWidth="1.5"
                />
                <circle cx="0" cy="0" r="1.8" fill="#38bdf8" />
              </g>

              {/* Cabeça firme no corpo, mira/laser do visor corre livremente */}
              <g transform={`translate(2, -40) rotate(${futHeadTilt})`}>
                <circle cx="0" cy="0" r="20" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="3" />

                <line x1="-18" y1="-6" x2="-22" y2="-18" stroke="#818cf8" strokeWidth="2" strokeLinecap="round" />
                <circle cx="-22" cy="-18" r="2.2" fill="#38bdf8" />

                <rect
                  x="-15"
                  y="-7"
                  width="31"
                  height="10"
                  rx="5"
                  fill="#0f172a"
                  stroke="#818cf8"
                  strokeWidth="2"
                />
                {/* Feixe laser cibernético fixo no visor, sem descer */}
                <circle
                  cx={clamp(look.ox * 1.4, -9, 9)}
                  cy={clamp(-2 + look.oy * 0.25, -3.5, -0.5)}
                  r="2.8"
                  fill="#38bdf8"
                  filter="url(#softGlow)"
                />
                <line
                  x1={clamp(look.ox * 1.4 - 5, -12, 4)}
                  y1="-2"
                  x2={clamp(look.ox * 1.4 + 5, -4, 12)}
                  y2="-2"
                  stroke="#38bdf8"
                  strokeWidth="1.2"
                  opacity="0.7"
                />

                <line x1="-4" y1="9" x2="5" y2="8" stroke={ui.strokeMain} strokeWidth="2" strokeLinecap="round" />
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 63)">
              <rect
                x="-24"
                y="-8.5"
                width="48"
                height="17"
                rx="4.5"
                fill={isHovered ? '#818cf8' : ui.headFill}
                fillOpacity={isHovered ? '0.25' : '0.85'}
                stroke={isHovered ? '#818cf8' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-19, -6) scale(0.5)" className="text-indigo-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.futurista }} />
              </g>
              <text
                x="3.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="8"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Futurista
              </text>
            </g>
            <title>Futurista</title>
          </g>
        );
      })()}

      {/* ============================================================
          5. CÉTICO (x: 472, y: 192) — Ponto Central: (480, 150)
          POLISH IMPECCABLE:
          - Somente reage e segue o mouse quando entrar no círculo de 15cm
          - Fora do círculo, permanece imerso na leitura do seu livro
      ============================================================ */}
      {(() => {
        const rawLook = getLookVector(480, 150, 9, 3.5);
        // O Cético somente reage e segue o mouse quando o cursor entrar no seu círculo de 15cm
        const eyeX = ceticoCares ? rawLook.ox : 3.2;
        const eyeY = ceticoCares ? rawLook.oy : -0.6;
        // Cabeça firme no queixo: micro-inclinação anatômica de no máx 4° somente quando reage
        const ceticoHeadTilt = ceticoCares ? clamp(rawLook.ox * 0.35, -4, 4) : 0;
        // Livro abaixa 14px quando reage ao intruso dentro do círculo
        const bookDropY = ceticoCares ? 14 : 0;
        const bob = Math.sin(time * 1.8) * 1.5;
        const isHovered = hoveredPersona === 'cetico';

        return (
          <g
            transform="translate(472, 192)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('cetico')}
            onMouseEnter={() => setHoveredPersona('cetico')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            {/* ANEL DE PROXIMIDADE DE 15CM (3X MENOR: r=44) */}
            {showCeticoRadius && (
              <g transform="translate(20, -37)" className="pointer-events-none">
                <circle
                  cx="0"
                  cy="0"
                  r={CETICO_RADIUS}
                  fill={ceticoCares ? 'rgba(244, 63, 94, 0.08)' : 'none'}
                  stroke={ceticoCares ? '#f43f5e' : ui.strokeSecondary}
                  strokeWidth="1.2"
                  strokeDasharray="3 4"
                  opacity={ceticoCares ? '0.85' : '0.35'}
                />
              </g>
            )}

            <ellipse cx="0" cy="50" rx="24" ry="5" fill={ui.strokeMain} opacity="0.12" />

            {/* Pernas viradas ~35° para a direita */}
            <path
              d="M -3 15 L -7 49 M 6 15 L 11 49"
              stroke={ui.strokeMain}
              strokeWidth="3.2"
              strokeLinecap="round"
            />

            <g transform={`translate(0, ${bob})`}>
              {/* Tronco de velhote rotacionado 35° para a direita */}
              <path
                d="M -2 15 Q 4 -2 6 -20"
                stroke={ui.strokeMain}
                strokeWidth="3.5"
                fill="none"
                strokeLinecap="round"
              />

              {/* BRAÇO ESQUERDO (ombro do lado direito/fundo na rotação 35°) SUBINDO PARA APOIAR NO QUEIXO */}
              <path
                d="M 9 -13 C 23 -10, 22 -24, 13 -23"
                stroke={ui.strokeMain}
                strokeWidth="3"
                fill="none"
                strokeLinecap="round"
              />

              {/* CABEÇA DE CÍRCULO (Velhote Careca no topo + Cabelo dos 2 lados + 35° p/ Direita) */}
              <g transform={`translate(8, -42) rotate(${ceticoHeadTilt})`}>
                <circle
                  cx="0"
                  cy="0"
                  r="21.5"
                  fill={ui.headFill}
                  stroke={ui.strokeMain}
                  strokeWidth="3"
                />

                {/* Brilho na careca no topo */}
                <path
                  d="M -7 -15 Q 0 -19 8 -14"
                  stroke="#ffffff"
                  strokeWidth="1.8"
                  fill="none"
                  strokeLinecap="round"
                  opacity={isDark ? '0.35' : '0.7'}
                />
                <path d="M -3 -11 Q 4 -12 10 -10" stroke={ui.strokeSecondary} strokeWidth="1.3" fill="none" />

                {/* Tufo de cabelo esquerdo */}
                <path
                  d="M -19 -6 C -26 -8, -28 -1, -22 3 C -27 6, -24 12, -17 9 Z"
                  fill="#d4d4d8"
                  stroke="#71717a"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />

                {/* Tufo de cabelo direito */}
                <path
                  d="M 18 -7 C 25 -9, 27 -2, 22 2 C 26 5, 23 10, 17 8 Z"
                  fill="#d4d4d8"
                  stroke="#71717a"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />

                {/* Olhos Desconfiados em círculo orbital livre */}
                <g transform="translate(4, -2.5)">
                  {(() => {
                    const eye = getOrbitalEye(eyeX * 0.75, eyeY * 0.55, 4.0, 2.0);
                    const pupilRadius = ceticoCares ? 2.6 : 2.1;
                    return (
                      <>
                        <circle cx={-5 + eye.x} cy={eye.y} r={pupilRadius} fill={ui.strokeMain} />
                        <circle cx={6 + eye.x} cy={eye.y} r={pupilRadius} fill={ui.strokeMain} />
                      </>
                    );
                  })()}

                  <path
                    d={
                      ceticoCares
                        ? 'M -12 -7 L -1 -3 M 2 -4 L 13 -9'
                        : 'M -10 -4 L -1 -3 M 2 -3 L 11 -4'
                    }
                    stroke={ceticoCares ? (isDark ? '#e4e4e7' : '#52525b') : '#a1a1aa'}
                    strokeWidth={ceticoCares ? '3' : '2.2'}
                    strokeLinecap="round"
                  />

                  <line x1="-9" y1="4" x2="-1" y2="3.5" stroke={ui.strokeSecondary} strokeWidth="1.5" />
                  <line x1="2" y1="3.5" x2="10" y2="4" stroke={ui.strokeSecondary} strokeWidth="1.5" />
                </g>

                {/* Boca torta cética */}
                <path
                  d={
                    ceticoCares
                      ? 'M -2 9 Q 5 5 11 11'
                      : 'M 1 9 L 9 8.5'
                  }
                  stroke={ui.strokeMain}
                  strokeWidth="2.2"
                  fill="none"
                  strokeLinecap="round"
                />
              </g>

              {/* MÃO ESQUERDA APOIADA NO QUEIXO */}
              <circle
                cx={13 + Math.sin(time * 4) * 0.7}
                cy="-22.5"
                r="3.8"
                fill={ui.headFill}
                stroke={ui.strokeMain}
                strokeWidth="2.2"
              />

              {/* BRAÇO DIREITO (ombro da frente/esquerda na rotação 35°) SEGURANDO O LIVRO ABERTO NA MÃO DIREITA */}
              <path
                d={`M -3 -11 C 6 2, 22 -8, 35 ${-25 + bookDropY}`}
                stroke={ui.strokeMain}
                strokeWidth="3.1"
                fill="none"
                strokeLinecap="round"
              />

              {/* LIVRO DE CAPA MARROM ABERTO NA MÃO DIREITA (~15cm do rosto) */}
              <g transform={`translate(39, ${-32 + bookDropY}) rotate(-10)`}>
                {/* Páginas abertas */}
                <path
                  d="M -11 -12 L 2 -9 L 11 -13 L 11 9 L 2 12 L -11 8 Z"
                  fill="#fef3c7"
                  stroke="#d97706"
                  strokeWidth="1.2"
                />
                {/* Capa Marrom */}
                <path
                  d="M -13 -10 L 0 -7 L 0 14 L -13 10 Z"
                  fill="url(#brownBookGrad)"
                  stroke="#431407"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <path
                  d="M 0 -7 L 12 -11 L 12 10 L 0 14 Z"
                  fill="#9a3412"
                  stroke="#431407"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <line x1="0" y1="-7" x2="0" y2="14" stroke="#290f02" strokeWidth="2.2" />
                <line x1="-8" y1="-5" x2="-2" y2="-4" stroke="#78350f" strokeWidth="1.2" />
                <line x1="3" y1="-6" x2="9" y2="-8" stroke="#78350f" strokeWidth="1.2" />
                {/* Mão direita segurando a base do livro aberto */}
                <circle
                  cx="-2"
                  cy="11"
                  r="3.5"
                  fill={ui.headFill}
                  stroke={ui.strokeMain}
                  strokeWidth="2"
                />
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 63)">
              <rect
                x="-23"
                y="-8.5"
                width="46"
                height="17"
                rx="4.5"
                fill={ceticoCares || isHovered ? '#f43f5e' : ui.headFill}
                fillOpacity={ceticoCares || isHovered ? '0.25' : '0.85'}
                stroke={ceticoCares || isHovered ? '#f43f5e' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-18, -6) scale(0.5)" className="text-rose-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.cetico }} />
              </g>
              <text
                x="3.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="8.5"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Cético
              </text>
            </g>
            <title>Cético</title>
          </g>
        );
      })()}

      {/* ============================================================
          6. AUDITOR (x: 765, y: 196) — Ponto Central: (765, 150)
      ============================================================ */}
      {(() => {
        const look = getLookVector(765, 150, 9, 3.5);
        const glareX = look.ox;
        const glareY = look.oy * 0.7;
        // Cabeça firme: micro-inclinação anatômica de no máx 3°
        const auditorHeadTilt = clamp(look.ox * 0.2, -3, 3);
        const angryBounce = isAuditorBlowingWhistle
          ? Math.abs(Math.sin(time * 14)) * -6
          : Math.sin(time * 2.6) * 2;
        const isHovered = hoveredPersona === 'auditor';

        return (
          <g
            transform="translate(765, 196)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('auditor')}
            onMouseEnter={() => setHoveredPersona('auditor')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            <ellipse cx="0" cy="46" rx="32" ry="6" fill={ui.strokeMain} opacity="0.16" />

            <path
              d="M -10 24 L -14 45 M 10 24 L 14 45"
              stroke={ui.strokeMain}
              strokeWidth="3.8"
              strokeLinecap="round"
            />
            <path
              d="M -14 45 L -22 45 M 14 45 L 7 45"
              stroke={ui.strokeMain}
              strokeWidth="4.5"
              strokeLinecap="round"
            />

            <g transform={`translate(0, ${angryBounce}) rotate(${auditorHeadTilt})`}>
              <circle
                cx="0"
                cy="-12"
                r="34"
                fill={ui.headFill}
                stroke={isAuditorBlowingWhistle ? '#ef4444' : ui.strokeMain}
                strokeWidth="3.4"
              />

              <path
                d="M -32 2 Q 0 10 32 2"
                stroke="#fbbf24"
                strokeWidth="4"
                fill="none"
              />
              <rect x="-12" y="1" width="10" height="7" rx="1.5" fill="#fbbf24" stroke="#18181b" strokeWidth="1.2" />
              <polygon
                points="-18,-8 -14,-13 -10,-8 -12,-2 -16,-2"
                fill="#fbbf24"
                stroke="#92400e"
                strokeWidth="1"
              />

              <g transform="translate(-2, -43) rotate(-6)">
                <path
                  d="M -24 2 L -28 -9 L 0 -14 L 26 -7 L 22 2 Z"
                  fill="url(#policeCapGrad)"
                  stroke="#fbbf24"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <line x1="-23" y1="0" x2="21" y2="0" stroke="#fbbf24" strokeWidth="2.8" strokeDasharray="4 4" />
                <path
                  d="M -24 2 L -37 5 L -16 6 Z"
                  fill="#0f172a"
                  stroke="#fbbf24"
                  strokeWidth="1.5"
                />
                <circle cx="-10" cy="-6" r="3.5" fill="#fbbf24" />
              </g>

              <g transform="translate(-10, -18)">
                <path
                  d="M -17 -10 L -5 -3"
                  stroke={isAuditorBlowingWhistle ? '#ef4444' : ui.strokeMain}
                  strokeWidth="3.5"
                  strokeLinecap="round"
                />
                <path
                  d="M 10 -10 L -1 -3"
                  stroke={isAuditorBlowingWhistle ? '#ef4444' : ui.strokeMain}
                  strokeWidth="3.5"
                  strokeLinecap="round"
                />

                {/* Olhos do auditor em círculo orbital livre */}
                {(() => {
                  const eye = getOrbitalEye(glareX * 0.7, glareY * 0.5, 3.8, 1.8);
                  return (
                    <>
                      <circle cx={-10 + eye.x} cy={-3.5 + eye.y} r="2.8" fill={ui.strokeMain} />
                      <circle cx={3 + eye.x} cy={-3.5 + eye.y} r="2.8" fill={ui.strokeMain} />
                    </>
                  );
                })()}

                {isAuditorBlowingWhistle ? (
                  <g>
                    <circle cx="-12" cy="9" r="5.5" fill="#ef4444" fillOpacity="0.35" stroke={ui.strokeMain} strokeWidth="2" />
                    <circle cx="4" cy="9" r="5" fill="#ef4444" fillOpacity="0.35" stroke={ui.strokeMain} strokeWidth="2" />
                  </g>
                ) : (
                  <path
                    d="M -11 11 Q -4 6 3 11"
                    stroke={ui.strokeMain}
                    strokeWidth="2.6"
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
              </g>

              {isAuditorBlowingWhistle ? (
                <g>
                  <path
                    d="M -18 4 C -34 0, -34 -8, -22 -10"
                    stroke={ui.strokeMain}
                    strokeWidth="3.2"
                    fill="none"
                    strokeLinecap="round"
                  />
                  <g transform="translate(-29, -10) rotate(10)">
                    <circle cx="-4" cy="0" r="5.5" fill="#ef4444" stroke="#7f1d1d" strokeWidth="1.6" />
                    <rect x="0" y="-3" width="8" height="4.5" rx="1" fill="#ef4444" stroke="#7f1d1d" strokeWidth="1.5" />
                    <circle cx="-4" cy="0" r="1.8" fill="#fca5a5" />
                  </g>
                  <g transform="translate(-45, -12)" filter="url(#softGlow)">
                    <path
                      d="M 0 -7 Q -6 0 0 7"
                      stroke="#ef4444"
                      strokeWidth="2.4"
                      fill="none"
                      strokeLinecap="round"
                    />
                    <path
                      d="M -7 -12 Q -15 0 -7 12"
                      stroke="#ef4444"
                      strokeWidth="2"
                      fill="none"
                      strokeLinecap="round"
                      opacity="0.8"
                    />
                    <path
                      d="M -14 -17 Q -25 0 -14 17"
                      stroke="#fbbf24"
                      strokeWidth="1.6"
                      fill="none"
                      strokeLinecap="round"
                      opacity="0.6"
                    />
                    <text
                      x="-38"
                      y="-18"
                      fill="#ef4444"
                      fontSize="11"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      PIIIIII!
                    </text>
                  </g>
                </g>
              ) : (
                <g>
                  <path
                    d="M -26 2 C -38 6, -42 -2, -36 -8"
                    stroke={ui.strokeMain}
                    strokeWidth="3.2"
                    fill="none"
                    strokeLinecap="round"
                  />
                  <g transform="translate(-40, -11) rotate(-20)">
                    <path d="M 4 2 Q 12 12 18 8" stroke="#ef4444" strokeWidth="1.5" fill="none" />
                    <circle cx="-3" cy="0" r="5" fill="#ef4444" stroke="#7f1d1d" strokeWidth="1.5" />
                    <rect x="1" y="-2.5" width="7" height="4" rx="1" fill="#ef4444" stroke="#7f1d1d" strokeWidth="1.5" />
                  </g>
                </g>
              )}

              <g
                transform={`translate(-22, -22) rotate(${
                  isAuditorBlowingWhistle
                    ? Math.sin(time * 16) * 25 - 25
                    : Math.sin(time * 2.5) * 8 - 15
                })`}
              >
                <line x1="6" y1="14" x2="-12" y2="-16" stroke={ui.strokeMain} strokeWidth="3.2" strokeLinecap="round" />
                <line x1="-12" y1="-16" x2="-18" y2="-28" stroke="#fbbf24" strokeWidth="3.5" strokeLinecap="round" />
                <g transform="translate(-22, -36)">
                  <circle
                    cx="0"
                    cy="0"
                    r="11"
                    fill={isAuditorBlowingWhistle ? '#ef4444' : '#fbbf24'}
                    stroke="#ffffff"
                    strokeWidth="2"
                    filter="url(#softGlow)"
                  />
                  <line x1="-5" y1="0" x2="5" y2="0" stroke="#ffffff" strokeWidth="2.8" strokeLinecap="round" />
                </g>
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 59)">
              <rect
                x="-25"
                y="-8.5"
                width="50"
                height="17"
                rx="4.5"
                fill={isAuditorBlowingWhistle || isHovered ? '#fbbf24' : ui.headFill}
                fillOpacity={isAuditorBlowingWhistle || isHovered ? '0.25' : '0.85'}
                stroke={isAuditorBlowingWhistle || isHovered ? '#fbbf24' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-20, -6) scale(0.5)" className="text-amber-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.auditor }} />
              </g>
              <text
                x="3.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="8.5"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Auditor
              </text>
            </g>
            <title>Auditor</title>
          </g>
        );
      })()}

      {/* ============================================================
          7. REDATOR (x: 895, y: 186) — Ponto Central: (890, 144)
          IMPECCABLE POLISH:
          - Reage em uníssono e conjunto com os outros especialistas
          - Reage ao apito/alerta do Auditor olhando para ele com espanto
          - Cavidades oculares definidas e pupilas em círculo orbital 360°
          - Prancheta e caneta reativas com anotações e escrita em tempo real
      ============================================================ */}
      {(() => {
        const look = getLookVector(890, 144, 9, 3.5);
        const isStartled = isAuditorBlowingWhistle;

        // Quando o Auditor apita, o Redator se volta com espanto para o Auditor à esquerda
        const effectiveOx = isStartled ? -6.5 : look.ox;
        const effectiveOy = isStartled ? -0.8 : look.oy;

        const bob = Math.sin(time * 2.3 + 0.7) * 2.2;
        // Cabeça expressiva virando sutilmente na direção do grupo ou do alerta
        const redatorHeadTilt = isStartled ? -6 : clamp(effectiveOx * 0.35, -4.5, 4.5);
        const isHovered = hoveredPersona === 'redator';
        const isNear = look.dist < 120;
        const waveAngle =
          redatorWaveActive || isHovered || (isNear && effectiveOx > 0) || phase === 'synthesis'
            ? Math.sin(time * 12) * 18
            : isStartled
            ? -25 + Math.sin(time * 14) * 8
            : Math.sin(time * 2) * 4;

        // Prancheta e caneta reativas ao olhar e ao grupo
        const clipboardTilt = 10 + effectiveOx * 0.4;
        const penAngle = Math.sin(time * 6) * 4 + effectiveOx * 0.6;
        const penScribble = isTyping || phase === 'synthesis'
          ? Math.sin(time * 16) * 2.2
          : Math.sin(time * 7) * 1.4;
        const bodyLean = isStartled ? -3 : effectiveOx * 0.2;

        return (
          <g
            transform="translate(895, 186)"
            className="cursor-pointer"
            onClick={() => handleCharacterClick('redator')}
            onMouseEnter={() => setHoveredPersona('redator')}
            onMouseLeave={() => setHoveredPersona(null)}
          >
            <ellipse cx="0" cy="56" rx="23" ry="4.5" fill={ui.strokeMain} opacity="0.12" />

            {/* Pernas do redator */}
            <path
              d="M -5 18 L -8 55 M 6 18 L 10 55"
              stroke={ui.strokeMain}
              strokeWidth="3"
              strokeLinecap="round"
            />

            {/* Tronco com leve conexão anatômica ao grupo */}
            <g transform={`translate(${bodyLean}, ${bob})`}>
              <path
                d="M 2 18 Q -3 -2 -5 -20"
                stroke={ui.strokeMain}
                strokeWidth="3.2"
                fill="none"
                strokeLinecap="round"
              />
              <path
                d="M -10 -18 Q -3 -14 4 -18 L 6 -6 L 1 -7 Z"
                fill="#34d399"
              />

              {/* Braço acenando / reagindo à proximidade ou recuando no susto */}
              <g transform={`translate(-6, -12) rotate(${waveAngle})`}>
                <path
                  d="M 0 0 C -16 -8, -22 -20, -16 -30"
                  stroke={ui.strokeMain}
                  strokeWidth="2.8"
                  fill="none"
                  strokeLinecap="round"
                />
                <circle cx="-16" cy="-30" r="3.5" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="2" />
              </g>

              {/* Braço segurando prancheta de síntese com inclinação reativa */}
              <path
                d="M -2 -10 C 12 -4, 18 4, 12 10"
                stroke={ui.strokeMain}
                strokeWidth="2.8"
                fill="none"
                strokeLinecap="round"
              />
              <g transform={`translate(16, 4) rotate(${clipboardTilt})`}>
                {/* Base da prancheta */}
                <rect
                  x="-10"
                  y="-14"
                  width="20"
                  height="26"
                  rx="3"
                  fill={ui.headFill}
                  stroke="#34d399"
                  strokeWidth="2"
                />
                {/* Clipe metálico no topo */}
                <rect x="-5" y="-16" width="10" height="4" rx="1.5" fill="#94a3b8" stroke="#475569" strokeWidth="1" />
                {/* Linhas de anotações */}
                <line x1="-6" y1="-7" x2="6" y2="-7" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" />
                <line x1="-6" y1="-2" x2="6" y2="-2" stroke={ui.strokeSecondary} strokeWidth="1.2" strokeLinecap="round" />
                <line x1="-6" y1="3" x2="3" y2="3" stroke={ui.strokeSecondary} strokeWidth="1.2" strokeLinecap="round" />

                {/* Traço de anotação caligráfica ativa */}
                <path
                  d="M -5 7 Q -2 5 2 8"
                  stroke="#10b981"
                  strokeWidth="1.4"
                  strokeDasharray="2 2"
                  fill="none"
                />
              </g>

              {/* Mão e caneta esmeralda anotando com movimento ativo */}
              <g transform={`translate(${16 + effectiveOx * 0.25}, ${4 + penScribble}) rotate(${penAngle})`}>
                <line x1="8" y1="-14" x2="-2" y2="0" stroke="#34d399" strokeWidth="3" strokeLinecap="round" />
                <polygon points="-2,0 -4,3 -1,4" fill="#10b981" />
                <circle cx="6" cy="-10" r="3" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="1.8" />
              </g>

              {/* Cabeça firme no tronco com micro-tilt anatômico */}
              <g transform={`translate(${-5 + effectiveOx * 0.2}, -42) rotate(${redatorHeadTilt})`}>
                <circle
                  cx="0"
                  cy="0"
                  r="21"
                  fill={ui.headFill}
                  stroke={ui.strokeMain}
                  strokeWidth="3"
                />

                {/* Cabelo e topete estilizado */}
                <path
                  d="M -6 -20 Q -2 -28 6 -23 Q 11 -27 12 -19"
                  stroke={ui.strokeMain}
                  strokeWidth="2.4"
                  fill="none"
                  strokeLinecap="round"
                />

                {/* Sobrancelhas expressivas (reagem com espanto se o Auditor apita) */}
                <path
                  d={
                    isStartled
                      ? 'M -12 -12 Q -7 -16 -3 -12 M 3 -12 Q 7 -16 12 -12'
                      : 'M -12 -9 Q -7 -13 -3 -9 M 3 -9 Q 7 -13 12 -9'
                  }
                  stroke={ui.strokeMain}
                  strokeWidth="2"
                  fill="none"
                  strokeLinecap="round"
                />

                {/* Cavidades oculares definidas e pupilas em círculo orbital 360° */}
                {(() => {
                  const eye = getOrbitalEye(effectiveOx * 0.75, effectiveOy * 0.55, 4.2, 2.1);
                  return (
                    <g>
                      {/* Cavidade orbital esquerda */}
                      <ellipse cx="-6" cy="-3.5" rx="5" ry="3.8" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="1.4" />
                      {/* Cavidade orbital direita */}
                      <ellipse cx="6" cy="-3.5" rx="5" ry="3.8" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="1.4" />

                      {/* Pupilas escuras nítidas que navegam livremente no círculo */}
                      <circle cx={-6 + eye.x} cy={-3.5 + eye.y} r="2.5" fill={ui.strokeMain} />
                      <circle cx={6 + eye.x} cy={-3.5 + eye.y} r="2.5" fill={ui.strokeMain} />

                      {/* Brilhos especulares brancos que dão vida e foco ao olhar */}
                      <circle cx={-6.8 + eye.x} cy={-4.4 + eye.y} r="0.9" fill="#ffffff" />
                      <circle cx={5.2 + eye.x} cy={-4.4 + eye.y} r="0.9" fill="#ffffff" />
                    </g>
                  );
                })()}

                {/* Blush esmeralda sutil */}
                <circle cx="-12" cy="4" r="3" fill="#34d399" opacity="0.28" />
                <circle cx="12" cy="4" r="3" fill="#34d399" opacity="0.28" />

                {/* Expressão da boca: aberta em espanto com apito do auditor, ou sorriso sutil */}
                {isStartled ? (
                  <ellipse cx="0" cy="7" rx="3.2" ry="4.2" fill={ui.headFill} stroke={ui.strokeMain} strokeWidth="2.2" />
                ) : (
                  <path
                    d={`M ${-8 + effectiveOx * 0.3} 5 Q 0 15 ${8 + effectiveOx * 0.3} 5`}
                    stroke={ui.strokeMain}
                    strokeWidth="2.4"
                    fill="none"
                    strokeLinecap="round"
                  />
                )}
              </g>
            </g>

            {/* Rótulo de Identificação com Mini-Ícone */}
            <g transform="translate(0, 69)">
              <rect
                x="-25"
                y="-8.5"
                width="50"
                height="17"
                rx="4.5"
                fill={isHovered || phase === 'synthesis' ? '#34d399' : ui.headFill}
                fillOpacity={isHovered || phase === 'synthesis' ? '0.25' : '0.85'}
                stroke={isHovered || phase === 'synthesis' ? '#34d399' : ui.stageFloor}
                strokeWidth="1.2"
              />
              <g transform="translate(-20, -6) scale(0.5)" className="text-emerald-400">
                <g dangerouslySetInnerHTML={{ __html: PERSONA_CHOSEN_SVG.redator }} />
              </g>
              <text
                x="3.5"
                y="3"
                textAnchor="middle"
                fill={ui.strokeMain}
                fontSize="8.5"
                fontFamily="system-ui, -apple-system, sans-serif"
                fontWeight="600"
              >
                Redator
              </text>
            </g>
            <title>Redator</title>
          </g>
        );
      })()}
    </svg>
  );
}

export default function App() {
  return (
    <div className="w-screen h-screen bg-[#09090b] flex items-center justify-center p-6 overflow-hidden">
      <div className="w-full max-w-5xl">
        <DeepResearchCharacters />
      </div>
    </div>
  );
}