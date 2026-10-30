import React, { useEffect, useMemo, useState } from 'react';
import { History, Trash2, ExternalLink, Calendar, Hash, AlertCircle, FileText, Plus, Search } from 'lucide-react';
import { PipelineStatusResumo, ResearchHistoryRecord } from '../types/api';
import { api } from '../services/api';
import { ErrorNotice } from './ErrorNotice';
import { formatarTitulo } from '../utils/texto';

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
      <header className="card-header" style={{ marginBottom: 0 }}>
        <div>
          <h1 id="history-heading" className="card-title">
            Histórico de Investigações
          </h1>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              marginTop: '4px',
              fontSize: '0.8rem',
              color: 'var(--color-text-muted)',
            }}
          >
            <AlertCircle size={14} aria-hidden="true" />
            <span>
              Histórico deste dispositivo. Segredos nunca são gravados.
            </span>
          </div>
        </div>

        {records.length > 0 && (
          <button
            type="button"
            className="btn-secondary"
            onClick={onClearAll}
            title="Remover todas as pesquisas do histórico local"
            style={{ color: 'var(--color-danger-text)' }}
          >
            <Trash2 size={16} aria-hidden="true" />
            <span>Limpar histórico</span>
          </button>
        )}
      </header>

      {records.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 16px' }}>
          <History size={36} color="var(--color-text-muted)" style={{ margin: '0 auto 12px' }} />
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            Nenhuma pesquisa gravada no histórico deste navegador
          </h2>
          <p style={{ marginTop: '6px', fontSize: '0.88rem', color: 'var(--color-text-secondary)' }}>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
                    <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                      ID: {record.id_pesquisa.slice(0, 8)}...
                    </span>
                  </div>

                  <h3 className="history-title" title={record.tema}>
                    {formatarTitulo(record.tema)}
                  </h3>

                  <div className="history-meta">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
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
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <Hash size={13} aria-hidden="true" />
                      {`${record.total_pontos} ${record.total_pontos === 1 ? 'ponto' : 'pontos'}`}
                    </span>
                    {hasDossier && (
                      <>
                        <span>•</span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
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
                      const rotuloEtapa: Record<string, string> = {
                        planejado: 'Planejado',
                        buscando: 'Buscando',
                        auditando: 'Auditando',
                        redigindo: 'Redigindo',
                        concluido: 'Concluído',
                        reprovado: 'Reprovado',
                        falha: 'Falhou',
                      };
                      return (
                        <>
                          <span>•</span>
                          <span
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                            title={`Estágio atual no servidor: ${vivo.status_pipeline} (${vivo.total_pontos} pontos)`}
                          >
                            <span aria-hidden="true">●</span>
                            {`${rotuloEtapa[vivo.status_pipeline] ?? vivo.status_pipeline} · ${concluidos}/${vivo.total_pontos}`}
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
                    className="btn-secondary"
                    onClick={() => onDeleteRecord(record.id_pesquisa)}
                    title="Excluir do histórico local"
                    style={{ padding: '8px 10px' }}
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
