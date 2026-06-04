const { test, expect } = require('@playwright/test');
const {
  expectToast,
  installMockAmap,
  registerAndLogin,
} = require('./helpers');

async function createBlankTrip(page, { title, city, days, startDate }) {
  await page.getByTestId('nav-trips').click();
  await expect(page).toHaveURL(/\/trips$/);
  await page.getByTestId('trip-new-entry-btn').click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByTestId('trip-new-form')).toBeVisible();

  await page.getByTestId('trip-new-title-input').fill(title);
  await page.getByTestId('trip-new-origin-city-input').fill(city);
  await page.getByTestId('trip-new-days-input').fill(String(days));
  if (startDate) {
    await page.getByTestId('trip-new-date-input').fill(startDate);
  }

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/trips') &&
      response.status() === 201
  );
  await page.getByTestId('trip-new-submit-btn').click();
  await createResponsePromise;
  await expect(page).toHaveURL(/\/trips\/\d+$/);
}

test('logged-in user can add a scenic resource and move it to the next day', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_editor_move');

  await createBlankTrip(page, {
    title: `跨天移动测试 ${Date.now()}`,
    city: '呼和浩特',
    days: 3,
    startDate: '2026-04-10',
  });

  const day1 = page.getByTestId('trip-day-card').nth(0);
  const day2 = page.getByTestId('trip-day-card').nth(1);

  await day1.getByTestId('trip-add-resource-btn').click();
  await expect(day1.getByTestId('trip-resource-panel')).toBeVisible();
  await day1.getByTestId('trip-resource-keyword-input').fill('大召寺');
  await day1.getByTestId('trip-resource-search-btn').click();

  const scenicResult = day1.getByTestId('trip-resource-result').filter({ hasText: '大召寺' });
  await expect(scenicResult).toBeVisible();
  await scenicResult.getByTestId('trip-resource-select-btn').click();

  await expect(day1.getByTestId('trip-item-title-input').first()).toHaveValue('大召寺');

  await day1.getByTestId('trip-move-next-day-btn').first().click();
  await expect(day1.getByTestId('trip-item-title-input')).toHaveCount(0);
  await expect(day2.getByTestId('trip-item-title-input').first()).toHaveValue('大召寺');

  await expect(page.getByTestId('trip-map-section')).toBeVisible();
  await expect(page.getByTestId('trip-map-empty')).toBeVisible();
  await page.getByTestId('trip-map-day-btn').nth(1).click();
  await expect(page.getByTestId('trip-map-canvas')).toBeVisible();
  await expect
    .poll(async () => await page.getByTestId('trip-map-canvas').getAttribute('data-marker-count'))
    .toBe('1');

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
  await expect(page.getByTestId('trip-day-card')).toHaveCount(3);
  await expect(page.getByTestId('trip-day-card').nth(0).getByTestId('trip-item-title-input')).toHaveCount(0);
  await expect(page.getByTestId('trip-day-card').nth(1).getByTestId('trip-item-title-input').first()).toHaveValue('大召寺');
});

test('logged-in user can repick a custom item to hotel and keep schedule fields', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_editor_repick');

  await createBlankTrip(page, {
    title: `资源重选测试 ${Date.now()}`,
    city: '呼和浩特',
    days: 2,
    startDate: '2026-04-10',
  });

  const day1 = page.getByTestId('trip-day-card').first();

  await day1.getByTestId('trip-add-item-btn').click();
  await expect(day1.getByTestId('trip-item-type-input').first()).toHaveValue('custom');
  await day1.getByTestId('trip-item-start-time-input').first().fill('09:00');
  await day1.getByTestId('trip-item-end-time-input').first().fill('10:30');
  await day1.getByTestId('trip-item-transport-mode-input').first().fill('walk');
  await day1.getByTestId('trip-item-note-input').first().fill('保留备注');

  await day1.getByTestId('trip-repick-resource-btn').first().click();
  await expect(day1.getByTestId('trip-resource-panel')).toBeVisible();
  await day1.getByTestId('trip-resource-type-select').selectOption('hotel');
  await day1.getByTestId('trip-resource-keyword-input').fill('香格里拉');
  await day1.getByTestId('trip-resource-search-btn').click();

  const hotelResult = day1.getByTestId('trip-resource-result').filter({ hasText: '呼和浩特香格里拉大酒店' });
  await expect(hotelResult).toBeVisible();
  await hotelResult.getByTestId('trip-resource-select-btn').click();

  await expect(day1.getByTestId('trip-item-type-input').first()).toHaveValue('hotel');
  await expect(day1.getByTestId('trip-item-title-input').first()).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(day1.getByTestId('trip-item-start-time-input').first()).toHaveValue('09:00');
  await expect(day1.getByTestId('trip-item-end-time-input').first()).toHaveValue('10:30');
  await expect(day1.getByTestId('trip-item-transport-mode-input').first()).toHaveValue('walk');
  await expect(day1.getByTestId('trip-item-note-input').first()).toHaveValue('保留备注');

  await expect(page.getByTestId('trip-map-canvas')).toBeVisible();
  await expect
    .poll(async () => await page.getByTestId('trip-map-canvas').getAttribute('data-marker-count'))
    .toBe('1');

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
  const reloadedDay1 = page.getByTestId('trip-day-card').first();
  await expect(reloadedDay1.getByTestId('trip-item-type-input').first()).toHaveValue('hotel');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').first()).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(reloadedDay1.getByTestId('trip-item-start-time-input').first()).toHaveValue('09:00');
  await expect(reloadedDay1.getByTestId('trip-item-end-time-input').first()).toHaveValue('10:30');
  await expect(reloadedDay1.getByTestId('trip-item-transport-mode-input').first()).toHaveValue('walk');
  await expect(reloadedDay1.getByTestId('trip-item-note-input').first()).toHaveValue('保留备注');
});
