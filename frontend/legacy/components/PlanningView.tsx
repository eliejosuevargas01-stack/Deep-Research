import React, { useEffect, useState } from 'react';
import { ErrorNotice } from './ErrorNotice';
import { apresentarErro } from '../utils/erros';
import { formatarTitulo } from '../utils/texto';
import { PersonaIcon } from './ResearchIcons';

export interface PlanningViewProps {
  tema: string;
  iniciadoEm: number;
  raciocinio: string;
  erro?: string | null;
  onRetry?: () => void;
  /** Nível do título: 1 na tela real, 2 quando a view aparece como amostra. */
  tituloNivel?: 1 | 2;
  tituloId?: string;
}

const ETAPAS = [
  'Interpretando o pedido',
  'Normalizando escopo e recência',
  'Dividindo em pontos',
  'Levantando hipóteses',
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
const ROTULOS: Record<string, string> = {
  tema: 'Tema',
  objetivo: 'Objetivo',
  pedido: 'Pedido',
  justificativa: 'Por que dividir assim',
  resumo: 'Resumo',
  tese: 'Tese',
  publico: 'Público',
  formato_entrega: 'Entrega',
  escopo: 'Escopo',
  pressupostos: 'Pressupostos',
  ambiguidades: 'Ambiguidades',
  riscos: 'Riscos',
  pontos: 'Pontos de investigação',
  criterios: 'Critérios',
};

function valorLegivel(v: unknown): string {
  if (v == null) return '';
  if (Array.isArray(v)) {
    return v
      .map((item) => {
        if (item && typeof item === 'object') {
          const o = item as Record<string, unknown>;
          return String(o.titulo ?? o.pergunta ?? o.texto ?? o.descricao ?? JSON.stringify(o));
        }
        return String(item);
      })
      .join('\n• ');
  }
  if (typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, item]) => `${ROTULOS[k] ?? k}: ${valorLegivel(item)}`)
      .join(' · ');
  }
  return String(v);
}

/** Objeto já parseado -> linhas legíveis, na ordem dos rótulos conhecidos. */
function formatarObjeto(obj: Record<string, unknown>): string {
  return Object.keys(ROTULOS)
    .filter((k) => obj[k] != null)
    .map((k) => {
      const valor = valorLegivel(obj[k]);
      if (!valor) return '';
      return `${ROTULOS[k]}:\n${Array.isArray(obj[k]) ? '• ' : ''}${valor}`;
    })
    .filter(Boolean)
    .join('\n\n');
}

/** O raciocínio chega em pedaços: JSON completo, JSON truncado ou prosa. */
function extrairCamposParciais(texto: string): string {
  const linhas: string[] = [];
  for (const chave of Object.keys(ROTULOS)) {
    const str = texto.match(new RegExp(`"${chave}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)("|$)`, 's'));
    if (str && str[1] && str[1].trim()) {
      linhas.push(`${ROTULOS[chave]}: ${str[1].replace(/\\n/g, ' ').replace(/\\"/g, '"').trim()}`);
      continue;
    }
    const arr = texto.match(new RegExp(`"${chave}"\\s*:\\s*\\[([\\s\\S]*?)(\\]|$)`, 's'));
    if (arr && arr[1]) {
      const itens = [...arr[1].matchAll(/"((?:[^"\\]|\\.)*)("|$)/g)]
        .map((m) => m[1].replace(/\\n/g, ' ').replace(/\\"/g, '"').trim())
        .filter(Boolean);
      if (itens.length > 0) linhas.push(`${ROTULOS[chave]}:\n• ${itens.join('\n• ')}`);
    }
  }
  return linhas.join('\n\n');
}

/**
 * O planejador devolve JSON; a tela mostra texto, nunca chave crua.
 * Enquanto o JSON não fecha, extrai só os campos já chegados.
 */
export function raciocinioLegivel(bruto: string): string {
  const texto = (bruto || '').trim();
  if (!texto) return '';
  if (!texto.includes('"') || !texto.includes(':')) return bruto;
  const inicio = texto.indexOf('{');
  if (inicio >= 0) {
    try {
      const dados = JSON.parse(texto.slice(inicio)) as Record<string, unknown>;
      if (dados && typeof dados === 'object') {
        const completo = formatarObjeto(dados);
        if (completo) return completo;
      }
    } catch {
      /* JSON ainda incompleto: cai na extração parcial */
    }
  }
  return extrairCamposParciais(texto);
}

export const PlanningView: React.FC<PlanningViewProps> = ({
  tema,
  iniciadoEm,
  raciocinio,
  erro,
  onRetry,
  tituloNivel = 1,
  tituloId = 'planning-title',
}) => {
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
    <section className="planning-view" aria-labelledby={tituloId} aria-busy={!erro}>
      <div className="planning-status">
        <span className="planning-header-icon" aria-hidden="true">
          <PersonaIcon persona="planejador" size={28} ativo={!erro} />
        </span>
        <span className="planning-status-text">
          {erro ? 'O planejador parou' : 'Planejador em ação'}
        </span>
        <span className="planning-elapsed" aria-live="off">{formatar(decorrido)}</span>
      </div>

      {tituloNivel === 1 ? (
        <h1 id={tituloId} className="planning-theme">{formatarTitulo(tema)}</h1>
      ) : (
        <h2 id={tituloId} className="planning-theme">{formatarTitulo(tema)}</h2>
      )}
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
        {raciocinioLegivel(raciocinio) ? (
          <pre className="planning-reasoning-text">{raciocinioLegivel(raciocinio)}</pre>
        ) : (
          <p className="planning-reasoning-empty">
            {erro ? 'Sem raciocínio registrado para esta tentativa.' : 'Aguardando o primeiro token do modelo…'}
          </p>
        )}
      </div>

      {erro && (
        <div className="planning-error">
          <ErrorNotice
            compact
            falha={apresentarErro(erro, { acao: 'elaborar o plano' })}
            onRetry={onRetry}
            retryLabel="Tentar de novo"
          />
        </div>
      )}
    </section>
  );
};
