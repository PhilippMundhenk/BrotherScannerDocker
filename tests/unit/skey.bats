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

# --- skey_daemon_choice / skey_daemon_process (#188) -----------------------

@test "daemon_choice: defaults to brscan-skey" {
  run skey_daemon_choice ""
  [ "$output" = "brscan-skey" ]
  run skey_daemon_choice
  [ "$output" = "brscan-skey" ]
  run skey_daemon_choice brscan-skey
  [ "$output" = "brscan-skey" ]
}

@test "daemon_choice: openskey, case-insensitively" {
  run skey_daemon_choice openskey
  [ "$output" = "openskey" ]
  run skey_daemon_choice OpenSkey
  [ "$output" = "openskey" ]
}

@test "daemon_choice: anything else falls back to brscan-skey" {
  run skey_daemon_choice nonsense
  [ "$output" = "brscan-skey" ]
}

@test "daemon_process: the process name per daemon" {
  run skey_daemon_process openskey
  [ "$output" = "openskey" ]
  run skey_daemon_process brscan-skey
  [ "$output" = "brscan-skey-exe" ]
}

# --- interface_ipv4 --------------------------------------------------------

@test "interface_ipv4: the first IPv4 address of the interface" {
  ip() {
    echo "2: eth0    inet 192.168.44.58/24 brd 192.168.44.255 scope global eth0"
    echo "2: eth0    inet 10.0.0.5/8 scope global secondary eth0"
  }
  run interface_ipv4 eth0
  [ "$status" -eq 0 ]
  [ "$output" = "192.168.44.58" ]
}

@test "interface_ipv4: nothing for an empty interface name or one without an address" {
  run interface_ipv4 ""
  [ "$status" -ne 0 ]
  ip() { :; }
  run interface_ipv4 eth9
  [ -z "$output" ]
}

# --- device_reachable (#193) ------------------------------------------------

@test "device_reachable: asks openskey over SNMP and passes the address and port on" {
  cat > "$test_tmp/openskey" <<'STUB'
#!/usr/bin/env bash
echo "$1 IPADDRESS=$IPADDRESS SKEY_DEVICE_PORT=$SKEY_DEVICE_PORT" > "${STUB_LOG}"
echo '{"device_ip":"192.0.2.10","reachable":true,"registered":true}'
STUB
  chmod +x "$test_tmp/openskey"
  export OPENSKEY_BIN="$test_tmp/openskey" STUB_LOG="$test_tmp/stub.log"
  run device_reachable 192.0.2.10 1161
  [ "$status" -eq 0 ]
  [ "$(cat "$test_tmp/stub.log")" = "status IPADDRESS=192.0.2.10 SKEY_DEVICE_PORT=1161" ]
}

@test "device_reachable: a device that does not answer SNMP is unreachable" {
  cat > "$test_tmp/openskey" <<'STUB'
#!/usr/bin/env bash
echo '{"device_ip":"192.0.2.10","reachable":false,"registered":null}'
exit 2
STUB
  chmod +x "$test_tmp/openskey"
  export OPENSKEY_BIN="$test_tmp/openskey"
  run device_reachable 192.0.2.10
  [ "$status" -eq 1 ]
}

@test "device_reachable: the SNMP check runs even while a scan is active (no side effects)" {
  cat > "$test_tmp/openskey" <<'STUB'
#!/usr/bin/env bash
echo '{"reachable":true}'
STUB
  chmod +x "$test_tmp/openskey"
  export OPENSKEY_BIN="$test_tmp/openskey" TMPDIR="$test_tmp"
  touch "$test_tmp/STATUS_SCAN"
  run device_reachable 192.0.2.10
  [ "$status" -eq 0 ]
}

@test "device_reachable: without openskey the scan port is never opened during a scan" {
  export OPENSKEY_BIN="$test_tmp/does-not-exist" TMPDIR="$test_tmp"
  touch "$test_tmp/STATUS_SCAN"
  run device_reachable 127.0.0.1
  [ "$status" -eq 2 ]
}

@test "device_reachable: without openskey and idle, a closed scan port means unreachable" {
  export OPENSKEY_BIN="$test_tmp/does-not-exist" TMPDIR="$test_tmp"
  run device_reachable 127.0.0.1
  [ "$status" -eq 1 ]
}
