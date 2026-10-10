import { expect, test } from '@playwright/test';
import { inContainer, listFiles, pdfPageCount, scannerStatus, waitFor, waitForQueueIdle } from '../helpers';

// #101: scans are jobs with an id and a state; parameters per request; rear
// scan for a specific job; actions description; reachability in the status.

async function job(request: import('@playwright/test').APIRequestContext, id: string) {
  const res = await request.get(`/api/jobs/${id}`);
  return { status: res.status(), body: res.ok() ? await res.json() : null };
}

async function waitForState(request: import('@playwright/test').APIRequestContext, id: string, states: string[], timeoutMs: number) {
  let last: any = null;
  await waitFor(async () => {
    const r = await job(request, id);
    last = r.body;
    return r.status === 200 && states.includes(r.body.state);
  }, timeoutMs, `job ${id} to reach ${states.join('|')} (last: ${JSON.stringify(last)})`);
  return last;
}

test.describe('jobs API', () => {
  test.beforeEach(async ({ request }) => {
    await waitFor(async () => {
      const s = await scannerStatus(request);
      return !s.scan && !s.waiting && !s.ocr;
    }, 60_000, 'scanner to be idle');
    await waitForQueueIdle(60_000);
  });

  test('actions are described with labels, parameters and defaults', async ({ request }) => {
    const res = await request.get('/api/actions');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.actions.map((a: any) => a.target)).toEqual(['file', 'email', 'ocr', 'image']);
    expect(body.actions[0]).toMatchObject({ label: 'Scan to file', enabled: true });
    expect(body.parameters.resolution.default).toBe(100); // the e2e container runs with RESOLUTION=100
    expect(Object.keys(body.parameters)).toEqual(['resolution', 'mode', 'source', 'wait']);
    expect(body.authentication).toBe('none');
    // #129: integrations read the version and the device from the same endpoint
    expect(body.api_version).toBe(1);
    expect(typeof body.version).toBe('string');
    expect(body.device).toMatchObject({ name: 'Scanner', model: 'MFC-SIMULATOR', host: '192.0.2.10' });
    expect(body.device.capabilities.mode).toEqual({ options: ['Black & White', 'Gray[Error Diffusion]', 'True Gray', '24bit Color[Fast]'], default: '24bit Color[Fast]' });
    expect(body.device.capabilities.resolution).toEqual({ options: [100, 150, 200, 300, 400, 600], default: 300 });
    expect(body.device.capabilities.source.options).toContain('FlatBed');
    expect(body.device.capabilities.source.default).toBe('Automatic Document Feeder(left aligned)');
  });

  test('status reports reachability (the test scanner address never answers)', async ({ request }) => {
    const status = await scannerStatus(request);
    expect(status).toHaveProperty('reachable');
    await expect.poll(async () => (await scannerStatus(request)).reachable, { timeout: 90_000 }).toBe(false);
  });

  test('a scan is a job: parameters are applied and the state goes through to done with an OCR copy', async ({ request }) => {
    const res = await request.post('/api/scanner/scanto', { form: { target: 'file', resolution: '100', mode: 'True Gray' } });
    expect(res.status()).toBe(200);
    const trigger = await res.json();
    expect(trigger.job).toMatch(/^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$/);
    expect(trigger.status_url).toBe(`/api/jobs/${trigger.job}`);

    const waiting = await waitForState(request, trigger.job, ['waiting_for_rear'], 30_000);
    expect(waiting).toMatchObject({ action: 'file', pages: 2, params: { RESOLUTION: '100', SCAN_MODE: 'True Gray' } });
    expect(waiting.waiting_until).toBeTruthy();

    const done = await waitForState(request, trigger.job, ['done'], 60_000);
    expect(done.file).toBe(`${trigger.job}.pdf`);
    expect(done.file_url).toBe(`/api/file/${trigger.job}.pdf/download`);
    expect(done.file_exists).toBe(true);
    expect(['queued', 'pending', 'in_progress', 'done']).toContain(done.ocr);

    await waitFor(async () => (await job(request, trigger.job)).body?.ocr === 'done', 60_000, 'OCR copy');
    const final = (await job(request, trigger.job)).body;
    expect(final.ocr_file_url).toBe(`/api/file/${trigger.job}-ocr.pdf/download`);

    const log = inContainer(['cat', '/var/log/scanner.log']);
    expect(log).toContain(`as job ${trigger.job} with --resolution '100' --mode 'True Gray'`);
    expect(log).toContain("'--mode=True Gray'");

    const list = await (await request.get('/api/jobs?limit=5')).json();
    expect(list[0].job).toBe(trigger.job);
  });

  test('rear pages for a specific job merge into one PDF', async ({ request }) => {
    const trigger = await (await request.post('/api/scanner/scanto', { form: { target: 'file' } })).json();
    await waitForState(request, trigger.job, ['waiting_for_rear'], 30_000);

    const rear = await request.post(`/api/jobs/${trigger.job}/rear`);
    expect(rear.status()).toBe(200);
    const done = await waitForState(request, trigger.job, ['done'], 60_000);
    expect(done.side).toBe('rear');
    expect(pdfPageCount(done.file)).toBe(4);

    // Not waiting any more: a second rear request is refused.
    const again = await request.post(`/api/jobs/${trigger.job}/rear`);
    expect(again.status()).toBe(409);
  });

  test('wait=true answers after the scan script finished', async ({ request }) => {
    const res = await request.post('/api/scanner/scanto', { form: { target: 'file', wait: 'true' } });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.method).toBe('get');
    expect(['waiting_for_rear', 'converting', 'done']).toContain(body.state);
    await waitForState(request, body.job, ['done'], 60_000);
  });

  test('invalid parameters and ids are rejected', async ({ request }) => {
    expect((await request.post('/api/scanner/scanto', { form: { target: 'file', resolution: 'abc' } })).status()).toBe(400);
    expect((await request.post('/api/scanner/scanto', { form: { target: 'file', mode: 'True Gray; rm -rf /' } })).status()).toBe(400);
    expect((await request.get('/api/jobs/not-a-job')).status()).toBe(400);
    expect((await request.get('/api/jobs/2000-01-01-00-00-00')).status()).toBe(404);
    expect((await request.post('/api/jobs/2000-01-01-00-00-00/rear')).status()).toBe(404);
  });

  test('a failed scan is reported as failed', async ({ request }) => {
    inContainer(['bash', '-c', 'echo SIM_FAIL=true >> /opt/brother/scanner/env.txt']);
    try {
      const trigger = await (await request.post('/api/scanner/scanto', { form: { target: 'file' } })).json();
      const failed = await waitForState(request, trigger.job, ['failed'], 30_000);
      expect(failed.error).toContain('cancelled');
      expect((await listFiles(request)).some((f) => f.file === `${trigger.job}.pdf`)).toBe(false);
    } finally {
      inContainer(['sed', '-i', '/^SIM_FAIL=/d', '/opt/brother/scanner/env.txt']);
    }
  });
});
