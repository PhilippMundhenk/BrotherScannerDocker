#!/usr/bin/env bats

# files/skey.sh: brscan-skey daemon supervision helpers (#179).

setup() {
  load '../helpers/common'
  common_setup
  source "$REPO_ROOT/files/skey.sh"
}

teardown() {
  common_teardown
}

# --- skey_should_restart ---------------------------------------------------

@test "should_restart: absolute ceiling fires regardless of soft limit" {
  run skey_should_restart 40 1000000 80 40
  [ "$status" -eq 0 ]
  run skey_should_restart 41 1000000 80 40
  [ "$status" -eq 0 ]
}

@test "should_restart: below the absolute ceiling and below the percentage does not fire" {
  run skey_should_restart 39 1000000 80 40
  [ "$status" -ne 0 ]
}

@test "should_restart: percentage of the soft limit fires when no ceiling is set" {
  run skey_should_restart 820 1000 80 0
  [ "$status" -eq 0 ]
  run skey_should_restart 800 1000 80 0
  [ "$status" -eq 0 ]
}

@test "should_restart: below the percentage does not fire" {
  run skey_should_restart 799 1000 80 0
  [ "$status" -ne 0 ]
}

@test "should_restart: default threshold is 80 percent" {
  run skey_should_restart 800 1000
  [ "$status" -eq 0 ]
  run skey_should_restart 799 1000
  [ "$status" -ne 0 ]
}

@test "should_restart: non-numeric or empty count never fires" {
  run skey_should_restart "" 1000 80 0
  [ "$status" -ne 0 ]
  run skey_should_restart abc 1000 80 0
  [ "$status" -ne 0 ]
}

@test "should_restart: a zero soft limit with no ceiling never fires" {
  run skey_should_restart 5000 0 80 0
  [ "$status" -ne 0 ]
}

# --- scan_active -----------------------------------------------------------

@test "scan_active: false when no status files are present" {
  export TMPDIR="$test_tmp"
  run scan_active
  [ "$status" -ne 0 ]
}

@test "scan_active: true while a scan status file is fresh" {
  export TMPDIR="$test_tmp"
  touch "$test_tmp/STATUS_SCAN"
  run scan_active
  [ "$status" -eq 0 ]
}

@test "scan_active: true while a front scan waits for rear pages" {
  export TMPDIR="$test_tmp"
  touch "$test_tmp/STATUS_WAITING"
  run scan_active
  [ "$status" -eq 0 ]
}

@test "scan_active: a stale status file (older than 10 minutes) is ignored" {
  export TMPDIR="$test_tmp"
  touch -d '20 minutes ago' "$test_tmp/STATUS_SCAN"
  run scan_active
  [ "$status" -ne 0 ]
}

# --- skey_fd_count / skey_daemon_soft_limit --------------------------------

@test "fd_count: returns failure for a process that does not exist" {
  run skey_fd_count 999999
  [ "$status" -ne 0 ]
}

@test "fd_count: counts the open descriptors of a live process" {
  [ -d "/proc/$$/fd" ] || skip "no /proc on this platform"
  run skey_fd_count "$$"
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^[0-9]+$ ]]
  [ "$output" -gt 0 ]
}

@test "soft_limit: falls back to a numeric value when the process is gone" {
  run skey_daemon_soft_limit 999999
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^[0-9]+$ ]]
}
