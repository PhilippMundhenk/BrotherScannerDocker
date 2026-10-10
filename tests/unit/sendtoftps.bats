#!/usr/bin/env bats

# Note: sendtoftps.sh does `cd /scans` unconditionally before the
# env-var check. The tests below tolerate `cd` failing (script does
# not use `set -e`) by asserting on stdout content rather than exit
# code where the env-var gate is exercised.

setup() {
  load '../helpers/common'
  common_setup
}

teardown() {
  common_teardown
}

@test "skips when user is empty" {
  run bash "$SCRIPT_DIR/sendtoftps.sh" "" pw host /path file.pdf
  [[ "$output" == *"FTP environment variables not set"* ]]
}

@test "skips when file argument is empty" {
  run bash "$SCRIPT_DIR/sendtoftps.sh" user pw host /path ""
  [[ "$output" == *"FTP environment variables not set"* ]]
}

@test "invokes curl with ftp url, credentials and upload file when all args present" {
  mock_record curl 0
  # The script chdirs to /scans before running curl. Create a /scans
  # equivalent in the sandbox and use a stub file path that exists
  # there. We approximate this by chdir'ing /scans if possible; if
  # not, the cd failure goes to stderr and we just verify the curl
  # invocation that follows.
  run bash "$SCRIPT_DIR/sendtoftps.sh" alice secret ftp.example /uploads/ scan.pdf
  [ "$(mock_call_count curl)" -eq 1 ]
  local call
  call="$(mock_calls curl)"
  [[ "$call" == *"alice:secret"* ]]
  [[ "$call" == *"ftp://ftp.example/uploads/"* ]]
  [[ "$call" == *"scan.pdf"* ]]
  [[ "$output" == *"successful"* ]]
}

@test "exits 1 with diagnostic output when curl fails" {
  mock_record curl 22
  run bash "$SCRIPT_DIR/sendtoftps.sh" alice secret ftp.example /uploads/ scan.pdf
  [ "$status" -eq 1 ]
  [[ "$output" == *"Uploading to ftp failed"* ]]
  [[ "$output" == *"user: alice"* ]]
}
