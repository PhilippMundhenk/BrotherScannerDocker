import { expect, test } from '@playwright/test';
import * as path from 'path';
import { docker, FIXTURES, inContainer, listFiles, readState, SAMPLE_FILE, scannerStatus, waitFor, waitForQueueIdle } from '../helpers';

// Error branches of the PHP backend that the feature specs do not reach
// (#126): malformed bodies, unknown files, stale status files, validation
// limits, the GET trigger variant, paging corners.

function ensureSampleFile() {
  const present = inContainer(['bash', '-c', `test -f /scans/${SAMPLE_FILE} && echo yes || echo no`]).trim();
  if (present !== 'yes') {
    docker(['cp', path.join(FIXTURES, 'sample.pdf'), `${readState().container}:/scans/${SAMPLE_FILE}`]);
    inContainer(['chmod', '666', `/scans/${SAMPLE_FILE}`]);
  }
}

test.describe('API edge cases', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
    await waitForQueueIdle(60_000);
    ensureSampleFile();
  });

  test('rename: malformed body, unknown file, too short name, datetime prefix', async ({ request }) => {
    const malformed = await request.put(`/api/file/${SAMPLE_FILE}/rename`, { data: 'not json', headers: { 'Content-Type': 'text/plain' } });
    expect(malformed.status()).toBe(400);
    // valid JSON, wrong shape: used to be a 500 (string offset access)
    const wrongShape = await request.put(`/api/file/${SAMPLE_FILE}/rename`, { data: 'just a string' });
    expect(wrongShape.status()).toBe(400);
    const noName = await request.put(`/api/file/${SAMPLE_FILE}/rename`, { data: { new_filename_prefix: 'none' } });
    expect(noName.status()).toBe(400);
    expect((await request.put('/api/file/missing.pdf/rename', { data: { new_filename: 'abc', new_filename_prefix: 'none' } })).status()).toBe(404);
    const short = await request.put(`/api/file/${SAMPLE_FILE}/rename`, { data: { new_filename: 'ab', new_filename_prefix: 'none' } });
    expect(short.status()).toBe(400);

    const copy = '2026-05-05-05-05-05.pdf';
    inContainer(['bash', '-c', `cp -p /scans/${SAMPLE_FILE} /scans/${copy} && chmod 666 /scans/${copy}`]);
    const before = (await listFiles(request)).find((f) => f.file === copy);
    expect(before).toBeTruthy();
    const res = await request.put(`/api/file/${copy}/rename`, { data: { new_filename: 'Stamped', new_filename_prefix: 'datetime' } });
    expect(res.status()).toBe(200);
    const expected = `${before!.date_from_file}-${before!.time_from_file} Stamped.pdf`;
    expect((await listFiles(request)).some((f) => f.file === expected)).toBe(true);
    expect((await request.delete(`/api/file/${encodeURIComponent(expected)}/delete`)).status()).toBe(200);
    expect((await request.delete(`/api/file/${encodeURIComponent(expected)}/delete`)).status()).toBe(404);
  });

  test('file endpoints reject unknown, dot and non-PDF names', async ({ request }) => {
    expect((await request.get('/api/file/missing.pdf/info')).status()).toBe(404);
    expect((await request.get('/api/file/missing.pdf/download')).status()).toBe(404);
    expect((await request.get('/api/file/missing.pdf/thumbnail')).status()).toBe(404);
    // "." survives the router but not the path check
    expect((await request.get('/api/file/./info')).status()).toBe(404);
    inContainer(['bash', '-c', 'echo hello > /scans/notes.pdf; chmod 666 /scans/notes.pdf']);
    try {
      expect((await request.get('/api/file/notes.pdf/info')).status()).toBe(400); // not a PDF inside
      expect((await listFiles(request)).some((f) => f.file === 'notes.pdf')).toBe(true); // the listing trusts the extension
    } finally {
      inContainer(['rm', '-f', '/scans/notes.pdf']);
    }
    const page = await request.get('/api/file-list?offset=99999&limit=5');
    expect(await page.json()).toEqual([]);
    const fromOne = await request.get('/api/file-list?offset=1');
    expect(fromOne.status()).toBe(200);
    expect((await fromOne.json()).length).toBe((await listFiles(request)).length - 1);
  });

  test('stale status files are ignored and removed', async ({ request }) => {
    // written by the scanner user in real life; chown so the web server may remove it
    const backdate = () => inContainer(['bash', '-c', 'echo 1 > /tmp/STATUS_WAITING; touch -d "10 minutes ago" /tmp/STATUS_WAITING; chown www-data /tmp/STATUS_WAITING; echo 1 > /tmp/STATUS_REACHABLE; touch -d "20 minutes ago" /tmp/STATUS_REACHABLE']);
    backdate();
    try {
      let status = await scannerStatus(request);
      // the container's reachability loop rewrites STATUS_REACHABLE every 60 s; if it
      // struck between the backdating and the request, backdate again and retry
      for (let attempt = 0; attempt < 3 && status.reachable !== null; attempt++) {
        backdate();
        status = await scannerStatus(request);
      }
      expect(status.waiting).toBe(false);
      expect(status.reachable).toBeNull();
      expect(inContainer(['bash', '-c', 'test -e /tmp/STATUS_WAITING && echo present || echo gone']).trim()).toBe('gone');
    } finally {
      inContainer(['rm', '-f', '/tmp/STATUS_WAITING', '/tmp/STATUS_REACHABLE']);
    }
  });

  test('settings validation: environment keys, numbers, limits, booleans, bodies', async ({ request }) => {
    const bad = await request.put('/api/settings', {
      data: { RESOLUTION: '200', KEEPALIVE_INTERVAL: '5', SCAN_WIDTH_MM: '0', SCANNER_PING_INTERVAL: 'soon', SCAN_TOP_MM: '5000', SCAN_MODE: 'x'.repeat(600), NOT_A_KEY: '1' },
    });
    expect(bad.status()).toBe(400);
    const errors = (await bad.json()).errors;
    expect(errors.RESOLUTION).toContain('environment');
    expect(errors.KEEPALIVE_INTERVAL).toContain('at least');
    expect(errors.SCAN_WIDTH_MM).toContain('at least');
    expect(errors.SCANNER_PING_INTERVAL).toContain('whole number');
    expect(errors.SCAN_TOP_MM).toContain('at most');
    const tooBig = await request.put('/api/settings', { data: { KEEPALIVE_INTERVAL: '5000' } });
    expect((await tooBig.json()).errors.KEEPALIVE_INTERVAL).toContain('at most');
    expect(errors.SCAN_MODE).toContain('too long');
    expect(errors.NOT_A_KEY).toContain('unknown');

    const ok = await request.put('/api/settings', { data: { USE_JPEG_COMPRESSION: 'yes', KEEPALIVE_INTERVAL: 30, SCAN_TOP_MM: '1.5', SCANNER_PING_INTERVAL: '0' } });
    expect(ok.status()).toBe(200);
    const file = inContainer(['cat', '/scans/.config/scanner.conf']);
    expect(file).toContain('USE_JPEG_COMPRESSION=true');
    expect(file).toContain('KEEPALIVE_INTERVAL=30');
    const cleared = await request.put('/api/settings', { data: { USE_JPEG_COMPRESSION: '', KEEPALIVE_INTERVAL: '', SCAN_TOP_MM: '', SCANNER_PING_INTERVAL: '' } });
    expect((await cleared.json()).removed.sort()).toEqual(['KEEPALIVE_INTERVAL', 'SCANNER_PING_INTERVAL', 'SCAN_TOP_MM', 'USE_JPEG_COMPRESSION']);

    const notJson = await request.put('/api/settings', { data: 'nope', headers: { 'Content-Type': 'application/json' } });
    expect(notJson.status()).toBe(400);
    const nothing = await request.put('/api/settings', { data: { SCAN_MODE: '' } });
    expect((await nothing.json()).removed).toEqual([]);
    const multiline = await request.put('/api/settings', { data: { SCAN_MODE: 'a\nb' } });
    expect(multiline.status()).toBe(400);
    // quoted values in a hand-written file are accepted
    inContainer(['bash', '-c', 'echo \'SCAN_SOURCE="FlatBed"\' >> /scans/.config/scanner.conf']);
    try {
      const all = (await (await request.get('/api/settings')).json()).settings as { key: string; value: string; source: string }[];
      expect(all.find((s) => s.key === 'SCAN_SOURCE')).toMatchObject({ value: 'FlatBed', source: 'file' });
    } finally {
      await request.put('/api/settings', { data: { SCAN_SOURCE: '' } });
    }
    const notBool = await request.put('/api/settings', { data: { KEEPALIVE: 'maybe' } });
    expect(notBool.status()).toBe(400);
    const notFloat = await request.put('/api/settings', { data: { SCAN_TOP_MM: 'tall' } });
    expect(notFloat.status()).toBe(400);
  });

  test('GET trigger variant with parameters, invalid targets and parameters', async ({ request }) => {
    expect((await request.get('/api/scanner/scanto/bogus')).status()).toBe(400);
    expect((await request.get('/api/scanner/scanto/file?resolution=1')).status()).toBe(400);
    expect((await request.get('/api/scanner/scanto/file?mode=' + encodeURIComponent('rm -rf /'))).status()).toBe(400);
    expect((await request.post('/api/scanner/scanto', { form: {} })).status()).toBe(400);

    const res = await request.get('/api/scanner/scanto/file?resolution=100&mode=' + encodeURIComponent('True Gray'));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.job).toMatch(/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$/);
    await waitFor(async () => {
      const r = await request.get(`/api/jobs/${body.job}`);
      return r.ok() && (await r.json()).state === 'done';
    }, 90_000, 'GET-triggered job to finish');
    const one = await request.get('/api/jobs?limit=1');
    expect((await one.json()).length).toBe(1);
    expect((await request.get('/api/jobs?limit=abc')).status()).toBe(200);
    expect((await request.get('/api/jobs/not-a-job')).status()).toBe(400);
    expect((await request.get('/api/jobs/1999-01-01-00-00-00')).status()).toBe(404);
    expect((await request.post('/api/jobs/not-a-job/rear')).status()).toBe(400);
    expect((await request.get('/api/dev/timezone')).status()).toBe(200);
    await waitForQueueIdle(60_000);
  });

  test('boolean settings from the file switch actions off and on', async ({ request, page }) => {
    const enabled = async (target: string) => {
      const body = await (await request.get('/api/actions')).json();
      return body.actions.find((a: { target: string }) => a.target === target).enabled as boolean;
    };
    try {
      expect((await request.put('/api/settings', { data: { DISABLE_GUI_SCANTOEMAIL: 'true' } })).status()).toBe(200);
      expect(await enabled('email')).toBe(false);
      await page.goto('/');
      await expect(page.locator('a.trigger-scan[data-trigger="email"]')).toHaveCount(0);
      expect((await request.put('/api/settings', { data: { DISABLE_GUI_SCANTOEMAIL: 'false' } })).status()).toBe(200);
      expect(await enabled('email')).toBe(true);
      await page.goto('/');
      await expect(page.locator('a.trigger-scan[data-trigger="email"]')).toHaveCount(1);
    } finally {
      await request.put('/api/settings', { data: { DISABLE_GUI_SCANTOEMAIL: '' } });
    }
  });

  test('two triggers in the same second get distinct job ids; rear pages without a waiting job', async ({ request }) => {
    const [a, b] = await Promise.all([
      request.post('/api/scanner/scanto', { form: { target: 'file' } }),
      request.post('/api/scanner/scanto', { form: { target: 'file' } }),
    ]);
    expect(a.status()).toBe(200);
    expect(b.status()).toBe(200);
    const jobs = [(await a.json()).job, (await b.json()).job];
    expect(jobs[0]).not.toBe(jobs[1]);
    await waitFor(async () => {
      const states = await Promise.all(jobs.map(async (j) => (await (await request.get(`/api/jobs/${j}`)).json()).state));
      return states.every((s) => s === 'done' || s === 'failed');
    }, 120_000, 'both jobs to finish');
    await waitForQueueIdle(60_000);

    const idleRear = await request.post('/api/scanner/scanto', { form: { target: 'email' } });
    expect(idleRear.status()).toBe(200);
    expect((await idleRear.json()).job).toBeNull();
    await new Promise((r) => setTimeout(r, 2000));
    expect((await request.get('/api/scanner/scanto/')).status()).toBe(400);
    // @-suppressed PHP warnings must not reach the log (#174)
    expect(inContainer(['bash', '-c', 'grep -c "mkdir(): File exists" /var/log/scanner.log || true']).trim()).toBe('0');
  });

  test('thumbnail cache: recreates its folder and drops stale versions', async ({ request }) => {
    const info = await (await request.get(`/api/file/${SAMPLE_FILE}/info`)).json();
    inContainer(['rm', '-rf', '/scans/.thumbnails']);
    const first = await request.get(`/api/file/${SAMPLE_FILE}/thumbnail`);
    expect(first.status()).toBe(200);
    expect(first.headers()['x-thumbnail-cache']).toBe('miss');
    const current = `/scans/.thumbnails/${SAMPLE_FILE}.${info.fileModificationTime}.jpg`;
    inContainer(['bash', '-c', `rm -f '${current}'; touch '/scans/.thumbnails/${SAMPLE_FILE}.1.jpg'; chmod 666 '/scans/.thumbnails/${SAMPLE_FILE}.1.jpg'`]);
    const second = await request.get(`/api/file/${SAMPLE_FILE}/thumbnail`);
    expect(second.headers()['x-thumbnail-cache']).toBe('miss');
    expect(inContainer(['bash', '-c', `ls /scans/.thumbnails/ | grep -c '${SAMPLE_FILE}.1.jpg' || true`]).trim()).toBe('0');
    expect(inContainer(['bash', '-c', `test -f '${current}' && echo yes || echo no`]).trim()).toBe('yes');
  });

  test('delete and rename report when the file system refuses', async ({ request }) => {
    const mode = inContainer(['stat', '-c', '%a', '/scans']).trim();
    inContainer(['chmod', '555', '/scans']);
    try {
      expect((await request.delete(`/api/file/${SAMPLE_FILE}/delete`)).status()).toBe(500);
      const rename = await request.put(`/api/file/${SAMPLE_FILE}/rename`, { data: { new_filename: 'Locked', new_filename_prefix: 'none' } });
      expect(rename.status()).toBe(400);
    } finally {
      inContainer(['chmod', mode, '/scans']);
    }
    expect((await listFiles(request)).some((f) => f.file === SAMPLE_FILE)).toBe(true);
  });

  test('empty file names and the plain list page', async ({ request }) => {
    expect((await request.get('/api/file//info')).status()).toBe(400);
    expect((await request.get('/api/file//download')).status()).toBe(400);
    const page = await request.get('/list-files');
    expect(page.status()).toBe(200);
    expect(await page.text()).toContain('list-group-item');
  });

  test('unknown paths answer JSON under /api and a page elsewhere', async ({ request }) => {
    const api = await request.get('/api/settings/extra');
    expect(api.status()).toBe(404);
    expect((await api.json()).code).toBe(404);
    const page = await request.get('/no-such-page');
    expect(page.status()).toBe(404);
    expect(await page.text()).toContain('could not be found');
  });
});
