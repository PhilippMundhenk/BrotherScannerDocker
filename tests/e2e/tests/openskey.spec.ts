import { expect, test } from '@playwright/test';
import * as path from 'path';
import { docker, FIXTURES, IMAGE } from '../helpers';

// #188: openskey, the open reimplementation of Brother's brscan-skey, as the
// Scan-to-PC button daemon (SKEY_DAEMON=openskey), exercised against its mock
// device running inside the container (SKEY_MOCK_DEVICE=true), so no hardware
// is needed:
//   - the daemon registers and verifies the registration by reading it back,
//   - GET /api/scanner/device reads the "scanner" over SNMP,
//   - a button press on the "device" becomes a job with trigger=button and
//     the event's fields (#187), exactly once although the device sends the
//     event twice.

const NAME = `bsd-e2e-openskey-${process.pid}`;
const PORT = Number(process.env.E2E_OPENSKEY_PORT || 18120);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function scannerLog(): string {
  return docker(['exec', NAME, 'cat', '/var/log/scanner.log']);
}

async function get(pathname: string) {
  const res = await fetch(`http://localhost:${PORT}${pathname}`);
  return { status: res.status, body: res.headers.get('content-type')?.includes('json') ? await res.json() : await res.text() };
}

test.describe('openskey button daemon', () => {
  test.beforeAll(async () => {
    docker([
      'run', '-d', '--name', NAME, '-p', `${PORT}:8080`,
      '-v', `${path.join(FIXTURES, 'scanimage')}:/usr/bin/scanimage:ro`,
      '-e', 'WEBSERVER=true', '-e', 'PORT=8080',
      '-e', 'NAME=Scanner', '-e', 'MODEL=MFC-L2700DW',
      // the mock device answers on 127.0.0.1 (UDP 1161 by default), and
      // sends button events back to the same address
      '-e', 'IPADDRESS=127.0.0.1', '-e', 'HOST_IPADDRESS=127.0.0.1',
      '-e', 'SKEY_DAEMON=openskey', '-e', 'SKEY_MOCK_DEVICE=true',
      '-e', 'KEEPALIVE_INTERVAL=5', '-e', 'SCANNER_PING_INTERVAL=0',
      '-e', 'DEVICE_STATUS_CACHE_SECONDS=0',
      '-e', 'RESOLUTION=100', '-e', 'REAR_PAGE_WAIT_SECONDS=2',
      '-e', 'SIM_PAGES=1', '-e', 'SIM_SCAN_SECONDS=0.2',
      IMAGE,
    ]);
    const deadline = Date.now() + 90_000;
    let up = false;
    while (Date.now() < deadline && !up) {
      try {
        up = (await fetch(`http://localhost:${PORT}/api/scanner/status`)).ok;
      } catch {
        /* not up yet */
      }
      if (!up) await sleep(1000);
    }
    if (!up) throw new Error(`openskey container not reachable:\n${docker(['logs', NAME])}`);
  });

  test.afterAll(async () => {
    try {
      docker(['rm', '-f', NAME]);
    } catch {
      /* already gone */
    }
  });

  test('runs openskey instead of brscan-skey and verifies its registration', async () => {
    const logs = docker(['logs', NAME]);
    expect(logs).toContain('button daemon: openskey');
    expect(logs).toContain('mock device started on UDP :1161');
    expect(logs).toContain('registration keepalive: built into openskey');
    await expect.poll(() => scannerLog(), { timeout: 30_000 }).toContain('registration verified');
    expect(docker(['exec', NAME, 'bash', '-c', 'pgrep -x brscan-skey-exe || echo none']).trim()).toBe('none');
    expect(docker(['exec', NAME, 'bash', '-c', 'pgrep -x openskey | wc -l']).trim()).toBe('1');
    const status = (await get('/api/scanner/status')).body;
    expect(status.buttons).toBe(true);
  });

  test('the device status endpoint reads the scanner over SNMP, scanner objects only', async () => {
    const { status, body } = await get('/api/scanner/device');
    expect(status).toBe(200);
    expect(body).toMatchObject({
      device_ip: '127.0.0.1',
      reachable: true,
      registered: true,
      model: 'MFC-L2700DW',
      serial: 'E73941F6N621420',
      firmware: 'Y2309112149',
      net_scanner_supported: true,
      net_scanner_enabled: true,
      scan_key_supported: true,
      scan_key_enabled: true,
      cached: false,
    });
    expect(body.display).toContain('Scan:');
    expect(typeof body.checked).toBe('string');
    // this is a scanner project: no printer objects
    for (const key of Object.keys(body)) expect(key).not.toMatch(/toner|drum|page/i);
  });

  test('a button press on the device becomes one job with trigger=button and the event fields', async () => {
    const before = ((await get('/api/jobs?limit=50')).body as any[]).length;
    // the mock sends the event twice (same SEQ), like a real device
    docker(['exec', NAME, 'openskey-mock-device', '--button', 'FILE', '--params', '3,1,0,2']);

    let job: any = null;
    await expect
      .poll(async () => {
        const jobs = (await get('/api/jobs?limit=50')).body as any[];
        job = jobs.find((j) => j.trigger === 'button') || null;
        return job !== null;
      }, { timeout: 30_000 })
      .toBe(true);
    expect(job).toMatchObject({
      action: 'file',
      trigger: 'button',
      button: { function: 'file', seq: 56, regid: 60614, params: { p1: 3, p2: 1, p3: 0, p4: 2 } },
    });

    await expect
      .poll(async () => ((await get(`/api/jobs/${job.job}`)).body as any).state, { timeout: 60_000 })
      .toBe('done');
    const done = (await get(`/api/jobs/${job.job}`)).body;
    expect(done.file).toBe(`${job.job}.pdf`);
    expect(done.file_exists).toBe(true);

    // deduplicated: the device's resend did not start a second scan
    await sleep(3000);
    const jobs = (await get('/api/jobs?limit=50')).body as any[];
    expect(jobs.length).toBe(before + 1);
    expect(scannerLog()).toContain('duplicate event (SEQ=56) ignored');
  });

  test('the watchdog revives openskey after it dies', async () => {
    const before = docker(['exec', NAME, 'bash', '-c', 'pgrep -x openskey | head -1']).trim();
    expect(before).not.toBe('');
    docker(['exec', NAME, 'pkill', '-x', 'openskey']);
    await expect
      .poll(() => docker(['exec', NAME, 'bash', '-c', 'pgrep -x openskey | head -1 || true']).trim(), { timeout: 90_000 })
      .not.toBe('');
    const after = docker(['exec', NAME, 'bash', '-c', 'pgrep -x openskey | head -1']).trim();
    expect(after).not.toBe(before);
    expect(scannerLog()).toContain('watchdog: openskey is not running, starting it');
  });
});
