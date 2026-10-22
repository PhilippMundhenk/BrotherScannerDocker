# Web UI and API

[Back to the README](../README.md)

The image comes with an integrated web server for the web UI and the REST API. Enable it with `WEBSERVER=true`; the port is 80 unless `PORT` says otherwise. Individual actions can be renamed and hidden:

```
- WEBSERVER=true # optional, activates GUI & API
- PORT=33355 # optional, sets port for webserver (default: 80)
- DISABLE_GUI_SCANTOIMAGE=true # optional, deactivates button "Scan to image"
- DISABLE_GUI_SCANTOOCR=true # optional, deactivates button "Scan to OCR"
- RENAME_GUI_SCANTOFILE="Scan front pages" # optional, renames button "Scan to file" to "Scan front pages"
- RENAME_GUI_SCANTOEMAIL="Scan rear pages" # optional, renames button "Scan to email" to "Scan rear pages"
```

## The pages

The web UI is at the container's address and port. One button per enabled action starts a scan; the status under the model name follows the scanner (ready, scanning, waiting for rear pages, OCR running) and shows the OCR queue while something is queued.

![Screenshot of the main web interface](gui-main.png)

Below the status, an "Options" toggle opens three selectors for the resolution, colour mode and paper source the device listed at startup (`scanimage -A`), with the container's setting as default. The choice is remembered in the browser, shown on the toggle ("Options: 200 dpi, True Gray") and sent with every scan started from the page. A selector is hidden when the device did not report options for it.

The file list (PDF icon, top right) shows the scans newest first, with a thumbnail, size and date, a download button and, with `ALLOW_GUI_FILEOPERATIONS=true`, rename and delete:

![Screenshot of the file list](gui-filelist.png)

Every entry shows the top of the first page as a thumbnail across the width of the list. Thumbnails are rendered once per file by the scan pipeline right after a scan (and, for existing scans, by a low-priority sweep at container start), cached in `/scans/.thumbnails` and loaded lazily, so a folder with a thousand scans stays fast; `GUI_THUMBNAILS=false` turns them off. A thumbnail that is still missing is rendered on request, as the scan user; when that fails the entry keeps a document icon and the log says why (`thumbnail failed for ...`).

The settings page (cog icon next to the model name) is described in [Configuration](configuration.md#settings-page).

The interface does not block when pressing a button; wait for a scan to complete before pressing another one.

## API

The web UI uses a REST API that other systems (Home Assistant, a control panel next to the scanner, scripts) can use as well. The full description is in [swagger.yaml](swagger.yaml).

Start a scan and get a job id back:

```
curl -X POST -d target=file http://<ContainerIP>:<Port>/api/scanner/scanto
{"message": "Scan triggered", "target": "file", "job": "2026-10-10-19-25-20", "status_url": "/api/jobs/2026-10-10-19-25-20"}
```

Optional form fields override the container settings for this job only: `resolution` (dpi), `mode` and `source` (the values the device lists at startup), and `wait=true` to answer only when the scan script has finished. `GET /api/scanner/scanto/<target>` does the same and always waits.

Follow the job:

```
curl http://<ContainerIP>:<Port>/api/jobs/2026-10-10-19-25-20
{"job": "...", "action": "file", "state": "waiting_for_rear", "pages": 2, "waiting_until": "...", ...}
```

States: `queued`, `scanning`, `waiting_for_rear`, `scanning_rear`, `converting`, `done` (with `file`, `file_url`, and `ocr` being `none`, `pending`, `in_progress`, `failed` or `done` with `ocr_file_url`), `failed` (with `error`). Every job also says who started it: `trigger` is `button` (the Scan-to-PC button on the device) or `api` (this API or the web UI); a button-started job carries what the button daemon reported under `button` (`function`, `seq`, `regid`, `params` with the per-press fields `p1`..`p4`), which only [openskey](https://github.com/PhilippMundhenk/openskey) hands on (Brother's `brscan-skey` reports nothing). `GET /api/jobs` lists the recent jobs, newest first. `POST /api/jobs/<id>/rear` scans the rear pages for that specific job while it is waiting for them (the "Scan to E-mail" action always addresses the latest job).

Other endpoints:

- `GET /api/actions` describes the available actions, their labels and the accepted parameters, plus the image version and the device (name, model, address and the mode/resolution/source options it listed at startup, for integrations like Home Assistant).
- `GET /api/scanner/status` reports `scan`, `waiting`, `ocr`, `reachable` (whether the device answered the last connection check), `buttons` (the Scan-to-PC button daemon runs) and `queue` (OCR jobs pending, in progress and failed, and whether the worker is holding back for a busy scanner).
- `GET /api/scanner/device` asks the scanner itself, over SNMP through the bundled [openskey](https://github.com/PhilippMundhenk/openskey): `registered` (the device currently lists this container as a Scan-to-PC destination), `model`, `serial`, `firmware`, the panel `display` line, and whether network scanning and the Scan-to-PC key are supported and enabled (`net_scanner_*`, `scan_key_*`). Scanner objects only. Answers are reused for `DEVICE_STATUS_CACHE_SECONDS`; `DEVICE_STATUS=false` turns the endpoint off (404).
- Files: `/api/file-list` (newest first; `?offset=N&limit=M` for one page, the `X-Total-Count` header carries the total), `/api/file/<name>/info`, `/api/file/<name>/download`, `/api/file/<name>/thumbnail`; with `ALLOW_GUI_FILEOPERATIONS=true` also rename (`PUT /api/file/<name>/rename`) and delete (`DELETE /api/file/<name>/delete`).
- Settings: `GET`/`PUT /api/settings` and `POST /api/settings/import-environment`, see [Configuration](configuration.md).

## API token

Set `API_TOKEN` to require a token for everything that starts a scan or changes a file: `Authorization: Bearer <token>`, the `X-API-Token` header, or a `token` field. The web UI sends it itself, so anyone who can open the UI can use the API, which is the same trust level as before.

## Deprecated endpoints

The endpoints of the web UI before the rewrite still answer so that existing automations keep working, but they are deprecated: `GET /active.php` returns the JSON of `/api/scanner/status`, `GET /scan.php?target=<file|email|image|OCR>` behaves like `GET /api/scanner/scanto/<target>`. `list.php` and `download.php` are gone; use `/api/file-list` and `/api/file/<name>/download`.
