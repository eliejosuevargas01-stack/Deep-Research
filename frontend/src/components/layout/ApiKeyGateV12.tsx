import { useState } from 'react';
import { Check, KeyRound, RefreshCw } from 'lucide-react';
import {
  ApiV12Error,
  gravarApiKey,
  lerApiKey,
  lerConfig,
  limparApiKey,
} from '../../services/apiV12';

interface Props {
  aoValidar?: () => void;
}

/**
 * Gate de API key no topo da rota Pesquisa: visível quando não há chave salva.
 * Salvar valida com GET /config; ao validar, o chamador refaz config e retoma
 * o polling/SSE ativo. Chave ativa mostra estado + botão trocar.
 */
export function ApiKeyGateV12({ aoValidar }: Props) {
  const [temChave, setTemChave] = useState<boolean>(() => lerApiKey() != null);
  const [valor, setValor] = useState('');
  const [mostrar, setMostrar] = useState(false);
  const [testando, setTestando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function salvarETestar(e: React.FormEvent) {
    e.preventDefault();
    const chave = valor.trim();
    if (!chave) {
      setErro('Cole a API key antes de salvar.');
      return;
    }
    setTestando(true);
    setErro(null);
    gravarApiKey(chave);
    try {
      await lerConfig();
      setValor('');
      setTemChave(true);
      aoValidar?.();
    } catch (err) {
      limparApiKey();
      setTemChave(false);
      setErro(err instanceof ApiV12Error ? err.message : 'Falha ao validar a chave.');
    } finally {
      setTestando(false);
    }
  }

  function trocar() {
    limparApiKey();
    setValor('');
    setTemChave(false);
    setErro(null);
  }

  if (temChave) {
    return (
      <div className="alert-banner info" role="status" data-testid="api-key-ativa">
        <Check size={15} aria-hidden="true" style={{ verticalAlign: '-2px' }} />{' '}
        Chave ativa neste navegador.{' '}
        <button type="button" className="btn-secondary" onClick={trocar}>
          Trocar chave
        </button>
      </div>
    );
  }

  return (
    <section className="card" aria-label="Configurar API key" data-testid="api-key-gate">
      <div className="card-header">
        <h2 className="card-title">
          <KeyRound size={16} aria-hidden="true" style={{ verticalAlign: '-2px' }} />{' '}
          API key necessária
        </h2>
      </div>
      <p className="v12-muted">
        O backend exige <code>X-API-Key</code>. Cole a chave uma vez — ela fica só neste
        navegador e acompanha todas as requisições e o stream ao vivo.
      </p>
      <form onSubmit={salvarETestar} noValidate className="v12-form">
        <div className="form-group">
          <label className="form-label" htmlFor="v12-gate-api-key">
            API key do backend
          </label>
          <div className="v12-row">
            <input
              id="v12-gate-api-key"
              className="form-input"
              type={mostrar ? 'text' : 'password'}
              autoComplete="off"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="cole a API key"
            />
            <div className="v12-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setMostrar((v) => !v)}
                aria-pressed={mostrar}
              >
                {mostrar ? 'Ocultar' : 'Mostrar'}
              </button>
              <button
                type="submit"
                className="btn-start-research"
                disabled={testando || !valor.trim()}
              >
                {testando ? (
                  <>
                    <RefreshCw size={14} aria-hidden="true" /> Testando…
                  </>
                ) : (
                  'Salvar e testar'
                )}
              </button>
            </div>
          </div>
        </div>
        {erro && (
          <div className="alert-banner danger" role="alert">
            {erro}
          </div>
        )}
      </form>
    </section>
  );
}
