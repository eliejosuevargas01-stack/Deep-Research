import React, { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { ArrowUp, Loader2 } from 'lucide-react';
import { ResearchPreferences, ResearchPreferencesProps } from './ResearchPreferences';

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
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(({
  value,
  onChange,
  onSubmit,
  isSubmitting,
  disabled = false,
  placeholder = 'Descreva um novo tema de pesquisa (ex: O futuro da matriz energética no Brasil)...',
  preferencesProps,
  currentPlanActive = false,
}, ref) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const length = value.trim().length;
  const isValid = length >= 5 && length <= 500;

  let helperMessage = 'Mínimo de 5 e máximo de 500 caracteres. Pressione Enter para planejar ou Shift+Enter para nova linha.';
  let helperClass = 'helper-info';
  if (length > 0 && length < 5) {
    helperMessage = `Faltam ${5 - length} ${5 - length === 1 ? 'caractere' : 'caracteres'} para atingir o mínimo de 5. Limite máximo: 500 caracteres. Shift+Enter insere quebra de linha.`;
    helperClass = 'helper-warning';
  } else if (length > 500) {
    helperMessage = `Tema excede o limite em ${length - 500} ${length - 500 === 1 ? 'caractere' : 'caracteres'} (máximo 500). Reduza o texto para continuar.`;
    helperClass = 'helper-warning';
  } else if (isValid) {
    helperMessage = 'Tema com comprimento válido (pressione Enter para planejar ou Shift+Enter para nova linha).';
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
      {/* Aviso de plano ativo permanece fora da caixa; o controle de preferências
          desce para o rodapé do composer, como chip de modelo do ImagineArt. */}
      {currentPlanActive && (
        <div className="composer-toolbar">
          <span className="composer-plan-indicator">
            Plano formulado — submeter novo tema elaborará outro plano
          </span>
        </div>
      )}

      <div className={`composer-box ${disabled || isSubmitting ? 'disabled' : ''}`}>
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
          />

          <button
            type="button"
            className="composer-send-btn"
            onClick={onSubmit}
            disabled={!isValid || isSubmitting || disabled}
            aria-label="Planejar investigação"
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

        <div className="composer-meta" role="toolbar" aria-label="Opções do tema">
          {preferencesProps && <ResearchPreferences {...preferencesProps} />}
          <div
            className={`composer-counter ${length > 0 && !isValid ? 'invalid' : ''} ${isValid ? 'is-valid' : ''}`}
            title="O tema deve conter entre 5 e 500 caracteres"
            aria-hidden="true"
          >
            {length}/500
          </div>
        </div>
      </div>

      <div id="composer-helper-text" className="composer-helper-text" aria-live="polite">
        <span className={helperClass}>
          {helperMessage}
        </span>
      </div>
    </div>
  );
});

Composer.displayName = 'Composer';
