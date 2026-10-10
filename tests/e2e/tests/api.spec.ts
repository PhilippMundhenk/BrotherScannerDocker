import { expect, test } from '@playwright/test';
import { inContainer, listFiles, SAMPLE_FILE, scannerStatus } from '../helpers';

test.describe('API', () => {
  test('status reports the three booleans and is idle at rest', async ({ request }) => {
    const status = await scannerStatus(request);
    expect(status).toEqual({ scan: false, waiting: false, ocr: false });
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

  test('rejects path traversal and unknown files', async ({ request }) => {
    expect((await request.get('/api/file/..%2F..%2Fetc%2Fpasswd/info')).status()).toBe(400);
    expect((await request.get('/api/file/does-not-exist.pdf/info')).status()).toBe(404);
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
    const after = await listFiles(request);
    expect(after.some((f) => f.file === copy)).toBe(false);
    const renamed = after.find((f) => f.file === '2026-02-03 Invoice Müller.pdf');
    expect(renamed).toBeDefined();
    expect(renamed!.fileModificationTime).toBe(before.fileModificationTime);

    const del = await request.delete(`/api/file/${encodeURIComponent('2026-02-03 Invoice Müller.pdf')}/delete`);
    expect(del.status()).toBe(200);
    expect((await listFiles(request)).some((f) => f.file === '2026-02-03 Invoice Müller.pdf')).toBe(false);
  });

  test('rename rejects invalid names', async ({ request }) => {
    const res = await request.put(`/api/file/${SAMPLE_FILE}/rename`, {
      data: { new_filename: 'a/b', new_filename_prefix: 'none' },
    });
    expect(res.status()).toBe(400);
    expect((await listFiles(request)).some((f) => f.file === SAMPLE_FILE)).toBe(true);
  });
});
