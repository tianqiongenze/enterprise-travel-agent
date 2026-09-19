import { expect, test } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

/**
 * CORS headers are included so the stub also works when the app talks to the
 * default cross-origin base URL (http://localhost:8080), not just same-origin.
 */
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
};

const RECOMMEND_PATTERN = '**/api/v1/travel/recommend';

const stubRecommendResponse = {
  traceId: 'stub-trace-0001',
  aiRationale: 'Stubbed recommendation for E2E run',
  hotelOptions: [
    { name: '北京国贸大酒店', price: 1280, score: 4.8, reason: '近会议中心，适合商务出行' },
    { name: '如家精选酒店', price: 388, score: 4.2, reason: '性价比高，符合差旅标准' },
  ],
  transportOptions: [{ name: 'G1 高铁', price: 553, score: 4.9, reason: '班次多，准点率高' }],
  itinerary: [
    { day: 1, name: '天安门广场 + 王府井', reason: '经典市区路线' },
    { day: 2, name: '颐和园 + 圆明园', reason: '皇家园林一日游' },
  ],
  engagementRecommendations: [],
  auditLogs: [],
  a2aLogs: [],
  memoryBefore: {},
  memoryAfter: {},
  memoryHits: [],
  registeredAgents: [],
  registeredTools: ['search_hotels', 'search_transports', 'search_attractions'],
};

async function fulfillOptions(route: Route): Promise<boolean> {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: CORS_HEADERS });
    return true;
  }
  return false;
}

async function login(page: Page): Promise<void> {
  await page.goto('/login');
  await page.getByPlaceholder('paste gateway access token').fill('e2e-token');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page).toHaveURL(/\/app$/);
}

test.describe('travel recommend flow', () => {
  test('successful recommend renders structured result cards', async ({ page }) => {
    await page.route(RECOMMEND_PATTERN, async (route) => {
      if (await fulfillOptions(route)) {
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: CORS_HEADERS,
        body: JSON.stringify(stubRecommendResponse),
      });
    });

    await login(page);
    await expect(page.getByRole('heading', { name: 'Enterprise Travel Agent Web' })).toBeVisible();

    await page.getByRole('button', { name: 'Get Recommendation' }).click();

    await expect(page.locator('.result-card')).toHaveCount(3);
    await expect(page.locator('.item-card')).toHaveCount(5);
    await expect(page.getByText('北京国贸大酒店')).toBeVisible();
    await expect(page.getByText('G1 高铁')).toBeVisible();
    await expect(page.getByText('颐和园 + 圆明园')).toBeVisible();
  });

  test('403 recommend response shows unauthorized error alert', async ({ page }) => {
    await page.route(RECOMMEND_PATTERN, async (route) => {
      if (await fulfillOptions(route)) {
        return;
      }
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        headers: CORS_HEADERS,
        body: JSON.stringify({ code: 'FORBIDDEN', message: 'policy denied' }),
      });
    });

    await login(page);

    await page.getByRole('button', { name: 'Get Recommendation' }).click();

    // api.ts mapError maps 401/403 to this message; no redirect happens.
    const alert = page.locator('[role="alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Unauthorized request. Check token or gateway policy.');
    await expect(page.locator('.result-card')).toHaveCount(0);
  });
});
