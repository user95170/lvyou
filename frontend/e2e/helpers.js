const { expect } = require('@playwright/test');

const DEFAULT_PASSWORD = '123456';
const DEFAULT_CITY = '呼和浩特';
const AGENT_PROMPT = '想去呼伦贝尔玩2天，预算3000，亲子';

function createUser(prefix = 'e2e_user') {
  const suffix = `${Date.now()}_${Math.floor(Math.random() * 1_000_000)}`;
  const username = `${prefix}_${suffix}`;
  return {
    username,
    email: `${username}@example.com`,
    password: DEFAULT_PASSWORD,
  };
}

async function register(page, user) {
  await page.goto('/register');
  await page.getByTestId('register-username').fill(user.username);
  await page.getByTestId('register-password').fill(user.password);
  await page.getByTestId('register-email').fill(user.email);
  await page.getByTestId('register-submit').click();
  await expect(page).toHaveURL(/\/login$/);
}

async function login(page, user) {
  await page.getByTestId('login-username').fill(user.username);
  await page.getByTestId('login-password').fill(user.password);
  await page.getByTestId('login-submit').click();
  await expect(page).toHaveURL(/\/$/);
}

async function registerAndLogin(page, prefix = 'e2e_user') {
  const user = createUser(prefix);
  await register(page, user);
  await login(page, user);
  await waitForHomeRecommendations(page);
  return user;
}

async function waitForHomeRecommendations(page) {
  await expect
    .poll(async () => await page.getByTestId('home-scenic-card').count())
    .toBeGreaterThan(1);
}

async function waitForBrowseCards(page) {
  await expect
    .poll(async () => await page.getByTestId('browse-card').count())
    .toBeGreaterThan(0);
}

async function expectToast(page) {
  await expect(page.getByTestId('toast')).toBeVisible();
}

module.exports = {
  AGENT_PROMPT,
  DEFAULT_CITY,
  expectToast,
  registerAndLogin,
  waitForBrowseCards,
  waitForHomeRecommendations,
};
