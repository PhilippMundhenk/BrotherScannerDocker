# Tests

Four layers, all defined in `.github/workflows/test.yml`. The workflow is
reusable only: the PR publish workflow runs it for every pull request and the
master publish workflow before every release build, so an image is only
produced when every layer is green and nothing runs twice:

| Layer | Tool | What it covers | Command |
|---|---|---|---|
| static analysis | shellcheck | the remaining shell scripts: `files/runScanner.sh`, `run.sh`, `update-container.sh` | `make lint` |
| shell hygiene | bats-core | `bash -n` on the shell scripts, executable bits in `script/`, Dockerfile sanity | `bats tests/unit` |
| Python units | pytest | `script/scanner.py` (environment parsing, blank page removal, post-processing, rear wait), the OCR queue (`script/ocr_queue.py`) and the notification helpers, with subprocesses mocked | `pytest tests/python` |
| end-to-end | Playwright | the built image running with a simulated scanner and a fake OCR service: web UI, REST API, scan pipeline, OCR queue, file ownership | `cd tests/e2e && npx playwright test` |

## Coverage

- Python: `pytest --cov --cov-report=term-missing tests/python` (configuration in `.coveragerc`); CI fails below 95%.
- PHP: the e2e job runs against a coverage flavour of the image (`tests/coverage/Dockerfile.coverage`, php-pcov) that records the executed lines of every request; `tests/coverage/php_report.py` merges the dumps into a per-file report and fails below 95%. Files no request loads count as uncovered.
- Shell: bats covers the sourceable `files/config.sh`; the entrypoint itself is exercised by the e2e container start.
- JavaScript: exercised by the Playwright specs (drawer, thumbnails, settings page, token header).

## Running locally

```bash
# static analysis + shell hygiene
sudo apt-get install -y bats shellcheck
make lint
bats tests/unit

# Python units
pip install pytest requests==2.32.3
pytest tests/python

# end-to-end (needs Docker and Node 18+)
docker build -t brotherscanner:e2e .
cd tests/e2e
npm ci
npx playwright install chromium        # once
IMAGE=brotherscanner:e2e npx playwright test
```

`npm run report` opens the HTML report of the last run. On failure, the
container log and `/var/log/scanner.log` are saved to `tests/e2e/output/`.

## Layout

```
tests/
  helpers/common.bash        shared bats helpers
  unit/*.bats                bats tests
  python/
    conftest.py              puts script/ on sys.path, clean_env fixture
    test_*.py                pytest tests
  e2e/
    fixtures/scanimage       scanner simulator (stand-in for SANE's scanimage)
    fixtures/sample.pdf      seeded into /scans; also the fake OCR response
    global-setup.ts          starts the container and the fake OCR service
    helpers.ts               API helpers, docker exec helpers
    tests/*.spec.ts          Playwright specs
```

## The scanner simulator

`tests/e2e/fixtures/scanimage` is a small Python program that is bind-mounted
over `/usr/bin/scanimage` in the test container. The real pipeline (the
`scanto*.py` entry points, `scanner.py`, GraphicsMagick, Ghostscript, pdftk,
the OCR queue worker) runs unchanged; only the scanner itself is simulated.
It answers device queries, writes `SIM_PAGES` PGM pages per scan (each with a
black rectangle so blank page removal keeps them), sleeps `SIM_SCAN_SECONDS`
per page, and fails every scan when `SIM_FAIL=true`.

The test container also runs with `REAR_PAGE_WAIT_SECONDS=6` so that a front
scan converts after six seconds instead of two minutes, and `KEEPALIVE=false`
since there is no device to register with.

## What is not covered

The Brother driver itself (`brscan4`, `brscan-skey`): registration with the
device, the button events, and the SNMP keepalive. Those need real hardware.
