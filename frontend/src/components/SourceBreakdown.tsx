import React from 'react';
import {
  ExternalLink,
  ChevronRight,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  BookmarkCheck,
  FileQuestion,
  FileText,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { FontesResumo, FonteItem, FontesStatus } from '../types/api';
import './SourceBreakdown.css';
import { ErrorNotice } from './ErrorNotice';
import { apresentarErro } from '../utils/erros';

export interface SourceBreakdownProps {
  fontes: FontesResumo | null | undefined;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  fallbackCitations?: string[];
  isMismatch?: boolean;
  mismatchNotice?: string | null;
}

/**
 * Validador estrito de protocolos seguros para prevenção de XSS e esquemas perigosos.
 */
function isSafeUrl(url?: string): boolean {
  if (!url) return false;
  const clean = url.trim().toLowerCase();
  return clean.startsWith('http://') || clean.startsWith('https://');
}

/**
 * Extrai domínio de forma segura a partir do domínio explícito ou da URL.
 */
function getDomain(url: string, explicitDomain?: string | null): string {
  if (explicitDomain && explicitDomain.trim()) {
    return explicitDomain.trim();
  }
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

interface SourceListSectionProps {
  items: FonteItem[];
  emptyMessage: string;
}

const SourceListSection: React.FC<SourceListSectionProps> = ({ items, emptyMessage }) => {
  if (items.length === 0) {
    return <p className="source-empty-message">{emptyMessage}</p>;
  }

  return (
    <div className="source-items-list" role="list">
      {items.map((item, idx) => {
        const safe = isSafeUrl(item.url);
        const domain = getDomain(item.url, item.dominio);

        return (
          <div key={`${item.url}-${idx}`} className="source-item-row" role="listitem">
            <div className="source-item-top">
              <span className="source-item-domain" title={`Domínio: ${domain}`}>
                {domain}
              </span>
              {item.titulo && <span className="source-item-title">{item.titulo}</span>}
            </div>

            {safe ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="source-item-url-link"
                title={`Abrir fonte externa: ${item.url}`}
              >
                <span>{item.url}</span>
                <ExternalLink size={12} aria-hidden="true" style={{ flexShrink: 0 }} />
              </a>
            ) : (
              <span className="source-item-url-link" style={{ color: 'var(--color-text-muted)' }}>
                {item.url}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

export const SourceBreakdown: React.FC<SourceBreakdownProps> = ({
  fontes,
  loading = false,
  error = null,
  onRetry,
  fallbackCitations = [],
  isMismatch = false,
  mismatchNotice = null,
}) => {
  // Status confirmado apenas se fontes válidas estiverem disponíveis; loading/erro/mismatch são estados distintos
  const status: FontesStatus | null = fontes ? fontes.status : null;
  const isConfirmedLegacy = status === 'indisponivel' && !loading && !error && !isMismatch;

  // Contadores fidedignos: desconhecido NUNCA é apresentado como 0
  const totalConsultadasDisplay =
    !loading && !isMismatch && fontes && fontes.total_consultadas !== null && fontes.total_consultadas !== undefined
      ? fontes.total_consultadas
      : '—';

  const totalUtilizadasCount =
    !loading && !isMismatch && fontes && fontes.total_utilizadas !== null && fontes.total_utilizadas !== undefined
      ? fontes.total_utilizadas
      : !loading && !isMismatch && fallbackCitations.length > 0 && !error
      ? fallbackCitations.length
      : '—';

  const totalNaoUtilizadasDisplay =
    !loading && !isMismatch && fontes && fontes.total_nao_utilizadas !== null && fontes.total_nao_utilizadas !== undefined
      ? fontes.total_nao_utilizadas
      : '—';

  // Vetores de fontes: suprimidos quando houver divergência de versão (isMismatch)
  const itemsUtilizadas: FonteItem[] = isMismatch
    ? []
    : fontes && Array.isArray(fontes.utilizadas) && fontes.utilizadas.length > 0
    ? fontes.utilizadas
    : !error && !loading
    ? fallbackCitations.map((url) => ({
        url,
        titulo: null,
        dominio: getDomain(url),
      }))
    : [];

  const itemsNaoUtilizadas: FonteItem[] =
    isMismatch || !fontes || !Array.isArray(fontes.nao_utilizadas) ? [] : fontes.nao_utilizadas;

  const itemsConsultadas: FonteItem[] =
    isMismatch || !fontes || !Array.isArray(fontes.consultadas) ? [] : fontes.consultadas;

  return (
    <section
      className="source-breakdown-card"
      aria-label="De onde vêm as fontes"
    >
      <header className="source-breakdown-header">
        <div className="source-breakdown-title-row">
          <h2 className="source-breakdown-title">
            <Layers size={18} aria-hidden="true" />
            <span>Fontes da Investigação</span>
          </h2>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {loading && (
              <span className="source-status-badge indisponivel" title="Consultando status de fontes">
                <RefreshCw size={12} className="animate-spin" aria-hidden="true" />
                <span>Carregando...</span>
              </span>
            )}
            {!loading && !isMismatch && status === 'completo' && (
              <span className="source-status-badge completo" title="Todas as fontes auditadas">
                <CheckCircle2 size={12} aria-hidden="true" />
                <span>Evidências completas</span>
              </span>
            )}
            {!loading && !isMismatch && status === 'parcial' && (
              <span className="source-status-badge parcial" title="Evidências parcialmente disponíveis">
                <AlertCircle size={12} aria-hidden="true" />
                <span>Evidências parciais</span>
              </span>
            )}
            {isConfirmedLegacy && (
              <span
                className="source-status-badge indisponivel"
                title="Relatório sem registro bruto de leituras"
              >
                <AlertTriangle size={12} aria-hidden="true" />
                <span>Legado / Indisponível</span>
              </span>
            )}
          </div>
        </div>

        {/* Linha Coesa de Contadores Agrupados (Recusa do template de 3 cards métricos decorados) */}
        <div
          className="source-counters-bar"
          role="group"
          aria-label="As três contas de fontes"
        >
          <div className="source-counter-item">
            <span className="source-counter-label">Total consultadas:</span>
            <span
              className="source-counter-value"
              aria-label={`Total de fontes consultadas: ${totalConsultadasDisplay}`}
            >
              {totalConsultadasDisplay}
            </span>
          </div>

          <span className="source-counter-divider" aria-hidden="true">
            •
          </span>

          <div className="source-counter-item">
            <span className="source-counter-label">Utilizadas no dossiê:</span>
            <span
              className="source-counter-value accent"
              aria-label={`Total de fontes utilizadas no dossiê: ${totalUtilizadasCount}`}
            >
              {totalUtilizadasCount}
            </span>
          </div>

          <span className="source-counter-divider" aria-hidden="true">
            •
          </span>

          <div className="source-counter-item">
            <span className="source-counter-label">Consultadas mas não citadas:</span>
            <span
              className="source-counter-value"
              aria-label={`Fontes consultadas mas não citadas: ${totalNaoUtilizadasDisplay}`}
            >
              {totalNaoUtilizadasDisplay}
            </span>
          </div>
        </div>

        {/* Explicação clara e factual: não citada significa material contextual investigado, não rejeitado */}
        <p className="source-explanation-note">
          Fontes consultadas mas não citadas representam referências e leituras de apoio que compuseram o
          contexto investigativo, sem citação direta no texto final (não constituem fontes rejeitadas).
        </p>
      </header>

      {/* Indicador de carregamento */}
      {loading && (
        <div className="source-loading-state" role="status" aria-live="polite">
          <RefreshCw size={15} className="animate-spin" aria-hidden="true" />
          <span>Carregando fontes...</span>
        </div>
      )}

      {/* Aviso conciso de divergência de versão/hash de artefato (rejeição estrita de fontes alheias) */}
      {isMismatch && (
        <div className="source-notice-banner warning" role="alert">
          <AlertTriangle size={18} aria-hidden="true" />
          <div>
            <strong>
              {mismatchNotice ||
                'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.'}
            </strong>
          </div>
        </div>
      )}

      {/* Erro de requisição (sem ocultar relatório ou quebrar cópia) */}
      {error && !loading && (
        <div className="source-notice-banner">
          <ErrorNotice
            compact
            falha={apresentarErro(error, { acao: 'carregar as fontes' })}
            onRetry={onRetry}
            retryLabel="Carregar de novo"
          />
        </div>
      )}

      {/* Relatório legado confirmado: explicação honesta sem inventar zeros ou afirmar partição completa */}
      {isConfirmedLegacy && (
        <div className="source-notice-banner info" role="status">
          <AlertCircle size={18} aria-hidden="true" />
          <div>
            <strong>Este relatório não guardou as leituras brutas:</strong>
            <p style={{ marginTop: '2px', fontSize: '0.82rem' }}>
              As contagens de fontes consultadas e não citadas não foram registradas para este dossiê e são
              apresentadas como indisponíveis (—). Exibindo abaixo as citações conhecidas extraídas do texto
              publicado.
            </p>
          </div>
        </div>
      )}

      {/* Observação diagnóstica do backend quando presente */}
      {fontes?.observacao && !isConfirmedLegacy && !isMismatch && (
        <div className="source-notice-banner info" role="status">
          <AlertCircle size={18} aria-hidden="true" />
          <div>
            <span>{fontes.observacao}</span>
          </div>
        </div>
      )}

      {/* Grupos acessíveis nativos com <details> / <summary> (somente exibidos se não houver mismatch e não estiver carregando) */}
      {!isMismatch && !loading && (
        <div className="source-groups-container">
          {/* Grupo 1: Utilizadas no Dossiê (Inicia recolhido junto às demais categorias para visualização compacta) */}
          <details className="source-group-details">
            <summary className="source-group-summary">
              <div className="source-group-summary-left">
                <ChevronRight size={16} className="source-group-toggle-icon" aria-hidden="true" />
                <BookmarkCheck size={16} color="var(--color-primary)" aria-hidden="true" />
                <span>Fontes citadas no dossiê</span>
              </div>
              <span className="source-group-badge active" aria-label={`${totalUtilizadasCount} fontes utilizadas`}>
                {totalUtilizadasCount}
              </span>
            </summary>
            <div className="source-group-content">
              <SourceListSection
                items={itemsUtilizadas}
                emptyMessage={
                  itemsUtilizadas.length === 0 && totalUtilizadasCount === '—'
                    ? 'Nenhuma citação de fonte identificada no texto publicado.'
                    : 'Nenhuma fonte citada identificada no texto publicado.'
                }
              />
            </div>
          </details>

          {/* Grupo 2: Consultadas mas Não Citadas (Fechado por padrão) */}
          <details className="source-group-details">
            <summary className="source-group-summary">
              <div className="source-group-summary-left">
                <ChevronRight size={16} className="source-group-toggle-icon" aria-hidden="true" />
                <FileQuestion size={16} color="var(--color-text-muted)" aria-hidden="true" />
                <span>Consultadas, não citadas</span>
              </div>
              <span
                className="source-group-badge"
                aria-label={`${totalNaoUtilizadasDisplay} fontes consultadas mas não citadas`}
              >
                {totalNaoUtilizadasDisplay}
              </span>
            </summary>
            <div className="source-group-content">
              {isConfirmedLegacy || fontes?.total_nao_utilizadas === null ? (
                <p className="source-empty-message">
                  Contabilidade de fontes consultadas indisponível para este relatório legado.
                </p>
              ) : (
                <SourceListSection
                  items={itemsNaoUtilizadas}
                  emptyMessage={
                    fontes?.total_nao_utilizadas === 0
                      ? 'Nenhuma fonte consultada permaneceu sem citação direta.'
                      : 'Contabilidade não registrada para esta categoria.'
                  }
                />
              )}
            </div>
          </details>

          {/* Grupo 3: Todas as Fontes Consultadas (Fechado por padrão) */}
          <details className="source-group-details">
            <summary className="source-group-summary">
              <div className="source-group-summary-left">
                <ChevronRight size={16} className="source-group-toggle-icon" aria-hidden="true" />
                <FileText size={16} color="var(--color-text-muted)" aria-hidden="true" />
                <span>Consultadas com leitura confirmada</span>
              </div>
              <span
                className="source-group-badge"
                aria-label={`${totalConsultadasDisplay} fontes consultadas`}
              >
                {totalConsultadasDisplay}
              </span>
            </summary>
            <div className="source-group-content">
              {isConfirmedLegacy || fontes?.total_consultadas === null ? (
                <p className="source-empty-message">
                  Contabilidade de leituras confirmadas indisponível para este relatório legado.
                </p>
              ) : (
                <SourceListSection
                  items={itemsConsultadas}
                  emptyMessage={
                    fontes?.total_consultadas === 0
                      ? 'Nenhuma fonte com leitura confirmada registrada.'
                      : 'Contabilidade não registrada para esta categoria.'
                  }
                />
              )}
            </div>
          </details>
        </div>
      )}
    </section>
  );
};
