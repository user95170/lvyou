const { test, expect } = require('@playwright/test');
const {
  dragTripItem,
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

async function addResourceToDay(dayCard, { type = 'scenic_spot', keyword, expectedName }) {
  await dayCard.getByTestId('trip-add-resource-btn').click();
  await expect(dayCard.getByTestId('trip-resource-panel')).toBeVisible();

  if (type !== 'scenic_spot') {
    await dayCard.getByTestId('trip-resource-type-select').selectOption(type);
  }
  if (keyword) {
    await dayCard.getByTestId('trip-resource-keyword-input').fill(keyword);
  }

  await dayCard.getByTestId('trip-resource-search-btn').click();
  const result = dayCard.getByTestId('trip-resource-result').filter({ hasText: expectedName });
  await expect(result).toBeVisible();
  await result.getByTestId('trip-resource-select-btn').click();
}

test('logged-in user can drag items within the same day and keep the saved order', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_editor_drag_same_day');

  await createBlankTrip(page, {
    title: `同日拖拽排序 ${Date.now()}`,
    city: '呼和浩特',
    days: 1,
    startDate: '2026-04-10',
  });

  const day1 = page.getByTestId('trip-day-card').first();

  await addResourceToDay(day1, {
    keyword: '博物院',
    expectedName: '内蒙古博物院',
  });
  await addResourceToDay(day1, {
    keyword: '大召寺',
    expectedName: '大召寺',
  });

  const firstCard = day1.getByTestId('trip-item-card').nth(0);
  const secondHandle = day1.getByTestId('trip-item-card').nth(1).getByTestId('trip-drag-handle');
  await dragTripItem(page, secondHandle, firstCard, 'before');

  await expect(day1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('大召寺');
  await expect(day1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('内蒙古博物院');

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
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('大召寺');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('内蒙古博物院');
});

test('logged-in user can drag a resource item across days into an arbitrary position', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_editor_drag_cross_day');

  await createBlankTrip(page, {
    title: `跨天拖拽排序 ${Date.now()}`,
    city: '呼和浩特',
    days: 3,
    startDate: '2026-04-10',
  });

  const day1 = page.getByTestId('trip-day-card').nth(0);
  const day2 = page.getByTestId('trip-day-card').nth(1);

  await addResourceToDay(day1, {
    keyword: '大召寺',
    expectedName: '大召寺',
  });

  await day2.getByTestId('trip-add-item-btn').click();
  await day2.getByTestId('trip-item-title-input').nth(0).fill('Day2 自定义 A');
  await day2.getByTestId('trip-add-item-btn').click();
  await day2.getByTestId('trip-item-title-input').nth(1).fill('Day2 自定义 B');

  const sourceHandle = day1.getByTestId('trip-item-card').first().getByTestId('trip-drag-handle');
  const targetCard = day2.getByTestId('trip-item-card').nth(0);
  await dragTripItem(page, sourceHandle, targetCard, 'after');

  await expect(day1.getByTestId('trip-item-card')).toHaveCount(0);
  await expect(day2.getByTestId('trip-item-title-input').nth(0)).toHaveValue('Day2 自定义 A');
  await expect(day2.getByTestId('trip-item-title-input').nth(1)).toHaveValue('大召寺');
  await expect(day2.getByTestId('trip-item-title-input').nth(2)).toHaveValue('Day2 自定义 B');

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
  const reloadedDay1 = page.getByTestId('trip-day-card').nth(0);
  const reloadedDay2 = page.getByTestId('trip-day-card').nth(1);
  await expect(page.getByTestId('trip-day-card')).toHaveCount(3);
  await expect(reloadedDay1.getByTestId('trip-item-card')).toHaveCount(0);
  await expect(reloadedDay2.getByTestId('trip-item-title-input').nth(0)).toHaveValue('Day2 自定义 A');
  await expect(reloadedDay2.getByTestId('trip-item-title-input').nth(1)).toHaveValue('大召寺');
  await expect(reloadedDay2.getByTestId('trip-item-title-input').nth(2)).toHaveValue('Day2 自定义 B');
});

test('logged-in user can apply a day route recommendation and keep custom fields intact', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_editor_recommendation');

  await createBlankTrip(page, {
    title: `路线建议应用 ${Date.now()}`,
    city: '呼和浩特',
    days: 1,
    startDate: '2026-04-10',
  });

  const day1 = page.getByTestId('trip-day-card').first();

  await day1.getByTestId('trip-add-item-btn').click();
  await day1.getByTestId('trip-item-title-input').nth(0).fill('自定义早餐');
  await day1.getByTestId('trip-item-start-time-input').nth(0).fill('08:00');
  await day1.getByTestId('trip-item-note-input').nth(0).fill('保留自定义备注');

  await addResourceToDay(day1, {
    keyword: '博物院',
    expectedName: '内蒙古博物院',
  });
  await addResourceToDay(day1, {
    keyword: '大召寺',
    expectedName: '大召寺',
  });
  await addResourceToDay(day1, {
    type: 'hotel',
    keyword: '香格里拉',
    expectedName: '呼和浩特香格里拉大酒店',
  });

  await expect(day1.getByTestId('trip-route-recommendation-list')).toBeVisible();
  await expect(day1.getByTestId('trip-apply-recommendation-btn')).toBeVisible();
  await expect
    .poll(async () => await page.getByTestId('trip-map-canvas').getAttribute('data-marker-titles'))
    .toBe('2. 内蒙古博物院|3. 大召寺|4. 呼和浩特香格里拉大酒店');

  await day1.getByTestId('trip-apply-recommendation-btn').click();

  await expect(day1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('内蒙古博物院');
  await expect(day1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(day1.getByTestId('trip-item-title-input').nth(2)).toHaveValue('大召寺');
  await expect(day1.getByTestId('trip-item-title-input').nth(3)).toHaveValue('自定义早餐');
  await expect(day1.getByTestId('trip-item-start-time-input').nth(3)).toHaveValue('08:00');
  await expect(day1.getByTestId('trip-item-note-input').nth(3)).toHaveValue('保留自定义备注');

  await expect
    .poll(async () => await page.getByTestId('trip-map-canvas').getAttribute('data-marker-titles'))
    .toBe('1. 内蒙古博物院|2. 呼和浩特香格里拉大酒店|3. 大召寺');

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
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('内蒙古博物院');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(2)).toHaveValue('大召寺');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(3)).toHaveValue('自定义早餐');
  await expect(reloadedDay1.getByTestId('trip-item-start-time-input').nth(3)).toHaveValue('08:00');
  await expect(reloadedDay1.getByTestId('trip-item-note-input').nth(3)).toHaveValue('保留自定义备注');
});
