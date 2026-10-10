#!/usr/bin/env bats

# Catch-all hygiene checks across every shell script in the repo.

setup() {
  load '../helpers/common'
}

# List of scripts to lint. Symlinks (scantofile.sh -> scantofile-0.2.4-1.sh
# etc.) are handled by globbing the versioned files plus the standalone
# helpers.
shell_scripts() {
  printf '%s\n' \
    "$SCRIPT_DIR/remove_blank.sh" \
    "$SCRIPT_DIR/scanRear.sh" \
    "$SCRIPT_DIR/scantoemail-0.2.4-1.sh" \
    "$SCRIPT_DIR/scantofile-0.2.4-1.sh" \
    "$SCRIPT_DIR/scantoimage-0.2.4-1.sh" \
    "$SCRIPT_DIR/scantoocr-0.2.4-1.sh" \
    "$SCRIPT_DIR/sendtoftps.sh" \
    "$SCRIPT_DIR/trigger_inotify.sh" \
    "$SCRIPT_DIR/trigger_telegram.sh" \
    "$REPO_ROOT/files/runScanner.sh" \
    "$REPO_ROOT/run.sh" \
    "$REPO_ROOT/update-container.sh"
}

@test "every shell script parses with bash -n" {
  local failed=0
  while IFS= read -r f; do
    if ! bash -n "$f" 2>/dev/null; then
      echo "PARSE FAIL: $f" >&2
      failed=1
    fi
  done < <(shell_scripts)
  [ "$failed" -eq 0 ]
}

@test "scripts under script/ have the executable bit set in git" {
  cd "$REPO_ROOT"
  # ls-files -s prints "<mode> <hash> <stage> <path>"; mode for an
  # executable regular file is 100755. Symlinks are mode 120000 and
  # are exempt.
  local bad
  bad="$(git ls-files -s script/ \
         | awk '$1 != "100755" && $1 != "120000" { print }')"
  if [ -n "$bad" ]; then
    echo "Files in script/ missing exec bit (or wrong mode):" >&2
    echo "$bad" >&2
    return 1
  fi
}

@test "Dockerfile copies the script directory into the image" {
  grep -qE '^COPY[[:space:]]+script[[:space:]]+/opt/brother/scanner/brscan-skey/script' "$REPO_ROOT/Dockerfile"
}

@test "Dockerfile installs the packages remove_blank.sh depends on" {
  # pdfinfo from poppler-utils; gs from ghostscript; pdftk; nawk from
  # graphicsmagick? actually nawk is not in the package list - flag it.
  grep -qE 'poppler-utils' "$REPO_ROOT/Dockerfile"
  grep -qE 'ghostscript'   "$REPO_ROOT/Dockerfile"
  grep -qE 'pdftk'         "$REPO_ROOT/Dockerfile"
}
