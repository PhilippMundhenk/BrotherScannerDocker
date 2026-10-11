import { expect, test } from '@playwright/test';
import { inContainer, listFiles, scannerStatus, triggerScan, waitFor, waitForNewFile, waitForQueueIdle } from '../helpers';

// #124: settings from a configuration file on the volume, editable through
// the settings page and the settings API. The e2e container runs with
// ALLOW_GUI_SETTINGS=true and RESOLUTION=100 in its environment.

const CONFIG = '/scans/.config/scanner.conf';

test.describe('settings page and API', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
    await waitForQueueIdle(60_000);
  });

  test.afterEach(async ({ request }) => {
    // Back to a clean file: remove everything this spec may have written.
    await request.put('/api/settings', { data: { SCAN_MODE: '', REMOVE_BLANK_THRESHOLD: '', RENAME_GUI_SCANTOFILE: '', KEEPALIVE_INTERVAL: '', FTP_PASSWORD: '' } });
  });

  test('GET lists every setting with source and lock state', async ({ request }) => {
    const res = await request.get('/api/settings');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.config_file).toBe(CONFIG);
    const byKey: Record<string, any> = {};
    for (const s of body.settings) byKey[s.key] = s;
    expect(byKey.RESOLUTION).toMatchObject({ value: '100', source: 'environment', locked: true, type: 'int' });
    expect(byKey.REMOVE_BLANK_THRESHOLD).toMatchObject({ value: '0.3', source: 'default', locked: false, type: 'float' });
    expect(byKey.NAME).toMatchObject({ restart: true });
    expect(byKey.FTP_PASSWORD).toMatchObject({ type: 'secret', value: '', is_set: true }); // delivered as a secret file
    expect(byKey.API_TOKEN).toMatchObject({ type: 'secret', is_set: false });
    expect(Object.keys(byKey).length).toBeGreaterThan(40);
  });

  test('PUT writes the file, applies to the next scan, and refuses environment-set keys', async ({ request }) => {
    const put = await request.put('/api/settings', { data: { SCAN_MODE: 'True Gray', REMOVE_BLANK_THRESHOLD: '0.5', KEEPALIVE_INTERVAL: '200' } });
    expect(put.status()).toBe(200);
    const result = await put.json();
    expect(result.saved.sort()).toEqual(['KEEPALIVE_INTERVAL', 'REMOVE_BLANK_THRESHOLD', 'SCAN_MODE']);
    expect(result.restart_required).toEqual(['KEEPALIVE_INTERVAL']);

    const file = inContainer(['cat', CONFIG]);
    expect(file).toContain('SCAN_MODE=True Gray');
    expect(file).toContain('REMOVE_BLANK_THRESHOLD=0.5');
    expect(inContainer(['stat', '-c', '%U', CONFIG])).toBe('www-data');

    const after = await (await request.get('/api/settings')).json();
    const mode = after.settings.find((s: any) => s.key === 'SCAN_MODE');
    expect(mode).toMatchObject({ value: 'True Gray', source: 'file' });

    // The scan scripts read the file per job: the next scan uses the new mode without a restart.
    const before = (await listFiles(request)).map((f) => f.file);
    await triggerScan(request, 'file');
    await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
    expect(inContainer(['cat', '/var/log/scanner.log'])).toContain("'--mode=True Gray', '--resolution=100'");

    const locked = await request.put('/api/settings', { data: { RESOLUTION: '200' } });
    expect(locked.status()).toBe(400);
    expect((await locked.json()).errors.RESOLUTION).toContain('environment');

    const invalid = await request.put('/api/settings', { data: { REMOVE_BLANK_THRESHOLD: 'lots', USE_JPEG_COMPRESSION: 'maybe', NOPE: '1' } });
    expect(invalid.status()).toBe(400);
    const errors = (await invalid.json()).errors;
    expect(errors.REMOVE_BLANK_THRESHOLD).toContain('number');
    expect(errors.USE_JPEG_COMPRESSION).toContain('true or false');
    expect(errors.NOPE).toContain('unknown');
    expect(inContainer(['cat', CONFIG])).not.toContain('lots');

    // An empty value removes the key again.
    const removed = await (await request.put('/api/settings', { data: { SCAN_MODE: '' } })).json();
    expect(removed.removed).toEqual(['SCAN_MODE']);
    expect(inContainer(['cat', CONFIG])).not.toContain('SCAN_MODE');
  });

  test('the settings page edits the file and marks sources and restarts', async ({ page, request }) => {
    await page.goto('/');
    await page.locator('#openSettings').click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.locator('h1')).toHaveText('Settings');

    const resolution = page.locator('#setting-RESOLUTION');
    await expect(resolution).toBeDisabled();
    await expect(page.locator('#row-RESOLUTION .badge', { hasText: 'environment' })).toBeVisible();
    await expect(page.locator('#row-NAME .badge', { hasText: 'restart' })).toBeVisible();

    await page.locator('#setting-RENAME_GUI_SCANTOFILE').fill('Scan front pages');
    await page.locator('#setting-REMOVE_BLANK_THRESHOLD').fill('0.7');
    await page.locator('#settings-save').click();
    await expect(page.locator('#settings-result')).toContainText('Saved: REMOVE_BLANK_THRESHOLD, RENAME_GUI_SCANTOFILE');
    await expect(page.locator('#row-RENAME_GUI_SCANTOFILE .source-badge')).toHaveText('file');

    // The web UI reads the file on every request: the home page shows the new label.
    await page.goto('/');
    await expect(page.locator('a.trigger-scan[data-trigger="file"]')).toHaveText('Scan front pages');
    const actions = await (await request.get('/api/actions')).json();
    expect(actions.actions[0].label).toBe('Scan front pages');

    // Validation errors show inline.
    await page.goto('/settings');
    await page.locator('#setting-REMOVE_BLANK_THRESHOLD').fill('abc');
    await page.locator('#settings-save').click();
    await expect(page.locator('#setting-REMOVE_BLANK_THRESHOLD')).toHaveClass(/is-invalid/);
    await expect(page.locator('#row-REMOVE_BLANK_THRESHOLD .setting-error')).toContainText('number');

    // A restart-required change is announced.
    await page.locator('#setting-REMOVE_BLANK_THRESHOLD').fill('0.3');
    await page.locator('#setting-KEEPALIVE_INTERVAL').fill('180');
    await page.locator('#settings-save').click();
    await expect(page.locator('#settings-result')).toContainText('Restart the container for: KEEPALIVE_INTERVAL');
  });

  test('secrets are masked and only sent when typed', async ({ page, request }) => {
    await page.goto('/settings');
    const password = page.locator('#setting-FTP_PASSWORD');
    await expect(password).toHaveAttribute('type', 'password');
    await expect(password).toHaveAttribute('placeholder', /set, leave empty to keep/);
    const body = await (await request.get('/api/settings')).json();
    const secret = body.settings.find((s: any) => s.key === 'FTP_PASSWORD');
    expect(secret.value).toBe('');
    expect(JSON.stringify(body)).not.toContain('e2e-secret-password');
  });

  test('the environment values can be copied into the file; the environment still wins', async ({ page, request }) => {
    // the e2e container sets RESOLUTION=100 and ALLOW_GUI_FILEOPERATIONS=true in its environment
    inContainer(['bash', '-c', `cp ${CONFIG} ${CONFIG}.bak 2>/dev/null || true`]);
    try {
      const res = await request.post('/api/settings/import-environment');
      expect(res.status()).toBe(200);
      const body = await res.json();
      expect(body.written).toContain('RESOLUTION');
      expect(body.environment).toContain('ALLOW_GUI_FILEOPERATIONS');
      expect(body.message).toContain('still wins');
      const file = inContainer(['cat', CONFIG]);
      expect(file).toContain('RESOLUTION=100');
      expect(file).toContain('ALLOW_GUI_FILEOPERATIONS=true');
      // the environment keeps precedence: still locked, still reported as environment
      const resolution = (await (await request.get('/api/settings')).json()).settings.find((s: any) => s.key === 'RESOLUTION');
      expect(resolution.source).toBe('environment');
      expect(resolution.locked).toBe(true);
      // a second copy writes nothing new
      const again = await (await request.post('/api/settings/import-environment')).json();
      expect(again.written).toEqual([]);
      expect(again.unchanged).toContain('RESOLUTION');

      // the page: confirmation dialog, then the result names the keys to remove from compose
      page.on('dialog', (dialog) => dialog.accept());
      await page.goto('/settings');
      await page.locator('#import-environment').click();
      await expect(page.locator('#import-result')).toContainText('remove from the compose file and restart');
      await expect(page.locator('#import-result')).toContainText('RESOLUTION');
    } finally {
      inContainer(['bash', '-c', `if [ -f ${CONFIG}.bak ]; then mv ${CONFIG}.bak ${CONFIG}; else rm -f ${CONFIG}; fi`]);
    }
  });
});
