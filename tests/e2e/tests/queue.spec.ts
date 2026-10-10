import { expect, test } from '@playwright/test';
import type { OcrMode } from '../fake-ocr';
import { inContainer, listFiles, readState, scannerStatus, triggerScan, waitFor, waitForNewFile, waitForQueueIdle } from '../helpers';

// #125: the status endpoint carries the OCR queue counts and the home page
// shows them under the scanner state.

async function setOcrMode(mode: OcrMode) {
  const res = await fetch(`http://localhost:${readState().ocrPort}/mode/${mode}`, { method: 'POST' });
  expect(res.ok).toBeTruthy();
}

test.describe('OCR queue in status and UI', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
    await waitForQueueIdle(60_000);
    inContainer(['bash', '-c', 'rm -f /scans/.ocr_queue/failed/*']);
  });

  test.afterEach(async () => {
    await setOcrMode('pdf');
    inContainer(['bash', '-c', 'rm -f /scans/.ocr_queue/failed/*']);
  });

  test('status carries the queue counts and the line is hidden while nothing is queued', async ({ page, request }) => {
    const status = await scannerStatus(request);
    expect(status.queue).toEqual({ pending: 0, in_progress: 0, failed: 0, holding: false });
    await page.goto('/');
    await expect(page.locator('#status-text')).toHaveText('Ready to scan');
    await expect(page.locator('#queue-text')).toBeHidden();
  });

  test('a slow OCR service shows the running upload in the status and on the home page', async ({ page, request }) => {
    await setOcrMode('slow');
    await page.goto('/');
    const before = (await listFiles(request)).map((f) => f.file);
    await triggerScan(request, 'file');
    await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));

    await expect.poll(async () => (await scannerStatus(request)).queue.in_progress, { timeout: 30_000 }).toBe(1);
    await expect(page.locator('#queue-text')).toHaveText('OCR: 1 running', { timeout: 15_000 });

    await waitForQueueIdle(90_000);
    await expect(page.locator('#queue-text')).toBeHidden({ timeout: 15_000 });
  });

  test('failed jobs are counted and shown', async ({ page, request }) => {
    inContainer(['bash', '-c', 'printf "PDF=/scans/gone.pdf\\nDATE=2000-01-01-00-00-00\\nSUFFIX=front\\nATTEMPTS=3\\n" > /scans/.ocr_queue/failed/1-2000-01-01-00-00-00-front.job']);
    await expect.poll(async () => (await scannerStatus(request)).queue.failed, { timeout: 10_000 }).toBe(1);
    await page.goto('/');
    await expect(page.locator('#queue-text')).toHaveText('OCR: 1 failed', { timeout: 15_000 });
  });
});
