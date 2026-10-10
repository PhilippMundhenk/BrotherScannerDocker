/**
 * Takes the README screenshots from a running container (not part of the test
 * run). Usage, from tests/e2e with the e2e image running on E2E_PORT:
 *
 *   npx tsx screenshots.ts http://localhost:18080 ../../doc
 *
 * Writes gui-main.png, gui-filelist.png and gui-settings.png. The container
 * should have a few PDFs in /scans and ALLOW_GUI_FILEOPERATIONS /
 * ALLOW_GUI_SETTINGS enabled so the screenshots show every feature.
 */
import { chromium } from '@playwright/test';
import * as path from 'path';

async function main() {
  const base = process.argv[2] || 'http://localhost:18080';
  const out = process.argv[3] || path.join(__dirname, '..', '..', 'doc');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1000, height: 720 }, deviceScaleFactor: 1 });
  await page.goto(base + '/');
  await page.waitForSelector('.trigger-scan');
  await page.waitForTimeout(1500); // status poll, icons
  await page.screenshot({ path: path.join(out, 'gui-main.png') });

  await page.locator('#triggerFiles').click();
  await page.waitForSelector('#offcanvasFiles .list-group-item');
  await page.waitForTimeout(1500); // thumbnails
  await page.screenshot({ path: path.join(out, 'gui-filelist.png') });

  await page.goto(base + '/settings');
  await page.waitForSelector('form');
  await page.screenshot({ path: path.join(out, 'gui-settings.png'), fullPage: false });
  await browser.close();
  console.log(`screenshots written to ${out}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
