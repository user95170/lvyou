const { test, expect } = require('@playwright/test');
const { expectToast, installMockAmap, registerAndLogin } = require('./helpers');

test('trip items added on home are carried into route planning and can be planned', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'route_plan');

  await page.getByTestId('home-add-trip-btn').nth(0).click();
  await expectToast(page);
  await page.getByTestId('home-add-trip-btn').nth(1).click();
  await expectToast(page);

  await page.getByTestId('nav-route').click();
  await expect(page).toHaveURL(/\/route$/);
  await expect(page.getByTestId('route-pending-hint')).toBeVisible();
  await expect
    .poll(async () => await page.locator('[data-testid="route-spot-checkbox"]:checked').count())
    .toBeGreaterThanOrEqual(2);

  await page.getByTestId('route-plan-btn').click();
  await expect(page.getByTestId('route-result')).toBeVisible();
  await expect(page.getByTestId('route-map-canvas')).toBeVisible();
});
