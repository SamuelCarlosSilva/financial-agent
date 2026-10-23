// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ApiFailure } from '../../api/types';
import { Icon } from '../icons';
import { Button } from './Button';
import './ErrorBanner.css';

export interface ErrorBannerProps extends ApiFailure {
  /** Só para falhas transitórias (503, proxy sem API, rede). */
  onRetry?: () => void;
  className?: string;
}

const TITLE: Record<string, string> = {
  upstream_unavailable: 'Serviço indisponível no momento',
  unauthorized: 'Chave de acesso ausente ou inválida',
  not_found: 'Conversa não encontrada',
  validation_error: 'Mensagem inválida',
  network_error: 'Sem conexão com o servidor',
};

/**
 * Texto ao usuário, da tabela "Erros" de contracts/client-api.md. O bundle mostrava a mensagem
 * da API crua; aqui só o 422 a usa (o motivo da recusa) e os status fora da tabela.
 */
export function errorMessage({ status, error }: ApiFailure): string {
  switch (status) {
    case 401:
      return 'A interface não está autorizada a falar com o serviço. Avise quem administra.';
    case 422:
      return `A mensagem não foi aceita: ${error.message}`;
    case 404:
      return 'Esta conversa expirou e foi apagada. Abrimos uma nova.';
    case 502:
    case 503:
    case 504:
      return 'O serviço está indisponível no momento.';
    case 0:
      return 'Não foi possível falar com o servidor. Verifique a conexão.';
    default:
      return error.message || 'Algo deu errado. Tente de novo.';
  }
}

/** Falha técnica: vermelho e `role="alert"`, diferente dos avisos de escopo (ScopeNotice). */
export function ErrorBanner({ status, error, onRetry, className }: ErrorBannerProps) {
  const title = `${status ? `${status} · ` : ''}${TITLE[error.code] ?? 'Erro'}`;
  return (
    <div role="alert" className={className ? `fa-error ${className}` : 'fa-error'}>
      <Icon name="alert" />
      <div className="fa-error-main">
        <div className="fa-error-title">{title}</div>
        <div className="fa-error-text">{errorMessage({ status, error })}</div>
        {error.request_id ? (
          <code className="fa-error-id">request_id {error.request_id}</code>
        ) : null}
      </div>
      {onRetry ? <Button onClick={onRetry}>Tentar de novo</Button> : null}
    </div>
  );
}
