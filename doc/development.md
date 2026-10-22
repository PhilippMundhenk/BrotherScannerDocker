# Development and testing

[Back to the README](../README.md)

Four test layers run in GitHub Actions for every pull request and before every image is published (`.github/workflows/test.yml`):

- shellcheck and bats for the remaining shell scripts (the entrypoint and the maintainer helpers),
- pytest for the Python pipeline, the OCR queue and the thumbnails, with a coverage gate,
- Playwright end-to-end tests that run the built image with a simulated scanner and a fake OCR service and drive the web UI and the API, with a PHP coverage gate,
- a documentation consistency test: every option in the settings catalogue is in the options table of [configuration.md](configuration.md) and vice versa, and every API route is in [swagger.yaml](swagger.yaml).

See [tests/README.md](../tests/README.md) for how to run them locally and what they cover. The screenshots in this folder come from `tests/e2e/screenshots.ts` run against a container started from the e2e image (`npx tsx screenshots.ts http://localhost:<port> ../../doc`).

Brother's own driver (the SANE backend's scan over TCP 54921 and the `brscan-skey` daemon) cannot be simulated and needs real hardware. The Scan-to-PC protocol around it can: with `SKEY_DAEMON=openskey` and `SKEY_MOCK_DEVICE=true` the container runs [openskey](https://github.com/PhilippMundhenk/openskey) against its mock device (a stand-in scanner inside the container that answers the SNMP registration and the status objects like a real MFC-L2700DW, and sends button events on request). `tests/e2e/tests/openskey.spec.ts` uses that to check the registration and its self-test, `GET /api/scanner/device`, and that a button press on the "device" (`docker exec <container> openskey-mock-device --button FILE`) becomes exactly one job with `trigger: button`. `SKEY_MOCK_DEVICE` is a test hook, not a feature.
