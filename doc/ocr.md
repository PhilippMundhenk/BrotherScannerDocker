# OCR

[Back to the README](../README.md)

The image is prepared to use an OCR service such as [TesseractOCRMicroservice](https://github.com/PhilippMundhenk/TesseractOCRMicroservice): every finished scan is uploaded, the service runs OCR, and the result is downloaded next to the scan with `-ocr` appended to the file name.

```
- OCR_SERVER=192.168.1.101
- OCR_PORT=8080
- OCR_PATH=ocr.php
```

This calls the OCR service at `https://192.168.1.101:8080/ocr.php`.

## The queue

Uploads are serialized through a persistent on-disk queue in `/scans/.ocr_queue` (`OCR_QUEUE_DIR`), so several scans in quick succession do not compete for upload bandwidth. Failed uploads are retried with increasing delay and end up in `/scans/.ocr_queue/failed/` after `OCR_MAX_ATTEMPTS` attempts. The queue survives container restarts; the web UI shows it under the status while something is queued, and the status endpoint reports it.

Uploads never start while the scanner is busy: scanning has priority and OCR waits for the scanner to be idle (`OCR_WAIT_FOR_IDLE_SCANNER`); `OCR_UPLOAD_LIMIT_RATE` can additionally cap the transfer rate so the scanner keeps enough network bandwidth.

## Validation of results

Every OCR result is checked before it is used: it must be a PDF that `pdfinfo` can read and it must have the same number of pages as the scan. A response that fails this check (for example the error text the OCR service sends when tesseract fails) is kept under `/scans/.ocr_queue/failed/` for inspection and the upload is retried; the scan itself is never touched. With `REMOVE_ORIGINAL_AFTER_OCR=true` the original is deleted only after a validated OCR copy is in place.

## Size of the OCR copy

The OCR service keeps the page images it receives, so the scan mode and `USE_JPEG_COMPRESSION` decide the size of the OCR copy as well; see [File sizes](setup.md#file-sizes).
