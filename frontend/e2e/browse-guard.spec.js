const { test, expect } = require('@playwright/test');
const { DEFAULT_CITY, expectToast, waitForBrowseCards } = require('./helpers');

test('browse supports filtering and blocks rating when user is anonymous', async ({ page }) => {
  await page.goto('/browse');
  await waitForBrowseCards(page);

  await page.getByTestId('browse-rate-btn').first().click();
  await expectToast(page);

  await page.getByTestId('browse-similar-btn').first().click();
  await expect(page.getByTestId('browse-similar-list')).toBeVisible();

  await page.getByTestId('browse-type').selectOption('hotel');
  await page.getByTestId('browse-city').fill(DEFAULT_CITY);
  await page.getByTestId('browse-search').click();
  await waitForBrowseCards(page);

  await page.getByTestId('browse-type').selectOption('food');
  await page.getByTestId('browse-search').click();
  await waitForBrowseCards(page);
});
