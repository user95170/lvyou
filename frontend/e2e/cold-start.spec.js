const { test, expect } = require('@playwright/test');
const { registerAndLogin } = require('./helpers');

test('new user sees cold-start guidance and can enter browse cold-start mode', async ({ page }) => {
  await registerAndLogin(page, 'cold_start');

  await expect(page.getByTestId('home-cold-start-banner')).toBeVisible();
  await page.getByTestId('home-cold-start-browse-link').click();

  await expect(page).toHaveURL(/\/browse\?mode=cold_start$/);
  await expect(page.getByTestId('browse-cold-start-tip')).toBeVisible();
});
