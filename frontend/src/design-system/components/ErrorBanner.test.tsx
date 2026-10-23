import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { ApiError } from '../../api/types';
import { ErrorBanner } from './ErrorBanner';

const RID = 'c3d2e1f0a9b84c7d6e5f4a3b2c1d0e9f';

function error(code: string, message = 'texto da API', request_id?: string): ApiError {
  return { code, message, ...(request_id ? { request_id } : {}) };
}

// Uma linha por linha da tabela "Erros" de contracts/client-api.md.
const ROWS: { status: number; error: ApiError; title: string; text: string }[] = [
  {
    status: 401,
    error: error('unauthorized', 'X-API-Key ausente ou inválida.'),
    title: '401 · Chave de acesso ausente ou inválida',
    text: 'A interface não está autorizada a falar com o serviço. Avise quem administra.',
  },
  {
    status: 422,
    error: error('validation_error', 'Entrada inválida: body.message'),
    title: '422 · Mensagem inválida',
    text: 'A mensagem não foi aceita: Entrada inválida: body.message',
  },
  {
    status: 404,
    error: error('not_found', 'Thread não encontrada.'),
    title: '404 · Conversa não encontrada',
    text: 'Esta conversa expirou e foi apagada. Abrimos uma nova.',
  },
  {
    status: 503,
    error: error('upstream_unavailable', 'Serviço temporariamente indisponível.'),
    title: '503 · Serviço indisponível no momento',
    text: 'O serviço está indisponível no momento.',
  },
  {
    status: 502,
    error: error('upstream_unavailable'),
    title: '502 · Serviço indisponível no momento',
    text: 'O serviço está indisponível no momento.',
  },
  {
    status: 504,
    error: error('upstream_unavailable'),
    title: '504 · Serviço indisponível no momento',
    text: 'O serviço está indisponível no momento.',
  },
  {
    status: 0,
    error: error('network_error'),
    title: 'Sem conexão com o servidor',
    text: 'Não foi possível falar com o servidor. Verifique a conexão.',
  },
];

describe('ErrorBanner', () => {
  it.each(ROWS)('$status: título e texto em pt-BR', ({ status, error, title, text }) => {
    render(<ErrorBanner status={status} error={error} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveClass('fa-error');
    expect(alert).not.toHaveClass('fa-notice');
    expect(alert).toHaveTextContent(title);
    expect(alert).toHaveTextContent(text);
  });

  it('status desconhecido mostra a mensagem da API', () => {
    render(<ErrorBanner status={500} error={error('http_error', 'Resposta inesperada (500).')} />);

    expect(screen.getByRole('alert')).toHaveTextContent('500 · Erro');
    expect(screen.getByRole('alert')).toHaveTextContent('Resposta inesperada (500).');
  });

  it('mostra o request_id em mono quando existe', () => {
    const { rerender } = render(
      <ErrorBanner status={503} error={error('upstream_unavailable', '', RID)} />,
    );

    const id = screen.getByText(`request_id ${RID}`);
    expect(id.tagName).toBe('CODE');

    rerender(<ErrorBanner status={503} error={error('upstream_unavailable')} />);
    expect(screen.queryByText(/request_id/)).not.toBeInTheDocument();
  });

  it('"Tentar de novo" só aparece com onRetry e chama onRetry', async () => {
    const { rerender } = render(<ErrorBanner status={401} error={error('unauthorized')} />);
    expect(screen.queryByRole('button', { name: 'Tentar de novo' })).not.toBeInTheDocument();

    const onRetry = vi.fn();
    rerender(<ErrorBanner status={503} error={error('upstream_unavailable')} onRetry={onRetry} />);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Tentar de novo' }));

    expect(onRetry).toHaveBeenCalledOnce();
  });
});
