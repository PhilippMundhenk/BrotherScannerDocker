#!/usr/bin/env bats

setup() {
  load '../helpers/common'
  common_setup
}

teardown() {
  common_teardown
}

@test "skips when any SSH var is missing (no user)" {
  run bash "$SCRIPT_DIR/trigger_inotify.sh" "" pass host /remote/path file.pdf
  [ "$status" -eq 0 ]
  [[ "$output" == *"SSH environment variables not set"* ]]
}

@test "skips when filepath is empty" {
  run bash "$SCRIPT_DIR/trigger_inotify.sh" user pass host "" file.pdf
  [ "$status" -eq 0 ]
  [[ "$output" == *"SSH environment variables not set"* ]]
}

@test "invokes sshpass+ssh when all SSH vars are present" {
  mock_record sshpass 0
  # ssh is invoked *through* sshpass in the real script; sshpass mock
  # records the full argv so we don't need a separate ssh mock.

  run bash "$SCRIPT_DIR/trigger_inotify.sh" alice secret host.example /remote scan.pdf
  [ "$status" -eq 0 ]
  [ "$(mock_call_count sshpass)" -eq 1 ]
  local call
  call="$(mock_calls sshpass)"
  [[ "$call" == *"alice@host.example"* ]]
  [[ "$call" == *"/remote/scan.pdf"* ]]
  [[ "$output" == *"trigger inotify successful"* ]]
}

@test "exits 1 and logs failure when sshpass fails" {
  mock_record sshpass 5
  run bash "$SCRIPT_DIR/trigger_inotify.sh" alice secret host.example /remote scan.pdf
  [ "$status" -eq 1 ]
  [[ "$output" == *"trigger inotify failed"* ]]
}
