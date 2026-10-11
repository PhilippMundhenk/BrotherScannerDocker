# Customizing the scan scripts

[Back to the README](../README.md)

The scan actions are implemented in Python in the folder `script/` of this repository:

| File | Called for | Does |
|---|---|---|
| `scantofile.py` | "Scan to File" button, web UI, API | scans the front pages, waits for rear pages, converts to PDF, runs the post-processing |
| `scantoemail.py` | "Scan to E-mail" button, web UI, API | scans the rear pages of the last front scan and merges them into one PDF |
| `scantoocr.py` | "Scan to OCR" button, web UI, API | like scan to file, but in gray mode |
| `scantoimage.py` | "Scan to Image" button, web UI, API | placeholder, only logs that it is not implemented |
| `scanner.py` | | the shared pipeline: scanning, blank page removal, PDF conversion, notifications, OCR queueing |
| `ocr_queue.py` | started by the container | the OCR upload queue worker |
| `thumbnails.py` | started by the container, called by the pipeline | thumbnails for the file list |

The Brother driver calls these through `/opt/brother/scanner/brscan-skey/brscan-skey.config`, one entry per shortcut button on the scanner.

If you want different behaviour, mount your own versions over `/opt/brother/scanner/brscan-skey/script/` (for example `-v "$PWD/script/:/opt/brother/scanner/brscan-skey/script/"`) and keep the file names, or point `brscan-skey.config` at anything executable. A script does not need to scan at all; any program that the scanner user can run works. All scripts log to `/var/log/scanner.log`, which the container prints to its output.
