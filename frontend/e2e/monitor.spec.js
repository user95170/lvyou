const { test, expect } = require('@playwright/test');

test('monitor page shows system overview from backend metrics', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('nav-monitor').click();

  await expect(page).toHaveURL(/\/monitor$/);
  await expect(page.getByRole('heading', { name: '系统监控' })).toBeVisible();
  await expect(page.getByTestId('monitor-status')).toContainText('ok');
  await expect(page.getByTestId('monitor-resource-scenic')).toContainText('景点');
  await expect(page.getByTestId('monitor-resource-hotels')).toContainText('酒店');
  await expect(page.getByTestId('monitor-resource-foods')).toContainText('美食');
  await expect(page.getByTestId('monitor-recommend-request-count')).toContainText('请求');

  await expect
    .poll(async () => {
      const text = await page.getByTestId('monitor-resource-scenic').innerText();
      const match = text.match(/\d+/);
      return match ? Number(match[0]) : 0;
    })
    .toBeGreaterThan(0);
});
