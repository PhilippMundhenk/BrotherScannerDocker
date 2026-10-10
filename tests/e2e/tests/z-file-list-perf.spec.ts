import { expect, test } from '@playwright/test';
import { inContainer, listFiles, SAMPLE_FILE } from '../helpers';

// #110: with many scans the drawer stayed empty until the whole directory had
// been rendered. The list is now paginated newest first; the drawer shows the
// first batch at once and keeps loading in the background. This spec seeds
// SEED files, measures the latencies and prints them into the report.

const SEED = 1200;
const BATCH = 20;
const BUDGET_FIRST_BATCH_MS = 2_000; // drawer shows the first entries
const BUDGET_PAGE_API_MS = 1_000; // one API page
const BUDGET_FULL_API_MS = 5_000; // unpaginated API list (compatibility)
const BUDGET_COMPLETE_MS = 60_000; // drawer has loaded everything

function record(info: ReturnType<typeof test.info>, label: string, ms: number, budget: number) {
  const line = `${label}: ${ms.toFixed(0)} ms (budget ${budget} ms)`;
  console.log(line);
  info.annotations.push({ type: 'timing', description: line });
}

test.describe('file list with many files', () => {
  test.beforeAll(async () => {
    // Date-stamped names like the pipeline produces, modification times one hour apart.
    inContainer(['bash', '-c', `
      for i in $(seq 1 ${SEED}); do
        d=$(date -u -d "2024-01-01 +$i hours" +%Y-%m-%d-%H-%M-%S)
        cp /scans/${SAMPLE_FILE} "/scans/seed-$d.pdf"
        touch -d "2024-01-01 +$i hours" "/scans/seed-$d.pdf"
      done`]);
    expect(Number(inContainer(['bash', '-c', 'ls /scans/seed-*.pdf | wc -l']))).toBe(SEED);
  });

  test.afterAll(async () => {
    inContainer(['bash', '-c', 'rm -f /scans/seed-*.pdf']);
  });

  test('API pages are newest first, carry the total, and answer fast', async ({ request }) => {
    const t0 = performance.now();
    const res = await request.get(`/api/file-list?limit=${BATCH}`);
    const pageMs = performance.now() - t0;
    expect(res.status()).toBe(200);
    const page = await res.json();
    expect(page).toHaveLength(BATCH);
    expect(Number(res.headers()['x-total-count'])).toBeGreaterThanOrEqual(SEED + 1);
    for (let i = 1; i < page.length; i++) {
      expect(page[i - 1].fileModificationTime).toBeGreaterThanOrEqual(page[i].fileModificationTime);
    }
    record(test.info(), `GET /api/file-list?limit=${BATCH}`, pageMs, BUDGET_PAGE_API_MS);
    expect(pageMs).toBeLessThan(BUDGET_PAGE_API_MS);

    const second = await (await request.get(`/api/file-list?offset=${BATCH}&limit=${BATCH}`)).json();
    expect(second).toHaveLength(BATCH);
    expect(second[0].file).not.toBe(page[0].file);
    expect(page[page.length - 1].fileModificationTime).toBeGreaterThanOrEqual(second[0].fileModificationTime);

    const beyond = await (await request.get(`/api/file-list?offset=${SEED + 1000}&limit=${BATCH}`)).json();
    expect(beyond).toEqual([]);
  });

  test('the unpaginated API list still returns everything', async ({ request }) => {
    const t0 = performance.now();
    const all = await listFiles(request);
    const fullMs = performance.now() - t0;
    expect(all.length).toBeGreaterThanOrEqual(SEED + 1);
    record(test.info(), 'GET /api/file-list (all)', fullMs, BUDGET_FULL_API_MS);
    expect(fullMs).toBeLessThan(BUDGET_FULL_API_MS);
  });

  test('the drawer shows the newest entries first and keeps loading in the background', async ({ page }) => {
    await page.goto('/');
    const head = await page.request.get('/api/file-list?limit=1');
    const newest = (await head.json())[0];
    const total = Number(head.headers()['x-total-count']);
    expect(total).toBeGreaterThanOrEqual(SEED + 1);

    // Count the batch requests the drawer makes, to prove it loads incrementally.
    const batchRequests: string[] = [];
    page.on('request', (req) => {
      if (req.url().includes('/list-files')) batchRequests.push(req.url());
    });

    const t0 = performance.now();
    await page.locator('#triggerFiles').click();
    const items = page.locator('#fileslist-items .list-group-item');
    // The first batch is on screen long before the list is complete (locally
    // all batches arrive within a second, so "at least" rather than "exactly").
    await expect.poll(() => items.count(), { timeout: BUDGET_FIRST_BATCH_MS + 1000 }).toBeGreaterThanOrEqual(BATCH);
    const firstBatchMs = performance.now() - t0;
    record(test.info(), `drawer shows first ${BATCH} entries`, firstBatchMs, BUDGET_FIRST_BATCH_MS);
    expect(firstBatchMs).toBeLessThan(BUDGET_FIRST_BATCH_MS);

    await expect(items.first().locator('.file-name')).toHaveText(newest.name);

    await expect(items).toHaveCount(total, { timeout: BUDGET_COMPLETE_MS });
    const completeMs = performance.now() - t0;
    record(test.info(), `drawer complete with ${total} entries`, completeMs, BUDGET_COMPLETE_MS);
    await expect(page.locator('#fileslist-loading')).toBeHidden();
    expect(batchRequests.length).toBe(Math.ceil(total / BATCH));
    expect(batchRequests[0]).toContain(`offset=0&limit=${BATCH}`);
    expect(batchRequests[1]).toContain(`offset=${BATCH}&limit=${BATCH}&fragment=1`);

    // Reopening restarts the load cleanly (no duplicates from a cancelled run).
    await page.locator('#offcanvasFiles .btn-close').click();
    await page.locator('#triggerFiles').click();
    await expect(items).toHaveCount(total, { timeout: BUDGET_COMPLETE_MS });
    const ids = await items.evaluateAll((nodes) => nodes.map((n) => n.id));
    expect(new Set(ids).size).toBe(ids.length);
  });
});
