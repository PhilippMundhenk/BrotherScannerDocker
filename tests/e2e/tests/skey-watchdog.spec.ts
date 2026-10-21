import { expect, test } from '@playwright/test';
import * as path from 'path';
import { docker, FIXTURES, IMAGE } from '../helpers';

// brscan-skey leaks one UDP socket per registration cycle inside Brother's
// closed binary (#179): the daemon eventually hits its open-file limit and
// stops handling the scanner's front-panel buttons. The image contains the
// leak from the outside by (a) starting the daemon with its soft limit raised
// to the hard limit and (b) a watchdog that restarts the daemon when it has
// died or its open-file count has climbed toward the limit.
//
// These tests run the REAL Brother daemon (only scanimage is faked) against an
// unreachable device address, which still reaches the leaking socket-open step,
// so the leak really happens here. They assert the mitigation holds for both
// the brscan4 and the brscan5 registration path, so a future driver bump that
// changes this behaviour is caught. A low SKEY_WATCHDOG_MAX_FDS makes the
// fd-based restart fire within the test window instead of after years.
//
// If a future driver stops leaking, the "restarts at least once" check will
// fail: that is the intended signal to re-evaluate whether the watchdog is
// still needed, not a flake.

interface Model {
  label: string;
  model: string;
  driver: string;
}

const MODELS: Model[] = [
  { label: 'brscan4', model: 'MFC-L2700DW', driver: 'brscan4' },
  { label: 'brscan5', model: 'DS-940DW', driver: 'brscan5' },
];

const MAX_FDS = 25;
const CEILING = 90; // MAX_FDS plus a generous margin for growth between checks
let port = Number(process.env.E2E_WATCHDOG_PORT || 18110);

function daemonPid(name: string): string {
  return docker(['exec', name, 'bash', '-c', 'pgrep -x brscan-skey-exe | head -1']).trim();
}

function daemonFds(name: string, pid: string): number {
  if (!pid) return 0;
  const out = docker(['exec', name, 'bash', '-c', `find /proc/${pid}/fd -mindepth 1 2>/dev/null | wc -l`]).trim();
  return Number(out) || 0;
}

function restartCount(name: string): number {
  const out = docker([
    'exec', name, 'bash', '-c',
    'grep -c "restarting to release leaked sockets" /var/log/scanner.log 2>/dev/null || true',
  ]).trim();
  return Number(out) || 0;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

for (const m of MODELS) {
  test.describe(`brscan-skey watchdog (${m.label}, ${m.model})`, () => {
    const NAME = `bsd-e2e-watchdog-${m.label}-${process.pid}`;
    const PORT = port++;

    test.beforeAll(async () => {
      docker([
        'run', '-d', '--name', NAME, '-p', `${PORT}:8080`,
        '-v', `${path.join(FIXTURES, 'scanimage')}:/usr/bin/scanimage:ro`,
        '-e', 'WEBSERVER=true', '-e', 'PORT=8080',
        '-e', 'NAME=Scanner', '-e', `MODEL=${m.model}`, '-e', 'IPADDRESS=192.0.2.10',
        '-e', 'SCANNER_PING_INTERVAL=0',
        // drive the leak fast and keep the watchdog on a short leash so the
        // fd-based restart happens inside the test window
        '-e', 'KEEPALIVE_INTERVAL=1',
        '-e', 'SKEY_WATCHDOG_INTERVAL=2', '-e', `SKEY_WATCHDOG_MAX_FDS=${MAX_FDS}`,
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
      if (!up) throw new Error(`watchdog container not reachable:\n${docker(['logs', NAME])}`);
    });

    test.afterAll(async () => {
      try {
        docker(['rm', '-f', NAME]);
      } catch {
        /* already gone */
      }
    });

    test(`picks the ${m.driver} driver and reports the buttons as up`, async () => {
      expect(docker(['logs', NAME])).toContain(`scanner driver: ${m.driver} for model ${m.model}`);
      const status = await (await fetch(`http://localhost:${PORT}/api/scanner/status`)).json();
      expect(status.buttons).toBe(true);
    });

    test('starts the daemon with the soft open-file limit raised above the default 1024', () => {
      const pid = daemonPid(NAME);
      expect(pid).not.toBe('');
      const soft = Number(
        docker(['exec', NAME, 'bash', '-c', `awk '/Max open files/{print $4}' /proc/${pid}/limits`]).trim(),
      );
      expect(soft).toBeGreaterThan(1024);
    });

    test('the watchdog revives the daemon after it dies', async () => {
      const before = daemonPid(NAME);
      expect(before).not.toBe('');
      docker(['exec', NAME, 'pkill', '-x', 'brscan-skey-exe']);
      let after = '';
      const deadline = Date.now() + 20_000;
      while (Date.now() < deadline) {
        await sleep(1000);
        after = daemonPid(NAME);
        if (after && after !== before) break;
      }
      expect(after).not.toBe('');
      expect(after).not.toBe(before);
      const status = await (await fetch(`http://localhost:${PORT}/api/scanner/status`)).json();
      expect(status.buttons).toBe(true);
    });

    test('contains the socket leak: fd count stays bounded and the daemon stays alive', async () => {
      let maxFds = 0;
      let deadMisses = 0;
      const deadline = Date.now() + 100_000;
      while (Date.now() < deadline) {
        const pid = daemonPid(NAME);
        if (!pid) {
          deadMisses++; // a brief gap during a restart is fine
        } else {
          deadMisses = 0;
          maxFds = Math.max(maxFds, daemonFds(NAME, pid));
        }
        // never missing for long: the restart gap is about a second
        expect(deadMisses).toBeLessThan(4);
        // never allowed to run away
        expect(maxFds).toBeLessThan(CEILING);
        if (restartCount(NAME) >= 1) break;
        await sleep(2000);
      }
      // The watchdog restarts the daemon only once its open files reach the
      // ceiling, so at least one restart proves both that the leak climbed to
      // the limit and that the watchdog contained it. (maxFds is not asserted
      // to reach the ceiling: the watchdog resets it between our samples, so
      // polling can miss the exact peak.)
      expect(restartCount(NAME)).toBeGreaterThanOrEqual(1);
      expect(maxFds).toBeLessThan(CEILING);
      // and the daemon is alive at the end, so the buttons work
      expect(daemonPid(NAME)).not.toBe('');
    });
  });
}
