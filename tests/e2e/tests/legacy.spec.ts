import { expect, test } from '@playwright/test';

// #148: the endpoints of the web UI before the rewrite keep answering so that
// existing automations (rest sensors, control panels) survive the upgrade.

test.describe('legacy endpoints', () => {
  test('active.php answers like the status endpoint', async ({ request }) => {
    const res = await request.get('/active.php');
    expect(res.status()).toBe(200);
    expect(res.headers()['content-type']).toContain('application/json');
    const body = await res.json();
    expect(body).toHaveProperty('scan');
    expect(body).toHaveProperty('waiting');
    const status = await (await request.get('/api/scanner/status')).json();
    expect(Object.keys(body).sort()).toEqual(Object.keys(status).sort());
  });

  test('scan.php triggers like the GET trigger, with the old upper-case OCR target', async ({ request }) => {
    expect((await request.get('/scan.php')).status()).toBe(400);
    expect((await request.get('/scan.php?target=nope')).status()).toBe(400);
    const res = await request.get('/scan.php?target=OCR');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.target).toBe('ocr');
    expect(body.job).toMatch(/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$/);
    await expect.poll(async () => (await (await request.get(`/api/jobs/${body.job}`)).json()).state, { timeout: 60_000 }).toBe('done');
  });
});
