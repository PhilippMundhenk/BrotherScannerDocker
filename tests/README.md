# Tests

Static analysis (shellcheck) and unit tests (bats-core) for the bash
scripts in this repository.

## Running locally

```bash
# Install once
sudo apt-get install -y bats shellcheck

# Run everything
make test          # from repo root
# or
bats tests/unit
shellcheck script/*.sh files/*.sh
```

## Layout

```
tests/
  helpers/
    common.bash        # shared setup, mock helpers
  unit/
    *.bats             # one file per script under test
```

## Mocking

External commands (`curl`, `wget`, `sshpass`, `ssh`, `pdfinfo`, `gs`,
`pdftk`, `scanimage`, `gm`, `nawk`, etc.) are mocked by prepending a
test-scoped directory of fake binaries to `$PATH`. See
`helpers/common.bash` for `mock_command` / `mock_record`.

## What is covered

| Script | Coverage |
|---|---|
| `script/trigger_telegram.sh` | env gating, encoded message body, wget call |
| `script/trigger_inotify.sh` | env gating, sshpass invocation, failure exit |
| `script/sendtoftps.sh` | env gating, curl invocation, failure exit |
| `script/remove_blank.sh` | env gating (no-op when threshold unset) |
| `script/scantoemail-0.2.4-1.sh` | trigger message, scanRear delegation |
| `script/scantoocr-0.2.4-1.sh` | placeholder error message |
| `script/scantoimage-0.2.4-1.sh` | placeholder error message |
| All `*.sh` | parses with `bash -n`, executable bit set |

What is *not* covered (would require live hardware or hours of
mocked-up fixtures): the full `scantofile`/`scanRear` scan pipeline,
`runScanner.sh` interface detection, the lighttpd PHP front-end.
