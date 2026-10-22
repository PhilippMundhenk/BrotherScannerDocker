import { expect, test } from '@playwright/test';
import { inContainer, listFiles, SAMPLE_FILE, scannerStatus } from '../helpers';

test.describe('API', () => {
  test('status reports the three booleans and is idle at rest', async ({ request }) => {
    const status = await scannerStatus(request);
    expect(status).toMatchObject({ scan: false, waiting: false, ocr: false });
    expect(status).toHaveProperty('reachable'); // true, false or null (check disabled or stale)
  });

  test('file list contains the seeded scan with parsed date and size', async ({ request }) => {
    const files = await listFiles(request);
    const sample = files.find((f) => f.file === SAMPLE_FILE);
    expect(sample).toBeDefined();
    expect(sample!.mimetype).toBe('application/pdf');
    expect(sample!.size).toBeGreaterThan(0);
    const info = await (await request.get(`/api/file/${SAMPLE_FILE}/info`)).json();
    expect(info.date_from_name).toBe('2026-01-02');
    expect(info.time_from_name).toBe('03:04:05');
    expect(info.extension).toBe('pdf');
  });

  test('download streams the PDF with a content-disposition header', async ({ request }) => {
    const res = await request.get(`/api/file/${SAMPLE_FILE}/download`);
    expect(res.status()).toBe(200);
    expect(res.headers()['content-type']).toContain('application/pdf');
    expect(res.headers()['content-disposition']).toContain(SAMPLE_FILE);
    const body = await res.body();
    expect(body.subarray(0, 5).toString()).toBe('%PDF-');
  });

  test('unknown files answer 404, path traversal never leaves /scans', async ({ request }) => {
    expect((await request.get('/api/file/does-not-exist.pdf/info')).status()).toBe(404);
    const traversal = await request.get('/api/file/..%2F..%2Fetc%2Fpasswd/download');
    expect([400, 404]).toContain(traversal.status());
    expect(await traversal.text()).not.toContain('root:');
    const encoded = await request.get('/api/file/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd/download');
    expect([400, 404]).toContain(encoded.status());
  });

  test('timezone of the container is used by the backend', async ({ request }) => {
    const tz = await (await request.get('/api/dev/timezone')).json();
    expect(tz.timezone).toBe('UTC');
  });

  test('rejects invalid scan targets', async ({ request }) => {
    const bad = await request.post('/api/scanner/scanto', { form: { target: 'rm -rf /' } });
    expect(bad.status()).toBe(400);
    expect(await bad.json()).toMatchObject({ code: 400 });
    const empty = await request.post('/api/scanner/scanto', { form: {} });
    expect(empty.status()).toBe(400);
  });

  test('rename with a date prefix keeps the modification time, delete removes the file', async ({ request }) => {
    // Work on a copy so the seeded sample stays available for the other specs.
    const copy = '2026-02-03-04-05-06.pdf';
    inContainer(['cp', '-p', `/scans/${SAMPLE_FILE}`, `/scans/${copy}`]);
    inContainer(['chmod', '666', `/scans/${copy}`]);
    const before = (await listFiles(request)).find((f) => f.file === copy)!;
    expect(before).toBeDefined();

    const rename = await request.put(`/api/file/${copy}/rename`, {
      data: { new_filename: 'Invoice Müller', new_filename_prefix: 'date' },
    });
    expect(rename.status()).toBe(200);

    // The prefix is the file's modification date (container runs in UTC), not the date in the old name.
    const datePrefix = new Date(before.fileModificationTime * 1000).toISOString().slice(0, 10);
    const renamedName = `${datePrefix} Invoice Müller.pdf`;
    const after = await listFiles(request);
    expect(after.some((f) => f.file === copy)).toBe(false);
    const renamed = after.find((f) => f.file === renamedName);
    expect(renamed, `expected ${renamedName} in ${after.map((f) => f.file).join(', ')}`).toBeDefined();
    expect(renamed!.fileModificationTime).toBe(before.fileModificationTime);

    const del = await request.delete(`/api/file/${encodeURIComponent(renamedName)}/delete`);
    expect(del.status()).toBe(200);
    expect((await listFiles(request)).some((f) => f.file === renamedName)).toBe(false);
  });

  test('rename rejects invalid names', async ({ request }) => {
    const res = await request.put(`/api/file/${SAMPLE_FILE}/rename`, {
      data: { new_filename: 'a/b', new_filename_prefix: 'none' },
    });
    expect(res.status()).toBe(400);
    expect((await listFiles(request)).some((f) => f.file === SAMPLE_FILE)).toBe(true);
  });
});

test.describe('device status (#188)', () => {
  test('answers quickly with reachable=false for the unreachable test device, then from the cache', async ({ request }) => {
    const started = Date.now();
    const res = await request.get('/api/scanner/device');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({ device_ip: '192.0.2.10', reachable: false, registered: null, model: null, cached: false });
    expect(Date.now() - started).toBeLessThan(10_000);
    const again = await (await request.get('/api/scanner/device')).json();
    expect(again.cached).toBe(true);
    expect(again.checked).toBe(body.checked);
  });

  test('DEVICE_STATUS=false turns the endpoint off', async ({ request }) => {
    try {
      const put = await request.put('/api/settings', { data: { DEVICE_STATUS: 'false' } });
      expect(put.status()).toBe(200);
      const res = await request.get('/api/scanner/device');
      expect(res.status()).toBe(404);
      expect((await res.json()).message).toContain('DEVICE_STATUS');
    } finally {
      await request.put('/api/settings', { data: { DEVICE_STATUS: '' } });
    }
    expect((await request.get('/api/scanner/device')).status()).toBe(200);
  });
});
