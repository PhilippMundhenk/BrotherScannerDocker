#!/usr/bin/env bats

# Catch-all hygiene checks across every shell script in the repo.

setup() {
  load '../helpers/common'
}

# Shell scripts left after the Python rewrite: the container entrypoint
# and the two maintainer helpers.
shell_scripts() {
  printf '%s\n' \
    "$REPO_ROOT/files/config.sh" \
    "$REPO_ROOT/files/runScanner.sh" \
    "$REPO_ROOT/tools/run.sh" \
    "$REPO_ROOT/tools/update-container.sh"
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

@test "Dockerfile installs the packages the scan pipeline depends on" {
  # pdfinfo from poppler-utils; gs from ghostscript; pdftk; gm from graphicsmagick
  grep -qE 'poppler-utils'  "$REPO_ROOT/Dockerfile"
  grep -qE 'ghostscript'    "$REPO_ROOT/Dockerfile"
  grep -qE 'pdftk'          "$REPO_ROOT/Dockerfile"
  grep -qE 'graphicsmagick' "$REPO_ROOT/Dockerfile"
}

@test "Dockerfile keeps scanner and SSH clients without GUI or SSH server metapackages" {
  grep -qE '^[[:space:]]+procps[[:space:]]+\\$' "$REPO_ROOT/Dockerfile"
  grep -qE '^[[:space:]]+sane-utils[[:space:]]+\\$' "$REPO_ROOT/Dockerfile"
  grep -qE '^[[:space:]]+openssh-client[[:space:]]+\\$' "$REPO_ROOT/Dockerfile"
  ! grep -qE '^[[:space:]]+(sane|ssh|openssh-server)[[:space:]]+\\$' "$REPO_ROOT/Dockerfile"
}

@test "Dockerfile removes pip after installing application dependencies" {
  local install_line remove_line
  install_line=$(grep -nE '^pip install .*requests==' "$REPO_ROOT/Dockerfile" | cut -d: -f1)
  remove_line=$(grep -nE '^python3 -m pip uninstall --yes pip' "$REPO_ROOT/Dockerfile" | cut -d: -f1)
  [ -n "$install_line" ]
  [ -n "$remove_line" ]
  [ "$remove_line" -gt "$install_line" ]
}
