import { expect, test } from '@playwright/test';

import answerDocuments from './fixtures/answer-documents.json' with { type: 'json' };
import answerFxCalc from './fixtures/answer-fx-calc.json' with { type: 'json' };
import { mockApi } from './support/mockApi';

test('envia com Enter, bloqueia o duplo envio e mostra os documentos citados', async ({ page }) => {
  const api = await mockApi(page, { chat: { body: answerDocuments, delayMs: 800 } });
  await page.goto('/');

  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill('Como funciona o come-cotas?');
  await input.press('Enter');

  const log = page.getByRole('log');
  await expect(log.getByText('Como funciona o come-cotas?')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Respondendo…' })).toBeDisabled();
  await expect(page.getByRole('log').locator('.fa-tools')).toContainText('Verificando o escopo');

  // Enquanto a resposta não chega, um segundo Enter não envia nada.
  await input.fill('Outra pergunta');
  await input.press('Enter');

  const cards = log.getByRole('article');
  await expect(cards).toHaveCount(2);
  expect(api.requestsTo('POST', '/api/v1/chat')).toHaveLength(1);

  const comeCotas = cards.filter({ has: page.getByText('Come-cotas', { exact: true }) });
  await expect(comeCotas).toContainText('Documento');
  await expect(comeCotas).toContainText('come-cotas.md · p. 1 · relevância 0,82');
  await expect(comeCotas).toContainText('antecipação semestral do imposto de renda');

  const fundos = cards.filter({
    has: page.getByText('Tributação de fundos de investimento', { exact: true }),
  });
  await expect(fundos).toContainText('Documento');
  await expect(fundos).toContainText('tributacao-fundos.pdf · p. 3 · relevância 0,77');

  // O texto da resposta aparece como veio, com [2] e [4] viradas em marcadores.
  await expect(log.getByRole('button', { name: 'Fonte 2' })).toBeVisible();
  // Tela baixa e log rolado para o topo: o cartão fica fora da vista até o clique.
  await page.setViewportSize({ width: 1280, height: 420 });
  await log.evaluate((el) => el.scrollTo({ top: 0 }));
  await expect(fundos).not.toBeInViewport();
  await log.getByRole('button', { name: 'Fonte 4' }).click();
  await expect(fundos).toHaveClass(/is-highlighted/);
  await expect(comeCotas).not.toHaveClass(/is-highlighted/);
  await expect(fundos).toBeInViewport();
});

test('mostra cotação e cálculo sem arredondar e mantém a conversa', async ({ page }) => {
  const api = await mockApi(page, { chat: { body: answerFxCalc } });
  await page.goto('/');

  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill('Quanto são 500 euros em reais?');
  await input.press('Enter');

  const log = page.getByRole('log');
  const quote = log.getByRole('article').filter({ hasText: 'Cotação' });
  await expect(quote).toContainText('EUR-BRL');
  await expect(quote).toContainText('6,0123');
  await expect(quote).toContainText('valor usado nas conversões');
  await expect(quote).toContainText('6,0187');
  await expect(quote).toContainText('18/10/2026, 09:40 (horário de Brasília)');

  const calc = log.getByRole('article').filter({ hasText: 'Cálculo' });
  await expect(calc).toContainText('500 * 6.0123');
  await expect(calc).toContainText('3.006,15');

  await input.fill('E 800 euros?');
  await input.press('Enter');
  await expect(log.getByRole('article').filter({ hasText: 'Cálculo' })).toHaveCount(2);

  const [first, second] = api.requestsTo('POST', '/api/v1/chat');
  expect(first?.body).toEqual({ message: 'Quanto são 500 euros em reais?' });
  expect(second?.body).toEqual({ message: 'E 800 euros?', thread_id: answerFxCalc.thread_id });
});
