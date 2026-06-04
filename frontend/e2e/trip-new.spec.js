const { test, expect } = require('@playwright/test');
const {
  expectToast,
  registerAndLogin,
  waitForHomeRecommendations,
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

test('logged-in user can create a blank trip and later add a custom item', async ({ page }) => {
  await registerAndLogin(page, 'trip_blank_add_item');

  const tripTitle = `空白草稿 ${Date.now()}`;
  const updatedTitle = `${tripTitle} 已补内容`;
  await createBlankTrip(page, {
    title: tripTitle,
    city: '呼伦贝尔',
    days: 4,
    startDate: '2026-04-10',
  });

  await expect(page.getByTestId('trip-day-card')).toHaveCount(4);

  const firstDay = page.getByTestId('trip-day-card').first();
  await firstDay.getByTestId('trip-add-item-btn').click();
  await expect(page.getByTestId('trip-item-type-input').first()).toHaveValue('custom');

  await page.getByTestId('trip-title-input').fill(updatedTitle);
  await page.getByTestId('trip-day-note-input').first().fill('第一天到达后自由活动');
  await page.getByTestId('trip-item-title-input').first().fill('夜游成吉思汗广场');
  await page.getByTestId('trip-item-note-input').first().fill('晚上安排一个自定义活动');

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
  await expect(page.getByTestId('trip-day-card')).toHaveCount(4);
  await expect(page.getByTestId('trip-day-note-input').first()).toHaveValue('第一天到达后自由活动');
  await expect(page.getByTestId('trip-item-title-input').first()).toHaveValue('夜游成吉思汗广场');
  await expect(page.getByTestId('trip-item-note-input').first()).toHaveValue('晚上安排一个自定义活动');

  await page.getByTestId('nav-trips').click();
  await expect(page).toHaveURL(/\/trips$/);
  const tripCard = page.getByTestId('trip-card').filter({ hasText: updatedTitle });
  await expect(tripCard).toContainText('天数：4');
  await expect(tripCard).toContainText('项目数：1');
  await expect(tripCard).toContainText('manual_draft');

  page.once('dialog', (dialog) => dialog.accept());
  const deleteResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' &&
      response.url().includes('/api/trips/') &&
      response.status() === 200
  );
  await tripCard.getByTestId('trip-delete-btn').click();
  await deleteResponsePromise;
  await expectToast(page);
  await expect(page.getByText(updatedTitle)).toHaveCount(0);
});

test('logged-in user can keep and resave a blank draft with zero items', async ({ page }) => {
  await registerAndLogin(page, 'trip_blank_zero_item');

  const tripTitle = `零条目草稿 ${Date.now()}`;
  const updatedTitle = `${tripTitle} 已改标题`;
  await createBlankTrip(page, {
    title: tripTitle,
    city: '呼和浩特',
    days: 4,
    startDate: '2026-04-10',
  });

  await expect(page.getByTestId('trip-day-card')).toHaveCount(4);
  await expect(page.getByTestId('trip-item-title-input')).toHaveCount(0);

  await page.getByTestId('trip-title-input').fill(updatedTitle);
  await page.getByTestId('trip-day-note-input').nth(1).fill('第二天暂时空着');

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
  await expect(page.getByTestId('trip-item-title-input')).toHaveCount(0);
  await expect(page.getByTestId('trip-day-note-input').nth(1)).toHaveValue('第二天暂时空着');

  await page.getByTestId('nav-trips').click();
  await expect(page).toHaveURL(/\/trips$/);
  const tripCard = page.getByTestId('trip-card').filter({ hasText: updatedTitle });
  await expect(tripCard).toContainText('天数：4');
  await expect(tripCard).toContainText('项目数：0');

  page.once('dialog', (dialog) => dialog.accept());
  const deleteResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' &&
      response.url().includes('/api/trips/') &&
      response.status() === 200
  );
  await tripCard.getByTestId('trip-delete-btn').click();
  await deleteResponsePromise;
  await expectToast(page);
  await expect(page.getByText(updatedTitle)).toHaveCount(0);
});

test('guest user sees login guidance on blank trip creation page', async ({ page }) => {
  await page.goto('/');
  await waitForHomeRecommendations(page);

  await page.goto('/trips/new');
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByTestId('trip-new-login-hint')).toBeVisible();
  await expect(page.getByTestId('trip-new-form')).toHaveCount(0);
});
