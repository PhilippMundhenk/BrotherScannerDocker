#!/usr/bin/env bats

# files/config.sh: configuration file merged into the environment, with
# environment-set keys locked (#124).

setup() {
  load '../helpers/common'
  common_setup
  source "$REPO_ROOT/files/config.sh"
  CONF="$test_tmp/scanner.conf"
  LOCKED="$test_tmp/locked.txt"
  : >"$LOCKED"
}

teardown() {
  common_teardown
}

@test "default path, overridable with SCANNER_CONFIG_FILE" {
  unset SCANNER_CONFIG_FILE
  [ "$(config_file_path)" = "/scans/.config/scanner.conf" ]
  SCANNER_CONFIG_FILE=/config/x.conf
  [ "$(config_file_path)" = "/config/x.conf" ]
}

@test "missing file is fine" {
  run load_config_file "$test_tmp/none.conf" "$LOCKED"
  [ "$status" -eq 0 ]
  [[ "$output" == *"no configuration file"* ]]
}

@test "KEY=VALUE lines are exported; comments, blanks, quotes and CRLF handled" {
  printf '# comment\n\nRESOLUTION=200\r\nSCAN_MODE="True Gray"\nFTP_PATH=/a/b=c/\nno equals here\nlower=1\n' >"$CONF"
  unset RESOLUTION SCAN_MODE FTP_PATH
  run bash -c "source '$REPO_ROOT/files/config.sh'; load_config_file '$CONF' '$LOCKED'; echo \"R=\$RESOLUTION M=\$SCAN_MODE F=\$FTP_PATH L=\${lower:-unset}\""
  [[ "$output" == *"R=200 M=True Gray F=/a/b=c/ L=unset"* ]]
  [[ "$output" == *"ignoring line without '='"* ]]
  [[ "$output" == *"ignoring invalid key: lower"* ]]
  [[ "$output" == *"3 setting(s) loaded"* ]]
}

@test "keys set by the environment are not overridden" {
  printf 'RESOLUTION=200\nSCAN_MODE=True Gray\n' >"$CONF"
  printf 'RESOLUTION\n' >"$LOCKED"
  run bash -c "export RESOLUTION=600; source '$REPO_ROOT/files/config.sh'; load_config_file '$CONF' '$LOCKED'; echo \"R=\$RESOLUTION M=\$SCAN_MODE\""
  [[ "$output" == *"R=600 M=True Gray"* ]]
  [[ "$output" == *"RESOLUTION is set by the environment, file value ignored"* ]]
  [[ "$output" == *"1 overridden by the environment"* ]]
}

@test "record_locked_keys lists the exported variables, sorted" {
  run bash -c "export ZZZ_TEST=1 AAA_TEST=2; source '$REPO_ROOT/files/config.sh'; record_locked_keys '$LOCKED'; grep -n -E '^(AAA_TEST|ZZZ_TEST)$' '$LOCKED' | tr '\n' ' '"
  [[ "$output" == *"AAA_TEST"*"ZZZ_TEST"* ]]
  # sorted: AAA before ZZZ
  a=$(grep -n '^AAA_TEST$' "$LOCKED" | cut -d: -f1)
  z=$(grep -n '^ZZZ_TEST$' "$LOCKED" | cut -d: -f1)
  [ "$a" -lt "$z" ]
}
