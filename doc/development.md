# Development and testing

[Back to the README](../README.md)

Four test layers run in GitHub Actions for every pull request and before every image is published (`.github/workflows/test.yml`):

- shellcheck and bats for the remaining shell scripts (the entrypoint and the maintainer helpers),
- pytest for the Python pipeline, the OCR queue and the thumbnails, with a coverage gate,
- Playwright end-to-end tests that run the built image with a simulated scanner and a fake OCR service and drive the web UI and the API, with a PHP coverage gate,
- a documentation consistency test: every option in the settings catalogue is in the options table of [configuration.md](configuration.md) and vice versa, and every API route is in [swagger.yaml](swagger.yaml).

See [tests/README.md](../tests/README.md) for how to run them locally and what they cover. The screenshots in this folder come from `tests/e2e/screenshots.ts` run against a container started from the e2e image (`npx tsx screenshots.ts http://localhost:<port> ../../doc`).

The Brother driver itself (registration with the device, button events, the SNMP keepalive) cannot be simulated and needs real hardware.
