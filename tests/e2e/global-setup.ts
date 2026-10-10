import * as fs from 'fs';
import * as http from 'http';
import * as path from 'path';
import { AddressInfo } from 'net';
import { docker, FIXTURES, HOST_PORT, IMAGE, OUTPUT_DIR, SAMPLE_FILE, STATE_FILE } from './helpers';

/**
 * Starts one container from the image under test with:
 *   - the scanner simulator mounted over /usr/bin/scanimage
 *   - the web UI on HOST_PORT
 *   - a fake OCR service running in this process, reachable from the
 *     container as host.docker.internal
 * and tears everything down (dumping the container log) when the run ends.
 */

function startFakeOcr(): Promise<http.Server> {
  const pdf = fs.readFileSync(path.join(FIXTURES, 'sample.pdf'));
  const server = http.createServer((req, res) => {
    // Drain the multipart upload, then answer with a PDF like the real service does.
    req.on('data', () => undefined);
    req.on('end', () => {
      if (req.method !== 'POST') {
        res.writeHead(405).end();
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/pdf' });
      res.end(pdf);
    });
  });
  return new Promise((resolve) => server.listen(0, '0.0.0.0', () => resolve(server)));
}

async function waitForUrl(url: string, timeoutMs: number, container: string) {
  const deadline = Date.now() + timeoutMs;
  let lastError = '';
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
      lastError = `HTTP ${res.status}`;
    } catch (error) {
      lastError = String(error);
    }
    const state = docker(['inspect', '-f', '{{.State.Running}}', container]);
    if (state !== 'true') {
      throw new Error(`container exited during startup:\n${docker(['logs', container])}`);
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`${url} not reachable within ${timeoutMs} ms (${lastError})\n${docker(['logs', container])}`);
}

export default async function globalSetup() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const ocr = await startFakeOcr();
  const ocrPort = (ocr.address() as AddressInfo).port;
  const name = `bsd-e2e-${process.pid}`;

  const args = [
    'run', '-d', '--name', name,
    '--add-host=host.docker.internal:host-gateway',
    '-p', `${HOST_PORT}:8080`,
    '-v', `${path.join(FIXTURES, 'scanimage')}:/usr/bin/scanimage:ro`,
    // Docker-secrets style delivery of one credential (see secrets.spec.ts)
    '-v', `${path.join(FIXTURES, 'ftp_password.txt')}:/run/secrets/ftp_password:ro`,
    '-e', 'FTP_PASSWORD_FILE=/run/secrets/ftp_password',
    '-e', 'WEBSERVER=true', '-e', 'PORT=8080',
    '-e', 'NAME=Scanner', '-e', 'MODEL=MFC-SIMULATOR', '-e', 'IPADDRESS=192.0.2.10',
    '-e', 'TZ=UTC', '-e', 'KEEPALIVE=false',
    '-e', 'REAR_PAGE_WAIT_SECONDS=6',
    '-e', 'ALLOW_GUI_FILEOPERATIONS=true',
    '-e', 'OCR_SERVER=host.docker.internal', '-e', `OCR_PORT=${ocrPort}`, '-e', 'OCR_PATH=ocr.php',
    '-e', 'OCR_QUEUE_POLL_SECONDS=1', '-e', 'OCR_RETRY_BACKOFF_SECONDS=1',
    '-e', 'SIM_PAGES=2', '-e', 'SIM_SCAN_SECONDS=0.5',
    IMAGE,
  ];
  console.log(`starting ${IMAGE} as ${name}`);
  const container = docker(args);
  fs.writeFileSync(STATE_FILE, JSON.stringify({ container: name, ocrPort }, null, 2));

  // Seed /scans with one known PDF for the file listing / download / rename / delete tests.
  docker(['cp', path.join(FIXTURES, 'sample.pdf'), `${name}:/scans/${SAMPLE_FILE}`]);
  docker(['exec', name, 'chmod', '666', `/scans/${SAMPLE_FILE}`]);

  await waitForUrl(`http://localhost:${HOST_PORT}/api/scanner/status`, 90_000, name);
  console.log(`container ${container.slice(0, 12)} ready on port ${HOST_PORT}, fake OCR on ${ocrPort}`);

  return async () => {
    try {
      fs.writeFileSync(path.join(OUTPUT_DIR, 'container.log'), docker(['logs', name]));
      fs.writeFileSync(path.join(OUTPUT_DIR, 'scanner.log'), docker(['exec', name, 'cat', '/var/log/scanner.log']));
    } catch (error) {
      console.warn('could not collect container logs:', error);
    }
    try {
      docker(['rm', '-f', name]);
    } catch (error) {
      console.warn('could not remove container:', error);
    }
    await new Promise<void>((resolve) => ocr.close(() => resolve()));
  };
}
