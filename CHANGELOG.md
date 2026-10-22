# Changelog

All notable changes to the container. The Home Assistant integration and the dashboard card have their own release notes in their repositories.

## 2.2.0 (unreleased)

### Added

- Every scan job records who started it: `trigger` is `button` (the Scan-to-PC button on the device) or `api` (REST API / web UI), and a button-started job carries what the button daemon reported under `button` (function, sequence number, the per-press fields P1..P4) when the daemon hands them on, so Home Assistant can react to a button press on the scanner as such (#187).

### Fixed

- The scanner's front-panel Scan-to-PC buttons no longer stop working after a few days. Brother's `brscan-skey` daemon leaks a network socket on every registration cycle until it hits its open-file limit; the image now starts the daemon with a raised limit and a watchdog that restarts it if it dies or climbs toward the limit, never during a scan (#179). `SKEY_WATCHDOG`, `SKEY_WATCHDOG_INTERVAL`, `SKEY_WATCHDOG_THRESHOLD` and `SKEY_WATCHDOG_MAX_FDS` configure it; `GET /api/scanner/status` gains a `buttons` field.
- A scan that finds the document feeder empty is retried once from the flatbed, so a single button works for both the feeder and the glass again. brscan5 aborts an empty-feeder scan where brscan4 used to fall back to the glass; the retry restores that for newer models (#180). An explicit `SCAN_SOURCE` or `SCANNER_DRIVER=brscan4` keeps the previous behaviour.

## 2.1.0 (2026-10-14)

### Added

- Brother's `brscan5` driver next to `brscan4`; the entrypoint registers the model with brscan4 and, when that driver does not know it, with brscan5. `SCANNER_DRIVER=auto|brscan4|brscan5` (#173, #176). Fixes the partial pages of the DS-940DW, which brscan4 had been driving with a generic profile (#75).

### Fixed

- `@`-suppressed PHP warnings no longer reach the log (`mkdir(): File exists` on every trigger) (#174, #175).

## 2.0.0 (2026-10-11)

The first release in over a year and the largest since the project started. A v1 compose file keeps working as it is; the [migration guide](doc/migration.md) lists what changed and what is worth doing afterwards.

### Added

- Web UI: status with the OCR queue, one button per action, resolution/mode/source selectors behind an "Options" toggle, a file list that loads in batches with thumbnails of the first page, rename and delete, a settings page (#57, #118, #133, #135, #146, #151, #154, #166). Built on the routing rewrite by @vgarcia007.
- REST API: start scans with per-job parameters, jobs with ids and states, rear scan per job, status with device reachability and queue, file endpoints, device info and capabilities, optional `API_TOKEN` (#131, #136). Described in [doc/swagger.yaml](doc/swagger.yaml).
- Configuration file `/scans/.config/scanner.conf` next to the environment, and a settings page with `ALLOW_GUI_SETTINGS=true`; the environment wins over the file; a button copies environment values into the file (#134, #160, #162).
- OCR queue: uploads serialized through a persistent queue on the volume, retried with backoff, never while the scanner is busy; every result validated before use (#85, #98, #113, #117).
- Home Assistant integration and dashboard card, through HACS (#129, #136).
- Scanning: `SCAN_MODE` (gray, black and white), `SCAN_SOURCE` (duplex ADF in one pass), a configurable scan window (`SCAN_LEFT_MM`, `SCAN_TOP_MM`, `SCAN_WIDTH_MM`, `SCAN_HEIGHT_MM`), `REAR_PAGE_WAIT_SECONDS` (#123, #127).
- Scan-to-PC registration refreshed periodically (`KEEPALIVE`, `KEEPALIVE_INTERVAL`), so the destination no longer vanishes from the device (#90, #99, by @xiezhensheng).
- Secrets from files: `FTP_PASSWORD_FILE` and the other `*_FILE` variables (#103).
- `FTP_INSECURE=true` for plain FTP (#105); `TZ` for file names and the web UI (#114).
- Image tags `vX.Y.Z`, `vX.Y`, `vX` and `stable` from the tag workflow; `latest` is the master build (#170).
- Tests: shellcheck, bats, pytest and Playwright end-to-end tests with a scanner simulator and a fake OCR service gate every image; coverage above 95 % on the Python and the PHP side; docs consistency checks (#86, #100, #102, #137, #141).
- Documentation pages under `doc/` and a short README with a migration chapter (#140, #164).

### Changed

- The scan scripts are Python; one pipeline module and thin entry points for the four buttons (#57, #102; based on #48 by @pedropombeiro).
- Base image moved to Debian bookworm (#93); PDF page size is A4 at the scan resolution instead of 72 dpi pixels (#123).
- Scanning has priority over OCR; the OCR worker waits for an idle scanner and can be rate-limited (#117).
- The file list is paginated newest first and loads in batches (#118, #147); thumbnails are rendered by the pipeline as the scan user and never left broken (#146, #156).

### Fixed

- The OCR worker deleted the original scan after an invalid OCR result; the original is now only removed after a validated copy is in place (#106, #113).
- Scans started without a button press and the ADF paused between pages while OCR ran (#107, #108, #117).
- File names used UTC instead of the configured time zone (#111, #114).
- The rear scan takes over the waiting state cleanly; stale status files are ignored (#37, #73, #104, #84).
- The web UI failed after a container restart (#89); UID/GID defaults (#69, #70, #91, #97); OCR output much larger than the scan (#109, #120).
- Quoted values showed their quotes in button labels (#142, #145); log noise at worker start (#112, #115).
- Build: brscan-skey download (#82, #83), Debian bullseye packages gone (#92, #93), fork pull requests build without pushing (#94, #95).

### Deprecated

- `scan.php` and `active.php` keep answering for automations from before the rewrite (#149); use `/api/scanner/scanto` and `/api/scanner/status`.

### Removed

- `list.php` and `download.php`; use `/api/file-list` and `/api/file/<name>/download`.

### Breaking

- Plain FTP uploads need `FTP_INSECURE=true`; the default requires FTPS.
- Custom scripts mounted over `script/` need porting to the Python entry points (see [doc/customizing.md](doc/customizing.md)).

## 1.1.1 (2025-02-16)

- PHP 7 support for the web interface (#67).

## 1.1.0 (2024-10-20)

- Remove the non-OCR PDF after a successful OCR (`REMOVE_ORIGINAL_AFTER_OCR`, #41).
- Refined scanner actions (#45), FTP upload fixes (#46), custom `NAME` fixes (#47, #56, #58).
- Telegram message matches the inotify message (#34, @pedropombeiro); Dockerfile cleanup (#50) and CI linters (#51, @pedropombeiro).
- The scan scripts converted to a single Python script (#48, @pedropombeiro), the basis of the 2.0 pipeline.

## 1.0.0 (2024-09-22)

First versioned release, so that users can pin a version while master moves on.

- FTPS upload, inotify only with credentials, script symlinks for the driver, volume mount fixes (#4 to #8, @cwiggs).
- JPEG compression for the PDFs (#13, @Krifto).
- Upgraded web interface and Dockerfile (#23, #25, @vgarcia007); Telegram notifications from the GUI (#24).
- Blank page removal (#39), clean exit on cancelled scans (#35), temp directory fixes (#33, #38; @pedropombeiro).
- shellcheck fixes (#21, @pedropombeiro).
