const { expect } = require('@playwright/test');

const DEFAULT_PASSWORD = '123456';
const DEFAULT_CITY = '呼和浩特';
const AGENT_PROMPT = '想去呼伦贝尔玩2天，预算3000，亲子';

async function installMockAmap(page) {
  await page.addInitScript(() => {
    class MockMarker {
      constructor(options = {}) {
        this.options = options;
        this.type = 'marker';
      }
    }

    class MockPolyline {
      constructor(options = {}) {
        this.options = options;
        this.type = 'polyline';
      }
    }

    class MockPixel {
      constructor(x, y) {
        this.x = x;
        this.y = y;
      }
    }

    class MockMap {
      constructor(container, options = {}) {
        this.container = container;
        this.options = options;
        this.overlays = [];
        this.sync();
      }

      add(overlays) {
        const nextOverlays = Array.isArray(overlays) ? overlays : [overlays];
        this.overlays.push(...nextOverlays);
        this.sync();
      }

      clearMap() {
        this.overlays = [];
        this.sync();
      }

      remove(overlays) {
        const targets = Array.isArray(overlays) ? overlays : [overlays];
        this.overlays = this.overlays.filter((overlay) => !targets.includes(overlay));
        this.sync();
      }

      setFitView(overlays) {
        this.lastFitView = Array.isArray(overlays) ? overlays : this.overlays;
        this.sync();
      }

      destroy() {
        this.overlays = [];
        this.sync();
      }

      sync() {
        if (!this.container) {
          return;
        }

        const markers = this.overlays.filter((overlay) => overlay?.type === 'marker');
        const polylines = this.overlays.filter((overlay) => overlay?.type === 'polyline');

        this.container.dataset.mockAmap = 'ready';
        this.container.dataset.overlayCount = String(this.overlays.length);
        this.container.dataset.markerCount = String(markers.length);
        this.container.dataset.polylineCount = String(polylines.length);
        this.container.dataset.markerTitles = markers
          .map((marker) => marker?.options?.title || '')
          .join('|');
        this.container.dataset.pathPointCount = String(
          polylines[0]?.options?.path?.length || 0
        );
      }
    }

    window.AMap = {
      Map: MockMap,
      Marker: MockMarker,
      Polyline: MockPolyline,
      Pixel: MockPixel,
    };
  });
}

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

async function dragTripItem(page, sourceHandle, targetCard, placement = 'before') {
  const [sourceMetrics, targetMetrics, viewportHeight] = await Promise.all([
    sourceHandle.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        top: rect.top + window.scrollY,
        bottom: rect.bottom + window.scrollY,
      };
    }),
    targetCard.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        top: rect.top + window.scrollY,
        bottom: rect.bottom + window.scrollY,
      };
    }),
    page.evaluate(() => window.innerHeight),
  ]);

  const combinedTop = Math.min(sourceMetrics.top, targetMetrics.top);
  const combinedBottom = Math.max(sourceMetrics.bottom, targetMetrics.bottom);
  const combinedHeight = combinedBottom - combinedTop;
  const desiredScrollTop =
    combinedHeight + 120 <= viewportHeight
      ? Math.max(0, combinedTop - (viewportHeight - combinedHeight) / 2)
      : Math.max(0, combinedTop - 80);

  await page.evaluate((scrollTop) => {
    window.scrollTo(0, scrollTop);
  }, desiredScrollTop);
  await page.waitForTimeout(80);

  const sourceBox = await sourceHandle.boundingBox();
  const targetBox = await targetCard.boundingBox();
  if (!sourceBox || !targetBox) {
    throw new Error('unable to resolve drag coordinates');
  }

  const startX = sourceBox.x + sourceBox.width / 2;
  const startY = sourceBox.y + sourceBox.height / 2;
  const insertionOffset = Math.min(16, Math.max(8, targetBox.height * 0.08));
  const targetX = targetBox.x + targetBox.width / 2;
  const targetTopY = Math.min(targetBox.y + Math.max(24, targetBox.height * 0.2), viewportHeight - 80);

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + 8, startY + 8, { steps: 6 });

  await page.mouse.move(targetX, targetTopY, { steps: 20 });

  if (placement === 'after') {
    const desiredDropY = targetBox.y + targetBox.height + insertionOffset;
    const visibleDropY = viewportHeight - 40;
    const scrollDelta = Math.max(0, desiredDropY - visibleDropY);
    if (scrollDelta > 0) {
      await page.evaluate((delta) => {
        window.scrollBy(0, delta);
      }, scrollDelta);
      await page.waitForTimeout(80);
    }
  }

  const updatedTargetBox = await targetCard.boundingBox();
  if (!updatedTargetBox) {
    throw new Error('unable to resolve updated drop target coordinates');
  }

  const updatedTargetX = updatedTargetBox.x + updatedTargetBox.width / 2;
  const updatedTargetY =
    placement === 'after'
      ? Math.min(
          updatedTargetBox.y + updatedTargetBox.height + insertionOffset,
          viewportHeight - 24
        )
      : Math.max(updatedTargetBox.y + updatedTargetBox.height * 0.2, 24);

  await page.mouse.move(updatedTargetX, updatedTargetY, { steps: 12 });
  await page.waitForTimeout(120);
  await page.mouse.up();
}

module.exports = {
  AGENT_PROMPT,
  DEFAULT_CITY,
  dragTripItem,
  expectToast,
  installMockAmap,
  registerAndLogin,
  waitForBrowseCards,
  waitForHomeRecommendations,
};
