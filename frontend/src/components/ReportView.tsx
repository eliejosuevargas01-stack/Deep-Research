import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkParse from 'remark-parse';
import { unified } from 'unified';
import { Copy, Check, Download, ExternalLink, AlertTriangle, RotateCcw, CheckCircle2 } from 'lucide-react';
import { WriterResponse, FontesResumo } from '../types/api';
import { api } from '../services/api';
import { historyService } from '../services/history';
import { ErrorNotice } from './ErrorNotice';
import { SourceBreakdown } from './SourceBreakdown';
import { formatarTitulo } from '../utils/texto';

interface ReportViewProps {
  report: WriterResponse;
  onReset: () => void;
}

interface VerifiedSourcesState {
  reportId: string;
  publishedText: string;
  publishedHash: string;
  data: FontesResumo | null;
}

export interface BindingVerificationResult {
  isValid: boolean;
  reason?: string;
}

/**
 * Validador estrito de protocolos seguros para prevenção de XSS via Markdown links.
 */
function isSafeUrl(url?: string): boolean {
  if (!url) return false;
  const clean = url.trim().toLowerCase();
  return clean.startsWith('http://') || clean.startsWith('https://');
}

/**
 * Validador puro de produção para vinculação de integridade de fontes ao relatório ativo.
 * Regras estritas:
 * 1. Exige que o resumo de fontes seja fornecido.
 * 2. Exige correspondência idêntica de id_pesquisa quando presente em sources.
 * 3. Se o texto publicado completo (dossier_final) estiver ausente ou em branco (ex: registro legado apenas com resumo),
 *    rejeita a vinculação de resumo de fontes autoritativo de outro artigo por ID isolado e marca os totais como indisponíveis.
 * 4. Para relatórios com texto publicado completo:
 *    - Exige cálculo bem-sucedido de digest local (SHA-256) não-vazio.
 *    - Exige fornecimento obrigatório de artifact_hash pelo backend (inclusive para relatórios legados).
 *    - Exige igualdade exata (case-insensitive) entre artifact_hash e localHash.
 */
export function verifySourcesBinding(
  currentReportId: string,
  publishedText: string,
  localHash: string,
  sources: FontesResumo | null | undefined
): BindingVerificationResult {
  if (!sources) {
    return { isValid: false, reason: 'Nenhum resumo de fontes fornecido.' };
  }

  // 1. Validação estrita de ID da pesquisa
  if (sources.id_pesquisa && sources.id_pesquisa !== currentReportId) {
    return {
      isValid: false,
      reason: 'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.',
    };
  }

  // 2. Se o texto publicado completo estiver ausente ou em branco (ex: registro legado com apenas resumo)
  const cleanPublished = (publishedText || '').trim();
  if (cleanPublished.length === 0) {
    return {
      isValid: false,
      reason: 'Este registro contém apenas um resumo; não é possível confirmar os totais de fontes do relatório completo.',
    };
  }

  // 3. Exige cálculo local de digest bem-sucedido não-vazio
  if (!localHash || localHash.trim().length === 0) {
    return {
      isValid: false,
      reason: 'Falha no cálculo local de integridade do artefato publicado.',
    };
  }

  // 4. Exige fornecimento obrigatório de artifact_hash pelo backend para o artigo publicado
  if (!sources.artifact_hash || sources.artifact_hash.trim().length === 0) {
    return {
      isValid: false,
      reason: 'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.',
    };
  }

  // 5. Exige igualdade exata (case-insensitive) entre artifact_hash e localHash
  if (sources.artifact_hash.trim().toLowerCase() !== localHash.trim().toLowerCase()) {
    return {
      isValid: false,
      reason: 'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.',
    };
  }

  return { isValid: true };
}

/**
 * Extrai URLs canônicas citadas no corpo do Markdown usando o parser AST oficial.
 * Ignora blocos de código (code/inlineCode), resolve referências citadas e descarta definições não citadas.
 */
export function extractSourcesFromMarkdown(md: string): string[] {
  if (!md || typeof md !== 'string') return [];
  try {
    const processor = unified().use(remarkParse).use(remarkGfm);
    const tree = processor.parse(md);

    const definitions = new Map<string, string>();
    const urls = new Set<string>();
    const citedRefIds = new Set<string>();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    function collect(node: any) {
      if (!node) return;
      if (node.type === 'code' || node.type === 'inlineCode') return;
      if (node.type === 'definition' && typeof node.identifier === 'string' && typeof node.url === 'string') {
        definitions.set(node.identifier.toLowerCase(), node.url.trim());
      }
      if (node.type === 'link' && typeof node.url === 'string') {
        const clean = node.url.trim();
        if (clean.startsWith('http://') || clean.startsWith('https://')) {
          urls.add(clean);
        }
      }
      if (node.type === 'linkReference' && typeof node.identifier === 'string') {
        citedRefIds.add(node.identifier.toLowerCase());
      }
      if (Array.isArray(node.children)) {
        for (const child of node.children) {
          collect(child);
        }
      }
    }

    collect(tree);

    for (const refId of citedRefIds) {
      const defUrl = definitions.get(refId);
      if (defUrl && (defUrl.startsWith('http://') || defUrl.startsWith('https://'))) {
        urls.add(defUrl);
      }
    }

    return Array.from(urls);
  } catch {
    return [];
  }
}

/**
 * Calcula o hash SHA-256 do artefato publicado de forma idêntica à assinatura do backend.
 */
export async function computeArtifactHash(text: string): Promise<string> {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    return '';
  }
  try {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return '';
  }
}

export const ReportView: React.FC<ReportViewProps> = ({ report, onReset }) => {
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const containerRef = useRef<HTMLElement>(null);

  // Estados de contabilidade de fontes com vinculação estrita de versão/artefato
  const [verifiedSources, setVerifiedSources] = useState<VerifiedSourcesState | null>(null);
  const [loadingSources, setLoadingSources] = useState<boolean>(true);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [isMismatch, setIsMismatch] = useState<boolean>(false);
  const [mismatchNotice, setMismatchNotice] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState<number>(0);

  const markdownText = report.dossier_final || report.dossier_resumo || '';
  const isComplete = report.status === 'concluido';
  const fallbackSources = extractSourcesFromMarkdown(markdownText);
  const publishedText = report.dossier_final || '';

  // Defeito corrigido: ao concluir o relatório, garante foco no topo do dossiê em vez de rolar até o final/bibliografia
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (containerRef.current) {
      containerRef.current.focus();
    }
  }, []);

  // Hidratação e vinculação estrita de integridade de versão por artifact_hash e id_pesquisa
  useEffect(() => {
    let isCancelled = false;
    const abortController = new AbortController();

    // Limpa imediatamente o estado visível anterior ao trocar de relatório ou recalcular hash
    setLoadingSources(true);
    setSourcesError(null);
    setIsMismatch(false);
    setMismatchNotice(null);
    setVerifiedSources(null);

    const hydrateSources = async () => {
      // Se o texto publicado completo estiver ausente ou em branco (ex: registro contendo apenas resumo)
      const cleanPublished = (publishedText || '').trim();
      if (cleanPublished.length === 0) {
        setIsMismatch(true);
        setMismatchNotice(
          'Este registro contém apenas um resumo; não é possível confirmar os totais de fontes do relatório completo.'
        );
        setVerifiedSources(null);
        setLoadingSources(false);
        return;
      }

      const localHash = await computeArtifactHash(publishedText);
      if (isCancelled) return;

      // Se o relatório já traz o resumo de fontes injetado
      if (report.fontes) {
        const check = verifySourcesBinding(report.id_pesquisa, publishedText, localHash, report.fontes);
        if (!check.isValid) {
          setIsMismatch(true);
          setMismatchNotice(check.reason || 'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.');
          setVerifiedSources(null);
          setLoadingSources(false);
          return;
        }

        setVerifiedSources({
          reportId: report.id_pesquisa,
          publishedText,
          publishedHash: localHash,
          data: report.fontes,
        });
        setIsMismatch(false);
        setMismatchNotice(null);
        setLoadingSources(false);
        setSourcesError(null);
        return;
      }

      // Se não há id_pesquisa, não é possível consultar a API
      if (!report.id_pesquisa) {
        setVerifiedSources(null);
        setLoadingSources(false);
        return;
      }

      // Hidrata via GET /api/v1/pipeline/{id_pesquisa}/sources
      try {
        const data = await api.getSources(report.id_pesquisa, abortController.signal);
        if (isCancelled) return;

        const check = verifySourcesBinding(report.id_pesquisa, publishedText, localHash, data);
        if (!check.isValid) {
          setIsMismatch(true);
          setMismatchNotice(check.reason || 'As fontes disponíveis pertencem a outra versão deste relatório. O texto foi preservado.');
          setVerifiedSources(null);
          setLoadingSources(false);
          return;
        }

        // Resumo validado com sucesso
        setVerifiedSources({
          reportId: report.id_pesquisa,
          publishedText,
          publishedHash: localHash,
          data,
        });
        setIsMismatch(false);
        setMismatchNotice(null);
        setLoadingSources(false);

        // Atualização segura do histórico: APENAS se o registro existente coincidir exatamente com o corpo/hash publicado
        const existingRecord = historyService.get(report.id_pesquisa);
        if (existingRecord && existingRecord.writerResponse) {
          const existingText = existingRecord.writerResponse.dossier_final || '';
          if (existingText === publishedText) {
            const updatedRecord = {
              ...existingRecord,
              writerResponse: {
                ...existingRecord.writerResponse,
                fontes: data,
              },
            };
            historyService.save(updatedRecord);
          }
        }
      } catch (err: unknown) {
        if (isCancelled) return;
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        const errorMsg = err instanceof Error ? err.message : 'Falha na comunicação com o servidor';
        setSourcesError(errorMsg);
        setLoadingSources(false);
      }
    };

    hydrateSources();

    return () => {
      isCancelled = true;
      abortController.abort();
    };
  }, [report.id_pesquisa, publishedText, report.dossier_resumo, report.fontes, retryTrigger]);

  const handleRetrySources = () => {
    setRetryTrigger((prev) => prev + 1);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdownText);
      setCopied(true);
      setActionFeedback('Texto do dossiê copiado para a área de transferência.');
      setTimeout(() => {
        setCopied(false);
        setActionFeedback(null);
      }, 2500);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = markdownText;
      document.body.appendChild(textarea);
      textarea.select();
      const copiou = document.execCommand('copy');
      document.body.removeChild(textarea);
      if (!copiou) {
        setCopied(false);
        setActionFeedback('Não foi possível copiar. Selecione o texto e use Ctrl+C.');
        setTimeout(() => setActionFeedback(null), 4000);
        return;
      }
      setCopied(true);
      setActionFeedback('Texto do dossiê copiado para a área de transferência.');
      setTimeout(() => {
        setCopied(false);
        setActionFeedback(null);
      }, 2500);
    }
  };

  const handleDownload = () => {
    const safeName = (report.tema || 'dossier')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '-')
      .replace(/-+/g, '-')
      .slice(0, 50);
    const blob = new Blob([markdownText], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `dossie-${safeName}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setDownloaded(true);
    setActionFeedback('Arquivo Markdown baixado.');
    setTimeout(() => {
      setDownloaded(false);
      setActionFeedback(null);
    }, 2500);
  };

  // Fontes seguras derivadas exclusivamente se a identidade verificada bater COM AMBOS: id E texto publicado completo não-vazio
  const isExactIdentityMatched =
    !isMismatch &&
    Boolean(
      verifiedSources &&
        verifiedSources.reportId === report.id_pesquisa &&
        verifiedSources.publishedText === publishedText &&
        publishedText.trim().length > 0
    );

  const activeSources = isExactIdentityMatched ? verifiedSources!.data : null;

  const totalConsultadasText =
    activeSources && activeSources.total_consultadas !== null && activeSources.total_consultadas !== undefined
      ? `${activeSources.total_consultadas} consultadas`
      : '— consultadas';

  const totalUtilizadasCount =
    activeSources && activeSources.total_utilizadas !== null && activeSources.total_utilizadas !== undefined
      ? activeSources.total_utilizadas
      : !isMismatch && isExactIdentityMatched && fallbackSources.length > 0
      ? fallbackSources.length
      : '—';

  return (
    <article
      ref={containerRef}
      tabIndex={-1}
      className="report-card"
      id="dossier-report"
      aria-labelledby="dossier-heading"
    >
      {/* Feedback para leitores de tela */}
      {actionFeedback && (
        <div className="sr-only" role="status" aria-live="polite">
          {actionFeedback}
        </div>
      )}

      {/* Dossiê incompleto: diz o tamanho do problema antes do texto */}
      {!isComplete && (
        <div className="report-warning-slot">
          <ErrorNotice
            falha={{
              titulo: 'Este dossiê ficou incompleto',
              mensagem: 'Alguns pontos não tinham evidência suficiente. O texto abaixo foi preservado como está e pode ser lido e copiado normalmente.',
              detalhe: report.diagnostico || undefined,
              tom: 'aviso',
            }}
          />
        </div>
      )}

      {/* Cabeçalho e Barra de Ações do Dossiê */}
      <header className="report-header-actions">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              className={`status-badge-chip ${isComplete ? 'concluido' : 'reprovado'}`}
            >
              {isComplete ? (
                <>
                  <CheckCircle2 size={12} aria-hidden="true" />
                  <span>Dossiê Concluído</span>
                </>
              ) : (
                <>
                  <AlertTriangle size={12} aria-hidden="true" />
                  <span>Status: {report.status}</span>
                </>
              )}
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              {report.concluido_em
                ? new Date(report.concluido_em).toLocaleString('pt-BR')
                : 'Conclusão registrada'}
            </span>
          </div>
          <h1 id="dossier-heading" className="card-title" style={{ fontSize: '1.4rem' }}>
            {formatarTitulo(report.tema)}
          </h1>
        </div>

        <div className="report-buttons">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleCopy}
            title="Copiar texto Markdown para a área de transferência"
          >
            {copied ? (
              <>
                <Check size={16} aria-hidden="true" />
                <span>Copiado</span>
              </>
            ) : (
              <>
                <Copy size={16} aria-hidden="true" />
                <span>Copiar Markdown</span>
              </>
            )}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={handleDownload}
            title="Baixar arquivo .md formatado"
          >
            {downloaded ? (
              <>
                <Check size={16} aria-hidden="true" />
                <span>Baixado</span>
              </>
            ) : (
              <>
                <Download size={16} aria-hidden="true" />
                <span>Baixar .md</span>
              </>
            )}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={onReset}
            title="Iniciar nova pesquisa"
          >
            <RotateCcw size={16} aria-hidden="true" />
            <span>Nova pesquisa</span>
          </button>
        </div>
      </header>

      {/* Metadados Fidedignos do Artigo */}
      <div className="report-stats">
        <span>Volume textual: {report.total_caracteres_dossier.toLocaleString('pt-BR')} caracteres</span>
        <span>•</span>
        <span>
          Fontes: {totalConsultadasText} • {totalUtilizadasCount} utilizadas
        </span>
      </div>

      {/* Corpo Formatado do Dossiê */}
      <section className="markdown-body" aria-label="Conteúdo do dossiê analítico">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // O dossiê costuma começar com "# Título", o que geraria um segundo <h1>
            // ao lado do <h1> da página. Rebaixa todos os níveis em um degrau.
            h1: ({ children }) => <h2>{children}</h2>,
            h2: ({ children }) => <h3>{children}</h3>,
            a: ({ href, children, ...props }) => {
              const safe = isSafeUrl(href);
              if (!safe) {
                return <span>{children}</span>;
              }
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  {...props}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                >
                  <span>{children}</span>
                  <ExternalLink size={12} aria-hidden="true" />
                </a>
              );
            },
          }}
        >
          {markdownText}
        </ReactMarkdown>
      </section>

      {/* Detalhamento Contábil de Fontes (Substitui o rótulo enganoso anterior) */}
      <SourceBreakdown
        fontes={activeSources}
        loading={loadingSources}
        error={sourcesError}
        onRetry={handleRetrySources}
        fallbackCitations={fallbackSources}
        isMismatch={isMismatch}
        mismatchNotice={mismatchNotice}
      />
    </article>
  );
};
