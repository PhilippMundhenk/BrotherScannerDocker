#!/usr/bin/env bash
# Shared bats test helpers.
#
# Each test should `load '../helpers/common'` in its setup() and then use:
#   * REPO_ROOT       - absolute path to the repo
#   * SCRIPT_DIR      - absolute path to the script/ directory
#   * test_tmp        - a fresh per-test temp directory (auto-cleaned)
#   * mock_command    - drop a fake executable on PATH for one command
#   * mock_record     - drop a fake executable that records its argv
#   * mock_calls      - read back what mock_record captured

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd -P)"
SCRIPT_DIR="$REPO_ROOT/script"

common_setup() {
  test_tmp="$(mktemp -d)"
  MOCK_BIN="$test_tmp/mock_bin"
  MOCK_LOG_DIR="$test_tmp/mock_log"
  mkdir -p "$MOCK_BIN" "$MOCK_LOG_DIR"
  export PATH="$MOCK_BIN:$PATH"
}

common_teardown() {
  if [ -n "${test_tmp:-}" ] && [ -d "$test_tmp" ]; then
    rm -rf "$test_tmp"
  fi
}

# mock_command <name> [exit_code] [stdout]
mock_command() {
  local name="$1"
  local exit_code="${2:-0}"
  local stdout="${3:-}"
  cat >"$MOCK_BIN/$name" <<EOF
#!/usr/bin/env bash
printf '%s' "$stdout"
exit $exit_code
EOF
  chmod +x "$MOCK_BIN/$name"
}

# mock_record <name> [exit_code]
# Each invocation appends a line to $MOCK_LOG_DIR/<name>.log of the form
#   <argc>\t<arg1>\t<arg2>...
mock_record() {
  local name="$1"
  local exit_code="${2:-0}"
  cat >"$MOCK_BIN/$name" <<EOF
#!/usr/bin/env bash
{
  printf '%d' "\$#"
  for a in "\$@"; do printf '\t%s' "\$a"; done
  printf '\n'
} >>"$MOCK_LOG_DIR/$name.log"
exit $exit_code
EOF
  chmod +x "$MOCK_BIN/$name"
}

# mock_calls <name> - print the recorded invocations (one per line)
mock_calls() {
  local name="$1"
  cat "$MOCK_LOG_DIR/$name.log" 2>/dev/null || true
}

# mock_call_count <name>
mock_call_count() {
  local name="$1"
  if [ -f "$MOCK_LOG_DIR/$name.log" ]; then
    wc -l <"$MOCK_LOG_DIR/$name.log" | tr -d ' '
  else
    echo 0
  fi
}
