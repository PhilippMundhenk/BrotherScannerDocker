# Setup

[Back to the README](../README.md)

You have two options to set up the container: preferred (bridged networking) and fallback (host networking). The preferred method is more complex but works in more situations, the fallback is simpler but not possible everywhere.

## Preferred: bridged networking

The scanner contacts the container when a shortcut button is pressed, so the container needs the IP address under which it is reachable from the scanner: the Docker host, the virtual machine that runs Docker, and so on. The scanner ports have to be forwarded.

```yaml
services:
  brother-scanner:
    image: ghcr.io/philippmundhenk/brotherscannerdocker:v2
    volumes:
      - /path/on/host:/scans
    ports:
      - 54925:54925/udp # mandatory, for scanner tools
      - 54921:54921 # mandatory, for scanner tools
      - 161:161/udp # mandatory, for scanner tools
    environment:
      - NAME=Scanner
      - MODEL=MFC-L2700DW
      - IPADDRESS=192.168.1.10
      - UID=1000 # note: network mount needs to have correct permissions!
      - GID=1000 # note: network mount needs to have correct permissions!
      - TZ=Europe/Berlin
      - HOST_IPADDRESS=192.168.1.20
    restart: unless-stopped
```

Here the scanner (an MFC-L2700DW) runs on 192.168.1.10 and reaches the container via 192.168.1.20. The startup scripts configure the included Brother tooling accordingly.

## Fallback: host networking

The fallback is a little more robust but requires the container to be bridged to the host network rather than using Docker NAT, which is not possible everywhere (Docker on Windows or Mac, some VM setups).

```yaml
services:
  brother-scanner:
    image: ghcr.io/philippmundhenk/brotherscannerdocker:v2
    volumes:
      - /path/on/host:/scans
    environment:
      - NAME=Scanner
      - MODEL=MFC-L2700DW
      - IPADDRESS=192.168.1.10
      - UID=1000 # note: network mount needs to have correct permissions!
      - GID=1000 # note: network mount needs to have correct permissions!
      - TZ=Europe/Berlin
    restart: unless-stopped
    network_mode: "host"
```

No host IP address is needed; the startup scripts guess the host interface and adjust the Brother driver settings.

## Scanner driver

Brother ships two SANE drivers for Linux: `brscan4` for the older models (the MFC-L2700DW and most MFC/DCP devices up to about 2017) and `brscan5` for the newer ones (ADS-1200/1700W, DS-940DW and later). The image contains both. At start the model is registered with brscan4; when that driver does not know the model, with brscan5. The log says which one was taken:

```
scanner driver: brscan5 for model DS-940DW
```

A model unknown to both drivers runs on brscan4 with a generic profile, which may deliver wrong page geometry (a cut-off bottom, see [#75](https://github.com/PhilippMundhenk/BrotherScannerDocker/issues/75)); check the spelling of `MODEL` against Brother's name of the device, or force the driver with `SCANNER_DRIVER=brscan5`. The shortcut buttons, the web UI and the API work the same with either driver.

## Scanner buttons stop working

Brother's `brscan-skey` daemon drives the device's front-panel Scan-to-PC buttons. It has a bug: it leaks one network socket every time it registers with the scanner, so after enough registration cycles it reaches its open-file limit and silently stops responding to button presses while web-UI and API scanning keep working (see [#179](https://github.com/PhilippMundhenk/BrotherScannerDocker/issues/179)). The leak is inside Brother's closed-source binary and cannot be fixed from here.

The image contains it in two ways, so you should not notice it:

- the daemon starts with its open-file limit raised to the host maximum, which pushes a failure from days to years, and
- a watchdog restarts the daemon if it dies or its open files climb toward the limit, never during a scan. The daemon re-registers on start, so the buttons come straight back.

`GET /api/scanner/status` reports a `buttons` field (the daemon is running). The watchdog is on by default; `SKEY_WATCHDOG=false` turns it off, and `SKEY_WATCHDOG_INTERVAL`, `SKEY_WATCHDOG_THRESHOLD` and `SKEY_WATCHDOG_MAX_FDS` tune it (see [Configuration](configuration.md)).

## Image tags

| Tag | Points to |
|---|---|
| `v2.0.1` | exactly that release |
| `v2.0` | the newest patch release of that minor version |
| `v2` | the newest release of that major version (no breaking changes within it); the examples use this |
| `stable` | the newest release overall |
| `latest` | the current master build, i.e. the development state |
| branch name | the build of a pull request's branch |

Pre-releases (`v2.1.0-rc1`) only get their exact tag. The tags are set by the tag workflow when a `vX.Y.Z` tag is pushed.

## Permissions

The mounted folder `/scans` needs the correct permissions. By default the scanner runs with UID 1000 and GID 1000; set `UID` and `GID` to numeric values to change that. Unset or empty values use the defaults, and `UID=0` also uses 1000.

## The scanner buttons

The four scanner buttons map to these actions:

- **Scan to File** scans the front page(s) and waits up to two minutes (`REAR_PAGE_WAIT_SECONDS`) before converting to PDF.
- **Scan to E-mail** within that time (scanner button, web UI or API) scans the rear of the same stack: turn the stack over, no resorting needed. Both sides are interleaved into one PDF.
- **Scan to OCR** is Scan to File in gray mode.
- **Scan to Image** is a placeholder that only logs a message; mount your own script to use it (see [Customizing the scan scripts](customizing.md)).

If OCR, FTP, SSH or Telegram options are set, they run after every finished PDF.

## Duplex scanners

This image was written for simplex ADFs (front pages first, then the rear pages through Scan to E-mail). If your device lists a duplex source in the capabilities at startup, set `SCAN_SOURCE` to it, for example `SCAN_SOURCE=Automatic Document Feeder(left aligned,Duplex)`; the device then delivers both sides of every sheet in one pass as consecutive pages, and the rear-page scan is not needed. The value must match the device's wording exactly, including the parentheses.

## Calibration

The ADF feeds the sheet a little before the sensor starts, so the first millimetre or two of a page are not scanned and the 297 mm window reaches past the trailing edge, which shows as a dark or white bar at the bottom. The lost top edge cannot be recovered, but the window can be adjusted with `SCAN_TOP_MM`, `SCAN_HEIGHT_MM`, `SCAN_LEFT_MM` and `SCAN_WIDTH_MM`: scan a page with a ruler on it, compare, and set the values accordingly (`SCAN_HEIGHT_MM=295` is the usual fix for the bar). The device clamps the width to its maximum (211.9 mm on the MFC-L2700DW).

## File sizes

A 300 dpi 24-bit colour page is about 4 MB as a lossless PDF. For documents, set `SCAN_MODE=True Gray` (about a third) or `SCAN_MODE=Black & White` (a few tens of KB), and/or `USE_JPEG_COMPRESSION=true`. The OCR service keeps the page images it receives, so these settings also decide the size of the OCR copy.

## Full example

This compose file runs with minimal adaptions (MODEL, IPADDRESS, HOST_IPADDRESS and the volume):

```yaml
services:
  brother-scanner:
    image: ghcr.io/philippmundhenk/brotherscannerdocker:v2
    volumes:
      - /path/on/host:/scans
    ports:
      - 33355:33355
      - 54925:54925/udp # mandatory, for scanner tools
      - 54921:54921 # mandatory, for scanner tools
      - 161:161/udp # mandatory, for scanner tools
    environment:
      - NAME=Scanner
      - MODEL=MFC-L2700DW
      - IPADDRESS=192.168.1.10
      - HOST_IPADDRESS=192.168.1.20
      - OCR_SERVER=localhost # optional, for OCR
      - OCR_PORT=32800 # optional, for OCR
      - OCR_PATH=ocr.php # optional, for OCR
      - UID=1000 # optional, for /scans permissions
      - GID=1000 # optional, for /scans permissions
      - TZ=Europe/Berlin # optional, for correct time in scanned filenames
      - WEBSERVER=true # optional, activates GUI & API
      - PORT=33355 # optional, sets port for webserver (default: 80)
      - DISABLE_GUI_SCANTOIMAGE=true # optional, deactivates button "Scan to image"
      - DISABLE_GUI_SCANTOOCR=true # optional, deactivates button "Scan to OCR"
      - RENAME_GUI_SCANTOFILE="Scan front pages" # optional, renames button "Scan to file" to "Scan front pages"
      - RENAME_GUI_SCANTOEMAIL="Scan rear pages" # optional, renames button "Scan to email" to "Scan rear pages"
    restart: unless-stopped

  # optional, for OCR
  ocr:
    image: ghcr.io/philippmundhenk/tesseractocrmicroservice
    restart: unless-stopped
    ports:
      - 32800:80
```
