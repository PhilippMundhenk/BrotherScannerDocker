import { expect, test } from '@playwright/test';
import { SAMPLE_FILE } from '../helpers';

test.describe('home page', () => {
  test('shows the model, the status and the four scan buttons', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/MFC-SIMULATOR/);
    await expect(page.locator('h1')).toContainText('MFC-SIMULATOR');
    await expect(page.locator('#status-text')).toHaveText('Ready to scan');
    const buttons = page.locator('a.trigger-scan');
    await expect(buttons).toHaveCount(4);
    await expect(buttons.nth(0)).toHaveText('Scan to file');
    await expect(buttons.nth(1)).toHaveText('Scan to email');
    await expect(buttons.nth(2)).toHaveText('Scan to image');
    await expect(buttons.nth(3)).toHaveText('Scan to OCR');
  });

  test('file drawer lists the scans in /scans with download and file operation buttons', async ({ page }) => {
    await page.goto('/');
    await page.locator('#triggerFiles').click();
    const drawer = page.locator('#offcanvasFiles');
    await expect(drawer).toBeVisible();
    const entry = drawer.locator('.list-group-item', { hasText: SAMPLE_FILE.replace('.pdf', '') });
    await expect(entry).toBeVisible();
    await expect(entry.locator('a[href$="/download"]')).toHaveAttribute('href', `/api/file/${SAMPLE_FILE}/download`);
    // ALLOW_GUI_FILEOPERATIONS=true in the test container
    await expect(entry.locator('button.file-rename')).toBeVisible();
    await expect(entry.locator('button.file-delete')).toBeVisible();
  });

  test('delete asks for confirmation and can be cancelled', async ({ page }) => {
    await page.goto('/');
    await page.locator('#triggerFiles').click();
    const entry = page.locator('#offcanvasFiles .list-group-item', { hasText: SAMPLE_FILE.replace('.pdf', '') });
    await entry.locator('button.file-delete').click();
    await expect(entry.locator('.file-info-label-delete')).toBeVisible();
    await expect(entry.locator('.file-delete-confirm')).toBeVisible();
    await entry.locator('.file-delete-cancel').click();
    await expect(entry.locator('.file-info-label-delete')).toBeHidden();
    await expect(entry.locator('.file-buttons-default')).toBeVisible();
  });

  test('unknown page shows the error page, unknown API path answers JSON 404', async ({ page, request }) => {
    const res = await page.goto('/no/such/page');
    expect(res?.status()).toBe(404);
    await expect(page.locator('body')).toContainText('404');
    const api = await request.get('/api/no/such/thing');
    expect(api.status()).toBe(404);
    expect(await api.json()).toMatchObject({ code: 404 });
  });
});
