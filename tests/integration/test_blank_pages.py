"""Exercise the image's PDF tools without a scanner or extra Python packages."""

import contextlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, "/opt/brother/scanner/brscan-skey/script")
import scanner


def make_pdf(path, labels):
    """Write a PDF with blank pages or black rectangles and identifying text."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = []
    for label in labels:
        page = len(objects) + 1
        kids.append(f"{page} 0 R")
        objects.append(
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 400] "
             f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page + 1} 0 R >>").encode()
        )
        content = (
            f"0 g 30 70 240 200 re f BT /F1 18 Tf 30 310 Td ({label}) Tj ET"
            if label else ""
        ).encode()
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
    objects[1] = f'<< /Type /Pages /Count {len(labels)} /Kids [{" ".join(kids)}] >>'.encode()
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        (f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
         f"startxref\n{xref}\n%%EOF\n").encode()
    )
    path.write_bytes(data)


class BlankPageIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        # remove_blank_pages changes cwd; restore it before deleting the fixture.
        self.addCleanup(os.chdir, os.getcwd())
        self.root = Path(self.directory.name)

    def process(self, path):
        # Subprocess output needs a real file descriptor, not StringIO.
        with tempfile.TemporaryFile(mode="w+") as log:
            try:
                with contextlib.redirect_stdout(log):
                    scanner.remove_blank_pages(log, str(path), 0.55)
            finally:
                log.seek(0)
                print(log.read())

    def test_mixed_pages_preserve_content_and_order(self):
        pdf = self.root / "scan with spaces.pdf"
        labels = [f"PAGE-{number:02d}" if number not in (2, 11) else "" for number in range(1, 13)]
        make_pdf(pdf, labels)
        subprocess.run(["qpdf", "--check", str(pdf)], check=True)

        self.process(pdf)

        subprocess.run(["qpdf", "--check", str(pdf)], check=True)
        count = subprocess.check_output(["qpdf", "--show-npages", str(pdf)], text=True)
        self.assertEqual(count.strip(), "10")
        text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
        pages = text.split("\f")
        self.assertEqual(pages.pop(), "")
        self.assertEqual([page.strip() for page in pages], [label for label in labels if label])

    def assert_preserved(self, labels):
        pdf = self.root / "original.pdf"
        make_pdf(pdf, labels)
        original = pdf.read_bytes()
        self.process(pdf)
        self.assertEqual(pdf.read_bytes(), original)

    def test_all_blank_preserves_original_bytes(self):
        self.assert_preserved(["", ""])

    def test_no_blanks_preserves_original_bytes(self):
        self.assert_preserved(["FIRST", "SECOND"])

    def test_unreadable_input_preserves_original_bytes(self):
        pdf = self.root / "broken.pdf"
        pdf.write_bytes(b"not a PDF")
        self.process(pdf)
        self.assertEqual(pdf.read_bytes(), b"not a PDF")


if __name__ == "__main__":
    unittest.main(verbosity=2)
