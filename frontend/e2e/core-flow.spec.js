const { test, expect } = require('@playwright/test');
const {
  AGENT_PROMPT,
  expectToast,
  registerAndLogin,
  waitForBrowseCards,
  waitForHomeRecommendations,
} = require('./helpers');

test('core user flow covers register, browse, rate, recommend, route and agent', async ({ page }) => {
  await registerAndLogin(page, 'core_flow');

  await page.getByTestId('nav-browse').click();
  await expect(page).toHaveURL(/\/browse$/);
  await waitForBrowseCards(page);

  await page.getByTestId('browse-rate-btn').first().click();
  await expectToast(page);

  await page.getByTestId('browse-similar-btn').first().click();
  await expect(page.getByTestId('browse-similar-list')).toBeVisible();

  await page.getByTestId('nav-home').click();
  await expect(page).toHaveURL(/\/$/);
  await waitForHomeRecommendations(page);

  await page.getByTestId('home-add-trip-btn').nth(0).click();
  await expectToast(page);
  await page.getByTestId('home-add-trip-btn').nth(1).click();
  await expectToast(page);

  await page.getByTestId('nav-route').click();
  await expect(page).toHaveURL(/\/route$/);
  await page.getByTestId('route-plan-btn').click();
  await expect(page.getByTestId('route-result')).toBeVisible();

  await page.getByTestId('nav-profile').click();
  await expect(page).toHaveURL(/\/profile$/);
  await page.getByTestId('agent-input').fill(AGENT_PROMPT);
  await page.getByTestId('agent-send').click();
  await expect(page.getByTestId('agent-itinerary')).toBeVisible();
});
