import React, { useState, useEffect, useRef } from 'react';
import {
  Shield,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Save,
  Server,
  Info,
} from 'lucide-react';
import { api } from '../services/api';
import { ErrorNotice } from './ErrorNotice';
import { apresentarErro } from '../utils/erros';
import { CredentialSanitizedListItem } from '../types/api';
import '../styles/plan-settings-polish.css';

const FIELD_ORDER = [
  'LLM_BASE_URL',
  'JINA_BASE_URL',
  'N_PONTOS',
  'CALLBACK_WEBHOOK_URL',
] as const;

const FIELD_ELEMENT_IDS: Record<string, string> = {
  LLM_BASE_URL: 'llm-base-url',
  JINA_BASE_URL: 'jina-base-url',
  N_PONTOS: 'n-pontos',
  CALLBACK_WEBHOOK_URL: 'callback-url',
};

export interface SettingsFormData {
  OPENAI_API_KEY: string;
  LLM_BASE_URL: string;
  LLM_MODEL_LIGHT: string;
  LLM_MODEL_STRONG: string;
  JINA_API_KEY: string;
  JINA_BASE_URL: string;
  N_PONTOS: string;
  PERSONAS_CONFIG: string;
  CALLBACK_WEBHOOK_URL: string;
  WEBHOOK_HMAC_SECRET: string;
}

export const initialSettingsFormData: SettingsFormData = {
  OPENAI_API_KEY: '',
  LLM_BASE_URL: '',
  LLM_MODEL_LIGHT: '',
  LLM_MODEL_STRONG: '',
  JINA_API_KEY: '',
  JINA_BASE_URL: '',
  N_PONTOS: '',
  PERSONAS_CONFIG: '',
  CALLBACK_WEBHOOK_URL: '',
  WEBHOOK_HMAC_SECRET: '',
};

interface SettingsViewProps {
  draft?: SettingsFormData;
  onDraftChange?: (data: SettingsFormData) => void;
  onDiscardDraft?: () => void;
  /** Falha global de sessão: evita repetir o mesmo 500 neste cartão. */
  sessionError?: string | null;
  onRetrySession?: () => void;
  /** Aparência: tema e ambientação, antes exclusivos da folha rápida mobile. */
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
  ambientOn?: boolean;
  onToggleAmbient?: () => void;
}

function safeClientMask(chave: string, mascarado: string, tipo?: string): string {
  const sensitiveKeys = ['WEBHOOK_HMAC_SECRET', 'OPENAI_API_KEY', 'JINA_API_KEY', 'API_SECRET_KEY'];
  const isSensitive =
    sensitiveKeys.includes(chave) ||
    /(KEY|SECRET|TOKEN|PASS|CREDENTIAL|WEBHOOK)/i.test(chave) ||
    tipo === 'llm' ||
    tipo === 'webhook';

  if (isSensitive) {
    if (!mascarado || mascarado === '[REDACTED]' || mascarado.includes('****')) {
      return mascarado || '[REDACTED]';
    }
    if (mascarado.length <= 8) return '[REDACTED]';
    return `${mascarado.slice(0, 4)}****${mascarado.slice(-4)}`;
  }
  return mascarado;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  draft,
  onDraftChange,
  onDiscardDraft,
  sessionError = null,
  onRetrySession,
  theme = 'light',
  onToggleTheme,
  ambientOn = false,
  onToggleAmbient,
}) => {
  // Status de conexão e verificação
  const [connectionStatus, setConnectionStatus] = useState<
    'idle' | 'checking' | 'connected' | 'unauthorized' | 'error'
  >('idle');
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);

  // Lista de credenciais mascaradas vindas do backend
  const [credentialsList, setCredentialsList] = useState<CredentialSanitizedListItem[]>([]);
  const [credentialsFetchError, setCredentialsFetchError] = useState<string | null>(null);
  const [isLoadingCreds, setIsLoadingCreds] = useState(false);

  // Formulário de credenciais: usa o draft persistido em memória no App quando fornecido, ou estado local
  const [localFormData, setLocalFormData] = useState<SettingsFormData>(initialSettingsFormData);
  const formData = draft || localFormData;

  const setFormData = (
    next: SettingsFormData | ((prev: SettingsFormData) => SettingsFormData)
  ) => {
    const nextVal = typeof next === 'function' ? next(formData) : next;
    if (onDraftChange) {
      onDraftChange(nextVal);
    } else {
      setLocalFormData(nextVal);
    }
  };

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(null);
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);
  const [saveErrorDetalhe, setSaveErrorDetalhe] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Referências aos inputs reais para acessibilidade e foco pós-validação
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const handleFieldChange = (key: keyof SettingsFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (fieldErrors[key]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  // Detecta se há rascunho de configurações digitado
  const hasDirtyDraft = Object.values(formData).some((v) => v.trim().length > 0);

  // Proteção contra perda acidental de rascunho ao navegar ou fechar a aba
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasDirtyDraft) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasDirtyDraft]);

  // Carrega lista mascarada ao abrir
  const loadCredentials = async () => {
    setIsLoadingCreds(true);
    setCredentialsFetchError(null);
    try {
      const res = await api.listCredentials();
      setCredentialsList(res.credenciais || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setCredentialsFetchError(msg);
    } finally {
      setIsLoadingCreds(false);
    }
  };

  useEffect(() => {
    loadCredentials();
  }, []);

  // Testar Conexão com o backend
  const handleTestConnection = async () => {
    setConnectionStatus('checking');
    setConnectionMessage('Testando a conexão.');
    try {
      await api.healthCheck();
      // Tenta listar credenciais com a sessão/cookie atual
      const creds = await api.listCredentials();
      setCredentialsList(creds.credenciais || []);
      setCredentialsFetchError(null);
      setConnectionStatus('connected');
      setConnectionMessage('Conexão e sessão funcionando.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('401') || msg.toLowerCase().includes('não autorizad') || msg.toLowerCase().includes('ausente')) {
        setConnectionStatus('unauthorized');
        setConnectionMessage('A sessão não foi aceita. Recarregue a página para entrar de novo; se continuar, confira se o servidor está no mesmo endereço.');
      } else {
        setConnectionStatus('error');
        setConnectionMessage(apresentarErro(err, { acao: 'testar a conexão' }).mensagem);
      }
    }
  };

  // Validador estrito de URL com protocolo http/https e hostname válido
  const isValidUrl = (val: string): boolean => {
    try {
      const u = new URL(val.trim());
      return (u.protocol === 'http:' || u.protocol === 'https:') && Boolean(u.hostname && u.hostname.length > 0);
    } catch {
      return false;
    }
  };

  // Validador estrito de número inteiro positivo (rejeita decimais, 0 e negativos)
  const isPositiveInteger = (val: string): boolean => {
    const trimmed = val.trim();
    if (!/^\d+$/.test(trimmed)) return false;
    const n = Number(trimmed);
    return Number.isInteger(n) && n >= 1;
  };

  // Validação dos campos do formulário com rolagem e foco no primeiro controle inválido
  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (formData.LLM_BASE_URL.trim() && !isValidUrl(formData.LLM_BASE_URL)) {
      errors.LLM_BASE_URL = 'A URL deve ser válida e iniciar com http:// ou https://';
    }

    if (formData.JINA_BASE_URL.trim() && !isValidUrl(formData.JINA_BASE_URL)) {
      errors.JINA_BASE_URL = 'A URL deve ser válida e iniciar com http:// ou https://';
    }

    if (formData.CALLBACK_WEBHOOK_URL.trim() && !isValidUrl(formData.CALLBACK_WEBHOOK_URL)) {
      errors.CALLBACK_WEBHOOK_URL = 'A URL deve ser válida e iniciar com http:// ou https://';
    }

    if (formData.N_PONTOS.trim() && !isPositiveInteger(formData.N_PONTOS)) {
      errors.N_PONTOS = 'O número de pontos deve ser um inteiro positivo maior ou igual a 1 (sem decimais)';
    }

    setFieldErrors(errors);

    const firstInvalid = FIELD_ORDER.find((k) => Boolean(errors[k]));
    if (firstInvalid) {
      const targetId = FIELD_ELEMENT_IDS[firstInvalid];
      const focusControl = () => {
        const el = inputRefs.current[firstInvalid] || (typeof document !== 'undefined' ? document.getElementById(targetId) : null);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.focus();
        }
      };

      if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(focusControl);
      }
      setTimeout(focusControl, 30);
      return false;
    }

    return true;
  };

  // Salvar credenciais cifradas no backend
  const handleSaveCredentials = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!validateForm()) return;

    setIsSaving(true);
    setSaveSuccessMessage(null);
    setSaveErrorDetalhe(null);
    setSaveErrorMessage(null);

    const changedEntries: Array<{ chave: string; valor: string; tipo: 'llm' | 'jina' | 'webhook' | 'parametro'; base_url?: string }> = [];

    // Mapeamento estrito das chaves autorizadas
    if (formData.OPENAI_API_KEY.trim()) {
      changedEntries.push({ chave: 'OPENAI_API_KEY', valor: formData.OPENAI_API_KEY.trim(), tipo: 'llm' });
    }
    if (formData.LLM_BASE_URL.trim()) {
      changedEntries.push({ chave: 'LLM_BASE_URL', valor: formData.LLM_BASE_URL.trim(), tipo: 'llm', base_url: formData.LLM_BASE_URL.trim() });
    }
    if (formData.LLM_MODEL_LIGHT.trim()) {
      changedEntries.push({ chave: 'LLM_MODEL_LIGHT', valor: formData.LLM_MODEL_LIGHT.trim(), tipo: 'llm' });
    }
    if (formData.LLM_MODEL_STRONG.trim()) {
      changedEntries.push({ chave: 'LLM_MODEL_STRONG', valor: formData.LLM_MODEL_STRONG.trim(), tipo: 'llm' });
    }
    if (formData.JINA_API_KEY.trim()) {
      changedEntries.push({ chave: 'JINA_API_KEY', valor: formData.JINA_API_KEY.trim(), tipo: 'jina' });
    }
    if (formData.JINA_BASE_URL.trim()) {
      changedEntries.push({ chave: 'JINA_BASE_URL', valor: formData.JINA_BASE_URL.trim(), tipo: 'jina', base_url: formData.JINA_BASE_URL.trim() });
    }
    if (formData.N_PONTOS.trim()) {
      changedEntries.push({ chave: 'N_PONTOS', valor: formData.N_PONTOS.trim(), tipo: 'parametro' });
    }
    if (formData.PERSONAS_CONFIG.trim()) {
      changedEntries.push({ chave: 'PERSONAS_CONFIG', valor: formData.PERSONAS_CONFIG.trim(), tipo: 'parametro' });
    }
    if (formData.CALLBACK_WEBHOOK_URL.trim()) {
      changedEntries.push({ chave: 'CALLBACK_WEBHOOK_URL', valor: formData.CALLBACK_WEBHOOK_URL.trim(), tipo: 'webhook', base_url: formData.CALLBACK_WEBHOOK_URL.trim() });
    }
    if (formData.WEBHOOK_HMAC_SECRET.trim()) {
      changedEntries.push({ chave: 'WEBHOOK_HMAC_SECRET', valor: formData.WEBHOOK_HMAC_SECRET.trim(), tipo: 'webhook' });
    }

    if (changedEntries.length === 0) {
      setSaveErrorMessage('Nenhum campo com novo valor foi preenchido para salvar.');
      setIsSaving(false);
      return;
    }

    try {
      const savedKeys: string[] = [];
      const failedKeys: Array<{ chave: string; erro: string }> = [];
      const fieldsToClear: Record<string, string> = {};

      for (const item of changedEntries) {
        try {
          await api.saveCredential({
            chave: item.chave,
            valor: item.valor,
            tipo: item.tipo,
            base_url: item.base_url,
          });
          savedKeys.push(item.chave);
          fieldsToClear[item.chave] = '';
        } catch (err: unknown) {
          failedKeys.push({
            chave: item.chave,
            erro: err instanceof Error ? err.message : String(err),
          });
        }
      }

      // Limpa estritamente os campos que obtiveram sucesso na gravação
      if (savedKeys.length > 0) {
        setFormData((prev) => ({ ...prev, ...fieldsToClear }));
      }

      setSaveErrorDetalhe(
        failedKeys.length > 0 ? failedKeys.map((f) => `${f.chave}: ${f.erro}`).join('\n') : null
      );

      if (failedKeys.length === 0) {
        setSaveSuccessMessage(
          savedKeys.length === 1
            ? `${savedKeys[0]} foi salvo e cifrado.`
            : `${savedKeys.length} parâmetros foram salvos e cifrados: ${savedKeys.join(', ')}.`
        );
      } else if (savedKeys.length > 0) {
        setSaveSuccessMessage(`${savedKeys.join(', ')} salvo. O resto não foi gravado.`);
        setSaveErrorMessage(
          failedKeys.length === 1
            ? 'Uma credencial não foi salva'
            : `${failedKeys.length} credenciais não foram salvas`
        );
      } else {
        setSaveErrorMessage(
          failedKeys.length === 1
            ? 'Uma credencial não foi salva'
            : `${failedKeys.length} credenciais não foram salvas`
        );
      }

      // Recarrega a tabela de metadados
      await loadCredentials();
    } catch (err: unknown) {
      const falhaSalvar = apresentarErro(err, { acao: 'salvar a credencial' });
      setSaveErrorMessage(falhaSalvar.titulo);
      setSaveErrorDetalhe(falhaSalvar.detalhe ?? null);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="settings-container" aria-labelledby="settings-heading">
      <header className="card-header">
        <div>
          <h1 id="settings-heading" className="card-title">
            Configurações
          </h1>
          <p style={{ marginTop: '4px', fontSize: '0.88rem', color: 'var(--color-text-secondary)' }}>
            Chaves dos provedores e da busca ficam no servidor. A sessão abre sozinha, sem chave manual no navegador.
          </p>
        </div>
      </header>

      {/* Aparência: tema e ambientação. No mobile a aba Ajustes abre esta tela. */}
      {(onToggleTheme || onToggleAmbient) && (
        <section className="card" aria-labelledby="appearance-heading">
          <h2 id="appearance-heading" className="card-title" style={{ fontSize: '16px' }}>
            Aparência
          </h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '10px' }}>
            {onToggleTheme && (
              <button type="button" className="btn-secondary" aria-pressed={theme === 'dark'} onClick={onToggleTheme}>
                {theme === 'dark' ? 'Tema escuro' : 'Tema claro'}
              </button>
            )}
            {onToggleAmbient && (
              <button type="button" className="btn-secondary" aria-pressed={ambientOn} onClick={onToggleAmbient}>
                Ambientação {ambientOn ? 'ligada' : 'desligada'}
              </button>
            )}
          </div>
        </section>
      )}

      {/* Cartão 1: Conexão e Sessão Integrada */}
      <section className="card" aria-labelledby="auth-heading">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 12px', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
            <Server size={18} aria-hidden="true" color="var(--color-text-muted)" />
            <h2 id="auth-heading" className="card-title" style={{ fontSize: '16px' }}>
              Conexão e sessão
            </h2>
          </div>

          <div className="pill pill-green">
            <span className="dot" aria-hidden="true" />
            <span>Sessão ativa</span>
          </div>
        </div>

        <p style={{ fontSize: '14px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
          As chaves ficam no servidor e não chegam ao navegador.
        </p>

        {/* Teste de Conexão */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleTestConnection}
            disabled={connectionStatus === 'checking'}
          >
            {connectionStatus === 'checking' ? (
              <>
                <span className="spinner" aria-hidden="true" />
                <span>Testando...</span>
              </>
            ) : (
              <>
                <Server size={16} aria-hidden="true" />
                <span>Testar conexão</span>
              </>
            )}
          </button>

          {connectionStatus === 'connected' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-success-text)', fontSize: '0.85rem', fontWeight: 500 }} role="status">
              <CheckCircle2 size={16} />
              <span>{connectionMessage}</span>
            </div>
          )}

          {connectionStatus === 'unauthorized' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-danger-text)', fontSize: '0.85rem', fontWeight: 500 }} role="alert">
              <AlertTriangle size={16} />
              <span>{connectionMessage}</span>
            </div>
          )}

          {connectionStatus === 'error' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-danger-text)', fontSize: '0.85rem', fontWeight: 500 }} role="alert">
              <AlertTriangle size={16} />
              <span>{connectionMessage}</span>
            </div>
          )}
        </div>
      </section>

      {/* Cartão 2: Cadastro e Atualização de Credenciais Cifradas */}
      <section className="card" aria-labelledby="creds-heading">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Shield size={18} aria-hidden="true" color="var(--color-text-muted)" />
          <h2 id="creds-heading" className="card-title" style={{ fontSize: '16px' }}>
            Chaves dos provedores
          </h2>
        </div>

        {/* Aviso de Precedência RN-10 (Adendo 002) */}
        <div className="alert-banner info" style={{ marginBottom: '16px' }}>
          <Info size={18} aria-hidden="true" style={{ flexShrink: 0 }} />
          <div style={{ fontSize: '14px' }}>
            <strong>Qual valor vale:</strong> o que está salvo aqui tem prioridade. Campo vazio usa o .env. A
            chave-mestra <code>CREDENTIALS_MASTER_KEY</code> fica só no ambiente.
          </div>
        </div>

        {hasDirtyDraft && (
          <div className="alert-banner warning" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
              <AlertTriangle size={16} aria-hidden="true" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: '0.85rem' }}>
                Você possui alterações não salvas no formulário (preservadas em memória nesta sessão). Salve antes de navegar para não perder os valores digitados.
              </span>
            </div>
            {onDiscardDraft && (
              <button
                type="button"
                className="btn-secondary"
                onClick={onDiscardDraft}
                disabled={isSaving}
                style={{ fontSize: '0.82rem', padding: '4px 12px', minHeight: '32px' }}
                title="Descartar rascunho de configurações em memória"
              >
                Descartar rascunho
              </button>
            )}
          </div>
        )}

        <form noValidate onSubmit={handleSaveCredentials}>
          <div className="settings-grid-form">
            {/* OpenAI API Key */}
            <div className="form-group">
              <label htmlFor="openai-key" className="form-label">
                <span>OPENAI_API_KEY</span>
                <span className="form-label-hint">Chave de LLM</span>
              </label>
              <input
                id="openai-key"
                type="password"
                className="form-input"
                placeholder="sk-..."
                value={formData.OPENAI_API_KEY}
                onChange={(e) => handleFieldChange('OPENAI_API_KEY', e.target.value)}
                autoComplete="off"
              />
            </div>

            {/* LLM Base URL */}
            <div className="form-group">
              <label htmlFor="llm-base-url" className="form-label">
                <span>LLM_BASE_URL</span>
                <span className="form-label-hint">Endpoint do LLM</span>
              </label>
              <input
                ref={(el) => { inputRefs.current['LLM_BASE_URL'] = el; }}
                id="llm-base-url"
                type="url"
                className={`form-input ${fieldErrors.LLM_BASE_URL ? 'error' : ''}`}
                placeholder="https://api.openai.com/v1"
                value={formData.LLM_BASE_URL}
                onChange={(e) => handleFieldChange('LLM_BASE_URL', e.target.value)}
                aria-invalid={Boolean(fieldErrors.LLM_BASE_URL)}
                aria-describedby={fieldErrors.LLM_BASE_URL ? 'error-llm-base-url' : undefined}
              />
              {fieldErrors.LLM_BASE_URL && (
                <span id="error-llm-base-url" className="form-field-error" role="alert">
                  {fieldErrors.LLM_BASE_URL}
                </span>
              )}
            </div>

            {/* Model Light */}
            <div className="form-group">
              <label htmlFor="model-light" className="form-label">
                <span>LLM_MODEL_LIGHT</span>
                <span className="form-label-hint">Modelo rápido (Search)</span>
              </label>
              <input
                id="model-light"
                type="text"
                className="form-input"
                placeholder="gpt-4o-mini"
                value={formData.LLM_MODEL_LIGHT}
                onChange={(e) => handleFieldChange('LLM_MODEL_LIGHT', e.target.value)}
              />
            </div>

            {/* Model Strong */}
            <div className="form-group">
              <label htmlFor="model-strong" className="form-label">
                <span>LLM_MODEL_STRONG</span>
                <span className="form-label-hint">Modelo forte (Audit/Writer)</span>
              </label>
              <input
                id="model-strong"
                type="text"
                className="form-input"
                placeholder="gpt-4o"
                value={formData.LLM_MODEL_STRONG}
                onChange={(e) => handleFieldChange('LLM_MODEL_STRONG', e.target.value)}
              />
            </div>

            {/* JINA API Key */}
            <div className="form-group">
              <label htmlFor="jina-key" className="form-label">
                <span>JINA_API_KEY</span>
                <span className="form-label-hint">Busca web e scraping</span>
              </label>
              <input
                id="jina-key"
                type="password"
                className="form-input"
                placeholder="jina_..."
                value={formData.JINA_API_KEY}
                onChange={(e) => handleFieldChange('JINA_API_KEY', e.target.value)}
                autoComplete="off"
              />
            </div>

            {/* JINA Base URL */}
            <div className="form-group">
              <label htmlFor="jina-base-url" className="form-label">
                <span>JINA_BASE_URL</span>
                <span className="form-label-hint">Endpoint Jina</span>
              </label>
              <input
                ref={(el) => { inputRefs.current['JINA_BASE_URL'] = el; }}
                id="jina-base-url"
                type="url"
                className={`form-input ${fieldErrors.JINA_BASE_URL ? 'error' : ''}`}
                placeholder="https://s.jina.ai"
                value={formData.JINA_BASE_URL}
                onChange={(e) => handleFieldChange('JINA_BASE_URL', e.target.value)}
                aria-invalid={Boolean(fieldErrors.JINA_BASE_URL)}
                aria-describedby={fieldErrors.JINA_BASE_URL ? 'error-jina-base-url' : undefined}
              />
              {fieldErrors.JINA_BASE_URL && (
                <span id="error-jina-base-url" className="form-field-error" role="alert">
                  {fieldErrors.JINA_BASE_URL}
                </span>
              )}
            </div>

            {/* N_PONTOS */}
            <div className="form-group">
              <label htmlFor="n-pontos" className="form-label">
                <span>N_PONTOS</span>
                <span className="form-label-hint">Número de pontos padrão (1-20)</span>
              </label>
              <input
                ref={(el) => { inputRefs.current['N_PONTOS'] = el; }}
                id="n-pontos"
                type="number"
                min={1}
                max={20}
                className={`form-input ${fieldErrors.N_PONTOS ? 'error' : ''}`}
                placeholder="5"
                value={formData.N_PONTOS}
                onChange={(e) => handleFieldChange('N_PONTOS', e.target.value)}
                aria-invalid={Boolean(fieldErrors.N_PONTOS)}
                aria-describedby={fieldErrors.N_PONTOS ? 'error-n-pontos' : undefined}
              />
              {fieldErrors.N_PONTOS && (
                <span id="error-n-pontos" className="form-field-error" role="alert">
                  {fieldErrors.N_PONTOS}
                </span>
              )}
            </div>

            {/* PERSONAS_CONFIG */}
            <div className="form-group">
              <label htmlFor="personas-config" className="form-label">
                <span>PERSONAS_CONFIG</span>
                <span className="form-label-hint">Separadas por vírgula</span>
              </label>
              <input
                id="personas-config"
                type="text"
                className="form-input"
                placeholder="historiador,visionario,cetico,futurista"
                value={formData.PERSONAS_CONFIG}
                onChange={(e) => handleFieldChange('PERSONAS_CONFIG', e.target.value)}
              />
            </div>

            {/* CALLBACK_WEBHOOK_URL */}
            <div className="form-group">
              <label htmlFor="callback-url" className="form-label">
                <span>CALLBACK_WEBHOOK_URL</span>
                <span className="form-label-hint">URL de entrega</span>
              </label>
              <input
                ref={(el) => { inputRefs.current['CALLBACK_WEBHOOK_URL'] = el; }}
                id="callback-url"
                type="url"
                className={`form-input ${fieldErrors.CALLBACK_WEBHOOK_URL ? 'error' : ''}`}
                placeholder="https://webhook.site/..."
                value={formData.CALLBACK_WEBHOOK_URL}
                onChange={(e) => handleFieldChange('CALLBACK_WEBHOOK_URL', e.target.value)}
                aria-invalid={Boolean(fieldErrors.CALLBACK_WEBHOOK_URL)}
                aria-describedby={fieldErrors.CALLBACK_WEBHOOK_URL ? 'error-callback-url' : undefined}
              />
              {fieldErrors.CALLBACK_WEBHOOK_URL && (
                <span id="error-callback-url" className="form-field-error" role="alert">
                  {fieldErrors.CALLBACK_WEBHOOK_URL}
                </span>
              )}
            </div>

            {/* WEBHOOK_HMAC_SECRET */}
            <div className="form-group">
              <label htmlFor="webhook-secret" className="form-label">
                <span>WEBHOOK_HMAC_SECRET</span>
                <span className="form-label-hint">Segredo de assinatura</span>
              </label>
              <input
                id="webhook-secret"
                type="password"
                className="form-input"
                placeholder="Cole o segredo do webhook…"
                value={formData.WEBHOOK_HMAC_SECRET}
                onChange={(e) => handleFieldChange('WEBHOOK_HMAC_SECRET', e.target.value)}
                autoComplete="off"
              />
            </div>
          </div>

          {saveSuccessMessage && (
            <div className="alert-banner info" style={{ marginTop: '12px' }} role="status">
              <CheckCircle2 size={16} aria-hidden="true" />
              <span>{saveSuccessMessage}</span>
            </div>
          )}

          {saveErrorMessage && (
            <div style={{ marginTop: '12px' }}>
              <ErrorNotice
                compact
                falha={{
                  titulo: saveErrorMessage,
                  mensagem: 'Os campos continuam preenchidos. Corrija o que for preciso e salve de novo.',
                  detalhe: saveErrorDetalhe ?? undefined,
                  tom: 'erro',
                }}
                onRetry={() => void handleSaveCredentials()}
                retryLabel="Salvar de novo"
                retrying={isSaving}
              />
            </div>
          )}

          <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            {hasDirtyDraft && onDiscardDraft && (
              <button
                type="button"
                className="btn-secondary"
                onClick={onDiscardDraft}
                disabled={isSaving}
                style={{ minHeight: '44px' }}
                title="Descartar rascunho de configurações em memória"
              >
                <span>Descartar rascunho</span>
              </button>
            )}
            <button
              type="submit"
              className="btn-start-research"
              disabled={isSaving}
              style={{ minHeight: '44px' }}
            >
              {isSaving ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  <span>Cifrando e salvando...</span>
                </>
              ) : (
                <>
                  <Save size={16} aria-hidden="true" />
                  <span>Salvar credenciais</span>
                </>
              )}
            </button>
          </div>
        </form>
      </section>

      {/* Cartão 3: Listagem de Credenciais e Origem Ativa */}
      <section className="card" aria-labelledby="creds-list-heading">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 12px', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
            <Server size={18} aria-hidden="true" color="var(--color-text-muted)" />
            <h2 id="creds-list-heading" className="card-title" style={{ fontSize: '16px' }}>
              Credenciais salvas
            </h2>
          </div>

          <button
            type="button"
            className="btn-secondary"
            onClick={loadCredentials}
            disabled={isLoadingCreds}
            title="Atualizar lista de parâmetros"
          >
            <RefreshCw size={14} className={isLoadingCreds ? 'spinner' : ''} aria-hidden="true" />
            <span>Atualizar lista</span>
          </button>
        </div>

        {/* Tratamento honesto e segregado: Erro de requisição vs Lista vazia */}
        {credentialsFetchError ? (
          sessionError ? (
            <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', padding: '12px 0' }}>
              A lista de credenciais aparece assim que a sessão conectar.{' '}
              {onRetrySession && (
                <button type="button" className="error-notice__btn" style={{ marginLeft: 8, minHeight: 32 }} onClick={onRetrySession}>
                  Tentar de novo
                </button>
              )}
            </p>
          ) : (
            <div style={{ margin: '12px 0' }}>
              <ErrorNotice
                compact
                falha={apresentarErro(credentialsFetchError, { acao: 'carregar as credenciais' })}
                onRetry={loadCredentials}
                retrying={isLoadingCreds}
                retryLabel="Carregar de novo"
              />
            </div>
          )
        ) : credentialsList.length === 0 ? (
          <p style={{ fontSize: '0.88rem', color: 'var(--color-text-muted)', padding: '16px 0' }}>
            Nenhuma credencial salva. Enquanto isso, valem as variáveis do .env.
          </p>
        ) : (
          <div className="credentials-table-wrapper">
            <table className="credentials-table">
              <thead>
                <tr>
                  <th>Chave</th>
                  <th>Tipo</th>
                  <th>Origem</th>
                  <th>Valor</th>
                  <th>Atualizado em</th>
                </tr>
              </thead>
              <tbody>
                {credentialsList.map((cred) => (
                  <tr key={cred.chave}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{cred.chave}</td>
                    <td>{cred.tipo}</td>
                    <td>
                      <span className={`origin-badge ${cred.origem_ativa}`}>
                        {cred.origem_ativa === 'ambiente' ? 'Ambiente (.env)' : 'Banco cifrado'}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>
                      {safeClientMask(cred.chave, cred.mascarado, cred.tipo)}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                      {new Date(cred.atualizado_em).toLocaleString('pt-BR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
