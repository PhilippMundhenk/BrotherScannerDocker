import * as http from 'http';

/**
 * Fake OCR microservice for the end-to-end tests.
 *
 * Like the real TesseractOCRMicroservice it takes a multipart upload with a
 * PDF in the `userfile` field and answers with a PDF. The answer has the same
 * number of pages as the upload (the real service keeps the page count), so
 * the worker's validation accepts it.
 *
 * POST /mode/<name> switches the behaviour for the following uploads:
 *   pdf      (default) a valid PDF with the uploaded page count
 *   garbage  HTTP 200 with the text "Error: File not found." (what the real
 *            service sends when tesseract fails)
 *   empty    HTTP 200 with an empty body
 *   error    HTTP 500
 *   short    HTTP 200 with a valid PDF that has one page fewer than the upload
 */
export type OcrMode = 'pdf' | 'garbage' | 'empty' | 'error' | 'short';

/** Count the page objects of a PDF (not the /Pages tree node). */
export function countPdfPages(pdf: Buffer): number {
  const matches = pdf.toString('latin1').match(/\/Type\s*\/Page(?![s\w])/g);
  return matches ? matches.length : 0;
}

/** Build a minimal but well-formed PDF with `pages` blank A4 pages (pdfinfo-readable). */
export function buildPdf(pages: number, label = 'fake OCR output'): Buffer {
  const objects: string[] = [];
  const kids = Array.from({ length: pages }, (_, i) => `${3 + i} 0 R`).join(' ');
  objects.push('<< /Type /Catalog /Pages 2 0 R >>');
  objects.push(`<< /Type /Pages /Kids [${kids}] /Count ${pages} >>`);
  const contentsStart = 3 + pages;
  for (let i = 0; i < pages; i++) {
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${contentsStart + i} 0 R /Resources << /Font << /F1 ${contentsStart + pages} 0 R >> >> >>`);
  }
  for (let i = 0; i < pages; i++) {
    const text = `BT /F1 12 Tf 72 800 Td (${label} page ${i + 1}) Tj ET`;
    objects.push(`<< /Length ${text.length} >>\nstream\n${text}\nendstream`);
  }
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');

  let body = '%PDF-1.4\n';
  const offsets: number[] = [];
  objects.forEach((obj, index) => {
    offsets.push(Buffer.byteLength(body, 'latin1'));
    body += `${index + 1} 0 obj\n${obj}\nendobj\n`;
  });
  const xrefOffset = Buffer.byteLength(body, 'latin1');
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) {
    body += `${String(offset).padStart(10, '0')} 00000 n \n`;
  }
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(body, 'latin1');
}

export function startFakeOcr(): Promise<http.Server> {
  let mode: OcrMode = 'pdf';
  const server = http.createServer((req, res) => {
    const modeMatch = /^\/mode\/(pdf|garbage|empty|error|short)$/.exec(req.url || '');
    if (modeMatch && req.method === 'POST') {
      mode = modeMatch[1] as OcrMode;
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(`mode ${mode}`);
      return;
    }
    const chunks: Buffer[] = [];
    req.on('data', (chunk: Buffer) => chunks.push(chunk));
    req.on('end', () => {
      if (req.method !== 'POST') {
        res.writeHead(405).end();
        return;
      }
      const uploadedPages = Math.max(1, countPdfPages(Buffer.concat(chunks)));
      switch (mode) {
        case 'garbage':
          res.writeHead(200, { 'Content-Type': 'application/zip' });
          res.end('Error: File not found.');
          return;
        case 'empty':
          res.writeHead(200, { 'Content-Type': 'application/pdf' });
          res.end();
          return;
        case 'error':
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end('Error! Internal Server Error');
          return;
        case 'short':
          res.writeHead(200, { 'Content-Type': 'application/pdf' });
          res.end(buildPdf(Math.max(1, uploadedPages - 1)));
          return;
        default:
          res.writeHead(200, { 'Content-Type': 'application/pdf' });
          res.end(buildPdf(uploadedPages));
      }
    });
  });
  return new Promise((resolve) => server.listen(0, '0.0.0.0', () => resolve(server)));
}
