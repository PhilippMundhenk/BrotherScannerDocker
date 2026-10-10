import { expect, test } from '@playwright/test';
import * as path from 'path';
import { docker, FIXTURES, IMAGE, SAMPLE_FILE } from '../helpers';

// A container with the optional features switched off: no file operations,
// no settings page, no thumbnails, one action disabled and one renamed. The
// main container (global-setup) has everything on, so these branches only
// run here. Like token.spec this starts its own short-lived container.

const PORT = Number(process.env.E2E_RESTRICTED_PORT || 18091);
const NAME = `bsd-e2e-restricted-${process.pid}`;

test.describe('restricted configuration', () => {
  test.beforeAll(async () => {
    docker([
      'run', '-d', '--name', NAME, '-p', `${PORT}:8080`,
      '-v', `${path.join(FIXTURES, 'scanimage')}:/usr/bin/scanimage:ro`,
      '-e', 'WEBSERVER=true', '-e', 'PORT=8080', '-e', 'IPADDRESS=192.0.2.10', '-e', 'KEEPALIVE=false',
      '-e', 'SCANNER_PING_INTERVAL=0', '-e', 'RESOLUTION=100',
      '-e', 'GUI_THUMBNAILS=false', '-e', 'DISABLE_GUI_SCANTOIMAGE=true', '-e', 'RENAME_GUI_SCANTOFILE=Archive',
      '-e', 'RENAME_GUI_SCANTOEMAIL=Backside', '-e', 'RENAME_GUI_SCANTOIMAGE=Picture', '-e', 'RENAME_GUI_SCANTOOCR=Text',
      // explicit false values used to be truthy strings in config.php (#126)
      '-e', 'DISABLE_GUI_SCANTOOCR=false', '-e', 'ALLOW_GUI_FILEOPERATIONS=false', '-e', 'ALLOW_GUI_SETTINGS=false',
      IMAGE,
    ]);
    const deadline = Date.now() + 90_000;
    let up = false;
    while (Date.now() < deadline && !up) {
      try {
        up = (await fetch(`http://localhost:${PORT}/api/scanner/status`)).ok;
      } catch {
        /* not up yet */
      }
      if (!up) await new Promise((r) => setTimeout(r, 1000));
    }
    if (!up) throw new Error(`restricted container not reachable:\n${docker(['logs', NAME])}`);
    // before the sample file arrives the list is empty
    const empty = await (await fetch(`http://localhost:${PORT}/list-files`)).text();
    if (!empty.includes('No scans yet')) throw new Error('empty list page does not say "No scans yet"');
    docker(['cp', path.join(FIXTURES, 'sample.pdf'), `${NAME}:/scans/${SAMPLE_FILE}`]);
    docker(['exec', NAME, 'chmod', '666', `/scans/${SAMPLE_FILE}`]);
  });

  test.afterAll(async () => {
    if (process.env.PHP_COVERAGE_DIR) {
      try {
        docker(['cp', `${NAME}:/var/www/coverage/.`, process.env.PHP_COVERAGE_DIR]);
      } catch {
        /* no coverage image */
      }
    }
    try {
      docker(['rm', '-f', NAME]);
    } catch {
      /* already gone */
    }
  });

  test('actions carry the labels and disabled flags', async ({ playwright }) => {
    const api = await playwright.request.newContext({ baseURL: `http://localhost:${PORT}` });
    const actions = (await (await api.get('/api/actions')).json()).actions as { target: string; label: string; enabled: boolean }[];
    expect(actions.find((a) => a.target === 'file')?.label).toBe('Archive');
    expect(actions.map((a) => a.label)).toEqual(['Archive', 'Backside', 'Text', 'Picture']);
    expect(actions.find((a) => a.target === 'image')?.enabled).toBe(false);
    expect(actions.find((a) => a.target === 'ocr')?.enabled).toBe(true);
    await api.dispose();
  });

  test('file operations, settings and thumbnails are off', async ({ playwright }) => {
    const api = await playwright.request.newContext({ baseURL: `http://localhost:${PORT}` });
    expect((await api.delete(`/api/file/${SAMPLE_FILE}/delete`)).status()).toBe(403);
    expect((await api.put(`/api/file/${SAMPLE_FILE}/rename`, { data: { new_filename: 'Renamed', new_filename_prefix: 'none' } })).status()).toBe(403);
    expect((await api.get(`/api/file/${SAMPLE_FILE}/thumbnail`)).status()).toBe(404);
    expect((await api.get('/api/settings')).status()).toBe(403);
    expect((await api.put('/api/settings', { data: { SCAN_MODE: 'x' } })).status()).toBe(403);
    expect((await api.get('/settings')).status()).toBe(403);
    const info = await api.get(`/api/file/${SAMPLE_FILE}/info`);
    expect(info.status()).toBe(200);
    await api.dispose();
  });

  test('the page reflects the configuration', async ({ page }) => {
    await page.goto(`http://localhost:${PORT}/`, { waitUntil: 'networkidle' });
    await expect(page.locator('a.trigger-scan[data-trigger="file"]')).toHaveText('Archive');
    await expect(page.locator('a.trigger-scan[data-trigger="image"]')).toHaveCount(0);
    await expect(page.locator('a.trigger-scan[data-trigger="ocr"]')).toHaveCount(1);
    await page.locator('#triggerFiles').click();
    const entry = page.locator('#offcanvasFiles .list-group-item', { hasText: SAMPLE_FILE.replace('.pdf', '') });
    await expect(entry).toBeVisible({ timeout: 30_000 });
    await expect(entry.locator('img.thumb')).toHaveCount(0);
    await expect(entry.locator('button.file-delete')).toHaveCount(0);
  });
});
