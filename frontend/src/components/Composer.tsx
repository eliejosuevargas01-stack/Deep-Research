import React, { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { ArrowUp, CornerDownLeft, Keyboard, Loader2, Sparkles } from 'lucide-react';
import { ResearchPreferences, ResearchPreferencesProps } from './ResearchPreferences';
import '../styles/forms-parity.css';
import '../styles/composer-parity.css';

export interface ComposerHandle {
  focus: () => void;
}

interface ComposerProps {
  value: string;
  onChange: (val: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  disabled?: boolean;
  placeholder?: string;
  preferencesProps?: ResearchPreferencesProps;
  currentPlanActive?: boolean;
  /** Rótulo do modelo em uso no seletor de acessórios (padrão: roteamento Auto). */
  modelLabel?: string;
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(({
  value,
  onChange,
  onSubmit,
  isSubmitting,
  disabled = false,
  placeholder = 'Descreva o tema da pesquisa: ângulo, período e a decisão que a resposta deve sustentar…',
  preferencesProps,
  currentPlanActive = false,
  modelLabel = 'Auto',
}, ref) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const length = value.trim().length;
  const isValid = length >= 5 && length <= 500;

  // Copy do prompt: estado vazio explica o formato; estados de erro dizem
  // exatamente quanto falta ou quanto sobra, sem repetir a mesma frase.
  let helperMessage = 'Do tema ao plano em um passo. Enter envia; Shift+Enter abre nova linha; 5 a 500 caracteres.';
  let helperClass = 'helper-info';
  if (length > 0 && length < 5) {
    helperMessage = `Faltam ${5 - length} ${5 - length === 1 ? 'caractere' : 'caracteres'} para o mínimo de 5 (limite: 500). Shift+Enter abre nova linha.`;
    helperClass = 'helper-warning';
  } else if (length > 500) {
    helperMessage = `Excede o máximo de 500 em ${length - 500} ${length - 500 === 1 ? 'caractere' : 'caracteres'}. Encurte o tema para planejar.`;
    helperClass = 'helper-warning';
  } else if (isValid) {
    helperMessage = `Tema válido: ${length}/500 caracteres. Enter planeja; Shift+Enter abre nova linha.`;
    helperClass = 'helper-success';
  }

  useImperativeHandle(ref, () => ({
    focus: () => {
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    },
  }));

  // Auto-resize do textarea conforme conteúdo ou largura disponível mudam
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) {
      return;
    }

    const adjustHeight = () => {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    };

    adjustHeight();

    if (typeof ResizeObserver === 'undefined') {
      return;
    }

    let prevWidth = el.clientWidth;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const currentWidth = entry.contentRect.width;
        if (Math.abs(currentWidth - prevWidth) >= 1) {
          prevWidth = currentWidth;
          adjustHeight();
        }
      }
    });

    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Evita submissão durante composição IME (teclados internacionais/acentos)
    if (e.nativeEvent.isComposing) {
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isValid && !isSubmitting && !disabled) {
        onSubmit();
      }
    }
  };

  return (
    <div className="composer-anchor" role="region" aria-label="Entrada de tema de pesquisa">
      {/* Aviso de plano ativo permanece fora da caixa; as ferramentas da
          investigação agora vivem dentro da linha de acessórios. */}
      {currentPlanActive && (
        <div className="composer-toolbar" role="note">
          <span className="composer-plan-indicator">
            <Sparkles size={13} className="composer-plan-icon" aria-hidden="true" />
            Plano formulado — submeter novo tema elaborará outro plano
          </span>
        </div>
      )}

      <div className={`composer-box ${disabled || isSubmitting ? 'disabled' : ''}`}>
        {/* Linha 1: acessórios na própria barra — sem faixa de status separada. */}
        <div
          className="composer-accessories"
          role="toolbar"
          aria-label="Ações do tema"
          aria-orientation="horizontal"
        >
          <div className="composer-meta-group" role="group" aria-label="Parâmetros da pesquisa">
            {preferencesProps && <ResearchPreferences {...preferencesProps} />}
          </div>

          <span className="composer-model-pill" title="Modelo em uso: roteamento automático">
            {modelLabel}
          </span>

          {/* BottomDock (App) transporta os quatro painéis para este slot. */}
          <div className="composer-tools" data-composer-tools />

          <div
            className={`composer-counter ${length > 0 && !isValid ? 'invalid' : ''} ${isValid ? 'is-valid' : ''}`}
            title="O tema deve conter entre 5 e 500 caracteres"
            aria-hidden="true"
          >
            {length}/500
          </div>
        </div>

        {/* Linha 2: campo de tema */}
        <div className="composer-main">
          <label htmlFor="composer-theme-input" className="sr-only">
            Tema de pesquisa
          </label>
          <textarea
            id="composer-theme-input"
            ref={textareaRef}
            className="composer-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            disabled={disabled || isSubmitting}
            aria-label="Tema de pesquisa"
            aria-invalid={length > 0 && !isValid}
            aria-describedby="composer-helper-text"
            aria-keyshortcuts="Enter Shift+Enter"
            autoComplete="off"
            spellCheck
          />
        </div>

        {/* Linha 3: dicas discretas à esquerda, envio à direita */}
        <div className="composer-actions">
          <div className="composer-shortcut" aria-hidden="true">
            <kbd className="composer-shortcut-key">
              <CornerDownLeft size={11} aria-hidden="true" />
              Enter
            </kbd>
            <span className="composer-shortcut-label">planeja</span>
            <kbd className="composer-shortcut-key">
              <Keyboard size={11} aria-hidden="true" />
              Shift+Enter
            </kbd>
            <span className="composer-shortcut-label">nova linha</span>
          </div>

          <button
            type="button"
            className="composer-send-btn"
            onClick={onSubmit}
            disabled={!isValid || isSubmitting || disabled}
            aria-label="Planejar investigação"
            aria-keyshortcuts="Enter"
            title={
              isSubmitting
                ? 'Processando plano...'
                : !isValid
                ? 'Digite entre 5 e 500 caracteres para planejar'
                : 'Enviar tema para elaboração de plano (Enter)'
            }
          >
            {isSubmitting ? (
              <Loader2 size={18} className="spinner" aria-hidden="true" />
            ) : (
              <ArrowUp size={18} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      <p className="composer-legal">
        A IA pode cometer erros. Verifique as fontes citadas antes de decidir.
      </p>

      <div
        id="composer-helper-text"
        className={`composer-helper-text ${isValid || length === 0 ? 'is-quiet' : ''}`}
        aria-live="polite"
      >
        <span className={helperClass}>
          {helperMessage}
        </span>
      </div>
    </div>
  );
});

Composer.displayName = 'Composer';
