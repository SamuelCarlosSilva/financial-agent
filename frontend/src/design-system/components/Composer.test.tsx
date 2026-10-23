import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Composer } from './Composer';

function setup(props: Parameters<typeof Composer>[0] = {}) {
  const onSubmit = vi.fn<(message: string) => void>();
  const view = render(<Composer onSubmit={onSubmit} {...props} />);
  const input = screen.getByRole('textbox', { name: 'Sua pergunta' });
  return { ...view, onSubmit, input, user: userEvent.setup() };
}

/** Texto longo direto no campo: digitar 4000 caracteres um a um seria lento demais. */
function typeLong(input: HTMLElement, length: number) {
  fireEvent.change(input, { target: { value: 'a'.repeat(length) } });
}

describe('Composer', () => {
  it('Enter envia o texto como foi digitado e limpa o campo', async () => {
    const { input, onSubmit, user } = setup();

    await user.type(input, '  Quanto é 2 + 2?  {Enter}');

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith('  Quanto é 2 + 2?  ');
    expect(input).toHaveValue('');
  });

  it('Shift+Enter quebra a linha sem enviar', async () => {
    const { input, onSubmit, user } = setup();

    await user.type(input, 'linha 1{Shift>}{Enter}{/Shift}linha 2');

    expect(onSubmit).not.toHaveBeenCalled();
    expect(input).toHaveValue('linha 1\nlinha 2');
  });

  it('bloqueia mensagem vazia ou só com espaços', async () => {
    const { input, onSubmit, user } = setup();
    const send = screen.getByRole('button', { name: 'Enviar' });

    expect(send).toBeDisabled();
    await user.type(input, '   {Enter}');

    expect(send).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('mostra o contador só a partir de 3.600 caracteres', () => {
    const { input } = setup();

    typeLong(input, 3599);
    expect(screen.queryByText(/\/ 4\.000/)).not.toBeInTheDocument();

    typeLong(input, 3600);
    expect(screen.getByText('3.600 / 4.000')).toBeInTheDocument();
  });

  it('aceita 4.000 caracteres e bloqueia 4.001 com o motivo em texto', async () => {
    const { input, onSubmit, user } = setup();
    const send = screen.getByRole('button', { name: 'Enviar' });

    typeLong(input, 4000);
    expect(send).toBeEnabled();
    expect(screen.queryByText(/passa do limite/)).not.toBeInTheDocument();

    typeLong(input, 4001);
    expect(send).toBeDisabled();
    expect(input).toHaveAccessibleDescription('A mensagem passa do limite de 4.000 caracteres.');
    await user.type(input, '{Enter}');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('com busy ignora o envio e mostra o botão ocupado', async () => {
    const { input, onSubmit, user } = setup({ busy: true });

    await user.type(input, 'Outra pergunta{Enter}');

    expect(onSubmit).not.toHaveBeenCalled();
    expect(input).toHaveValue('Outra pergunta');
    expect(screen.getByRole('button', { name: 'Respondendo…' })).toBeDisabled();
  });
});
