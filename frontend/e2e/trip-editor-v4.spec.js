const { test, expect } = require('@playwright/test');
const {
  expectToast,
  installMockAmap,
  registerAndLogin,
} = require('./helpers');

async function installRouteOptionsMock(page, optionsByCall = []) {
  let callCount = 0;
  await page.route('**/api/route/options', async (route) => {
    const option =
      optionsByCall[Math.min(callCount, Math.max(optionsByCall.length - 1, 0))] || {
        duration_min: 30,
        distance_km: 12,
      };
    callCount += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        options: [
          {
            label: `方案 ${callCount}`,
            duration_min: option.duration_min,
            distance_km: option.distance_km,
            legs: [{ mode: 'drive' }],
          },
        ],
      }),
    });
  });

  return {
    getCallCount() {
      return callCount;
    },
  };
}

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

test('logged-in user can recalculate a real route, apply it to the day, and keep the saved order', async ({ page }) => {
  await installMockAmap(page);
  await installRouteOptionsMock(page, [
    { duration_min: 44, distance_km: 18.6 },
    { duration_min: 12, distance_km: 8.4 },
    { duration_min: 28, distance_km: 11.9 },
    { duration_min: 30, distance_km: 12.5 },
    { duration_min: 26, distance_km: 10.3 },
  ]);
  await registerAndLogin(page, 'trip_editor_real_route_apply');

  await createBlankTrip(page, {
    title: `真实路线重算 ${Date.now()}`,
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
  await addResourceToDay(day1, {
    type: 'hotel',
    keyword: '香格里拉',
    expectedName: '呼和浩特香格里拉大酒店',
  });

  await day1.getByTestId('trip-real-route-recalc-btn').click();
  await expect(day1.getByTestId('trip-real-route-list')).toBeVisible();
  await expect(day1.getByTestId('trip-real-route-metric').nth(0)).toContainText('12');
  await expect(day1.getByTestId('trip-real-route-metric').nth(1)).toContainText('8.4');

  await day1.getByTestId('trip-real-route-apply-btn').click();
  await expect(day1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(day1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('大召寺');
  await expect(day1.getByTestId('trip-item-title-input').nth(2)).toHaveValue('内蒙古博物院');

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
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('大召寺');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(2)).toHaveValue('内蒙古博物院');
});

test('mixed custom and routeable items keep custom fields after applying a real route result', async ({ page }) => {
  await installMockAmap(page);
  await installRouteOptionsMock(page, [
    { duration_min: 36, distance_km: 13.8 },
    { duration_min: 11, distance_km: 6.4 },
    { duration_min: 28, distance_km: 9.3 },
  ]);
  await registerAndLogin(page, 'trip_editor_real_route_custom');

  await createBlankTrip(page, {
    title: `真实路线自定义项 ${Date.now()}`,
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
    type: 'hotel',
    keyword: '香格里拉',
    expectedName: '呼和浩特香格里拉大酒店',
  });

  await day1.getByTestId('trip-real-route-recalc-btn').click();
  await expect(day1.getByTestId('trip-real-route-list')).toBeVisible();
  await day1.getByTestId('trip-real-route-apply-btn').click();

  await expect(day1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(day1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('内蒙古博物院');
  await expect(day1.getByTestId('trip-item-title-input').nth(2)).toHaveValue('自定义早餐');
  await expect(day1.getByTestId('trip-item-start-time-input').nth(2)).toHaveValue('08:00');
  await expect(day1.getByTestId('trip-item-note-input').nth(2)).toHaveValue('保留自定义备注');

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
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(0)).toHaveValue('呼和浩特香格里拉大酒店');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(1)).toHaveValue('内蒙古博物院');
  await expect(reloadedDay1.getByTestId('trip-item-title-input').nth(2)).toHaveValue('自定义早餐');
  await expect(reloadedDay1.getByTestId('trip-item-start-time-input').nth(2)).toHaveValue('08:00');
  await expect(reloadedDay1.getByTestId('trip-item-note-input').nth(2)).toHaveValue('保留自定义备注');
});

test('real route recalculation does not call the API when a day has fewer than two routeable items', async ({ page }) => {
  await installMockAmap(page);
  const routeOptionsMock = await installRouteOptionsMock(page, [
    { duration_min: 20, distance_km: 8.1 },
  ]);
  await registerAndLogin(page, 'trip_editor_real_route_empty');

  await createBlankTrip(page, {
    title: `真实路线空态 ${Date.now()}`,
    city: '呼和浩特',
    days: 1,
    startDate: '2026-04-10',
  });

  const day1 = page.getByTestId('trip-day-card').first();
  await addResourceToDay(day1, {
    keyword: '博物院',
    expectedName: '内蒙古博物院',
  });

  await expect(day1.getByTestId('trip-real-route-empty')).toContainText('至少需要 2 个');
  await day1.getByTestId('trip-real-route-recalc-btn').click();
  await expect(day1.getByTestId('trip-real-route-empty')).toContainText('至少需要 2 个');
  await page.waitForTimeout(200);
  expect(routeOptionsMock.getCallCount()).toBe(0);
});

test('changing a resource after recalculation marks the real route result as stale', async ({ page }) => {
  await installMockAmap(page);
  await installRouteOptionsMock(page, [
    { duration_min: 24, distance_km: 10.4 },
    { duration_min: 10, distance_km: 5.7 },
    { duration_min: 18, distance_km: 8.2 },
  ]);
  await registerAndLogin(page, 'trip_editor_real_route_stale');

  await createBlankTrip(page, {
    title: `真实路线 stale ${Date.now()}`,
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

  await day1.getByTestId('trip-real-route-recalc-btn').click();
  await expect(day1.getByTestId('trip-real-route-list')).toBeVisible();
  await expect(day1.getByTestId('trip-real-route-apply-btn')).toBeEnabled();

  await day1.getByTestId('trip-repick-resource-btn').first().click();
  await expect(day1.getByTestId('trip-resource-panel')).toBeVisible();
  await day1.getByTestId('trip-resource-type-select').selectOption('hotel');
  await day1.getByTestId('trip-resource-keyword-input').fill('香格里拉');
  await day1.getByTestId('trip-resource-search-btn').click();
  const hotelResult = day1
    .getByTestId('trip-resource-result')
    .filter({ hasText: '呼和浩特香格里拉大酒店' });
  await expect(hotelResult).toBeVisible();
  await hotelResult.getByTestId('trip-resource-select-btn').click();

  await expect(day1.getByText('当前结果已过期，请重新点击“开始重算”获取最新方案。')).toBeVisible();
  await expect(day1.getByTestId('trip-real-route-apply-btn')).toBeDisabled();
});
