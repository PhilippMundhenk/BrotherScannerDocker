#!/usr/bin/env bats

# scantoemail-0.2.4-1.sh writes only to /var/log/scanner.log. To keep
# the test hermetic we redirect that path to a sandbox file and then
# inspect its contents.

setup() {
  load '../helpers/common'
  common_setup
  # Stage an env.txt the script will source.
  mkdir -p "$test_tmp/opt/brother/scanner"
  cat >"$test_tmp/opt/brother/scanner/env.txt" <<EOF
FOO=bar
BAZ=qux
EOF
  # Stage a wrapper that points the script at our sandbox by patching
  # the two hardcoded absolute paths.
  cp "$SCRIPT_DIR/scantoemail-0.2.4-1.sh" "$test_tmp/scantoemail.sh"
  sed -i \
    -e "s|/var/log/scanner.log|$test_tmp/scanner.log|g" \
    -e "s|/opt/brother/scanner/env.txt|$test_tmp/opt/brother/scanner/env.txt|g" \
    "$test_tmp/scantoemail.sh"
  # Put a fake scanRear.sh next to it that just echoes its argv.
  cat >"$test_tmp/scanRear.sh" <<'EOF'
#!/usr/bin/env bash
echo "scanRear called with: $*"
EOF
  chmod +x "$test_tmp/scanRear.sh"
}

teardown() {
  common_teardown
}

@test "logs trigger banner and invokes scanRear.sh with forwarded args" {
  run bash "$test_tmp/scantoemail.sh" device1 friendly-name
  [ "$status" -eq 0 ]
  # All output goes to the log file, not stdout.
  [ -f "$test_tmp/scanner.log" ]
  run cat "$test_tmp/scanner.log"
  [[ "$output" == *"scantoemail.sh triggered"* ]]
  [[ "$output" == *"scanRear called with: device1 friendly-name"* ]]
}
