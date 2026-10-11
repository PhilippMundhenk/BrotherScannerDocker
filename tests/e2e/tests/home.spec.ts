import { expect, test } from '@playwright/test';
import { inContainer, SAMPLE_FILE } from '../helpers';

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
    // scripts and styles carry a version that changes with every image build (#144)
    await expect(page.locator('script[src^="/assets/scripts.js?v="]')).toHaveAttribute('src', /\?v=\d+$/);
    await expect(page.locator('link[href^="/assets/style.css?v="]')).toHaveAttribute('href', /\?v=\d+$/);
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

test.describe('scan options', () => {
  test('resolution, mode and source come from the device, are remembered and sent with the scan', async ({ page, request }) => {
    await page.goto('/');
    const options = page.locator('#scan-options');
    await expect(options).toBeVisible();
    const resolution = page.locator('select[data-option="resolution"]');
    const mode = page.locator('select[data-option="mode"]');
    const source = page.locator('select[data-option="source"]');
    // the simulator lists 100..600 dpi with 300 as device default; the container runs with RESOLUTION=100
    await expect(resolution.locator('option').first()).toHaveText('Default (100 dpi)');
    await expect(page.locator('label[for="scan-resolution"]')).toHaveText('Resolution');
    await expect(resolution.locator('option')).toHaveCount(7);
    await expect(mode.locator('option')).toHaveText(['Default (24bit Color[Fast])', 'Black & White', 'Gray[Error Diffusion]', 'True Gray', '24bit Color[Fast]']);
    await expect(source.locator('option')).toHaveCount(4);

    await resolution.selectOption('200');
    await mode.selectOption('True Gray');
    await page.reload();
    await expect(page.locator('select[data-option="resolution"]')).toHaveValue('200');
    await expect(page.locator('select[data-option="mode"]')).toHaveValue('True Gray');
    await expect(page.locator('select[data-option="source"]')).toHaveValue('');

    const trigger = page.waitForResponse((res) => res.url().endsWith('/api/scanner/scanto') && res.request().method() === 'POST');
    await page.locator('a.trigger-scan[data-trigger="file"]').click();
    const response = await trigger;
    const body = new URLSearchParams(response.request().postData() || '');
    const job = await response.json();
    expect(body.get('target')).toBe('file');
    expect(body.get('resolution')).toBe('200');
    expect(body.get('mode')).toBe('True Gray');
    expect(body.has('source')).toBe(false);
    await expect.poll(async () => (await (await request.get(`/api/jobs/${job.job}`)).json()).state, { timeout: 60_000 }).toBe('done');
    expect(inContainer(['cat', '/var/log/scanner.log'])).toContain(`as job ${job.job} with --resolution '200' --mode 'True Gray'`);

    // back to the defaults for the other specs
    await page.locator('select[data-option="resolution"]').selectOption('');
    await page.locator('select[data-option="mode"]').selectOption('');
  });
});
