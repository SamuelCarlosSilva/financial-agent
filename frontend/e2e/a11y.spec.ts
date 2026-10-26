import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

import answerDocuments from './fixtures/answer-documents.json' with { type: 'json' };
import answerFxCalc from './fixtures/answer-fx-calc.json' with { type: 'json' };
import error503 from './fixtures/error-503.json' with { type: 'json' };
import history from './fixtures/history.json' with { type: 'json' };
import outOfScope from './fixtures/out-of-scope.json' with { type: 'json' };
import { mockApi } from './support/mockApi';

const KEY = 'finagent.threads.v1';
// Id próprio: o `thread_id` do histórico é o mesmo da resposta de `answer-documents`.
const THREAD = { id: '11111111-1111-4111-8111-111111111111', title: 'O que é come-cotas?' };
const HISTORY = { ...history, thread_id: THREAD.id };

async function seedThread(page: Page) {
  const entry = { ...THREAD, lastActivity: new Date().toISOString() };
  await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), [
    KEY,
    JSON.stringify([entry]),
  ] as const);
}

async function ask(page: Page, question: string) {
  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  await input.fill(question);
  await input.press('Enter');
  await expect(page.getByRole('button', { name: 'Enviar' })).toBeVisible();
}

async function expectNoViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(
    violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`),
  ).toEqual([]);
}

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`axe, tema ${colorScheme === 'light' ? 'claro' : 'escuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ colorScheme });
    });

    test('tela vazia', async ({ page }) => {
      await mockApi(page);
      await page.goto('/');
      await expect(page.getByRole('textbox', { name: 'Sua pergunta' })).toBeVisible();
      await expectNoViolations(page);
    });

    test('resposta com fontes', async ({ page }) => {
      await mockApi(page, { chat: { body: answerDocuments } });
      await page.goto('/');
      await ask(page, 'Como funciona o come-cotas?');
      await expect(page.getByRole('log').getByRole('article')).toHaveCount(2);
      await expectNoViolations(page);
    });

    test('recusa', async ({ page }) => {
      await mockApi(page, { chat: { body: outOfScope } });
      await page.goto('/');
      await ask(page, 'Me dá uma receita de bolo');
      await expect(page.getByRole('log').getByRole('note')).toBeVisible();
      await expectNoViolations(page);
    });

    test('erro', async ({ page }) => {
      await mockApi(page, { chat: { status: 503, body: error503 } });
      await page.goto('/');
      await ask(page, 'Oi');
      await expect(page.getByRole('alert')).toBeVisible();
      await expectNoViolations(page);
    });

    test('histórico aberto', async ({ page }) => {
      await seedThread(page);
      await mockApi(page, { history: { body: HISTORY } });
      await page.goto(`/#/t/${THREAD.id}`);
      await expect(page.getByRole('log').getByText('O que é come-cotas?')).toBeVisible();
      await expectNoViolations(page);
    });
  });
}

/**
 * O elemento focado tem indicador visível: o contorno do `:focus-visible` ou, no campo do
 * composer (que não tem contorno próprio), a borda do composer na cor de foco.
 */
async function expectVisibleFocus(page: Page) {
  const visible = await page.evaluate(() => {
    const el = document.activeElement;
    if (!(el instanceof HTMLElement) || el === document.body) return false;
    const style = getComputedStyle(el);
    if (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) return true;
    const composer = el.closest<HTMLElement>('.fa-composer');
    if (!composer) return false;
    const probe = document.createElement('span');
    probe.style.color = 'var(--focus)';
    composer.append(probe);
    const focusColor = getComputedStyle(probe).color;
    probe.remove();
    return getComputedStyle(composer).borderTopColor === focusColor;
  });
  expect(visible, 'o foco deve estar visível').toBe(true);
}

/** Tab (ou Shift+Tab) até `target` receber o foco, sem usar o mouse. */
async function tabTo(page: Page, target: Locator, backwards = false) {
  for (let i = 0; i < 60; i++) {
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) {
      await expectVisibleFocus(page);
      return;
    }
    await page.keyboard.press(backwards ? 'Shift+Tab' : 'Tab');
  }
  throw new Error(`não chegou ao elemento com ${backwards ? 'Shift+Tab' : 'Tab'}`);
}

test('todo o fluxo funciona só com o teclado, com o foco sempre visível', async ({ page }) => {
  await seedThread(page);
  await mockApi(page, {
    chat: [{ body: answerDocuments }, { status: 503, body: error503 }, { body: answerFxCalc }],
    history: { body: HISTORY },
  });
  await page.goto('/');

  const input = page.getByRole('textbox', { name: 'Sua pergunta' });
  const log = page.getByRole('log');
  const list = page.getByRole('navigation', { name: 'Conversas' });

  // Enviar.
  await tabTo(page, input);
  await page.keyboard.type('Como funciona o come-cotas?');
  await page.keyboard.press('Enter');
  await expect(log.getByRole('article')).toHaveCount(2);

  // Ativar um marcador [n].
  const marker = log.getByRole('button', { name: 'Fonte 4' });
  await tabTo(page, marker, true);
  await page.keyboard.press('Enter');
  await expect(
    log.getByRole('article').filter({ hasText: 'Tributação de fundos de investimento' }),
  ).toHaveClass(/is-highlighted/);

  // Abrir uma conversa da lista.
  const thread = list.getByRole('button', { name: /O que é come-cotas\?/ });
  await tabTo(page, thread, true);
  await page.keyboard.press('Space');
  await expect(thread).toHaveAttribute('aria-current', 'page');
  await expect(log.getByText('O que é come-cotas?')).toBeVisible();

  // Nova conversa.
  const newThread = list.getByRole('button', { name: 'Nova conversa' });
  await tabTo(page, newThread, true);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#\/$/);

  // Erro e "Tentar de novo".
  await tabTo(page, input);
  await page.keyboard.type('Quanto são 500 euros em reais?');
  await page.keyboard.press('Enter');
  const retry = log.getByRole('alert').getByRole('button', { name: 'Tentar de novo' });
  await expect(retry).toBeVisible();
  await tabTo(page, retry, true);
  await page.keyboard.press('Space');
  await expect(log.getByRole('alert')).toHaveCount(0);
  await expect(log.getByRole('article').filter({ hasText: 'Cálculo' })).toBeVisible();
});
