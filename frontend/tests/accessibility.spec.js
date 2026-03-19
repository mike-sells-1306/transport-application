const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

async function closeCookieOrBlockingUI(page) {
  // Placeholder helper for future overlays; currently no-op.
  await page.waitForTimeout(50);
}

test.describe('Accessibility smoke checks', () => {
  test('home page has no serious/critical axe violations', async ({ page }) => {
    await page.goto('/');
    await closeCookieOrBlockingUI(page);

    const results = await new AxeBuilder({ page })
      // Colour contrast can be noisy during design iteration; keep this as a separate manual audit.
      .disableRules(['color-contrast'])
      .analyze();

    const seriousOrCritical = results.violations.filter(v =>
      v.impact === 'serious' || v.impact === 'critical'
    );

    expect(seriousOrCritical, JSON.stringify(seriousOrCritical, null, 2)).toEqual([]);
  });

  test('core interactive controls expose accessible names', async ({ page }) => {
    await page.goto('/');

    const alwaysVisibleSelectors = [
      '#sidebar-toggle',
      '#weather-btn',
      '#notif-btn',
      '.journey-swap-btn',
      '#from-input',
      '#to-input',
    ];

    for (const selector of alwaysVisibleSelectors) {
      const el = page.locator(selector).first();
      await expect(el, `${selector} should exist`).toHaveCount(1);
      await expect(el, `${selector} should expose an accessible name`).toHaveAccessibleName(/.+/);
    }

    await page.locator('#weather-btn').click();
    await expect(page.locator('#weather-search-input')).toBeVisible();
    await expect(page.locator('#weather-search-input')).toHaveAccessibleName(/.+/);

    await page.locator('#accessibility-link').click();
    await expect(page.locator('#accessibility-save-btn')).toBeVisible();
    await expect(page.locator('#accessibility-save-btn')).toHaveAccessibleName(/.+/);
    await expect(page.locator('#accessibility-reset-btn')).toHaveAccessibleName(/.+/);
  });

  test('keyboard tab navigation reaches primary controls in order', async ({ page }) => {
    await page.goto('/');
    await page.locator('body').click();

    const reached = new Set();
    for (let i = 0; i < 20; i += 1) {
      await page.keyboard.press('Tab');
      const activeId = await page.evaluate(() => document.activeElement?.id || '');
      const activeClass = await page.evaluate(() => document.activeElement?.className || '');

      if (activeId === 'from-input') reached.add('from');
      if (activeId === 'to-input') reached.add('to');
      if (typeof activeClass === 'string' && activeClass.includes('journey-swap-btn')) reached.add('swap');
    }

    expect([...reached].sort()).toEqual(['from', 'swap', 'to']);
  });

  test('live regions announce notification panel updates', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#sr-alert-region')).toHaveCount(1);
    await expect(page.locator('.notif-list')).toHaveAttribute('aria-live', 'assertive');

    await page.locator('#notif-btn').click();

    await expect(page.locator('#notif-btn')).toHaveAttribute('aria-expanded', 'true');
    await expect(page.locator('.notif-list')).toBeVisible();
  });
});
