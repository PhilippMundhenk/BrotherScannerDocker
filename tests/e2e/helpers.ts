import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import type { APIRequestContext } from '@playwright/test';

export const IMAGE = process.env.IMAGE || 'brotherscanner:e2e';
export const HOST_PORT = Number(process.env.E2E_PORT || 18080);
export const OUTPUT_DIR = path.join(__dirname, 'output');
export const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');
export const FIXTURES = path.join(__dirname, 'fixtures');

/** The sample PDF copied into /scans before the tests start. */
export const SAMPLE_FILE = '2026-01-02-03-04-05.pdf';

export interface State {
  container: string;
  ocrPort: number;
}

export function readState(): State {
  return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
}

export function docker(args: string[], input?: string): string {
  return execFileSync('docker', args, { encoding: 'utf8', input, stdio: ['pipe', 'pipe', 'pipe'] }).trim();
}

export function inContainer(args: string[]): string {
  return docker(['exec', readState().container, ...args]);
}

export interface FileInfo {
  file: string;
  name: string;
  size: number;
  fileModificationTime: number;
  mimetype: string;
}

export async function listFiles(request: APIRequestContext): Promise<FileInfo[]> {
  const res = await request.get('/api/file-list');
  if (!res.ok()) throw new Error(`file-list returned ${res.status()}`);
  return (await res.json()) as FileInfo[];
}

export async function scannerStatus(request: APIRequestContext): Promise<{ scan: boolean; waiting: boolean; ocr: boolean }> {
  const res = await request.get('/api/scanner/status');
  if (!res.ok()) throw new Error(`status returned ${res.status()}`);
  return res.json();
}

export async function triggerScan(request: APIRequestContext, target: string) {
  const res = await request.post('/api/scanner/scanto', { form: { target } });
  if (!res.ok()) throw new Error(`scanto ${target} returned ${res.status()}: ${await res.text()}`);
  return res.json();
}

/** Poll until a file that was not in `before` shows up (optionally matching a filter). */
export async function waitForNewFile(
  request: APIRequestContext,
  before: string[],
  timeoutMs: number,
  filter: (name: string) => boolean = () => true,
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const names = (await listFiles(request)).map((f) => f.file);
    const fresh = names.filter((n) => !before.includes(n) && filter(n));
    if (fresh.length > 0) return fresh[0];
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`no new file within ${timeoutMs} ms`);
}

export async function waitFor(predicate: () => Promise<boolean>, timeoutMs: number, what: string): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`timed out after ${timeoutMs} ms waiting for ${what}`);
}

/** Page count of a PDF inside the container's /scans, via pdftk's companion pdfinfo. */
export function pdfPageCount(file: string): number {
  const info = inContainer(['pdfinfo', `/scans/${file}`]);
  const match = /^Pages:\s+(\d+)/m.exec(info);
  if (!match) throw new Error(`pdfinfo gave no page count for ${file}: ${info}`);
  return Number(match[1]);
}

/** Page size line from pdfinfo, e.g. "595 x 842 pts (A4)". */
export function pdfPageSize(file: string): string {
  const info = inContainer(['pdfinfo', `/scans/${file}`]);
  const match = /^Page size:\s+(.+)$/m.exec(info);
  return match ? match[1].trim() : '';
}

export function ownerOf(file: string): string {
  return inContainer(['stat', '-c', '%U', `/scans/${file}`]);
}

/** Wait until no OCR job is pending or in progress (the 'ocr' status flag only reflects a running curl). */
export async function waitForQueueIdle(timeoutMs: number): Promise<void> {
  await waitFor(async () => {
    const q = queueContents();
    return q.pending.length === 0 && q.in_progress.length === 0;
  }, timeoutMs, 'OCR queue to drain');
}

export function queueContents(): Record<string, string[]> {
  const out = inContainer(['bash', '-c', 'for d in pending in_progress failed; do echo "$d:$(ls /scans/.ocr_queue/$d 2>/dev/null | tr "\\n" " ")"; done']);
  const result: Record<string, string[]> = {};
  for (const line of out.split('\n')) {
    const [dir, files] = line.split(':');
    result[dir] = files.trim() ? files.trim().split(' ') : [];
  }
  return result;
}
