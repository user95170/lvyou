const { test, expect } = require('@playwright/test');
const {
  expectToast,
  installMockAmap,
  registerAndLogin,
  waitForHomeRecommendations,
} = require('./helpers');

test('logged-in user can save, edit and delete a trip from route planning', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_crud');

  await page.getByTestId('home-add-trip-btn').nth(0).click();
  await expectToast(page);
  await page.getByTestId('home-add-trip-btn').nth(1).click();
  await expectToast(page);

  await page.getByTestId('nav-route').click();
  await expect(page).toHaveURL(/\/route$/);
  await expect(page.getByTestId('route-pending-hint')).toBeVisible();

  await page.getByTestId('route-plan-btn').click();
  await expect(page.getByTestId('route-result')).toBeVisible();
  await expect(page.getByTestId('route-map-section')).toBeVisible();
  await expect(page.getByTestId('route-map-canvas')).toBeVisible();
  await expect
    .poll(async () => await page.getByTestId('route-map-canvas').getAttribute('data-marker-count'))
    .not.toBe('0');
  await expect(page.getByTestId('route-save-section')).toBeVisible();

  const tripTitle = `E2E 行程 ${Date.now()}`;
  const updatedTitle = `${tripTitle} 已编辑`;

  await page.getByTestId('route-save-title-input').fill(tripTitle);
  await page.getByTestId('route-save-date-input').fill('2026-04-10');
  await page.getByTestId('route-save-btn').click();

  await expect(page).toHaveURL(/\/trips\/\d+$/);
  await expect(page.getByTestId('trip-detail-form')).toBeVisible();
  await expect(page.getByTestId('trip-title-input')).toHaveValue(tripTitle);
  await expect(page.getByTestId('trip-map-section')).toBeVisible();
  await expect(page.getByTestId('trip-map-canvas')).toBeVisible();
  await expect
    .poll(async () => await page.getByTestId('trip-map-canvas').getAttribute('data-marker-count'))
    .not.toBe('0');

  await page.getByTestId('trip-title-input').fill(updatedTitle);
  await page.getByTestId('trip-item-note-input').first().fill('上午先去');
  const updateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      response.url().includes('/api/trips/') &&
      response.status() === 200
  );
  await page.getByTestId('trip-save-btn').click();
  await updateResponsePromise;
  await expectToast(page);

  await page.reload();
  await expect(page.getByTestId('trip-title-input')).toHaveValue(updatedTitle);
  await expect(page.getByTestId('trip-item-note-input').first()).toHaveValue('上午先去');

  await page.getByTestId('nav-trips').click();
  await expect(page).toHaveURL(/\/trips$/);
  await expect(page.getByTestId('trip-list')).toBeVisible();
  await expect(page.getByText(updatedTitle)).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  const deleteResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' &&
      response.url().includes('/api/trips/') &&
      response.status() === 200
  );
  await page.getByTestId('trip-delete-btn').first().click();
  await deleteResponsePromise;
  await expectToast(page);
  await expect(page.getByText(updatedTitle)).toHaveCount(0);
});

test('guest user can still plan a route but cannot save it', async ({ page }) => {
  await installMockAmap(page);
  await page.goto('/');
  await waitForHomeRecommendations(page);

  await page.getByTestId('home-add-trip-btn').nth(0).click();
  await expectToast(page);
  await page.getByTestId('home-add-trip-btn').nth(1).click();
  await expectToast(page);

  await page.getByTestId('nav-route').click();
  await expect(page).toHaveURL(/\/route$/);
  await expect(page.getByTestId('route-pending-hint')).toBeVisible();

  await page.getByTestId('route-plan-btn').click();
  await expect(page.getByTestId('route-result')).toBeVisible();
  await expect(page.getByTestId('route-map-section')).toBeVisible();
  await expect(page.getByTestId('route-map-canvas')).toBeVisible();
  await expect(page.getByTestId('route-save-section')).toBeVisible();
  await expect(page.getByTestId('route-login-hint')).toBeVisible();
  await expect(page.getByTestId('route-save-btn')).toHaveCount(0);
});

test('route and trip detail show config error when AMap key is missing', async ({ page }) => {
  await page.addInitScript(() => {
    window.__AMAP_JS_KEY_OVERRIDE__ = '';
  });
  await registerAndLogin(page, 'trip_map_key_missing');

  await page.getByTestId('home-add-trip-btn').nth(0).click();
  await expectToast(page);
  await page.getByTestId('home-add-trip-btn').nth(1).click();
  await expectToast(page);

  await page.getByTestId('nav-route').click();
  await expect(page).toHaveURL(/\/route$/);
  await page.getByTestId('route-plan-btn').click();
  await expect(page.getByTestId('route-result')).toBeVisible();
  await expect(page.getByTestId('route-map-config-error')).toBeVisible();

  await page.getByTestId('route-save-title-input').fill(`Map Key Missing ${Date.now()}`);
  await page.getByTestId('route-save-date-input').fill('2026-04-10');
  await page.getByTestId('route-save-btn').click();

  await expect(page).toHaveURL(/\/trips\/\d+$/);
  await expect(page.getByTestId('trip-detail-form')).toBeVisible();
  await expect(page.getByTestId('trip-map-config-error')).toBeVisible();
});
