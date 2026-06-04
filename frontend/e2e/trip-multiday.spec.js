const { test, expect } = require('@playwright/test');
const {
  AGENT_PROMPT,
  expectToast,
  installMockAmap,
  registerAndLogin,
  waitForHomeRecommendations,
} = require('./helpers');

const MOCK_ITINERARY_RESPONSE = {
  reply: '已为你生成 3 天行程草案。',
  slots: {
    destination: '呼伦贝尔',
    days: 3,
    budget_amount: 3200,
    budget_level: 2,
    transport_mode: 'drive',
    travel_style: 'family',
    interests: ['草原', '美食'],
  },
  actions: ['upsert_profile', 'suggest_itinerary'],
  profile: {
    user_id: 1,
    travel_style: 'family',
    budget_level: 2,
    prefer_scenic_types: '草原,美食',
    prefer_food_types: null,
  },
  itinerary: {
    city: '呼伦贝尔',
    days: [
      {
        day_index: 1,
        note: '第一天先看草原',
        items: [
          {
            type: 'scenic_spot',
            id: 1,
            name: '莫日格勒河景区',
            address: '陈巴尔虎旗草原腹地',
            start_time: '09:00',
            end_time: '11:30',
          },
        ],
      },
      {
        day_index: 2,
        note: '第二天吃本地特色',
        items: [
          {
            type: 'food_place',
            id: 2,
            name: '草原手把肉馆',
            address: '海拉尔区胜利大街',
            start_time: '12:00',
            end_time: '13:00',
          },
        ],
      },
      {
        day_index: 3,
        note: '第三天看湿地日落',
        items: [
          {
            type: 'scenic_spot',
            id: 3,
            name: '额尔古纳湿地',
            address: '额尔古纳市拉布大林街道',
            start_time: '16:00',
            end_time: '18:30',
          },
        ],
      },
    ],
  },
};

async function mockAgentChat(page) {
  await page.route('**/api/agent/chat', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ITINERARY_RESPONSE),
    });
  });
}

test('logged-in user can save and edit a multi-day trip from agent itinerary', async ({ page }) => {
  await installMockAmap(page);
  await registerAndLogin(page, 'trip_multiday');
  await mockAgentChat(page);

  await page.getByTestId('nav-profile').click();
  await expect(page).toHaveURL(/\/profile$/);

  await page.getByTestId('agent-input').fill(AGENT_PROMPT);
  await page.getByTestId('agent-send').click();

  await expect(page.getByTestId('agent-itinerary')).toBeVisible();
  await expect(page.getByTestId('agent-save-section')).toBeVisible();
  await expect(page.getByTestId('agent-save-title-input')).toHaveValue('呼伦贝尔多日行程');

  const tripTitle = `Agent 多日行程 ${Date.now()}`;
  const updatedTitle = `${tripTitle} 已编辑`;

  await page.getByTestId('agent-save-title-input').fill(tripTitle);
  await page.getByTestId('agent-save-date-input').fill('2026-04-10');

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/trips') &&
      response.status() === 201
  );
  await page.getByTestId('agent-save-btn').click();
  await createResponsePromise;

  await expect(page).toHaveURL(/\/trips\/\d+$/);
  await expect(page.getByTestId('trip-detail-form')).toBeVisible();
  await expect(page.getByTestId('trip-day-card')).toHaveCount(3);
  await expect(page.getByTestId('trip-map-section')).toBeVisible();
  await expect(page.getByTestId('trip-map-canvas')).toBeVisible();

  await page.getByTestId('trip-title-input').fill(updatedTitle);
  await page.getByTestId('trip-item-note-input').first().fill('第一天上午先去');

  await page.getByTestId('trip-add-day-btn').click();
  await expect(page.getByTestId('trip-day-card')).toHaveCount(4);

  const lastDay = page.getByTestId('trip-day-card').last();
  await expect(lastDay.getByTestId('trip-add-item-btn')).toBeVisible();
  await lastDay.getByTestId('trip-add-item-btn').click();
  await expect(page.getByTestId('trip-item-type-input').last()).toHaveValue('custom');
  await page.getByTestId('trip-day-note-input').last().fill('第四天自由活动');
  await page.getByTestId('trip-item-title-input').last().fill('夜游成吉思汗广场');
  await page.getByTestId('trip-item-note-input').last().fill('晚上安排自定义活动');

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
  await expect(page.getByTestId('trip-day-note-input').last()).toHaveValue('第四天自由活动');
  await expect(page.getByTestId('trip-item-title-input').last()).toHaveValue('夜游成吉思汗广场');
  await expect(page.getByTestId('trip-item-note-input').last()).toHaveValue('晚上安排自定义活动');

  await page.getByTestId('nav-trips').click();
  await expect(page).toHaveURL(/\/trips$/);
  await expect(page.getByTestId('trip-list')).toBeVisible();

  const tripCard = page.getByTestId('trip-card').filter({ hasText: updatedTitle });
  await expect(tripCard).toContainText('天数：4');
  await expect(tripCard).toContainText('项目数：4');

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

test('guest user can preview agent itinerary but cannot save it as a trip', async ({ page }) => {
  await page.goto('/');
  await waitForHomeRecommendations(page);
  await mockAgentChat(page);

  await page.getByTestId('nav-profile').click();
  await expect(page).toHaveURL(/\/profile$/);

  await page.getByTestId('agent-input').fill(AGENT_PROMPT);
  await page.getByTestId('agent-send').click();

  await expect(page.getByTestId('agent-itinerary')).toBeVisible();
  await expect(page.getByTestId('agent-save-login-hint')).toBeVisible();
  await expect(page.getByTestId('agent-save-btn')).toHaveCount(0);
});
