import { expect, test, type Page } from '@playwright/test';

import answerDocuments from './fixtures/answer-documents.json' with { type: 'json' };
import answerFxCalc from './fixtures/answer-fx-calc.json' with { type: 'json' };
import error401 from './fixtures/error-401.json' with { type: 'json' };
import error422 from './fixtures/error-422.json' with { type: 'json' };
import error503 from './fixtures/error-503.json' with { type: 'json' };
import { mockApi } from './support/mockApi';

const UNAVAILABLE = 'O serviço está indisponível no momento.';
const NETWORK = 'Não foi possível falar com o servidor. Verifique a conexão.';

async function ask(page: Page, question: string) {
  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill(question);
  await input.press('Enter');
  await expect(page.getByRole('button', { name: 'Enviar' })).toBeVisible();
}

test('503 mostra request_id e "Tentar de novo" reenvia a mesma pergunta na mesma conversa', async ({
  page,
}) => {
  const api = await mockApi(page, {
    chat: [
      { body: answerFxCalc },
      { status: 503, body: error503 },
      { body: { ...answerDocuments, thread_id: answerFxCalc.thread_id } },
    ],
  });
  await page.goto('/');
  await ask(page, 'Quanto são 500 euros em reais?');
  await ask(page, 'Como funciona o come-cotas?');

  const log = page.getByRole('log');
  const banner = log.getByRole('alert');
  await expect(banner).toContainText('503 · Serviço indisponível no momento');
  await expect(banner).toContainText(UNAVAILABLE);
  await expect(banner.locator('code')).toHaveText(`request_id ${error503.error.request_id}`);
  // Erro técnico não é aviso de escopo: aparência e papel diferentes.
  await expect(banner).toHaveClass(/fa-error/);
  await expect(log.getByRole('note')).toHaveCount(0);

  await banner.getByRole('button', { name: 'Tentar de novo' }).click();

  await expect(log.getByRole('alert')).toHaveCount(0);
  await expect(log.getByRole('article').filter({ hasText: 'Come-cotas' }).first()).toBeVisible();
  await expect(log.getByText('Como funciona o come-cotas?')).toHaveCount(1);

  const [, failed, retried] = api.requestsTo('POST', '/api/v1/chat');
  expect(failed?.body).toEqual({
    message: 'Como funciona o come-cotas?',
    thread_id: answerFxCalc.thread_id,
  });
  expect(retried?.body).toEqual(failed?.body);
});

test('401 mostra a mensagem de autorização, sem "Tentar de novo"', async ({ page }) => {
  await mockApi(page, { chat: { status: 401, body: error401 } });
  await page.goto('/');
  await ask(page, 'Oi');

  const banner = page.getByRole('alert');
  await expect(banner).toContainText(
    'A interface não está autorizada a falar com o serviço. Avise quem administra.',
  );
  await expect(banner).toContainText(`request_id ${error401.error.request_id}`);
  await expect(banner.getByRole('button', { name: 'Tentar de novo' })).toHaveCount(0);
});

test('422 mostra o motivo, sem "Tentar de novo"', async ({ page }) => {
  await mockApi(page, { chat: { status: 422, body: error422 } });
  await page.goto('/');
  await ask(page, 'Oi');

  const banner = page.getByRole('alert');
  await expect(banner).toContainText('A mensagem não foi aceita: Entrada inválida: body.message');
  await expect(banner.getByRole('button', { name: 'Tentar de novo' })).toHaveCount(0);
});

test('502 com corpo HTML (proxy sem API) mostra indisponibilidade com retry', async ({ page }) => {
  await mockApi(page);
  await page.route('**/api/v1/chat', (route) =>
    route.fulfill({
      status: 502,
      contentType: 'text/html',
      body: '<html><body>502 Bad Gateway</body></html>',
    }),
  );
  await page.goto('/');
  await ask(page, 'Oi');

  const banner = page.getByRole('alert');
  await expect(banner).toContainText('502 · Serviço indisponível no momento');
  await expect(banner).toContainText(UNAVAILABLE);
  await expect(banner.getByRole('button', { name: 'Tentar de novo' })).toBeVisible();
});

test('falha de rede mostra o texto de conexão com retry', async ({ page }) => {
  await mockApi(page);
  await page.route('**/api/v1/chat', (route) => route.abort('internetdisconnected'));
  await page.goto('/');
  await ask(page, 'Oi');

  const banner = page.getByRole('alert');
  await expect(banner).toContainText('Sem conexão com o servidor');
  await expect(banner).toContainText(NETWORK);
  await expect(banner.getByRole('button', { name: 'Tentar de novo' })).toBeVisible();
});

test('serviço degradado ao abrir mostra aviso persistente, e o composer continua usável', async ({
  page,
}) => {
  const api = await mockApi(page, {
    health: [
      { status: 503, body: { status: 'degraded', database: 'unavailable' } },
      { body: { status: 'ok', database: 'ok' } },
    ],
  });
  await page.goto('/');

  const banner = page.getByRole('alert');
  await expect(banner).toContainText(UNAVAILABLE);
  await expect(page.getByRole('textbox', { name: 'Sua pergunta' })).toBeEnabled();

  await banner.getByRole('button', { name: 'Tentar de novo' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(api.requestsTo('GET', '/api/health')).toHaveLength(2);
});

test('sem rede ao abrir também mostra o aviso de indisponibilidade', async ({ page }) => {
  await mockApi(page);
  await page.route('**/api/health', (route) => route.abort('internetdisconnected'));
  await page.goto('/');

  const banner = page.getByRole('alert');
  await expect(banner).toContainText(UNAVAILABLE);
  await expect(banner.getByRole('button', { name: 'Tentar de novo' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Sua pergunta' })).toBeEnabled();
});
