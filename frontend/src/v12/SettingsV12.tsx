import { useEffect, useState } from 'react';
import {
  ApiV12Error,
  PAPEIS,
  gravarApiKey,
  lerApiKey,
  lerConfig,
  limparApiKey,
  salvarConfig,
  type AppConfig,
} from '../services/apiV12';

const NUMERICAS = ['max_concurrent_children', 'max_spawn_depth', 'oneshot_max_children'] as const;
/** Mínimo aceito por campo (espelha settings.py: ge=1/ge=1/ge=0). */
const MINIMOS: Record<(typeof NUMERICAS)[number], number> = {
  max_concurrent_children: 1,
  max_spawn_depth: 1,
  oneshot_max_children: 0,
};

export function SettingsView() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [form, setForm] = useState({
    default_model: '',
    max_concurrent_children: '40',
    max_spawn_depth: '2',
    oneshot_max_children: '0',
    modelos: {} as Record<string, string>,
  });
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  // API key do backend (fetch + SSE): só existe no navegador, nunca volta no GET.
  const [apiKeyLocal, setApiKeyLocal] = useState('');
  const [mostrarApiKey, setMostrarApiKey] = useState(false);
  const [apiKeySalva, setApiKeySalva] = useState<boolean>(() => lerApiKey() != null);

  useEffect(() => {
    let vivo = true;
    lerConfig()
      .then((c) => {
        if (!vivo) return;
        setCfg(c);
        setForm({
          default_model: c.default_model ?? '',
          max_concurrent_children: String(c.max_concurrent_children ?? 40),
          max_spawn_depth: String(c.max_spawn_depth ?? 2),
          oneshot_max_children: String(c.oneshot_max_children ?? 0),
          modelos: { ...(c.modelos_por_papel ?? {}) } as Record<string, string>,
        });
      })
      .catch((e) => {
        if (vivo) setErro(e instanceof ApiV12Error ? e.message : 'Falha ao carregar configuração.');
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });
    return () => {
      vivo = false;
    };
  }, []);

  function salvarApiKeyLocal(): void {
    // Nunca loga a chave: persiste no navegador e limpa o campo.
    gravarApiKey(apiKeyLocal);
    setApiKeyLocal('');
    setApiKeySalva(lerApiKey() != null);
    setOk('API key salva neste navegador.');
  }

  function removerApiKeyLocal(): void {
    limparApiKey();
    setApiKeyLocal('');
    setApiKeySalva(false);
    setOk('API key removida deste navegador.');
  }

  async function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setOk(null);
    const numeros: Record<string, number> = {};
    for (const k of NUMERICAS) {
      const minimo = MINIMOS[k];
      const v = Number((form[k] as string).trim());
      if (!Number.isInteger(v) || v < minimo) {
        setErro(`Campo ${k} precisa ser um inteiro ≥ ${minimo}.`);
        return;
      }
      numeros[k] = v;
    }
    setSalvando(true);
    try {
      const patch: Record<string, unknown> = {
        default_model: form.default_model.trim() || undefined,
        ...numeros,
        modelos_por_papel: Object.fromEntries(
          PAPEIS.map((p) => [p, (form.modelos[p] ?? '').trim() || undefined]).filter(
            ([, v]) => v !== undefined,
          ),
        ),
      };
      // Provedor (base_url/api_key) vem do ambiente — nunca vai no PUT.
      const atualizada = await salvarConfig(patch as never);
      setCfg(atualizada);
      setOk('Configuração salva.');
    } catch (err) {
      setErro(err instanceof ApiV12Error ? err.message : 'Falha ao salvar configuração.');
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return (
      <section className="card" aria-label="Carregando configuração">
        <p role="status">
          <span className="spinner spinner--xs" aria-hidden="true" /> Carregando configuração…
        </p>
      </section>
    );
  }

  return (
    <section className="card" aria-label="Configuração">
      <div className="card-header">
        <h2 className="card-title">Configuração</h2>
      </div>
      <form onSubmit={submeter} noValidate className="v12-form">
        <div className="form-group">
          <label className="form-label" htmlFor="v12-browser-api-key">
            API key do backend (navegador{apiKeySalva ? ' — salva' : ''})
          </label>
          <div className="v12-row">
            <input
              id="v12-browser-api-key"
              className="form-input"
              type={mostrarApiKey ? 'text' : 'password'}
              autoComplete="off"
              value={apiKeyLocal}
              onChange={(e) => setApiKeyLocal(e.target.value)}
              placeholder={apiKeySalva ? '•••••• (salva)' : 'cole a API key'}
            />
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setMostrarApiKey((v) => !v)}
              aria-pressed={mostrarApiKey}
            >
              {mostrarApiKey ? 'Ocultar' : 'Mostrar'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={salvarApiKeyLocal}
              disabled={!apiKeyLocal.trim()}
            >
              Salvar key
            </button>
            {apiKeySalva && (
              <button type="button" className="btn-secondary" onClick={removerApiKeyLocal}>
                Limpar
              </button>
            )}
          </div>
        </div>
        <div className="form-group">
          <span className="form-label">base_url (provedor)</span>
          <p className="v12-muted" data-testid="v12-base-url">
            {cfg?.base_url || '—'} · definido por ambiente
          </p>
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="v12-default-model">
            default_model
          </label>
          <input
            id="v12-default-model"
            className="form-input"
            type="text"
            value={form.default_model}
            onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
          />
        </div>
        <div className="v12-row v12-row-3">
          {NUMERICAS.map((k) => (
            <div className="form-group" key={k}>
              <label className="form-label" htmlFor={`v12-${k}`}>
                {k}
              </label>
              <input
                id={`v12-${k}`}
                className="form-input"
                type="number"
                min={MINIMOS[k]}
                step={1}
                value={form[k] as string}
                onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <h3 className="v12-subtitle">Modelos por papel</h3>
        <div className="v12-row v12-row-2">
          {PAPEIS.map((p) => (
            <div className="form-group" key={p}>
              <label className="form-label" htmlFor={`v12-papel-${p}`}>
                {p}
              </label>
              <input
                id={`v12-papel-${p}`}
                className="form-input"
                type="text"
                value={form.modelos[p] ?? ''}
                placeholder={cfg?.modelos_por_papel?.[p] || ''}
                onChange={(e) =>
                  setForm((f) => ({ ...f, modelos: { ...f.modelos, [p]: e.target.value } }))
                }
              />
            </div>
          ))}
        </div>
        {erro && (
          <div className="alert-banner danger" role="alert">
            {erro}
          </div>
        )}
        {ok && (
          <div className="alert-banner info" role="status">
            {ok}
          </div>
        )}
        <button type="submit" className="btn-start-research" disabled={salvando}>
          {salvando ? 'Salvando…' : 'Salvar'}
        </button>
      </form>
    </section>
  );
}
