import { expect, test, type Page, type Request } from '@playwright/test';

import answerDocuments from './fixtures/answer-documents.json' with { type: 'json' };
import answerFxCalc from './fixtures/answer-fx-calc.json' with { type: 'json' };
import history from './fixtures/history.json' with { type: 'json' };
import { mockApi, type MockResponse } from './support/mockApi';

const KEY = 'finagent.threads.v1';
const EXPIRED = 'Esta conversa expirou e foi apagada. Abrimos uma nova.';
const ID_A = '11111111-1111-4111-8111-111111111111';
const ID_B = '22222222-2222-4222-8222-222222222222';

/** Histórico do fixture com o `thread_id` pedido na URL. */
function historyFor(request: Request): MockResponse {
  const id = new URL(request.url()).pathname.split('/').at(-2);
  return { body: { ...history, thread_id: id } };
}

/** Responde com `fixture`, mas mantém o `thread_id` enviado, como a API real. */
function chatKeepingThread(fixture: { thread_id: string }) {
  return (request: Request): MockResponse => {
    const sent = (request.postDataJSON() as { thread_id?: string }).thread_id;
    return { body: { ...fixture, thread_id: sent ?? fixture.thread_id } };
  };
}

async function seed(page: Page, entries: { id: string; title: string; lastActivity: string }[]) {
  await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), [
    KEY,
    JSON.stringify(entries),
  ] as const);
}

async function ask(page: Page, question: string) {
  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill(question);
  await Promise.all([page.waitForResponse('**/api/v1/chat'), input.press('Enter')]);
  await expect(page.getByRole('button', { name: 'Enviar' })).toBeVisible();
}

test('lista as conversas depois de recarregar e reabre uma com histórico e fontes', async ({
  page,
}) => {
  let chats = 0;
  const api = await mockApi(page, {
    chat: (request) => chatKeepingThread(chats++ === 0 ? answerDocuments : answerFxCalc)(request),
    history: historyFor,
  });
  await page.goto('/');

  const list = page.getByRole('navigation', { name: 'Conversas' });
  await expect(list).toContainText('Conversas sem atividade por 30 dias são apagadas.');

  await ask(page, 'Como funciona o come-cotas?');
  await expect(page).toHaveURL(new RegExp(`#/t/${answerDocuments.thread_id}$`));

  await list.getByRole('button', { name: 'Nova conversa' }).click();
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole('log').getByRole('article')).toHaveCount(0);

  await ask(page, 'Quanto são 500 euros em reais?');
  const [first, second] = api.requestsTo('POST', '/api/v1/chat');
  expect(first?.body).toEqual({ message: 'Como funciona o come-cotas?' });
  expect(second?.body).toEqual({ message: 'Quanto são 500 euros em reais?' });

  await page.reload();
  const comeCotas = list.getByRole('button', { name: /Como funciona o come-cotas\?/ });
  const euros = list.getByRole('button', { name: /Quanto são 500 euros em reais\?/ });
  await expect(comeCotas).toContainText(/hoje, \d{2}:\d{2}/);
  await expect(euros).toContainText(/hoje, \d{2}:\d{2}/);
  // A mais recente vem primeiro e é a que está aberta (o hash da URL foi mantido).
  await expect(list.getByRole('listitem').first()).toContainText('500 euros');
  await expect(euros).toHaveAttribute('aria-current', 'page');

  await comeCotas.click();
  await expect(comeCotas).toHaveAttribute('aria-current', 'page');
  await expect(page).toHaveURL(new RegExp(`#/t/${answerDocuments.thread_id}$`));
  expect(
    api.requestsTo('GET', `/api/v1/threads/${answerDocuments.thread_id}/messages`),
  ).toHaveLength(1);

  const log = page.getByRole('log');
  await expect(log.getByText('O que é come-cotas?')).toBeVisible();
  await expect(log.getByRole('article')).toHaveCount(3);
  await expect(log.getByRole('article').filter({ hasText: 'Come-cotas' })).toContainText(
    'Documento',
  );
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Como funciona o come-cotas?');

  await ask(page, 'E para fundos de ações?');
  expect(api.requestsTo('POST', '/api/v1/chat').at(-1)?.body).toEqual({
    message: 'E para fundos de ações?',
    thread_id: answerDocuments.thread_id,
  });
});

test('conversa expirada sai da lista, mostra o aviso e abre uma conversa nova', async ({
  page,
}) => {
  await seed(page, [
    { id: ID_A, title: 'Conversa antiga', lastActivity: new Date().toISOString() },
  ]);
  const api = await mockApi(page, {
    history: {
      status: 404,
      body: { error: { code: 'not_found', message: 'Conversa não encontrada.' } },
    },
    chat: { body: answerDocuments },
  });
  await page.goto('/');

  const list = page.getByRole('navigation', { name: 'Conversas' });
  await list.getByRole('button', { name: /Conversa antiga/ }).click();

  const notice = page.getByRole('log').getByRole('note');
  await expect(notice).toContainText('Conversa expirada');
  await expect(notice).toContainText(EXPIRED);
  await expect(list.getByRole('button', { name: /Conversa antiga/ })).toHaveCount(0);
  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByRole('alert')).toHaveCount(0);

  const stored = await page.evaluate((key) => window.localStorage.getItem(key), KEY);
  expect(JSON.parse(stored ?? '[]')).toEqual([]);

  // A pergunta seguinte começa uma conversa nova, sem thread_id.
  await ask(page, 'Como funciona o come-cotas?');
  expect(api.requestsTo('POST', '/api/v1/chat')[0]?.body).toEqual({
    message: 'Como funciona o come-cotas?',
  });
  await expect(notice).toHaveCount(0);
});

test('a lista de conversas funciona só com o teclado', async ({ page }) => {
  const now = Date.now();
  await seed(page, [
    { id: ID_A, title: 'Primeira conversa', lastActivity: new Date(now).toISOString() },
    { id: ID_B, title: 'Segunda conversa', lastActivity: new Date(now - 60_000).toISOString() },
  ]);
  const api = await mockApi(page, { history: historyFor });
  await page.goto('/');

  const list = page.getByRole('navigation', { name: 'Conversas' });
  await list.getByRole('button', { name: 'Nova conversa' }).focus();
  await page.keyboard.press('Tab');
  await expect(list.getByRole('button', { name: /Primeira conversa/ })).toBeFocused();
  await page.keyboard.press('Tab');
  const second = list.getByRole('button', { name: /Segunda conversa/ });
  await expect(second).toBeFocused();
  await page.keyboard.press('Enter');

  await expect(second).toHaveAttribute('aria-current', 'page');
  await expect(page).toHaveURL(new RegExp(`#/t/${ID_B}$`));
  expect(api.requestsTo('GET', `/api/v1/threads/${ID_B}/messages`)).toHaveLength(1);
  await expect(page.getByRole('log').getByRole('article')).toHaveCount(3);
});

test('um id inválido na URL abre uma conversa nova', async ({ page }) => {
  const api = await mockApi(page);
  await page.goto('/#/t/nao-e-um-uuid');

  await expect(page).toHaveURL(/#\/$/);
  await expect(page.getByText('Financial Agent', { exact: true }).last()).toBeVisible();
  expect(api.requestsTo('GET', /\/threads\//)).toHaveLength(0);
});
