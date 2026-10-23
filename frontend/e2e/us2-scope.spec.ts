import { expect, test, type Page } from '@playwright/test';

import advice from './fixtures/advice.json' with { type: 'json' };
import ambiguous from './fixtures/ambiguous.json' with { type: 'json' };
import notFound from './fixtures/not-found.json' with { type: 'json' };
import outOfScope from './fixtures/out-of-scope.json' with { type: 'json' };
import { mockApi } from './support/mockApi';

const ADVICE_SENTENCE = 'Esta resposta é informativa e não constitui recomendação de investimento.';

async function ask(page: Page, body: unknown) {
  await mockApi(page, { chat: { body } });
  await page.goto('/');
  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill('Pergunta de teste');
  await input.press('Enter');
  return page.getByRole('log');
}

const NOTICES = [
  { name: 'fora de escopo', fixture: outOfScope, title: 'Fora do escopo financeiro' },
  { name: 'ambígua', fixture: ambiguous, title: 'Preciso de um esclarecimento' },
  { name: 'sem resposta nas fontes', fixture: notFound, title: 'Não encontrei nas fontes' },
];

for (const { name, fixture, title } of NOTICES) {
  test(`pergunta ${name} mostra um aviso próprio, sem fontes e sem alerta`, async ({ page }) => {
    const log = await ask(page, fixture);

    const notice = log.getByRole('note');
    await expect(notice).toHaveCount(1);
    await expect(notice).toContainText(title);
    await expect(notice.locator('svg')).toBeVisible();
    await expect(notice.getByText(fixture.answer, { exact: true })).toBeVisible();

    await expect(log.getByRole('article')).toHaveCount(0);
    await expect(page.getByRole('alert')).toHaveCount(0);
  });
}

test('pergunta de recomendação mostra a resposta, as fontes e o aviso abaixo', async ({ page }) => {
  const log = await ask(page, advice);

  await expect(log.getByRole('article')).toHaveCount(1);
  await expect(log.getByRole('button', { name: 'Fonte 1' })).toBeVisible();

  const notice = log.getByRole('note');
  await expect(notice).toContainText('Não é recomendação de investimento');
  await expect(notice.locator('svg')).toBeVisible();
  await expect(notice.getByText(ADVICE_SENTENCE, { exact: true })).toBeVisible();

  // A frase sai da bolha e fica só no aviso; o resto do texto continua lá.
  const bubble = log.locator('.fa-msg-assistant');
  await expect(bubble).toContainText('A escolha entre CDB e Tesouro depende do seu prazo');
  await expect(bubble).not.toContainText(ADVICE_SENTENCE);

  const bubbleBox = await bubble.boundingBox();
  const noticeBox = await notice.boundingBox();
  expect(noticeBox!.y).toBeGreaterThanOrEqual(bubbleBox!.y + bubbleBox!.height);

  await expect(page.getByRole('alert')).toHaveCount(0);
});
