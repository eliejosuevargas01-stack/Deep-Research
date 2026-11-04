import React, { useEffect, useMemo, useState } from 'react';
import { History, Trash2, ExternalLink, Calendar, Hash, AlertCircle, FileText, Plus, Search } from 'lucide-react';
import { PipelineStatusResumo, ResearchHistoryRecord } from '../types/api';
import { api } from '../services/api';
import { ErrorNotice } from './ErrorNotice';
import { formatarTitulo, rotuloStatus } from '../utils/texto';

interface HistoryViewProps {
  records: ResearchHistoryRecord[];
  onSelectRecord: (record: ResearchHistoryRecord) => void;
  onDeleteRecord: (id_pesquisa: string) => void;
  onClearAll: () => void;
}

const STATUS_LABEL: Record<ResearchHistoryRecord['status'], string> = {
  planejado: 'Planejado',
  buscando: 'Buscando evidências',
  auditando: 'Em auditoria',
  redigindo: 'Redigindo',
  concluido: 'Concluído',
  reprovado: 'Reprovado',
  falha: 'Falhou',
};

export const HistoryView: React.FC<HistoryViewProps> = ({
  records,
  onSelectRecord,
  onDeleteRecord,
  onClearAll,
}) => {
  const [busca, setBusca] = useState('');
  const [filtro, setFiltro] = useState<'todos' | 'concluido' | 'andamento' | 'falha'>('todos');
  // Passo 3: status vivo por pesquisa, sem abrir SSE. Só consulta quem não
  // está concluído no registro local — dossiê pronto não muda de estágio.
  const [statusPorId, setStatusPorId] = useState<Record<string, PipelineStatusResumo>>({});
  const [statusFalhas, setStatusFalhas] = useState(0);

  useEffect(() => {
    let cancelado = false;
    const alvos = records.filter(
      (r) => r.status !== 'concluido' && !r.writerResponse?.dossier_final && !(r.id_pesquisa in statusPorId)
    );
    if (alvos.length === 0) return;
    void (async () => {
      const resultados = await Promise.allSettled(alvos.map((r) => api.getPipelineStatus(r.id_pesquisa)));
      if (cancelado) return;
      setStatusPorId((anterior) => {
        const proximo = { ...anterior };
        resultados.forEach((res, i) => {
          if (res.status === 'fulfilled') proximo[alvos[i].id_pesquisa] = res.value;
        });
        return proximo;
      });
      // Andamento ao vivo é best-effort: quando falha, a lista continua com o
      // status salvo e a pessoa precisa saber que ele pode estar velho.
      setStatusFalhas(resultados.filter((res) => res.status === 'rejected').length);
    })();
    return () => {
      cancelado = true;
    };
    // Intencional: dispara uma vez por conjunto de ids; o mapa evita refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [records]);

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return records.filter((r) => {
      const casaTermo = !termo || r.tema.toLowerCase().includes(termo) || r.id_pesquisa.toLowerCase().includes(termo);
      const casaFiltro =
        filtro === 'todos'
          ? true
          : filtro === 'falha'
          ? r.status === 'falha' || r.status === 'reprovado'
          : filtro === 'concluido'
          ? r.status === 'concluido'
          : r.status === 'buscando' || r.status === 'auditando' || r.status === 'redigindo';
      return casaTermo && casaFiltro;
    });
  }, [records, busca, filtro]);

  return (
    <div className="history-container" aria-labelledby="history-heading">
      <header className="card-header hist-header">
        <div>
          <h1 id="history-heading" className="card-title">
            Histórico de Investigações
          </h1>
          <div className="hist-subtitle">
            <AlertCircle size={14} aria-hidden="true" />
            <span>
              Histórico deste dispositivo. Segredos nunca são gravados.
            </span>
          </div>
        </div>

        {records.length > 0 && (
          <button
            type="button"
            className="btn-secondary hist-clear-btn"
            onClick={onClearAll}
            title="Remover todas as pesquisas do histórico local"
          >
            <Trash2 size={16} aria-hidden="true" />
            <span>Limpar histórico</span>
          </button>
        )}
      </header>

      {records.length === 0 ? (
        <div className="card hist-empty-card">
          <History size={36} color="var(--color-text-muted)" className="hist-empty-icon" />
          <h2 className="hist-empty-title">
            Nenhuma pesquisa gravada no histórico deste navegador
          </h2>
          <p className="hist-empty-text">
            Formule um tema e execute o fluxo: o resumo aparece aqui para reabrir quando quiser.
          </p>
          <button
            type="button"
            className="btn-new-research history-empty-cta"
            onClick={() => {
              window.location.hash = '#research';
              window.setTimeout(() => {
                document.querySelector<HTMLInputElement>('#composer-theme-input')?.focus();
              }, 120);
            }}
          >
            <Plus size={16} aria-hidden="true" />
            <span>Formular nova pesquisa</span>
          </button>
        </div>
      ) : (
        <div className="hist-list">
          <div className="history-toolbar">
            <label className="history-search">
              <Search size={14} aria-hidden="true" />
              <input
                type="search"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar por tema ou ID"
                aria-label="Buscar no histórico por tema ou ID"
              />
            </label>
            <div className="history-filters" role="group" aria-label="Filtrar histórico por situação">
              {([
                ['todos', 'Todos'],
                ['concluido', 'Concluídos'],
                ['andamento', 'Em andamento'],
                ['falha', 'Falhas'],
              ] as const).map(([valor, rotulo]) => (
                <button
                  key={valor}
                  type="button"
                  className={`history-filter ${filtro === valor ? 'selected' : ''}`}
                  aria-pressed={filtro === valor}
                  onClick={() => setFiltro(valor)}
                >
                  {rotulo}
                </button>
              ))}
            </div>
          </div>

          {statusFalhas > 0 && (
            <ErrorNotice
              compact
              falha={{
                titulo: 'O andamento ao vivo não atualizou',
                mensagem: `${statusFalhas === 1 ? 'Uma pesquisa ficou' : `${statusFalhas} pesquisas ficaram`} com a situação de antes. O histórico salvo continua certo.`,
                tom: 'aviso',
              }}
              onRetry={() => setStatusPorId({})}
              retryLabel="Atualizar andamento"
            />
          )}

          {filtrados.length === 0 && (
            <p className="history-empty-filter">Nenhuma pesquisa corresponde a este filtro.</p>
          )}
          <div role="status" aria-live="polite" className="sr-only">
            {filtrados.length} {filtrados.length === 1 ? 'pesquisa' : 'pesquisas'}
          </div>

          {filtrados.map((record) => {
            const hasDossier = Boolean(record.writerResponse?.dossier_final);
            return (
              <div
                key={record.id_pesquisa}
                className="history-item-card"
                onClick={(event) => {
                  // Linha inteira abre a pesquisa; os botões de ação continuam
                  // sendo os alvos acessíveis por teclado.
                  if ((event.target as HTMLElement).closest('button')) return;
                  onSelectRecord(record);
                }}
              >
                <div className="history-info">
                  <div className="hist-item-top">
                    <span
                      className={`status-badge-chip ${
                        record.status === 'concluido'
                          ? 'concluido'
                          : record.status === 'reprovado' || record.status === 'falha'
                          ? 'reprovado'
                          : 'planejado'
                      }`}
                    >
                      {STATUS_LABEL[record.status] ?? record.status}
                    </span>
                    <span className="hist-item-id">
                      ID: {record.id_pesquisa.slice(0, 8)}...
                    </span>
                  </div>

                  <h2 className="history-title" title={record.tema}>
                    <a className="history-title-link" href={`#research/${record.id_pesquisa}`}>
                      {formatarTitulo(record.tema)}
                    </a>
                  </h2>

                  <div className="history-meta">
                    <span className="hist-meta-item">
                      <Calendar size={13} aria-hidden="true" />
                      {new Date(record.criado_em).toLocaleDateString('pt-BR', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span>•</span>
                    <span className="hist-meta-item">
                      <Hash size={13} aria-hidden="true" />
                      {`${record.total_pontos} ${record.total_pontos === 1 ? 'ponto' : 'pontos'}`}
                    </span>
                    {hasDossier && (
                      <>
                        <span>•</span>
                        <span className="hist-meta-item">
                          <FileText size={13} aria-hidden="true" />
                          Dossiê disponível
                        </span>
                      </>
                    )}
                    {(() => {
                      const vivo = statusPorId[record.id_pesquisa];
                      if (!vivo || hasDossier || record.status === 'concluido') return null;
                      const concluidos = vivo.pontos.filter(
                        (p) => p.status === 'aprovado' || p.status === 'coletado'
                      ).length;
                      return (
                        <>
                          <span>•</span>
                          <span
                            className="hist-meta-item"
                            title={`Etapa no servidor: ${rotuloStatus(vivo.status_pipeline)} (${vivo.total_pontos} pontos)`}
                          >
                            <span aria-hidden="true">●</span>
                            {`${rotuloStatus(vivo.status_pipeline)} · ${concluidos}/${vivo.total_pontos}`}
                          </span>
                        </>
                      );
                    })()}
                  </div>
                </div>

                <div className="history-actions">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => onSelectRecord(record)}
                    title="Abrir esta pesquisa no workspace"
                  >
                    <ExternalLink size={15} aria-hidden="true" />
                    <span>Abrir</span>
                  </button>
                  <button
                    type="button"
                    className="btn-secondary hist-delete-btn"
                    onClick={() => onDeleteRecord(record.id_pesquisa)}
                    title="Excluir do histórico local"
                    aria-label={`Excluir pesquisa ${record.tema}`}
                  >
                    <Trash2 size={15} aria-hidden="true" color="var(--color-danger-text)" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
