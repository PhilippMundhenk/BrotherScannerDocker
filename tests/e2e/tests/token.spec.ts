import { expect, test } from '@playwright/test';
import * as path from 'path';
import { docker, FIXTURES, IMAGE } from '../helpers';

// #101: API_TOKEN protects everything that starts a scan or changes a file.
// This spec runs its own short-lived container with a token, next to the
// main one from global-setup (which has none).

const TOKEN = 'e2e-secret-token';
const PORT = Number(process.env.E2E_TOKEN_PORT || 18090);
const NAME = `bsd-e2e-token-${process.pid}`;

test.describe('API token', () => {
  test.beforeAll(async () => {
    docker([
      'run', '-d', '--name', NAME, '-p', `${PORT}:8080`,
      '-v', `${path.join(FIXTURES, 'scanimage')}:/usr/bin/scanimage:ro`,
      '-e', 'WEBSERVER=true', '-e', 'PORT=8080', '-e', 'IPADDRESS=192.0.2.10', '-e', 'KEEPALIVE=false',
      '-e', 'SCANNER_PING_INTERVAL=0', '-e', 'REAR_PAGE_WAIT_SECONDS=3', '-e', 'ALLOW_GUI_FILEOPERATIONS=true', '-e', 'ALLOW_GUI_SETTINGS=true',
      '-e', `API_TOKEN=${TOKEN}`, '-e', 'RESOLUTION=100',
      IMAGE,
    ]);
    const deadline = Date.now() + 90_000;
    while (Date.now() < deadline) {
      try {
        if ((await fetch(`http://localhost:${PORT}/api/scanner/status`)).ok) return;
      } catch {
        /* not up yet */
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    throw new Error(`token container not reachable:\n${docker(['logs', NAME])}`);
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

  test('read-only endpoints stay open, triggers need the token', async ({ playwright }) => {
    const api = await playwright.request.newContext({ baseURL: `http://localhost:${PORT}` });
    expect((await api.get('/api/scanner/status')).status()).toBe(200);
    expect((await api.get('/api/jobs')).status()).toBe(200);
    expect((await api.get('/api/file-list')).status()).toBe(200);
    expect((await api.get('/api/actions')).json().then((b) => b.authentication)).resolves.toContain('token required');

    const noToken = await api.post('/api/scanner/scanto', { form: { target: 'file' } });
    expect(noToken.status()).toBe(401);
    expect((await api.post('/api/scanner/scanto', { form: { target: 'file' }, headers: { 'X-API-Token': 'wrong' } })).status()).toBe(401);
    expect((await api.get('/api/scanner/scanto/file')).status()).toBe(401);
    expect((await api.delete('/api/file/x.pdf/delete')).status()).toBe(401);

    const bearer = await api.post('/api/scanner/scanto', { form: { target: 'file' }, headers: { Authorization: `Bearer ${TOKEN}` } });
    expect(bearer.status()).toBe(200);
    const header = await api.post('/api/scanner/scanto', { form: { target: 'file' }, headers: { 'X-API-Token': TOKEN } });
    expect(header.status()).toBe(200);
    const field = await api.post('/api/scanner/scanto', { form: { target: 'file', token: TOKEN } });
    expect(field.status()).toBe(200);
    await api.dispose();
  });

  test('the settings page carries the token, and the token may come as a query field', async ({ playwright }) => {
    const api = await playwright.request.newContext({ baseURL: `http://localhost:${PORT}` });
    const page = await api.get('/settings');
    expect(page.status()).toBe(200);
    expect(await page.text()).toContain(`<meta name="api-token" content="${TOKEN}">`);
    expect((await api.put('/api/settings', { data: { SCAN_MODE: 'True Gray' } })).status()).toBe(401);
    expect((await api.put('/api/settings?token=' + TOKEN, { data: { SCAN_MODE: 'True Gray' } })).status()).toBe(200);
    expect((await api.put('/api/settings?token=' + TOKEN, { data: { SCAN_MODE: '' } })).status()).toBe(200);
    await api.dispose();
  });

  test('the web UI carries the token and can still trigger scans', async ({ browser }) => {
    const page = await browser.newPage({ baseURL: `http://localhost:${PORT}` });
    await page.goto('/');
    await expect(page.locator('meta[name="api-token"]')).toHaveAttribute('content', TOKEN);
    const scanRequest = page.waitForResponse((r) => r.url().includes('/api/scanner/scanto') && r.request().method() === 'POST');
    await page.locator('a.trigger-scan[data-trigger="file"]').click();
    const response = await scanRequest;
    expect(response.status()).toBe(200);
    expect(response.request().headers()['x-api-token']).toBe(TOKEN);
    await page.close();
  });
});
