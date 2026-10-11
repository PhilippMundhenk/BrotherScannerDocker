# Migrating from v1 to v2

[Back to the README](../README.md)

A v1 compose file keeps working with the v2 image. This page lists what changed and what is worth doing afterwards.

## Settings: file and settings page

Every setting that was an environment variable can now also be a `KEY=VALUE` line in `/scans/.config/scanner.conf` on the volume, and with `ALLOW_GUI_SETTINGS=true` the web UI gets a settings page (cog icon next to the model name) that edits that file. The page shows every setting with its current value and where it comes from.

The precedence is: **environment wins over the file, the file wins over the default.** A value from the compose file is read-only on the page and carries an `environment` badge. To manage settings on the page:

1. Open the settings page and press "Copy environment values into the file". Every environment-set value, passwords and tokens included, is written into the configuration file; the result names the keys.
2. Remove those entries from the compose file (keep the mandatory NAME, MODEL and IPADDRESS wherever you like; they work from the file as well) and restart the container.
3. The file carries on with the same values, and the badges turn from `environment` into `file`.

Details: [Configuration](configuration.md).

## Web UI and API

The web UI was rewritten: status, OCR queue, file list with thumbnails, rename and delete, scan options (resolution, mode, source) and the settings page. The REST API is new and documented in [swagger.yaml](swagger.yaml): jobs with states, per-scan parameters, `wait=true`, status with reachability and queue, file endpoints, settings.

The old endpoints still answer, deprecated: `scan.php?target=...` behaves like `GET /api/scanner/scanto/<target>`, `active.php` returns the JSON of `/api/scanner/status`. `list.php` and `download.php` are gone; use `/api/file-list` and `/api/file/<name>/download`. An `API_TOKEN` can now protect everything that starts a scan or changes a file.

## OCR

Uploads go through a persistent queue, never run while the scanner is busy, and every result is validated (readable PDF, same page count) before it is used; with `REMOVE_ORIGINAL_AFTER_OCR=true` the original is removed only after a validated copy is in place. New options: `OCR_QUEUE_DIR`, `OCR_QUEUE_POLL_SECONDS`, `OCR_MAX_ATTEMPTS`, `OCR_WAIT_FOR_IDLE_SCANNER`, `OCR_UPLOAD_LIMIT_RATE`. See [OCR](ocr.md).

## Scanning

`SCAN_MODE`, `SCAN_SOURCE` (duplex ADFs scan both sides in one pass), the scan window (`SCAN_*_MM`) for calibration, `REAR_PAGE_WAIT_SECONDS`, `USE_JPEG_COMPRESSION` and `KEEPALIVE_INTERVAL` are new; the Scan-to-PC registration is refreshed periodically so the destination does not disappear from the device. Plain FTP needs an explicit `FTP_INSECURE=true`; secrets can come from files (`*_FILE`). See [Setup](setup.md) and [Configuration](configuration.md).

## Home Assistant

A Home Assistant integration and a dashboard card are available; see [Home Assistant](home-assistant.md). A `rest` sensor on `active.php` from v1 keeps working.

## Image

The image is based on `python:slim-bookworm`; the scan scripts are Python (`script/*.py`). If you mounted your own shell scripts over `script/`, port them (see [Customizing the scan scripts](customizing.md)).
