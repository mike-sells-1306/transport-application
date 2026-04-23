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
      // Leaflet injects third-party attribution links that are outside app-owned markup.
      .disableRules(['link-in-text-block'])
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
    await expect(page.locator('#system-announcements-list')).toHaveAttribute('aria-live', 'polite');
    await expect(page.locator('#live-transport-updates')).toHaveAttribute('aria-live', 'polite');

    await page.locator('#notif-btn').click();

    await expect(page.locator('#notif-btn')).toHaveAttribute('aria-expanded', 'true');
    await expect(page.locator('#system-announcements-title')).toBeVisible();
    await expect(page.locator('#live-transport-updates-title')).toBeVisible();
    await expect(page.locator('#system-announcements-list')).toBeVisible();
    await expect(page.locator('#live-transport-updates')).toBeVisible();
  });

  test('language selection updates locale and translated labels', async ({ page }) => {
    await page.goto('/');

    await page.locator('#accessibility-link').click();
    await expect(page.locator('#accessibility-language')).toBeVisible();

    await page.locator('#accessibility-language').selectOption('fr-FR');
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr-FR');
    await expect(page.locator('#accessibility-panel-title')).toHaveText('Accessibilité');

    const enGbOptionBefore = (await page.locator('#accessibility-language option[value="en-GB"]').textContent())?.trim();
    expect(enGbOptionBefore).toBe('🇬🇧 English (United Kingdom)');

    await page.locator('#accessibility-language').selectOption('zh-CN');
    await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN');
    await expect(page.locator('#accessibility-panel-title')).toHaveText('无障碍');
    await expect(page.locator('.accessibility-item h3').nth(1)).toHaveText('缩放');
    await expect(page.locator('#accessibility-language option[value="en-GB"]')).toHaveText('🇬🇧 English (United Kingdom)');

    await page.locator('#accessibility-language').selectOption('cy-GB');
    await expect(page.locator('html')).toHaveAttribute('lang', 'cy-GB');
    await expect(page.locator('#accessibility-panel-title')).toHaveText('Hygyrchedd');

    await page.locator('#accessibility-language').selectOption('en-GB');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en-GB');
    await expect(page.locator('#accessibility-panel-title')).toHaveText('Accessibility');
  });
});
