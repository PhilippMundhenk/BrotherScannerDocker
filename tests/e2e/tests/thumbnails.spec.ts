import { expect, test } from '@playwright/test';
import { inContainer, SAMPLE_FILE } from '../helpers';

// #130: thumbnails of the first page in the file list, rendered once and
// cached, lazily loaded with a bounded number of live images.

const SEED = 300;
const THUMB_KEEP = 40;

test.describe('thumbnails', () => {
  test('endpoint renders once, then serves from cache with ETag and 304', async ({ request }) => {
    inContainer(['bash', '-c', 'rm -f /scans/.thumbnails/*']);
    const first = await request.get(`/api/file/${SAMPLE_FILE}/thumbnail`);
    expect(first.status()).toBe(200);
    expect(first.headers()['content-type']).toBe('image/jpeg');
    expect(first.headers()['x-thumbnail-cache']).toBe('miss');
    expect(first.headers()['cache-control']).toContain('immutable');
    const etag = first.headers()['etag'];
    expect(etag).toMatch(/^"[0-9a-f]{32}"$/);
    expect((await first.body()).subarray(0, 3)).toEqual(Buffer.from([0xff, 0xd8, 0xff]));

    const second = await request.get(`/api/file/${SAMPLE_FILE}/thumbnail`);
    expect(second.headers()['x-thumbnail-cache']).toBe('hit');
    const cached = await request.get(`/api/file/${SAMPLE_FILE}/thumbnail`, { headers: { 'If-None-Match': etag } });
    expect(cached.status()).toBe(304);
    expect(inContainer(['bash', '-c', 'ls /scans/.thumbnails | wc -l']).trim()).toBe('1');
  });

  test('unknown files answer 404, unreadable PDFs get a placeholder', async ({ request }) => {
    expect((await request.get('/api/file/nope.pdf/thumbnail')).status()).toBe(404);
    inContainer(['bash', '-c', 'printf "%%PDF-1.4 broken" > /scans/2026-03-03-03-03-03.pdf; chmod 666 /scans/2026-03-03-03-03-03.pdf']);
    try {
      const res = await request.get('/api/file/2026-03-03-03-03-03.pdf/thumbnail');
      expect(res.status()).toBe(200);
      expect(res.headers()['content-type']).toContain('image/svg+xml');
      expect(res.headers()['x-thumbnail-cache']).toBe('placeholder');
    } finally {
      inContainer(['rm', '-f', '/scans/2026-03-03-03-03-03.pdf']);
    }
  });

  test('rename and delete drop the cached thumbnail', async ({ request }) => {
    const copy = '2026-04-04-04-04-04.pdf';
    inContainer(['cp', '-p', `/scans/${SAMPLE_FILE}`, `/scans/${copy}`]);
    inContainer(['chmod', '666', `/scans/${copy}`]);
    await request.get(`/api/file/${copy}/thumbnail`);
    expect(inContainer(['bash', '-c', `ls /scans/.thumbnails/${copy}.*.jpg | wc -l`]).trim()).toBe('1');
    const rename = await request.put(`/api/file/${copy}/rename`, { data: { new_filename: 'Thumb test', new_filename_prefix: 'none' } });
    expect(rename.status()).toBe(200);
    expect(inContainer(['bash', '-c', `ls /scans/.thumbnails/${copy}.*.jpg 2>/dev/null | wc -l`]).trim()).toBe('0');
    await request.get('/api/file/Thumb%20test.pdf/thumbnail');
    expect(inContainer(['bash', '-c', 'ls "/scans/.thumbnails/Thumb test.pdf."*.jpg | wc -l']).trim()).toBe('1');
    expect((await request.delete('/api/file/Thumb%20test.pdf/delete')).status()).toBe(200);
    expect(inContainer(['bash', '-c', 'ls "/scans/.thumbnails/Thumb test.pdf."*.jpg 2>/dev/null | wc -l']).trim()).toBe('0');
  });

  test('the drawer shows thumbnails for the visible entries', async ({ page }) => {
    await page.goto('/');
    await page.locator('#triggerFiles').click();
    const entry = page.locator('#offcanvasFiles .list-group-item', { hasText: SAMPLE_FILE.replace('.pdf', '') });
    const img = entry.locator('img.thumb');
    await expect(img).toHaveAttribute('data-src', new RegExp(`/api/file/${SAMPLE_FILE}/thumbnail\\?v=\\d+`));
    await expect.poll(async () => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0), { timeout: 15_000 }).toBe(true);
  });

  test('with many files only the thumbnails near the viewport are loaded and few stay in memory', async ({ page }) => {
    inContainer(['bash', '-c', `for i in $(seq 1 ${SEED}); do d=$(date -u -d "2023-01-01 +$i hours" +%Y-%m-%d-%H-%M-%S); cp /scans/${SAMPLE_FILE} "/scans/thumbseed-$d.pdf"; touch -d "2023-01-01 +$i hours" "/scans/thumbseed-$d.pdf"; done`]);
    try {
      const requests: string[] = [];
      page.on('request', (req) => {
        if (req.url().includes('/thumbnail')) requests.push(req.url());
      });
      await page.goto('/');
      await page.locator('#triggerFiles').click();
      const items = page.locator('#fileslist-items .list-group-item');
      await expect.poll(() => items.count(), { timeout: 60_000 }).toBeGreaterThanOrEqual(SEED);
      const afterLoad = requests.length;
      expect(afterLoad).toBeLessThan(80);  // only the first screens, not all 300

      // Scroll through the whole drawer in steps.
      const body = page.locator('#offcanvasFiles .offcanvas-body');
      for (let step = 0; step < 12; step++) {
        await body.evaluate((el, s) => { el.scrollTop = Math.round((el.scrollHeight - el.clientHeight) * (s / 11)); }, step);
        await page.waitForTimeout(250);
      }
      const live = await page.locator('img.thumb').evaluateAll((imgs) => imgs.filter((i) => i.getAttribute('src')).length);
      console.log(`thumbnail requests after scrolling: ${requests.length}, images kept alive: ${live}`);
      test.info().annotations.push({ type: 'timing', description: `thumbnail requests: ${requests.length}, live images: ${live}` });
      expect(live).toBeLessThanOrEqual(THUMB_KEEP + 20);
      expect(requests.length).toBeLessThan(SEED);
    } finally {
      inContainer(['bash', '-c', 'rm -f /scans/thumbseed-*.pdf /scans/.thumbnails/thumbseed-*']);
    }
  });

  test('GUI_THUMBNAILS=false hides the thumbnails and the endpoint', async ({ page, request }) => {
    await request.put('/api/settings', { data: { GUI_THUMBNAILS: 'false' } });
    try {
      await page.goto('/');
      await page.locator('#triggerFiles').click();
      await expect(page.locator('#offcanvasFiles .list-group-item').first()).toBeVisible();
      expect(await page.locator('img.thumb').count()).toBe(0);
      expect((await request.get(`/api/file/${SAMPLE_FILE}/thumbnail`)).status()).toBe(404);
    } finally {
      await request.put('/api/settings', { data: { GUI_THUMBNAILS: '' } });
    }
  });
});
