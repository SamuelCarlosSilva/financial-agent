import { expect, test } from '@playwright/test';

import answerFxCalc from './fixtures/answer-fx-calc.json' with { type: 'json' };
import history from './fixtures/history.json' with { type: 'json' };
import { mockApi } from './support/mockApi';

test('mostra o guardrail em andamento e, na resposta, os passos com par e expressão', async ({
  page,
}) => {
  await mockApi(page, { chat: { body: answerFxCalc, delayMs: 800 } });
  await page.goto('/');

  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill('Quanto são 500 euros em reais?');
  await input.press('Enter');

  // Durante a espera: um passo em andamento, anunciado com aria-live.
  const log = page.getByRole('log');
  const pending = log.locator('.fa-tools');
  await expect(pending).toHaveAttribute('aria-live', 'polite');
  await expect(pending.getByRole('listitem')).toHaveCount(1);
  await expect(pending).toContainText('Verificando o escopo em andamento');

  const toggle = log.getByRole('button', { name: 'Passos do agente' });
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  const steps = log.locator('.fa-tools');
  await expect(steps.getByRole('listitem')).toHaveCount(4);
  await expect(steps.getByRole('listitem').nth(0)).toContainText('Verificando o escopo concluído');
  const quote = steps.getByRole('listitem').filter({ hasText: 'Consultando cotação' });
  await expect(quote).toContainText('EUR-BRL');
  await expect(quote).toContainText('concluído');
  const calc = steps.getByRole('listitem').filter({ hasText: 'Calculando' });
  await expect(calc).toContainText('500 * 6.0123');
  await expect(calc).toContainText('concluído');
  await expect(steps.getByRole('listitem').nth(3)).toContainText('Conferindo a fundamentação');

  // Recolhe e expande só com o teclado.
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(steps).toBeHidden();
  await page.keyboard.press('Space');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(steps).toBeVisible();
});

test('só o turno mais novo começa expandido; o anterior recolhe', async ({ page }) => {
  await mockApi(page, { chat: { body: answerFxCalc } });
  await page.goto('/');

  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  const toggles = page.getByRole('log').getByRole('button', { name: 'Passos do agente' });
  await input.fill('Quanto são 500 euros em reais?');
  await input.press('Enter');
  await expect(toggles).toHaveCount(1);
  await input.fill('E 800 euros?');
  await input.press('Enter');
  await expect(toggles).toHaveCount(2);

  await expect(toggles.nth(0)).toHaveAttribute('aria-expanded', 'false');
  await expect(toggles.nth(1)).toHaveAttribute('aria-expanded', 'true');
});

test('turnos do histórico começam recolhidos', async ({ page }) => {
  await mockApi(page, { history: { body: history } });
  await page.goto(`/#/t/${history.thread_id}`);

  const toggles = page.getByRole('log').getByRole('button', { name: 'Passos do agente' });
  await expect(toggles).toHaveCount(2);
  for (const toggle of await toggles.all()) {
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  }
  await expect(page.getByRole('log').locator('.fa-tools')).toHaveCount(2);
  await expect(page.getByRole('log').locator('.fa-tools').first()).toBeHidden();
});
