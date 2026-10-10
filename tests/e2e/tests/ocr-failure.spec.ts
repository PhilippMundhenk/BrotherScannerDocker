import { expect, test } from '@playwright/test';
import type { OcrMode } from '../fake-ocr';
import { inContainer, listFiles, pdfPageCount, queueContents, readState, scannerStatus, triggerScan, waitFor, waitForNewFile } from '../helpers';

// The OCR microservice answers HTTP 200 with an error text when tesseract
// fails. That response must never become <date>-ocr.pdf and must never cost
// the original scan. The same holds for empty bodies, HTTP errors and PDFs
// with the wrong number of pages.

async function setOcrMode(mode: OcrMode) {
  const res = await fetch(`http://localhost:${readState().ocrPort}/mode/${mode}`, { method: 'POST' });
  expect(res.ok).toBeTruthy();
}

const cases: { mode: OcrMode; logLine: string; keepsResponse: boolean }[] = [
  { mode: 'garbage', logLine: 'rejected: not a PDF', keepsResponse: true },
  { mode: 'empty', logLine: 'rejected: empty file', keepsResponse: true },
  { mode: 'short', logLine: 'rejected: 1 pages, original has 2', keepsResponse: true },
  { mode: 'error', logLine: 'OCR upload failed for', keepsResponse: false },
];

test.describe('OCR result validation', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
    inContainer(['bash', '-c', 'rm -f /scans/.ocr_queue/failed/*']);
  });

  test.afterEach(async () => {
    await setOcrMode('pdf');
    inContainer(['bash', '-c', 'rm -f /scans/.ocr_queue/failed/*']);
  });

  for (const { mode, logLine, keepsResponse } of cases) {
    test(`an OCR response of kind "${mode}" is rejected and the original scan survives`, async ({ request }) => {
      await setOcrMode(mode);
      const before = (await listFiles(request)).map((f) => f.file);
      await triggerScan(request, 'file');
      const scanned = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
      const stem = scanned.replace('.pdf', '');

      // OCR_MAX_ATTEMPTS=3 with 1 s backoff: the job gives up within seconds.
      await waitFor(async () => {
        const q = queueContents();
        return q.pending.length === 0 && q.in_progress.length === 0 && q.failed.some((n) => n.endsWith('.job'));
      }, 60_000, 'job to be parked in failed/');

      const files = (await listFiles(request)).map((f) => f.file);
      expect(files).toContain(scanned);
      expect(files).not.toContain(`${stem}-ocr.pdf`);
      expect(pdfPageCount(scanned)).toBe(2);
      expect(inContainer(['bash', '-c', 'ls /scans/*.part 2>/dev/null | wc -l']).trim()).toBe('0');

      const failed = queueContents().failed;
      expect(failed.some((n) => n.endsWith('.job') && n.includes(stem))).toBe(true);
      const responses = failed.filter((n) => n.startsWith(stem) && n.includes('.response-'));
      expect(responses.length).toBe(keepsResponse ? 3 : 0);

      const log = inContainer(['cat', '/var/log/scanner.log']);
      expect(log).toContain(`${logLine}`);
      expect(log).toContain(`/scans/${scanned}`);
      if (keepsResponse) {
        expect(log).toContain(`OCR result for /scans/${scanned} rejected`);
        expect(log).toContain('original kept');
      }
    });
  }

  test('a valid OCR response produces the OCR copy with the same page count', async ({ request }) => {
    await setOcrMode('pdf');
    const before = (await listFiles(request)).map((f) => f.file);
    await triggerScan(request, 'file');
    const scanned = await waitForNewFile(request, before, 60_000, (n) => !n.endsWith('-ocr.pdf'));
    const ocrName = scanned.replace('.pdf', '-ocr.pdf');
    await waitFor(async () => (await listFiles(request)).some((f) => f.file === ocrName), 60_000, `OCR output ${ocrName}`);
    expect(pdfPageCount(ocrName)).toBe(pdfPageCount(scanned));
    expect(inContainer(['cat', '/var/log/scanner.log'])).toContain(`OCR finished -> /scans/${ocrName}`);
    expect(queueContents().failed).toEqual([]);
  });
});
