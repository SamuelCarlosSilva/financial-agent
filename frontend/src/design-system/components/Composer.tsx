// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import { useId, useState, type FormEvent, type KeyboardEvent } from 'react';

import { Button } from './Button';
import './Composer.css';

/** Limite de `ChatRequest.message`: o usuário nunca deve ver um 422 por tamanho. */
export const MAX_MESSAGE_LENGTH = 4000;
/** O contador aparece a partir daqui (data-model.md). */
export const COUNTER_FROM = 3600;

export interface ComposerProps {
  onSubmit?: (message: string) => void;
  /** Resposta em andamento: envios são ignorados. */
  busy?: boolean;
  placeholder?: string;
  defaultValue?: string;
}

const count = new Intl.NumberFormat('pt-BR');

export function Composer({
  onSubmit,
  busy = false,
  placeholder = 'Pergunte sobre investimentos, câmbio, impostos ou cálculos…',
  defaultValue = '',
}: ComposerProps) {
  const [value, setValue] = useState(defaultValue);
  const hintId = useId();

  const length = value.length;
  const over = length > MAX_MESSAGE_LENGTH;
  const empty = value.trim().length === 0;
  const blocked = empty || over || busy;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (blocked) return;
    onSubmit?.(value);
    setValue('');
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className={busy ? 'fa-composer is-busy' : 'fa-composer'} onSubmit={submit}>
      <textarea
        className="fa-composer-input"
        rows={2}
        value={value}
        aria-label="Sua pergunta"
        aria-describedby={over ? hintId : undefined}
        aria-invalid={over || undefined}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="fa-composer-bar">
        <div className="fa-composer-info">
          {length >= COUNTER_FROM ? (
            <span className={over ? 'fa-composer-count is-over' : 'fa-composer-count'}>
              {count.format(length)} / {count.format(MAX_MESSAGE_LENGTH)}
            </span>
          ) : null}
          {over ? (
            <span id={hintId} className="fa-composer-hint">
              A mensagem passa do limite de {count.format(MAX_MESSAGE_LENGTH)} caracteres.
            </span>
          ) : null}
        </div>
        <Button type="submit" variant="primary" icon="send" disabled={blocked}>
          {busy ? 'Respondendo…' : 'Enviar'}
        </Button>
      </div>
    </form>
  );
}
