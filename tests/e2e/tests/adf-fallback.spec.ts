import { expect, test } from '@playwright/test';
import * as path from 'path';
import { docker, FIXTURES, IMAGE } from '../helpers';

// brscan5 aborts a scan with "Document feeder out of documents" when the ADF is
// empty, where brscan4 silently scanned from the flatbed. When no source was
// chosen, the pipeline now retries once from the flatbed, so one button works
// for both the feeder and the glass (#180). The simulator reproduces the
// brscan5 behaviour with SIM_ADF_EMPTY=true.

const PORT = Number(process.env.E2E_ADF_PORT || 18120);
const NAME = `bsd-e2e-adf-${process.pid}`;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function fileList(): Promise<string[]> {
  const res = await fetch(`http://localhost:${PORT}/api/file-list`);
  if (!res.ok) return [];
  return ((await res.json()) as { file: string }[]).map((f) => f.file);
}

test.describe('ADF-empty fallback to the flatbed', () => {
  test.beforeAll(async () => {
    docker([
      'run', '-d', '--name', NAME, '-p', `${PORT}:8080`,
      '-v', `${path.join(FIXTURES, 'scanimage')}:/usr/bin/scanimage:ro`,
      '-e', 'WEBSERVER=true', '-e', 'PORT=8080',
      '-e', 'NAME=Scanner', '-e', 'MODEL=DS-940DW', '-e', 'IPADDRESS=192.0.2.10',
      '-e', 'KEEPALIVE=false', '-e', 'SCANNER_PING_INTERVAL=0', '-e', 'GUI_THUMBNAILS=false',
      '-e', 'RESOLUTION=100', '-e', 'REAR_PAGE_WAIT_SECONDS=3', '-e', 'SIM_PAGES=1',
      // the feeder is empty: a scan from it fails, a scan from the glass works
      '-e', 'SIM_ADF_EMPTY=true',
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
    if (!up) throw new Error(`adf container not reachable:\n${docker(['logs', NAME])}`);
  });

  test.afterAll(async () => {
    try {
      docker(['rm', '-f', NAME]);
    } catch {
      /* already gone */
    }
  });

  test('the device lists a flatbed, so the fallback is possible', () => {
    const caps = docker(['exec', NAME, 'cat', '/tmp/SCANNER_CAPABILITIES']);
    expect(caps.toLowerCase()).toContain('flatbed');
  });

  test('a scan with an empty feeder still produces a file, via the flatbed', async () => {
    const before = await fileList();
    const res = await fetch(`http://localhost:${PORT}/api/scanner/scanto`, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ target: 'file' }).toString(),
    });
    expect(res.ok).toBe(true);

    let fresh = '';
    const deadline = Date.now() + 40_000;
    while (Date.now() < deadline && !fresh) {
      await sleep(1000);
      fresh = (await fileList()).find((n) => !before.includes(n) && n.endsWith('.pdf')) || '';
    }
    expect(fresh, 'a PDF appeared after the flatbed retry').not.toBe('');

    // the pipeline logged the retry, and did not fall over
    const log = docker(['exec', NAME, 'cat', '/var/log/scanner.log']);
    expect(log).toContain('retrying the scan from the flatbed');
  });
});
