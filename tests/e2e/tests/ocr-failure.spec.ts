import { expect, test } from '@playwright/test';
import { inContainer, listFiles, queueContents, readState, scannerStatus, triggerScan, waitFor, waitForNewFile } from '../helpers';

// The OCR microservice answers HTTP 200 with an error text when tesseract
// fails. That response must never become <date>-ocr.pdf and must never cost
// the original scan.

async function setOcrMode(mode: 'pdf' | 'garbage' | 'empty' | 'error') {
  const res = await fetch(`http://localhost:${readState().ocrPort}/mode/${mode}`, { method: 'POST' });
  expect(res.ok).toBeTruthy();
}

test.describe('OCR result validation', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
  });

  test.afterEach(async () => {
    await setOcrMode('pdf');
  });

  for (const mode of ['garbage', 'empty', 'error'] as const) {
    test(`an OCR response of kind "${mode}" is rejected and the original scan survives`, async ({ request }) => {
      await setOcrMode(mode);
      // Mark where the failed/ folder stands before this job.
      const failedBefore = queueContents().failed.length;

      const before = (await listFiles(request)).map((f) => f.file);
      await triggerScan(request, 'file');
      const scanned = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
      const ocrName = scanned.replace('.pdf', '-ocr.pdf');

      // OCR_MAX_ATTEMPTS=3 with 1 s backoff: the job gives up within seconds.
      await waitFor(async () => {
        const q = queueContents();
        return q.pending.length === 0 && q.in_progress.length === 0 && q.failed.length > failedBefore;
      }, 60_000, 'job to be parked in failed/');

      const files = (await listFiles(request)).map((f) => f.file);
      expect(files).toContain(scanned);
      expect(files).not.toContain(ocrName);
      expect(inContainer(['bash', '-c', 'ls /scans/*.part 2>/dev/null | wc -l']).trim()).toBe('0');

      const failed = queueContents().failed;
      expect(failed.some((n) => n.endsWith('.job') && n.includes(scanned.replace('.pdf', '')))).toBe(true);
      if (mode !== 'error') {
        // 200 with a bad body: the body is kept for inspection, once per attempt
        const responses = failed.filter((n) => n.startsWith(scanned.replace('.pdf', '')) && n.includes('.response-'));
        expect(responses.length).toBe(3);
      }
      const log = inContainer(['cat', '/var/log/scanner.log']);
      expect(log).toContain(`OCR result for /scans/${scanned} rejected`);
      expect(log).toContain('original kept');

      // Clean up so later tests start from an empty failed/ folder.
      inContainer(['bash', '-c', 'rm -f /scans/.ocr_queue/failed/*']);
    });
  }

  test('a valid OCR response still produces the OCR copy', async ({ request }) => {
    await setOcrMode('pdf');
    const before = (await listFiles(request)).map((f) => f.file);
    await triggerScan(request, 'file');
    const scanned = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
    const ocrName = scanned.replace('.pdf', '-ocr.pdf');
    await waitFor(async () => (await listFiles(request)).some((f) => f.file === ocrName), 60_000, `OCR output ${ocrName}`);
    expect(inContainer(['cat', '/var/log/scanner.log'])).toContain(`OCR finished -> /scans/${ocrName}`);
  });
});
