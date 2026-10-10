import { expect, test } from '@playwright/test';
import {
  inContainer,
  listFiles,
  ownerOf,
  pdfPageCount,
  queueContents,
  scannerStatus,
  triggerScan,
  waitFor,
  waitForNewFile,
  waitForQueueIdle,
} from '../helpers';

// Each scan with the simulator takes about 1 s; the front scan then waits
// REAR_PAGE_WAIT_SECONDS (6 s in the test container) for rear pages before
// converting. OCR goes through the queue worker and the fake OCR service.

test.describe('scan pipeline (simulated scanner)', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
    // The previous test's OCR copy may still be in flight; the status flag
    // does not cover the queue's poll and backoff gaps, so wait for the queue.
    await waitForQueueIdle(60_000);
  });

  test('scan to file via the API produces a 2 page PDF owned by the scanner user, then an OCR copy', async ({ request }) => {
    const before = (await listFiles(request)).map((f) => f.file);
    expect(await triggerScan(request, 'file')).toMatchObject({ message: 'Scan triggered', target: 'file' });

    await expect.poll(async () => (await scannerStatus(request)).waiting, { timeout: 30_000 }).toBe(true);

    const scanned = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
    expect(scanned).toMatch(/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.pdf$/);
    expect(pdfPageCount(scanned)).toBe(2);
    expect(ownerOf(scanned)).toBe('Scanner');
    // #108: API-triggered scans are attributed in the log; a scan without such a line came from the device
    expect(inContainer(['cat', '/var/log/scanner.log'])).toContain('[API] scan to file triggered via API (return)');

    const ocrName = scanned.replace('.pdf', '-ocr.pdf');
    await waitFor(async () => (await listFiles(request)).some((f) => f.file === ocrName), 60_000, `OCR output ${ocrName}`);
    expect(ownerOf(ocrName)).toBe('Scanner');
    await waitFor(async () => {
      const q = queueContents();
      return q.pending.length === 0 && q.in_progress.length === 0;
    }, 30_000, 'OCR queue to drain');
    expect(queueContents().failed).toEqual([]);

    await expect.poll(async () => (await scannerStatus(request)).waiting, { timeout: 30_000 }).toBe(false);
  });

  test('front scan followed by a rear scan is merged into one 4 page PDF', async ({ request }) => {
    const before = (await listFiles(request)).map((f) => f.file);
    await triggerScan(request, 'file');
    await expect.poll(async () => (await scannerStatus(request)).waiting, { timeout: 30_000 }).toBe(true);

    // The rear scan must arrive while the front job is still waiting.
    await triggerScan(request, 'email');
    const merged = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
    expect(pdfPageCount(merged)).toBe(4);

    // #37: the UI must not keep showing 'waiting for rear pages' after the rear scan.
    await expect.poll(async () => (await scannerStatus(request)).waiting, { timeout: 10_000 }).toBe(false);

    // Exactly one new scan: the front job's own conversion was cancelled.
    await new Promise((r) => setTimeout(r, 8_000));
    const after = (await listFiles(request)).map((f) => f.file).filter((n) => !before.includes(n) && !n.endsWith('-ocr.pdf'));
    expect(after).toEqual([merged]);
  });

  test('scan to OCR uses the gray mode and still lands in /scans', async ({ request }) => {
    const before = (await listFiles(request)).map((f) => f.file);
    await triggerScan(request, 'ocr');
    const scanned = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
    expect(pdfPageCount(scanned)).toBe(2);
    expect(inContainer(['cat', '/var/log/scanner.log'])).toContain('--mode=True Gray');
  });

  test('a failing scanner cancels the job without leaving files behind', async ({ request }) => {
    // SIM_FAIL is read from env.txt by the scan scripts; flip it for this test only.
    inContainer(['bash', '-c', 'echo SIM_FAIL=true >> /opt/brother/scanner/env.txt']);
    try {
      const before = (await listFiles(request)).map((f) => f.file);
      await triggerScan(request, 'file');
      await new Promise((r) => setTimeout(r, 5_000));
      const after = (await listFiles(request)).map((f) => f.file).filter((n) => !n.endsWith('-ocr.pdf'));
      expect(after).toEqual(before.filter((n) => !n.endsWith('-ocr.pdf')));
      expect(inContainer(['cat', '/var/log/scanner.log'])).toContain('ERROR: Cancelling scanning!');
      expect(inContainer(['bash', '-c', 'ls -d /tmp/20* 2>/dev/null | wc -l']).trim()).toBe('0');
    } finally {
      inContainer(['sed', '-i', '/^SIM_FAIL=/d', '/opt/brother/scanner/env.txt']);
    }
  });

  test('scan button in the UI shows the waiting state and returns to ready', async ({ page, request }) => {
    const before = (await listFiles(request)).map((f) => f.file);
    await page.goto('/');
    await page.locator('a.trigger-scan[data-trigger="file"]').click();
    await expect(page.locator('#status-text')).toHaveText('Waiting for rear pages', { timeout: 30_000 });
    await expect(page.locator('#status-text')).toHaveText('Ready to scan', { timeout: 60_000 });
    await waitForNewFile(request, before, 30_000, (n) => !n.endsWith('-ocr.pdf'));
  });
});
