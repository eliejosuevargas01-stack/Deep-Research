import { useCallback, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ApiV12Error,
  criarPesquisa,
  ehErroApiKey,
  type ResearchCreateRequest,
  type ResearchRun,
} from '../services/apiV12';
import {
  type AuditoriaViva,
  type EstadoAoVivo,
  type EstadoPonto,
  type FonteViva,
  type PontoVivo,
} from './usePesquisaAoVivo';

/* ------------------------------------------------------------------ */
/* Histórico local (localStorage)                                      */
/* ------------------------------------------------------------------ */

export interface HistoricoItem {
  research_id: string;
  tema: string;
  status: string;
  criado_em: string;
}

const CHAVE_HISTORICO = 'dr:v12:historico';
/** Reexportada do hook; mantida aqui para compatibilidade de import. */
export { CHAVE_ATIVA } from './usePesquisaAoVivo';

function lerHistorico(): HistoricoItem[] {
  try {
    const bruto = localStorage.getItem(CHAVE_HISTORICO);
    if (!bruto) return [];
    const lista = JSON.parse(bruto) as unknown;
    if (!Array.isArray(lista)) return [];
    return lista.filter(
      (i): i is HistoricoItem =>
        !!i && typeof (i as HistoricoItem).research_id === 'string',
    );
  } catch {
    return [];
  }
}

function gravarHistorico(lista: HistoricoItem[]): void {
  try {
    localStorage.setItem(CHAVE_HISTORICO, JSON.stringify(lista.slice(0, 50)));
  } catch {
    /* armazenamento indisponível: segue sem persistir */
  }
}

function registrarNoHistorico(run: ResearchRun): void {
  const lista = lerHistorico().filter((i) => i.research_id !== run.research_id);
  lista.unshift({
    research_id: run.research_id,
    tema: run.tema,
    status: run.status,
    criado_em: new Date().toISOString(),
  });
  gravarHistorico(lista);
}

function atualizarStatusHistorico(research_id: string, status: string): void {
  gravarHistorico(
    lerHistorico().map((i) => (i.research_id === research_id ? { ...i, status } : i)),
  );
}

/* ------------------------------------------------------------------ */
/* Validação local (espelha contracts.py — evita 422 desnecessário)    */
/* ------------------------------------------------------------------ */

const ATUALIDADE_RE = /^(ALL|\d{1,3}[HDMY])$/;

export interface FormPesquisa {
  tema: string;
  profundidade: number;
  veracidade_alvo: number;
  max_rodadas_auditoria: number;
  atualidade: string;
  callback_url: string;
}

export function validarForm(f: FormPesquisa): Record<string, string> {
  const erros: Record<string, string> = {};
  if (f.tema.trim().length < 3) erros.tema = 'Tema precisa de ao menos 3 caracteres.';
  if (!Number.isInteger(f.profundidade) || f.profundidade < 1 || f.profundidade > 10)
    erros.profundidade = 'Profundidade deve ser um inteiro de 1 a 10.';
  if (Number.isNaN(f.veracidade_alvo) || f.veracidade_alvo < 0 || f.veracidade_alvo > 100)
    erros.veracidade_alvo = 'Veracidade alvo deve estar entre 0 e 100.';
  if (
    !Number.isInteger(f.max_rodadas_auditoria) ||
    f.max_rodadas_auditoria < 1 ||
    f.max_rodadas_auditoria > 10
  )
    erros.max_rodadas_auditoria = 'Máximo de rodadas deve ser um inteiro de 1 a 10.';
  if (!ATUALIDADE_RE.test(f.atualidade.trim()))
    erros.atualidade = 'Use ALL ou formato como 24H, 7D, 1M, 1Y.';
  try {
    const u = new URL(f.callback_url.trim());
    if (u.protocol !== 'http:' && u.protocol !== 'https:')
      erros.callback_url = 'callback_url precisa ser uma URL http(s).';
  } catch {
    erros.callback_url = 'callback_url precisa ser uma URL http(s) válida.';
  }
  return erros;
}

/* ------------------------------------------------------------------ */
/* Utilidades de apresentação                                          */
/* ------------------------------------------------------------------ */

function formatarData(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('pt-BR');
}

function statusClasse(status: string): string {
  if (status === 'COMPLETED') return 'pill pill-green';
  if (status === 'FAILED') return 'pill pill-red';
  return 'pill pill-amber';
}

function statusRotulo(status: string): string {
  if (status === 'COMPLETED') return 'Concluída';
  if (status === 'FAILED') return 'Falhou';
  return 'Processando';
}

function pontoClasse(estado: EstadoPonto): string {
  if (estado === 'aprovado' || estado === 'finalizado') return 'pill pill-green';
  if (estado === 'reprovado' || estado === 'erro') return 'pill pill-red';
  return 'pill pill-amber';
}

function pontoRotulo(p: PontoVivo): string {
  switch (p.estado) {
    case 'aprovado':
      return 'Aprovado';
    case 'finalizado':
      return 'Finalizado';
    case 'reprovado':
      return 'Reprovado';
    case 'erro':
      return 'Erro';
    case 'incompleto':
      return 'Incompleto';
    case 'coletado':
      return 'Coletado';
    case 'auditando':
      return 'Auditando';
    default:
      return 'Em execução';
  }
}

function UrlList({ titulo, urls }: { titulo: string; urls?: string[] | null }) {
  if (!urls || urls.length === 0) return null;
  return (
    <section className="card" aria-label={titulo}>
      <div className="card-header">
        <h3 className="card-title">
          {titulo} ({urls.length})
        </h3>
      </div>
      <ul className="v12-url-list">
        {urls.map((u) => (
          <li key={u}>
            <a href={u} target="_blank" rel="noreferrer noopener">
              {u}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Dossiê                                                              */
/* ------------------------------------------------------------------ */

function downloadMarkdown(run: ResearchRun): void {
  const linhas = [
    `# ${run.tema}`,
    '',
    `- research_id: ${run.research_id}`,
    `- status: ${run.status}`,
    `- criada em: ${run.created_at ?? '—'} | concluída em: ${run.completed_at ?? '—'}`,
    `- tokens totais: ${run.total_tokens ?? '—'}`,
    '',
    run.relatorio_final_consolidado ?? '(relatório ainda indisponível)',
    '',
  ];
  const lacunas = run.lacunas_finais_consolidadas;
  if (Array.isArray(lacunas) && lacunas.length > 0) {
    linhas.push('## Lacunas finais', '');
    for (const l of lacunas as Array<{ ponto_id?: number; lacunas?: string }>) {
      linhas.push(`- Ponto ${l.ponto_id ?? '?'}: ${l.lacunas ?? ''}`);
    }
    linhas.push('');
  }
  const blob = new Blob([linhas.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `dossie-${run.research_id}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function DossieView({ run }: { run: ResearchRun }) {
  const [copiado, setCopiado] = useState(false);
  const pontos = run.pontos ?? [];
  const auditorias = run.auditorias ?? [];
  const avaliacao = run.avaliacao_pontos ?? [];
  const terminal = run.status === 'COMPLETED' || run.status === 'FAILED';

  const copiar = useCallback(async () => {
    const texto = run.relatorio_final_consolidado ?? '';
    if (!texto) return;
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  }, [run.relatorio_final_consolidado]);

  // Pontos sem veredito após conclusão: perguntas não concluídas em destaque.
  const pendentes = pontos.filter((p) => p.aprovado !== true);
  const rotuloPonto = (p: (typeof pontos)[number]): string => {
    if (p.aprovado === true) return 'Aprovado';
    if (p.aprovado === false) return 'Reprovado';
    return terminal ? 'Incompleto' : 'Pendente';
  };
  const classePonto = (p: (typeof pontos)[number]): string => {
    if (p.aprovado === true) return 'pill pill-green';
    if (p.aprovado === false) return 'pill pill-red';
    return 'pill pill-amber';
  };

  return (
    <div className="v12-stack">
      <section className="card" aria-label="Resumo da pesquisa">
        <div className="card-header">
          <h2 className="card-title">{run.tema}</h2>
          <span className={statusClasse(run.status)} role="status">
            {statusRotulo(run.status)}
          </span>
        </div>
        <dl className="v12-meta">
          <div>
            <dt>ID</dt>
            <dd>
              <code>{run.research_id}</code>
            </dd>
          </div>
          <div>
            <dt>Profundidade</dt>
            <dd>{run.profundidade}</dd>
          </div>
          <div>
            <dt>Veracidade alvo</dt>
            <dd>{run.veracidade_alvo}</dd>
          </div>
          <div>
            <dt>Atualidade</dt>
            <dd>{run.atualidade}</dd>
          </div>
          <div>
            <dt>Tokens (prompt/compl/reac/total)</dt>
            <dd>
              {run.total_prompt_tokens ?? 0} / {run.total_completion_tokens ?? 0} /{' '}
              {run.total_reasoning_tokens ?? 0} / <strong>{run.total_tokens ?? 0}</strong>
            </dd>
          </div>
          <div>
            <dt>Criada em</dt>
            <dd>{formatarData(run.created_at)}</dd>
          </div>
          <div>
            <dt>Concluída em</dt>
            <dd>{formatarData(run.completed_at)}</dd>
          </div>
        </dl>
      </section>

      {run.status !== 'COMPLETED' && run.status !== 'FAILED' && (
        <div className="alert-banner info" role="status">
          <span className="spinner spinner--xs" aria-hidden="true" /> Processando — atualizações
          chegam ao vivo pelo stream.
        </div>
      )}
      {run.status === 'FAILED' && (
        <div className="alert-banner danger" role="alert">
          A pesquisa falhou{run.erro ? `: ${run.erro}` : ' no backend. Verifique os logs do servidor.'}
        </div>
      )}

      {terminal && pendentes.length > 0 && (
        <section className="card" aria-label="Perguntas não concluídas">
          <div className="card-header">
            <h3 className="card-title">
              Perguntas não concluídas ({pendentes.length})
            </h3>
          </div>
          <p className="v12-muted">
            Estes pontos não foram aprovados, mas o restante do dossiê segue válido.
          </p>
          <ul className="v12-incompletos">
            {pendentes.map((p) => (
              <li key={p.ponto_id}>
                <strong>Ponto {p.ponto_id}</strong> — {rotuloPonto(p)}
                {p.lacunas_ponto ? `: ${p.lacunas_ponto}` : ''}
              </li>
            ))}
          </ul>
        </section>
      )}

      {pontos.length > 0 && (
        <section className="card" aria-label="Pontos da pesquisa">
          <div className="card-header">
            <h3 className="card-title">Pontos ({pontos.length})</h3>
          </div>
          <div className="v12-grid">
            {pontos.map((p) => (
              <article key={p.ponto_id} className="v12-point-card">
                <header>
                  <strong>
                    {p.ponto_id}. {p.enunciado}
                  </strong>
                  <div className="v12-point-badges">
                    <span className={classePonto(p)}>{rotuloPonto(p)}</span>
                    <span className="pill" title="Porcentagem de aprovação">
                      {p.porcentagem_aprovacao ?? 0}% · rodada {p.rodada_atual ?? 1}
                    </span>
                  </div>
                </header>
                {p.relatorio_ponto && (
                  <div className="v12-md">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{p.relatorio_ponto}</ReactMarkdown>
                  </div>
                )}
                {p.lacunas_ponto && (
                  <p className="v12-lacunas">
                    <strong>Lacunas:</strong> {p.lacunas_ponto}
                  </p>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {auditorias.length > 0 && (
        <section className="card" aria-label="Histórico de auditorias">
          <div className="card-header">
            <h3 className="card-title">Auditorias ({auditorias.length})</h3>
          </div>
          <table className="v12-table">
            <thead>
              <tr>
                <th scope="col">Ponto</th>
                <th scope="col">Rodada</th>
                <th scope="col">Taxa</th>
                <th scope="col">Aprovado</th>
                <th scope="col">Modelo</th>
              </tr>
            </thead>
            <tbody>
              {auditorias.map((a, i) => (
                <tr key={`${a.ponto_id}-${a.rodada}-${i}`}>
                  <td>{a.ponto_id}</td>
                  <td>{a.rodada}</td>
                  <td>{a.porcentagem_aprovacao ?? '—'}%</td>
                  <td>{a.aprovado ? 'sim' : 'não'}</td>
                  <td>{a.model_used ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {avaliacao.length > 0 && (
        <section className="card" aria-label="Avaliação por ponto">
          <div className="card-header">
            <h3 className="card-title">Avaliação por ponto ({avaliacao.length})</h3>
          </div>
          <table className="v12-table">
            <thead>
              <tr>
                <th scope="col">Ponto</th>
                <th scope="col">Acertos</th>
                <th scope="col">Taxa</th>
                <th scope="col">Aprovado</th>
              </tr>
            </thead>
            <tbody>
              {avaliacao.map((a) => (
                <tr key={a.ponto_id}>
                  <td>{a.ponto_id}</td>
                  <td>
                    {a.perguntas_true ?? '—'}/{a.total_perguntas ?? '—'}
                  </td>
                  <td>{a.porcentagem_aprovacao ?? '—'}%</td>
                  <td>{a.aprovado ? 'sim' : 'não'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {run.relatorio_final_consolidado && (
        <section className="card" aria-label="Relatório final">
          <div className="card-header">
            <h3 className="card-title">Relatório final</h3>
            <div className="v12-actions">
              <button type="button" className="btn-secondary" onClick={copiar}>
                {copiado ? 'Copiado!' : 'Copiar'}
              </button>
              <button type="button" className="btn-secondary" onClick={() => downloadMarkdown(run)}>
                Baixar .md
              </button>
            </div>
          </div>
          <div className="v12-md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {run.relatorio_final_consolidado}
            </ReactMarkdown>
          </div>
        </section>
      )}

      <UrlList titulo="Fontes usadas" urls={run.urls_usadas_globais} />
      <UrlList titulo="Fontes lidas" urls={run.urls_lidas_globais} />
      <UrlList titulo="Lidas e não usadas" urls={run.urls_nao_usadas_globais} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Painel ao vivo (SSE)                                                 */
/* ------------------------------------------------------------------ */

function BarraProgresso({ pontos }: { pontos: PontoVivo[] }) {
  if (pontos.length === 0) return null;
  const prontos = pontos.filter(
    (p) => p.estado === 'aprovado' || p.estado === 'finalizado' || p.estado === 'reprovado',
  ).length;
  const pct = Math.round((prontos / pontos.length) * 100);
  return (
    <div className="v12-progresso" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="v12-progresso-barra" style={{ width: `${pct}%` }} />
      <span className="v12-progresso-rotulo">
        {prontos}/{pontos.length} pontos ({pct}%)
      </span>
    </div>
  );
}

function FontesAoVivo({ fontes }: { fontes: FonteViva[] }) {
  if (fontes.length === 0) return null;
  const grupos = new Map<string, FonteViva[]>();
  for (const f of fontes) {
    const chave =
      f.ponto_id != null
        ? `Ponto ${f.ponto_id}${f.persona ? ` · ${f.persona}` : ''}`
        : (f.persona ?? 'Outras');
    const lista = grupos.get(chave) ?? [];
    lista.push(f);
    grupos.set(chave, lista);
  }
  return (
    <section className="card" aria-label="Fontes lidas">
      <div className="card-header">
        <h3 className="card-title">Fontes lidas ({fontes.length})</h3>
      </div>
      {[...grupos.entries()].map(([grupo, itens]) => (
        <div key={grupo} className="v12-grupo">
          <h4 className="v12-grupo-titulo">{grupo}</h4>
          <ul className="v12-url-list">
            {itens.map((f) => (
              <li key={f.url}>
                <a href={f.url} target="_blank" rel="noreferrer noopener">
                  {f.url}
                </a>
                {f.usada === true && <span className="pill pill-green">usada</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function contagemRespostas(a: AuditoriaViva): string {
  if (!a.perguntas_respondidas) return a.perguntas_true != null ? `${a.perguntas_true}` : '—';
  const vals = Object.values(a.perguntas_respondidas);
  return `${vals.filter(Boolean).length}/${vals.length}`;
}

function AuditoriasAoVivo({ auditorias }: { auditorias: AuditoriaViva[] }) {
  if (auditorias.length === 0) return null;
  return (
    <section className="card" aria-label="Auditorias executadas">
      <div className="card-header">
        <h3 className="card-title">Auditorias ({auditorias.length})</h3>
      </div>
      <table className="v12-table">
        <thead>
          <tr>
            <th scope="col">Ponto</th>
            <th scope="col">Rodada</th>
            <th scope="col">Respostas</th>
            <th scope="col">Taxa</th>
            <th scope="col">Aprovado</th>
            <th scope="col">Modelo</th>
            <th scope="col">Tokens</th>
          </tr>
        </thead>
        <tbody>
          {auditorias.map((a, i) => (
            <tr key={`${a.ponto_id}-${a.rodada}-${i}`}>
              <td>{a.ponto_id}</td>
              <td>{a.rodada}</td>
              <td>{contagemRespostas(a)}</td>
              <td>{a.porcentagem_aprovacao ?? '—'}%</td>
              <td>
                <span className={a.aprovado ? 'pill pill-green' : 'pill pill-red'}>
                  {a.aprovado ? 'sim' : 'não'}
                </span>
              </td>
              <td>{a.model_used ?? '—'}</td>
              <td>{a.total_tokens ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function PainelAoVivo({ estado }: { estado: EstadoAoVivo }) {
  const { run, pontos, fontes, auditorias, tokens, contagens, conectado } = estado;
  const papeis = Object.entries(tokens.porPapel);
  return (
    <div className="v12-stack">
      <section className="card" aria-label="Acompanhamento ao vivo">
        <div className="card-header">
          <h2 className="card-title">{run?.tema ?? 'Pesquisa em andamento'}</h2>
          <span className={conectado ? 'pill pill-green' : 'pill pill-amber'} role="status">
            <span className={`v12-dot${conectado ? ' v12-dot--on' : ''}`} aria-hidden="true" />
            {conectado ? 'Ao vivo' : 'Reconectando…'}
          </span>
        </div>
        <dl className="v12-meta">
          <div>
            <dt>Status</dt>
            <dd>{run ? statusRotulo(run.status) : 'Carregando…'}</dd>
          </div>
          <div>
            <dt>Tokens totais</dt>
            <dd>
              <strong>{tokens.total}</strong>
              {' '}({tokens.prompt} prompt / {tokens.completion} compl. / {tokens.reasoning} reasoning)
            </dd>
          </div>
          {papeis.length > 0 && (
            <div>
              <dt>Tokens por papel</dt>
              <dd>{papeis.map(([papel, n]) => `${papel}: ${n}`).join(' · ')}</dd>
            </div>
          )}
          {Object.keys(contagens).length > 0 && (
            <div>
              <dt>Eventos</dt>
              <dd>{Object.entries(contagens).map(([t, n]) => `${t} (${n})`).join(' · ')}</dd>
            </div>
          )}
        </dl>
        <BarraProgresso pontos={pontos} />
      </section>

      {pontos.length > 0 && (
        <section className="card" aria-label="Pontos em acompanhamento">
          <div className="card-header">
            <h3 className="card-title">Pontos ({pontos.length})</h3>
          </div>
          <div className="v12-grid">
            {pontos.map((p) => (
              <article key={p.ponto_id} className="v12-point-card">
                <header>
                  <strong>
                    {p.ponto_id}.{p.enunciado ? ` ${p.enunciado}` : ''}
                  </strong>
                  <div className="v12-point-badges">
                    <span className={pontoClasse(p.estado)}>{pontoRotulo(p)}</span>
                    {p.porcentagem_aprovacao != null && (
                      <span className="pill" title="Porcentagem de aprovação">
                        {p.porcentagem_aprovacao}% · rodada {p.rodada ?? 1}
                      </span>
                    )}
                    {p.persona && <span className="pill">{p.persona}</span>}
                  </div>
                </header>
                {p.relatorio_trecho && <p className="v12-lacunas">{p.relatorio_trecho}</p>}
                {p.mensagem_erro && (
                  <p className="v12-lacunas" role="alert">
                    <strong>Erro:</strong> {p.mensagem_erro}
                  </p>
                )}
                {(p.urls_lidas.length > 0 || p.urls_usadas.length > 0) && (
                  <p className="v12-muted">
                    {p.urls_lidas.length} lidas · {p.urls_usadas.length} usadas
                  </p>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <FontesAoVivo fontes={fontes} />
      <AuditoriasAoVivo auditorias={auditorias} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tela: nova pesquisa + acompanhamento (hook no nível do app)           */
/* ------------------------------------------------------------------ */

const FORM_INICIAL: FormPesquisa = {
  tema: '',
  profundidade: 3,
  veracidade_alvo: 80,
  max_rodadas_auditoria: 4,
  atualidade: 'ALL',
  callback_url: '',
};

export function ResearchView({
  estado,
  aoCriar,
  aoNovaPesquisa,
  temaSugerido = null,
}: {
  estado: EstadoAoVivo;
  aoCriar: (researchId: string) => void;
  aoNovaPesquisa: () => void;
  temaSugerido?: string | null;
}) {
  const [form, setForm] = useState<FormPesquisa>(FORM_INICIAL);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [erroApi, setErroApi] = useState<string | null>(null);
  const [faltaApiKey, setFaltaApiKey] = useState(false);

  const ativa = estado.researchId != null;
  const run = estado.run;
  const emAndamento = !!run && run.status !== 'COMPLETED' && run.status !== 'FAILED';

  const set = <K extends keyof FormPesquisa>(k: K, v: FormPesquisa[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setErros((e) => {
      if (!e[k]) return e;
      const n = { ...e };
      delete n[k];
      return n;
    });
  };

  // Tema vindo do hero: preenche o campo e limpa o erro local.
  useEffect(() => {
    if (temaSugerido && temaSugerido.trim()) {
      setForm((f) => ({ ...f, tema: temaSugerido }));
      setErros((e) => {
        if (!e.tema) return e;
        const n = { ...e };
        delete n.tema;
        return n;
      });
    }
  }, [temaSugerido]);

  async function submeter(e: React.FormEvent) {
    e.preventDefault();
    const v = validarForm(form);
    setErros(v);
    if (Object.keys(v).length > 0) return;
    setEnviando(true);
    setErroApi(null);
    setFaltaApiKey(false);
    try {
      const body: ResearchCreateRequest = {
        tema: form.tema.trim(),
        profundidade: form.profundidade,
        veracidade_alvo: form.veracidade_alvo,
        max_rodadas_auditoria: form.max_rodadas_auditoria,
        atualidade: form.atualidade.trim() || 'ALL',
        callback_url: form.callback_url.trim(),
      };
      const criado = await criarPesquisa(body);
      aoCriar(criado.research_id);
    } catch (err) {
      if (ehErroApiKey(err)) setFaltaApiKey(true);
      setErroApi(err instanceof ApiV12Error ? err.message : 'Falha ao criar pesquisa.');
    } finally {
      setEnviando(false);
    }
  }

  if (!ativa) {
    return (
      <div className="v12-stack">
        <section className="card" aria-label="Nova pesquisa">
          <div className="card-header">
            <h2 className="card-title">Nova pesquisa</h2>
          </div>
          <form onSubmit={submeter} noValidate className="v12-form">
            <div className="form-group">
              <label className="form-label" htmlFor="v12-tema">
                Tema
              </label>
              <textarea
                id="v12-tema"
                className={`form-input${erros.tema ? ' error' : ''}`}
                value={form.tema}
                onChange={(e) => set('tema', e.target.value)}
                rows={3}
                placeholder="Ex.: impacto da IA generativa na pesquisa acadêmica"
                aria-invalid={!!erros.tema}
                aria-describedby={erros.tema ? 'v12-tema-erro' : undefined}
              />
              {erros.tema && (
                <p className="form-field-error" id="v12-tema-erro" role="alert">
                  {erros.tema}
                </p>
              )}
            </div>

            <div className="v12-row">
              <div className="form-group">
                <label className="form-label" htmlFor="v12-profundidade">
                  Profundidade (1–10): {form.profundidade}
                </label>
                <input
                  id="v12-profundidade"
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={form.profundidade}
                  onChange={(e) => set('profundidade', Number(e.target.value))}
                  aria-invalid={!!erros.profundidade}
                />
                {erros.profundidade && (
                  <p className="form-field-error" role="alert">
                    {erros.profundidade}
                  </p>
                )}
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="v12-veracidade">
                  Veracidade alvo (0–100)
                </label>
                <input
                  id="v12-veracidade"
                  className={`form-input${erros.veracidade_alvo ? ' error' : ''}`}
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={form.veracidade_alvo}
                  onChange={(e) => set('veracidade_alvo', Number(e.target.value))}
                  aria-invalid={!!erros.veracidade_alvo}
                />
                {erros.veracidade_alvo && (
                  <p className="form-field-error" role="alert">
                    {erros.veracidade_alvo}
                  </p>
                )}
              </div>
            </div>

            <div className="v12-row">
              <div className="form-group">
                <label className="form-label" htmlFor="v12-rodadas">
                  Rodadas de auditoria (1–10)
                </label>
                <select
                  id="v12-rodadas"
                  className="form-input"
                  value={form.max_rodadas_auditoria}
                  onChange={(e) => set('max_rodadas_auditoria', Number(e.target.value))}
                >
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                {erros.max_rodadas_auditoria && (
                  <p className="form-field-error" role="alert">
                    {erros.max_rodadas_auditoria}
                  </p>
                )}
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="v12-atualidade">
                  Atualidade
                </label>
                <select
                  id="v12-atualidade"
                  className="form-input"
                  value={form.atualidade}
                  onChange={(e) => set('atualidade', e.target.value)}
                >
                  {['ALL', '24H', '7D', '1M', '1Y'].map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
                {erros.atualidade && (
                  <p className="form-field-error" role="alert">
                    {erros.atualidade}
                  </p>
                )}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="v12-callback">
                callback_url
              </label>
              <input
                id="v12-callback"
                className={`form-input${erros.callback_url ? ' error' : ''}`}
                type="url"
                inputMode="url"
                placeholder="https://exemplo.com/webhook"
                value={form.callback_url}
                onChange={(e) => set('callback_url', e.target.value)}
                aria-invalid={!!erros.callback_url}
                aria-describedby={erros.callback_url ? 'v12-callback-erro' : undefined}
              />
              {erros.callback_url && (
                <p className="form-field-error" id="v12-callback-erro" role="alert">
                  {erros.callback_url}
                </p>
              )}
            </div>

            {erroApi && (
              <div className="alert-banner danger" role="alert">
                {erroApi}
                {faltaApiKey && (
                  <>
                    {' '}
                    <a href="#settings">Configurar API key</a>
                  </>
                )}
              </div>
            )}

            <button type="submit" className="btn-start-research" disabled={enviando}>
              {enviando ? 'Criando…' : 'Criar pesquisa'}
            </button>
          </form>
        </section>
      </div>
    );
  }

  return (
    <div className="v12-stack">
      <div className="v12-toolbar">
        <button type="button" className="btn-secondary" onClick={aoNovaPesquisa}>
          Nova pesquisa
        </button>
      </div>
      {estado.naoEncontrada && (
        <div className="alert-banner danger" role="alert">
          Pesquisa não encontrada no backend — verifique o histórico ou crie uma nova.
        </div>
      )}
      {estado.erro && (
        <div className="alert-banner danger" role="alert">
          {estado.erro}
          {estado.erro.includes('API key') && (
            <>
              {' '}
              <a href="#settings">Configurar API key</a>
            </>
          )}
        </div>
      )}
      {!run && !estado.naoEncontrada && !estado.erro && (
        <div className="alert-banner info" role="status">
          <span className="spinner spinner--xs" aria-hidden="true" /> Carregando pesquisa…
        </div>
      )}
      {emAndamento && <PainelAoVivo estado={estado} />}
      {run && !emAndamento && <DossieView run={run} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tela: histórico local                                               */
/* ------------------------------------------------------------------ */

export function HistoryViewLocal({
  itens,
  ativaId,
  onAbrir,
  onRecarregar,
}: {
  itens: HistoricoItem[];
  ativaId: string | null;
  onAbrir: (id: string) => void;
  onRecarregar: () => void;
}) {
  const [removendo, setRemovendo] = useState(false);
  if (itens.length === 0) {
    return (
      <section className="card hist-empty-card" aria-label="Histórico vazio">
        <h2 className="card-title">Nenhuma pesquisa ainda</h2>
        <p>Crie uma pesquisa na aba Pesquisa — ela aparece aqui automaticamente.</p>
      </section>
    );
  }
  return (
    <div className="v12-stack">
      <div className="v12-toolbar">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            const atual = lerHistorico();
            onRecarregar();
            void atual;
          }}
        >
          Atualizar lista
        </button>
        <button
          type="button"
          className="btn-secondary hist-delete-btn"
          disabled={removendo}
          onClick={() => {
            setRemovendo(true);
            gravarHistorico([]);
            onRecarregar();
            setRemovendo(false);
          }}
        >
          Limpar histórico local
        </button>
      </div>
      {itens.map((i) => (
        <article key={i.research_id} className={`card${i.research_id === ativaId ? ' v12-active' : ''}`}>
          <div className="card-header hist-header">
            <h3 className="card-title">{i.tema || i.research_id}</h3>
            <span className={statusClasse(i.status)}>{statusRotulo(i.status)}</span>
          </div>
          <p className="v12-muted">
            <code>{i.research_id}</code> · {formatarData(i.criado_em)}
          </p>
          <button type="button" className="btn-secondary" onClick={() => onAbrir(i.research_id)}>
            Abrir dossiê
          </button>
        </article>
      ))}
    </div>
  );
}

export { atualizarStatusHistorico, lerHistorico, registrarNoHistorico };
