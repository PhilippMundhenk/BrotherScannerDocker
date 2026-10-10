#!/usr/bin/env bats

# scantoocr-0.2.4-1.sh and scantoimage-0.2.4-1.sh are intentional
# placeholders. Each one writes a "not implemented" notice to
# /var/log/scanner.log and exits 0. Test that contract so future edits
# do not silently drop the message.

setup() {
  load '../helpers/common'
  common_setup
}

teardown() {
  common_teardown
}

run_placeholder() {
  local script="$1"
  cp "$SCRIPT_DIR/$script" "$test_tmp/$script"
  sed -i "s|/var/log/scanner.log|$test_tmp/scanner.log|g" "$test_tmp/$script"
  bash "$test_tmp/$script"
}

@test "scantoocr-0.2.4-1.sh prints the not-implemented notice" {
  run run_placeholder scantoocr-0.2.4-1.sh
  [ "$status" -eq 0 ]
  run cat "$test_tmp/scanner.log"
  [[ "$output" == *"ERROR!"* ]]
  [[ "$output" == *"not implemented"* ]]
}

@test "scantoimage-0.2.4-1.sh prints the not-implemented notice" {
  run run_placeholder scantoimage-0.2.4-1.sh
  [ "$status" -eq 0 ]
  run cat "$test_tmp/scanner.log"
  [[ "$output" == *"ERROR!"* ]]
  [[ "$output" == *"not implemented"* ]]
}
