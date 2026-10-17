import { test, expect } from '@playwright/test';

// Each test run gets a unique email to avoid "already registered" errors
const UNIQUE_ID = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const TEST_EMAIL = `e2e-${UNIQUE_ID}@example.com`;
const TEST_PASSWORD = 'testpass123';
const TEST_NAME = 'E2E Test User';

// Register once via API, reuse for subsequent tests
let registered = false;

async function ensureRegistered(page: import('@playwright/test').Page) {
  if (registered) return;
  await page.goto('/register');
  await page.fill('#displayName', TEST_NAME);
  await page.fill('#email', TEST_EMAIL);
  await page.fill('#password', TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/projects');
  registered = true;
}

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.fill('#email', TEST_EMAIL);
  await page.fill('#password', TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/projects');
}

test.describe('WP-13 Agent Film Web E2E', () => {
  test('registration and login flow', async ({ page }) => {
    await page.goto('/register');
    await expect(page.locator('h2')).toHaveText('Create account');

    await page.fill('#displayName', TEST_NAME);
    await page.fill('#email', TEST_EMAIL);
    await page.fill('#password', TEST_PASSWORD);
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/projects');
    await expect(page.locator('.topnav-user')).toHaveText(TEST_NAME);
    registered = true;
  });

  test('create project', async ({ page }) => {
    await ensureRegistered(page);
    await login(page);

    await page.click('button:has-text("+ New Project")');
    await page.fill('.create-form input:first-child', 'E2E Test Project');
    await page.fill('.create-form input:nth-child(2)', 'Created by Playwright');
    await page.click('.create-form button[type="submit"]');

    await expect(page.locator('.project-card h3')).toHaveText('E2E Test Project');
  });

  test('project detail and workbench navigation', async ({ page }) => {
    await ensureRegistered(page);
    await login(page);

    await page.click('.project-card');

    // Wait for project detail to load
    await page.waitForURL(/\/projects\/proj-/);
    await expect(page.locator('textarea')).toBeVisible();
    await expect(page.locator('select')).toHaveValue('one-click-quick');
  });

  test('settings page loads', async ({ page }) => {
    await ensureRegistered(page);
    await login(page);

    await page.click('a[href="/settings"]');
    await expect(page.locator('h1')).toHaveText('Settings');
    await expect(page.locator('.provider-item')).toHaveCount(6);
  });

  test('responsive layout - mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/login');
    await expect(page.locator('.auth-card')).toBeVisible();
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(375);
  });

  test('responsive layout - desktop viewport', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/login');
    await expect(page.locator('.auth-card')).toBeVisible();
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(1280);
  });

  test('logout flow', async ({ page }) => {
    await ensureRegistered(page);
    await login(page);

    await page.click('.btn-logout');
    await expect(page).toHaveURL('/login');
  });
});

