#!/usr/bin/env bash
# shellcheck shell=bash
# brscan-skey daemon supervision (#179). Sourced by runScanner.sh and testable
# with bats.
#
# Background: brscan-skey-exe is Brother's closed-source button daemon. It
# leaks one UDP socket on every registration cycle (its own periodic
# re-registration, every button press, and every `--refresh` from our
# keepalive): the firmware probe GetPhoenixFirmware opens a socket and never
# closes it. The sockets pile up until the process hits its open-file limit,
# after which it logs "Too many open files" and silently stops handling button
# presses. See doc/development.md and the issue #179 report.
#
# We cannot fix Brother's binary, so we contain the leak from the outside:
#   1. start the daemon with its soft open-file limit raised to the hard limit
#      (pushes the failure from days to years on a typical host), and
#   2. run a watchdog that restarts the daemon if it is gone or its open-file
#      count climbs toward the limit, never while a scan is in progress.
# Restarting the whole daemon is safe (unlike closing individual sockets, which
# the daemon reuses); it re-registers on start, so the buttons keep working.

# scan_active: true (0) when a scan or a front-scan-waiting-for-rear is in
# progress. The scan scripts mark both phases with status files in the temp
# directory; files older than 10 minutes are left-behind by a crash and
# ignored. Shared by the keepalive and the watchdog so neither disturbs a job.
scan_active() {
  local tmp="${TMPDIR:-/tmp}"
  [[ -n "$(find "$tmp" -maxdepth 1 \( -name STATUS_SCAN -o -name STATUS_WAITING \) -mmin -10 2>/dev/null)" ]]
}

# skey_fd_count <pid>: number of open file descriptors held by the daemon.
# Prints the count and returns 0, or returns 1 when the process is gone.
skey_fd_count() {
  local pid="$1"
  [[ -n "$pid" && -d "/proc/$pid/fd" ]] || return 1
  local n
  n=$(find "/proc/$pid/fd" -mindepth 1 2>/dev/null | wc -l)
  echo "$n"
}

# skey_should_restart <fds> <soft_limit> <threshold_pct> [<max_fds>]:
# true (0) when the daemon should be restarted to release leaked sockets, i.e.
# when the open-file count has reached an absolute ceiling (max_fds, when set
# and > 0) or threshold_pct percent of the soft limit. Pure arithmetic so it is
# unit-testable; non-numeric input is treated as "do not restart".
skey_should_restart() {
  local fds="$1" soft="$2" pct="${3:-80}" max_fds="${4:-0}"
  [[ "$fds" =~ ^[0-9]+$ ]] || return 1
  if [[ "$max_fds" =~ ^[0-9]+$ && "$max_fds" -gt 0 && "$fds" -ge "$max_fds" ]]; then
    return 0
  fi
  [[ "$soft" =~ ^[0-9]+$ && "$pct" =~ ^[0-9]+$ && "$soft" -gt 0 ]] || return 1
  (( fds * 100 >= soft * pct ))
}

# skey_daemon_soft_limit <pid>: the daemon's soft open-file limit from
# /proc/<pid>/limits (readable as root, which the entrypoint is). Falls back to
# the entrypoint shell's own hard limit, which is what start_skey_daemon raises
# the daemon's soft limit to.
skey_daemon_soft_limit() {
  local pid="$1" line soft
  if [[ -n "$pid" && -r "/proc/$pid/limits" ]]; then
    line=$(grep -E '^Max open files' "/proc/$pid/limits" 2>/dev/null)
    soft=$(awk '/^Max open files/ {print $4}' <<<"$line")
    if [[ "$soft" =~ ^[0-9]+$ ]]; then
      echo "$soft"
      return 0
    fi
  fi
  ulimit -Hn 2>/dev/null || echo 1024
}
