# Configuration

[Back to the README](../README.md)

Every setting can be given as an environment variable in the compose file, as a line in the configuration file on the volume, or on the settings page of the web UI (which writes that file).

## Precedence

A value set in the container environment wins over the configuration file, and the file wins over the built-in default. The settings page shows where each value comes from: an `environment` badge means the compose file (or `docker run -e`) sets it and it is read-only on the page; a `file` badge means the configuration file; no badge means the default, shown as placeholder.

## Options

| Variable                                 | Type      | Description                                                                                                                                      |
| ---------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| NAME                                     | mandatory | Arbitrary (avoid spaces) name to give your scanner. Displayed on scanner, if multiple servers are running.                                       |
| MODEL                                    | mandatory | Model of your scanner (e.g., MFC-L2700DW)                                                                                                        |
| IPADDRESS                                | mandatory | IP Address of your scanner                                                                                                                       |
| SCANNER_DRIVER | optional | `auto`, `brscan4` or `brscan5`. Which Brother SANE driver registers and drives the device; `auto` takes brscan4 when it knows the model and brscan5 otherwise (default: auto, see [Setup](setup.md#scanner-driver)) |
| HOST_IPADDRESS | optional | IP address under which the scanner reaches this container (bridged networking, see [Setup](setup.md)); empty for host networking |
| TZ | optional | Time zone for file names, logs and the web UI, e.g. `Europe/Berlin` (default: UTC) |
| RESOLUTION                               | optional  | DPI resolution of scan, refer to capabilities of printer on startup                                                                              |
| SCAN_MODE | optional | Scan mode as listed by the device in the capabilities at startup, e.g. `True Gray` or `Black & White` (default: device default, usually 24-bit colour). Scan to OCR uses `True Gray` unless this is set |
| SCAN_SOURCE | optional | Paper source as listed by the device at startup, e.g. `Automatic Document Feeder(left aligned,Duplex)` on duplex models or `FlatBed` (default: device default) |
| SCAN_LEFT_MM, SCAN_TOP_MM, SCAN_WIDTH_MM, SCAN_HEIGHT_MM | optional | Scan window in millimetres (defaults 0, 0, 215, 297). Use to calibrate the page position, e.g. `SCAN_HEIGHT_MM=295` removes the bar at the bottom of ADF scans |
| REAR_PAGE_WAIT_SECONDS | optional | How long a front scan waits for a rear scan before it is converted to PDF (default: 120) |
| REMOVE_BLANK_THRESHOLD                   | optional  | Percentage of content in page until which a page is considered blank. A good default is 0.3. Blank pages are removed if this variable is defined |
| REMOVE_ORIGINAL_AFTER_OCR                | optional  | Deletes the original scan, once OCR file is saved (default: false)                                                                               |
| FTP_USER                                 | optional  | Username of an FTP(S) server to upload the completed scan to (see [Uploads and notifications](notifications.md))                                 |
| FTP_PASSWORD                             | optional  | Password of an FTP(S) server to upload the completed scan to                                                                                     |
| FTP_HOST                                 | optional  | Address of an FTP(S) server to upload the completed scan to                                                                                      |
| FTP_PATH                                 | optional  | Path of an FTP(S) server to upload the completed scan to                                                                                         |
| FTP_INSECURE | optional | Set to "true" to upload via plain FTP instead of requiring TLS (FTPS). Credentials and files then travel unencrypted (default: false) |
| SSH_USER                                 | optional  | Username for an SSH connection to trigger inotify (see [Uploads and notifications](notifications.md))                                            |
| SSH_PASSWORD                             | optional  | Password for an SSH connection to trigger inotify                                                                                                |
| SSH_HOST                                 | optional  | Address for an SSH connection to trigger inotify                                                                                                 |
| SSH_PATH                                 | optional  | Path for an SSH connection to trigger inotify                                                                                                    |
| OCR_SERVER                               | optional  | Hostname of an OCR server (see [OCR](ocr.md))                                                                                                    |
| OCR_PORT                                 | optional  | Port of an OCR server                                                                                                                            |
| OCR_PATH                                 | optional  | Path of an OCR server                                                                                                                            |
| OCR_QUEUE_DIR | optional | Directory of the OCR upload queue, must be on the persistent volume (default: /scans/.ocr_queue) |
| OCR_QUEUE_POLL_SECONDS | optional | How often the OCR worker checks for queued uploads in seconds (default: 5) |
| OCR_MAX_ATTEMPTS | optional | Upload attempts per scan before it is moved to the failed/ folder of the queue (default: 5) |
| OCR_WAIT_FOR_IDLE_SCANNER | optional | Set to "false" to let OCR uploads run while the scanner is busy (default: true, uploads wait for the scanner to be idle) |
| OCR_UPLOAD_LIMIT_RATE | optional | Bandwidth limit for OCR uploads and downloads in curl syntax, e.g. 2M (default: unlimited) |
| WEBSERVER                                | optional  | activates GUI & API (default:false) (see [Web UI and API](web-ui.md))                                                                            |
| PORT                                     | optional  | sets port for webserver (default: 80)                                                                                                            |
| KEEPALIVE                                | optional  | set to "false" to disable the periodic Scan-to-PC re-registration keepalive (default: true)                                                      |
| KEEPALIVE_INTERVAL                       | optional  | seconds between keepalive re-registrations; must stay below the device-side lease of 360s (default: 120). The refresh is skipped while a scan is running or a front scan is waiting for rear pages, so it never interferes with an active job                                         |
| DISABLE_GUI_SCANTOFILE                   | optional  | deactivates button "Scan to file" (default: false)                                                                                               |
| DISABLE_GUI_SCANTOEMAIL                  | optional  | deactivates button "Scan to e-mail"                                                                                                              |
| DISABLE_GUI_SCANTOIMAGE                  | optional  | deactivates button "Scan to image"                                                                                                               |
| DISABLE_GUI_SCANTOOCR                    | optional  | deactivates button "Scan to OCR"                                                                                                                 |
| RENAME_GUI_SCANTOFILE="Scan front pages" | optional  | renames GUI button "Scan to file" to "Scan front pages"                                                                                          |
| RENAME_GUI_SCANTOEMAIL="Scan rear pages" | optional  | renames GUI button "Scan to email" to "Scan rear pages"                                                                                          |
| RENAME_GUI_SCANTOIMAGE="Scan photo"      | optional  | renames GUI button "Scan to image" to "Scan photo"                                                                                               |
| RENAME_GUI_SCANTOOCR="Scan High-Res"     | optional  | renames GUI button "Scan to OCR" to "Scan High-Res"                                                                                              |
| USE_JPEG_COMPRESSION | optional | use JPEG compression when creating PDFs; a 300 dpi colour page shrinks from about 4 MB to a few hundred KB (default: false, lossless) |
| TELEGRAM_TOKEN                           | optional  | If TELEGRAM_TOKEN and TELEGRAM_CHATID are set, then this sends notification                                                                      |
| TELEGRAM_CHATID                          | optional  | If TELEGRAM_TOKEN and TELEGRAM_CHATID are set, then this sends notification                                                                      |
| ALLOW_GUI_FILEOPERATIONS                 | optional  | true/false. Let you delete and rename files in files list                                                                                        |
| GUI_THUMBNAILS | optional | true/false. Thumbnails of the top of the first page in the file list, rendered once per file after the scan and cached in `/scans/.thumbnails` (default: true) |
| ALLOW_GUI_SETTINGS | optional | true/false. Enables the settings page (`/settings`) and the settings API, which write the configuration file (default: false) |
| SCANNER_CONFIG_FILE | optional | Path of the configuration file inside the container (default: /scans/.config/scanner.conf) |
| API_TOKEN | optional | When set, every request that starts a scan or changes a file must carry it (`Authorization: Bearer <token>`, `X-API-Token` header, or a `token` field). The web UI sends it itself (default: no token) |
| SCANNER_PING_INTERVAL | optional | Seconds between checks whether the scanner answers on its scan port, reported as `reachable` by the status endpoint; 0 disables (default: 60) |
| FTP_PASSWORD_FILE, SSH_PASSWORD_FILE, TELEGRAM_TOKEN_FILE, FTP_USER_FILE, SSH_USER_FILE, TELEGRAM_CHATID_FILE | optional | Path of a file inside the container to read the value from, for Docker secrets (see below) |

Quotes around a value, as in the examples above, are optional; one pair of surrounding quotes is dropped.

## Configuration file

Every setting in the table can also be put into a configuration file instead of the compose file: `KEY=VALUE` lines in `/scans/.config/scanner.conf` (on the scans volume, so it survives container updates; change the path with `SCANNER_CONFIG_FILE`). Lines starting with `#` are ignored.

```
# /scans/.config/scanner.conf
RESOLUTION=200
SCAN_MODE=True Gray
REMOVE_BLANK_THRESHOLD=0.5
RENAME_GUI_SCANTOFILE=Scan front pages
```

Changes to scan, post-processing, OCR, notification and web UI settings take effect with the next scan or request. Settings that only the entrypoint reads (NAME, UID/GID, MODEL, IPADDRESS, HOST_IPADDRESS, PORT, TZ, KEEPALIVE*, SCANNER_PING_INTERVAL, API_TOKEN, ALLOW_GUI_SETTINGS) need a container restart; the settings page marks them with a `restart` badge.

## Settings page

![Screenshot of the settings page](gui-settings.png)

With `ALLOW_GUI_SETTINGS=true` the web UI gets a settings page (cog icon next to the model name, `/settings`) that shows every setting with its current value and where it comes from, and writes the file. Values set in the environment are shown read-only. The same is available as `GET`/`PUT /api/settings` (see [swagger.yaml](swagger.yaml)); `PUT` needs the API token when one is configured.

### Moving from environment variables to the file

The settings page has a button, "Copy environment values into the file", that copies every environment-set value (passwords and tokens included) into the configuration file (`POST /api/settings/import-environment`). The environment still wins afterwards: remove the entries from the compose file and restart the container, and the file carries on with the same values, now editable on the page. The result line names exactly the keys to remove.

## Secrets

Passwords and tokens do not have to be written into the compose file. Every one of `FTP_USER`, `FTP_PASSWORD`, `SSH_USER`, `SSH_PASSWORD`, `TELEGRAM_TOKEN` and `TELEGRAM_CHATID` can instead be given as `<VARIABLE>_FILE`, pointing to a file inside the container whose content is used as the value (trailing newlines are stripped). This is how Docker secrets are delivered:

```yaml
services:
  brother-scanner:
    image: ghcr.io/philippmundhenk/brotherscannerdocker:v2
    environment:
      - FTP_USER=scanner
      - FTP_PASSWORD_FILE=/run/secrets/ftp_password
      - TELEGRAM_TOKEN_FILE=/run/secrets/telegram_token
    secrets:
      - ftp_password
      - telegram_token

secrets:
  ftp_password:
    file: ./secrets/ftp_password.txt
  telegram_token:
    file: ./secrets/telegram_token.txt
```

A plain variable takes precedence over its `_FILE` counterpart when both are set. The values are only visible to the scanner user inside the container.
