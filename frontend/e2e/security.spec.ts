import { expect, test, type Request } from '@playwright/test';

import answerDocuments from './fixtures/answer-documents.json' with { type: 'json' };
import history from './fixtures/history.json' with { type: 'json' };
import { mockApi } from './support/mockApi';

test('nenhuma requisição leva X-API-Key nem sai da origem da página', async ({ page, baseURL }) => {
  const origin = new URL(baseURL ?? '').origin;
  const seen: Request[] = [];
  page.on('request', (request) => seen.push(request));

  await mockApi(page, { chat: { body: answerDocuments }, history: { body: history } });
  await page.goto('/');

  // Fluxo completo: perguntar, abrir uma fonte, recarregar e reabrir a conversa pela lista.
  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill('Como funciona o come-cotas?');
  await input.press('Enter');
  const log = page.getByRole('log');
  await log.getByRole('button', { name: 'Fonte 2' }).click();

  await page.reload();
  await page.getByRole('navigation', { name: 'Conversas' }).getByRole('button').nth(1).click();
  await expect(log.getByText('O que é come-cotas?')).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  const types = new Set(seen.map((r) => r.resourceType()));
  // Sem isso o teste passaria sem ver as fontes nem a API.
  expect(types).toContain('font');
  expect(seen.some((r) => new URL(r.url()).pathname === '/api/v1/chat')).toBe(true);

  for (const request of seen) {
    expect(new URL(request.url()).origin, request.url()).toBe(origin);
    const headers = Object.keys(await request.allHeaders()).map((h) => h.toLowerCase());
    expect(headers, request.url()).not.toContain('x-api-key');
  }
});
