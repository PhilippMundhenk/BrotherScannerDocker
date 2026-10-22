#!/bin/bash

keepAliveRegistration() {
  # brscan-skey registers Scan-to-PC functions into the device via SNMP with a
  # hardcoded 360s lease (DURATION=360) and only (re-)registers on events:
  # daemon startup, a button press, or a device power-on. It has no timer-based
  # renewal, so where no such event occurs the device silently drops the
  # destination ("Scanner" disappears from the panel) after the lease expires.
  # brscan-skey ships an undocumented client flag, --refresh, which asks the
  # running daemon to re-register all network scanners. Run it every few
  # minutes to keep the registration alive.
  # Disable with KEEPALIVE=false. Interval: KEEPALIVE_INTERVAL seconds (< 360).
  # openskey refreshes (and verifies) the registration itself, from a socket
  # it closes again, and holds back while a scan runs (SKEY_HOLD_FILES).
  if [[ "$SKEY_DAEMON_CHOICE" == "openskey" ]]; then
    echo "registration keepalive: built into openskey (every ${KEEPALIVE_INTERVAL:-120}s, verified by reading the registration back)"
    return
  fi
  if [[ "${KEEPALIVE,,}" == "false" ]]; then
    echo "registration keepalive disabled"
    return
  fi
  INTERVAL="${KEEPALIVE_INTERVAL:-120}"
  if [[ "$INTERVAL" -ge 360 ]]; then
    echo "KEEPALIVE_INTERVAL >= 360 exceeds the device lease, clamping to 120"
    INTERVAL=120
  fi
  echo "starting registration keepalive (every ${INTERVAL}s, disable with KEEPALIVE=false)"
  while true; do
    sleep "$INTERVAL"
    # Never re-register while the device is busy with one of our jobs: a refresh
    # during a scan can stall the feeder, and it must not coincide with paper
    # in the ADF. The scan scripts mark both phases with status files in /tmp
    # (ignored when older than 10 minutes, i.e. left behind by a crash).
    if scan_active; then
      echo "keepalive: scan active, skipping registration refresh" >>/var/log/scanner.log
      continue
    fi
    su - "$NAME" -c "/usr/bin/brscan-skey --refresh" >>/var/log/scanner.log 2>&1
  done
}

# start_skey_daemon: launch Brother's button daemon with its soft open-file
# limit raised to the hard limit. The daemon leaks a socket per registration
# cycle (#179); the raised limit turns the failure from days into years, and
# pam_limits resets the soft limit to 1024 for the `su -` login session, so it
# has to be raised inside that session. The wrapper backgrounds brscan-skey-exe
# and returns; the daemon inherits the raised limit.
start_skey_daemon() {
  if [[ "$SKEY_DAEMON_CHOICE" == "openskey" ]]; then
    start_openskey
    return
  fi
  su - "$NAME" -c 'ulimit -Sn "$(ulimit -Hn)" 2>/dev/null; exec /usr/bin/brscan-skey' \
    >>/var/log/scanner.log 2>&1
}

# start_openskey: run the open reimplementation (SKEY_DAEMON=openskey, #188)
# as the scanner user, like brscan-skey. It needs the host address the device
# will send button events to: HOST_IPADDRESS, else the address of the
# interface facing the scanner. The scan scripts are called as
# "<script> <device> <name>", exactly as brscan-skey calls them, plus the
# button event in the environment (SKEY_FUNC, SKEY_P1..4, SKEY_SEQ, ...),
# which the job record keeps (#187). The environment goes through a file
# because `su -` starts from a clean one.
start_openskey() {
  local host_ip="${HOST_IPADDRESS:-$(interface_ipv4 "$interface")}"
  local script_dir=/opt/brother/scanner/brscan-skey/script
  local env_file=/opt/brother/scanner/openskey.env
  local func
  {
    printf 'export NAME=%q IPADDRESS=%q HOST_IPADDRESS=%q\n' "$NAME" "$IPADDRESS" "$host_ip"
    printf 'export KEEPALIVE_INTERVAL=%q SKEY_DEVICE_PORT=%q\n' "${KEEPALIVE_INTERVAL:-120}" "${SKEY_DEVICE_PORT:-161}"
    # never re-register while a scan runs or a front scan waits for rear pages
    printf 'export SKEY_HOLD_FILES=%q\n' "/tmp/STATUS_SCAN:/tmp/STATUS_WAITING"
    for func in file email image ocr; do
      printf "export SKEY_%s='python3 %s/scanto%s.py \"\$1\" \"\$2\"'\n" "${func^^}" "$script_dir" "$func"
    done
  } >"$env_file"
  chown "$NAME" "$env_file" && chmod 600 "$env_file"
  su - "$NAME" -s /bin/bash -c "source $env_file; exec /usr/local/bin/openskey" >>/var/log/scanner.log 2>&1 &
  echo "openskey started as $NAME (pid $!, device $IPADDRESS:${SKEY_DEVICE_PORT:-161}, host $host_ip)"
}

# skey_watchdog: restart the daemon if it has died or its open-file count has
# climbed toward the limit (leaked sockets, #179), never while a scan runs.
# SKEY_WATCHDOG=false disables it; SKEY_WATCHDOG_INTERVAL seconds between checks
# (default 60); SKEY_WATCHDOG_THRESHOLD percent of the soft limit that triggers
# a restart (default 80); SKEY_WATCHDOG_MAX_FDS an optional absolute ceiling.
skey_watchdog() {
  if [[ "${SKEY_WATCHDOG,,}" == "false" ]]; then
    echo "brscan-skey watchdog disabled"
    return
  fi
  local interval="${SKEY_WATCHDOG_INTERVAL:-60}"
  local pct="${SKEY_WATCHDOG_THRESHOLD:-80}"
  local max_fds="${SKEY_WATCHDOG_MAX_FDS:-0}"
  local ceiling=""
  [[ "$max_fds" =~ ^[0-9]+$ && "$max_fds" -gt 0 ]] && ceiling=" or $max_fds files"
  echo "starting $SKEY_DAEMON_CHOICE watchdog (every ${interval}s, restart at ${pct}% of the open-file limit${ceiling})"
  local pid fds soft
  while true; do
    sleep "$interval"
    pid=$(pgrep -x "$SKEY_DAEMON_PROCESS" | head -1)
    if [[ -z "$pid" ]]; then
      echo "watchdog: $SKEY_DAEMON_CHOICE is not running, starting it" >>/var/log/scanner.log
      start_skey_daemon
      continue
    fi
    # openskey has no leak (#179 is in Brother's binary): only liveness matters.
    [[ "$SKEY_DAEMON_CHOICE" == "openskey" ]] && continue
    scan_active && continue
    fds=$(skey_fd_count "$pid") || continue
    soft=$(skey_daemon_soft_limit "$pid")
    if skey_should_restart "$fds" "$soft" "$pct" "$max_fds"; then
      echo "watchdog: brscan-skey holds $fds of $soft open files, restarting to release leaked sockets (#179)" >>/var/log/scanner.log
      su - "$NAME" -c "/usr/bin/brscan-skey -t" >>/var/log/scanner.log 2>&1 || true
      sleep 1
      pgrep -x brscan-skey-exe >/dev/null && pkill -x brscan-skey-exe 2>/dev/null
      sleep 1
      start_skey_daemon
    fi
  done
}

echo "setting up secrets:"
# Docker secrets / *_FILE convention: when VAR is empty and VAR_FILE names a
# readable file, VAR is read from that file (trailing newlines stripped). This
# keeps passwords and tokens out of the compose file and the container
# environment listing.
for var in FTP_USER FTP_PASSWORD SSH_USER SSH_PASSWORD TELEGRAM_TOKEN TELEGRAM_CHATID; do
  file_var="${var}_FILE"
  if [[ -z "${!var}" && -n "${!file_var}" ]]; then
    if [[ -r "${!file_var}" ]]; then
      printf -v "$var" '%s' "$(<"${!file_var}")"
      export "${var?}"
      echo "read $var from ${!file_var}"
    else
      echo "WARNING: $file_var=${!file_var} is not readable, $var stays empty"
    fi
  fi
done
echo "-----"

echo "setting up configuration file:"
# Settings may come from a file on the volume (settings page) in addition to
# the environment. Environment wins; what the environment sets (including
# secrets read from *_FILE above) is recorded in locked.txt so the scripts and
# the settings page know which keys are fixed.
# shellcheck source=files/config.sh
source /opt/brother/config.sh
# shellcheck source=files/skey.sh
source /opt/brother/skey.sh
CONFIG_FILE="$(config_file_path)"
mkdir -p "$(dirname "$CONFIG_FILE")" && chmod 777 "$(dirname "$CONFIG_FILE")"
mkdir -p /opt/brother/scanner
record_locked_keys /opt/brother/scanner/locked.txt
chmod 644 /opt/brother/scanner/locked.txt
load_config_file "$CONFIG_FILE" /opt/brother/scanner/locked.txt
export SCANNER_CONFIG_FILE="$CONFIG_FILE"
# Defaults for what neither the environment nor the file sets (these used to
# be ENV lines in the Dockerfile, which made them look environment-set).
export MODEL="${MODEL:-MFC-L2700DW}"
export IPADDRESS="${IPADDRESS:-192.168.1.123}"
export REMOVE_BLANK_THRESHOLD="${REMOVE_BLANK_THRESHOLD-0.3}"
export FTP_PATH="${FTP_PATH:-/scans/}"
# Which Scan-to-PC button daemon runs: Brother's brscan-skey (default) or
# openskey, the open reimplementation (SKEY_DAEMON=openskey, see doc/setup.md).
SKEY_DAEMON_CHOICE=$(skey_daemon_choice "${SKEY_DAEMON:-}")
SKEY_DAEMON_PROCESS=$(skey_daemon_process "$SKEY_DAEMON_CHOICE")
echo "button daemon: $SKEY_DAEMON_CHOICE"
echo "-----"

echo "setting up user & logfile:"

NAME="${NAME:-Scanner}"

if [[ $NAME == *" "* ]]; then
  echo "Do not use spaces in NAME!"
  exit 1
fi

USERID=${UID:-1000}
GROUPID=${GID:-1000}

# Without an inherited UID, Bash sets its readonly UID to 0 when running as root.
if [[ $USERID == 0 ]]; then
  USERID=1000
fi

if [[ ! $USERID =~ ^[0-9]+$ || ! $GROUPID =~ ^[0-9]+$ ]]; then
  echo "UID and GID must be numeric (got UID='${UID}', GID='${GID}')"
  exit 1
fi

echo "using uid ${USERID}, gid ${GROUPID} for user ${NAME}"
groupadd --gid "$GROUPID" NAS
adduser "$NAME" --uid "$USERID" --gid "$GROUPID" --disabled-password --force-badname --gecos ""
mkdir -p /scans
chmod 777 /scans
echo -n "" >/var/log/scanner.log
chown "$NAME" /var/log/scanner.log
chmod 666 /var/log/scanner.log
env >/opt/brother/scanner/env.txt
chmod -R 777 /opt/brother
# env.txt carries the secrets to the scan scripts and the OCR worker, which
# run as the scanner user; nobody else needs to read it.
chown "$NAME" /opt/brother/scanner/env.txt
chmod 600 /opt/brother/scanner/env.txt
echo "-----"

echo "setting up interface:"
subnet="${IPADDRESS%.*.*}."
interface=$(ip addr show | grep -B10 "$subnet" | grep mtu | tail -1 | sed 's/[0-9]*: \(.*\): .*/\1/')
sed -i 's/^eth=.*//' /opt/brother/scanner/brscan-skey/brscan-skey.config
# if found an interface for scanner subnet. Will use this to contact scanner.
if [[ -z "$interface" ]]; then
  # if scanner subnet (roughly) not found in interfaces, assuming network_mode="host" is not set and using Docker default interface.
  interface="eth0"
fi
echo "eth=$interface" >>/opt/brother/scanner/brscan-skey/brscan-skey.config
echo "using interface: $interface"
echo "-----"

echo "setting up host IP:"
sed -i 's/^ip_address=.*//' /opt/brother/scanner/brscan-skey/brscan-skey.config
if [[ -z "$HOST_IPADDRESS" ]]; then
  echo "no host IP configured, using default discovery"
else
  echo "ip_address=$HOST_IPADDRESS" >>/opt/brother/scanner/brscan-skey/brscan-skey.config
fi
echo "-----"

echo "whole config:"
cat /opt/brother/scanner/brscan-skey/brscan-skey.config
echo "-----"

echo "starting scanner drivers..."
# Two Brother SANE backends are installed: brscan4 for the older models and
# brscan5 for the newer ones (ADS-1x00, DS-940DW, ...). Each brsaneconfig
# accepts any model name but marks one it does not know as "Unknown", and the
# backend then scans with a generic profile (wrong page geometry, #75). So the
# model is registered with brscan4 first, and when that driver does not know
# it, with brscan5. SCANNER_DRIVER=brscan4|brscan5 forces one. brscan-skey
# reads both registrations and calls the same scripts for either.
register_driver() { # $1 = 4|5
  su - "$NAME" -c "/usr/bin/brsaneconfig$1 -a name=$NAME model=$MODEL ip=$IPADDRESS"
}
unregister_driver() { # $1 = 4|5
  su - "$NAME" -c "/usr/bin/brsaneconfig$1 -r $NAME" >/dev/null 2>&1 || true
}
BRSCAN4_CFG=/opt/brother/scanner/brscan4/brsanenetdevice4.cfg
BRSCAN5_CFG=/opt/brother/scanner/brscan5/brsanenetdevice.cfg
SCANNER_DRIVER="${SCANNER_DRIVER:-auto}"
case "${SCANNER_DRIVER,,}" in
  brscan4)
    register_driver 4
    DRIVER=brscan4
    ;;
  brscan5)
    register_driver 5
    DRIVER=brscan5
    ;;
  *)
    register_driver 4
    if registration_known "$BRSCAN4_CFG" "$NAME"; then
      DRIVER=brscan4
    else
      unregister_driver 4
      register_driver 5
      if registration_known "$BRSCAN5_CFG" "$NAME"; then
        DRIVER=brscan5
      else
        unregister_driver 5
        register_driver 4
        DRIVER=brscan4
        echo "model $MODEL is unknown to both drivers; using brscan4 with a generic profile (set SCANNER_DRIVER=brscan5 for a newer model)"
      fi
    fi
    ;;
esac
echo "scanner driver: $DRIVER for model $MODEL"
echo "$DRIVER" >/tmp/SCANNER_DRIVER
chmod 644 /tmp/SCANNER_DRIVER
if [[ "${SKEY_MOCK_DEVICE,,}" == "true" ]]; then
  # Test hook (tests/e2e): a stand-in scanner, openskey's mock device, inside
  # the container, so the button daemon registers against it, button presses
  # can be injected and the device status read without hardware. Not for
  # production; see doc/development.md.
  export SKEY_DEVICE_PORT="${SKEY_DEVICE_PORT:-1161}"
  /usr/local/bin/openskey-mock-device --port "$SKEY_DEVICE_PORT" >>/var/log/scanner.log 2>&1 &
  echo "mock device started on UDP :$SKEY_DEVICE_PORT (SKEY_MOCK_DEVICE, tests only)"
fi
start_skey_daemon
echo "-----"

echo "setting up OCR queue worker:"
if [ -z "${OCR_SERVER}" ] || [ -z "${OCR_PORT}" ] || [ -z "${OCR_PATH}" ]; then
  echo "OCR not configured (OCR_SERVER, OCR_PORT, OCR_PATH), queue worker not started"
else
  OCR_QUEUE_DIR="${OCR_QUEUE_DIR:-/scans/.ocr_queue}"
  mkdir -p "$OCR_QUEUE_DIR/pending" "$OCR_QUEUE_DIR/in_progress" "$OCR_QUEUE_DIR/failed"
  chown -R "$NAME" "$OCR_QUEUE_DIR" 2>/dev/null || true
  chmod -R 777 "$OCR_QUEUE_DIR"
  # Supervisor: relaunch the worker forever, with a small backoff to avoid a
  # crash-loop. The worker runs as the scanner user, like the scan scripts, so
  # OCR output in /scans gets the same owner as the scans themselves. `su -`
  # starts with a clean environment, so the container environment (OCR_*,
  # FTP_*, SSH_*, TELEGRAM_*, REMOVE_ORIGINAL_AFTER_OCR) is loaded from env.txt
  # the same way the scan scripts do it.
  # ocr_queue.py loads the container environment from env.txt itself, so no
  # shell export is needed (env.txt contains UID, which bash refuses to export).
  su - "$NAME" -s /bin/bash -c '
    while true; do
      python3 /opt/brother/scanner/brscan-skey/script/ocr_queue.py worker
      echo "[ocr_worker supervisor] worker exited with $?; restarting in 5s"
      sleep 5
    done
  ' >>/var/log/scanner.log 2>&1 &
  echo "OCR queue worker started as $NAME (supervisor pid: $!)"
fi
echo "-----"

echo "setting up webserver:"
# thumbnail cache for the file list; written by the scan user (pipeline, sweep below,
# and the web server through sudo), so it belongs to that user
mkdir -p /scans/.thumbnails && chown "$NAME" /scans/.thumbnails 2>/dev/null; chmod 777 /scans/.thumbnails 2>/dev/null || true
if [ "$WEBSERVER" == "true" ]; then
  echo "www-data ALL=($NAME) NOPASSWD:ALL" >>/etc/sudoers

  echo "starting webserver for API & GUI..."
  {
    echo "<?php"
    echo "\$UID=$USERID;"
    echo "\$MODEL=\"$MODEL\";"
    # the device address and SNMP port for GET /api/scanner/device
    echo "\$IPADDRESS=\"$IPADDRESS\";"
    echo "\$SKEY_DEVICE_PORT=\"${SKEY_DEVICE_PORT:-161}\";"
    if [[ -n "$TZ" ]]; then
      echo "\$TZ=\"$TZ\";"
    fi
    # Every setting the environment provides (locked.txt) plus the backend
    # basics, as PHP literals: "true"/"false" become booleans so that
    # DISABLE_GUI_*=false or ALLOW_GUI_FILEOPERATIONS=false mean what they say,
    # everything else is an escaped string.
    php_literal() {
      local value="$1"
      # Compose list entries like `- KEY="Scan front pages"` keep their quotes;
      # drop one pair of matching surrounding quotes so they never reach the UI.
      if [[ ${#value} -ge 2 && ( ( ${value:0:1} == '"' && ${value: -1} == '"' ) || ( ${value:0:1} == "'" && ${value: -1} == "'" ) ) ]]; then
        value="${value:1:${#value}-2}"
      fi
      case "${value,,}" in
        true) echo "true" ;;
        false) echo "false" ;;
        *)
          value="${value//\\/\\\\}"
          value="${value//\"/\\\"}"
          value="${value//\$/\\\$}"
          echo "\"${value}\""
          ;;
      esac
    }
    for var in RESOLUTION SCAN_MODE SCAN_SOURCE API_TOKEN ALLOW_GUI_SETTINGS SCANNER_CONFIG_FILE; do
      if [[ -n "${!var}" ]]; then
        echo "\$${var}=$(php_literal "${!var}");"
      fi
    done
    while IFS= read -r key; do
      case "$key" in PATH|HOME|HOSTNAME|PWD|SHLVL|TERM|OLDPWD|UID|GID|EUID|PPID|LANG|LC_ALL|_|TZ|MODEL|IPADDRESS|SKEY_DEVICE_PORT) continue ;; esac
      [[ -n "${!key+x}" ]] || continue
      echo "\$${key}=$(php_literal "${!key}");"
    done </opt/brother/scanner/locked.txt
    # settings from the configuration file for keys the environment does not set;
    # extract() runs in the scope of whoever includes config.php (every view)
    echo "require_once('settings.php');"
    echo "extract(settings_file_overlay(), EXTR_OVERWRITE);"
    echo "?>"

  } >/var/www/html/config.php

  chown www-data /var/www/html/config.php
  if [[ -z ${PORT} ]]; then
    PORT=80
  fi

  echo "running on port $PORT"
  sed -i "s/server.port\W*= 80/server.port = $PORT/" /etc/lighttpd/lighttpd.conf
  /usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf
  echo "webserver started"

  # Thumbnails of the existing scans, newest first, at low priority and only
  # while no scan runs; the drawer then never has to render on request.
  if [[ "${GUI_THUMBNAILS,,}" != "false" && "${GUI_THUMBNAILS}" != "0" ]]; then
    su - "$NAME" -s /bin/bash -c 'nice -n 19 python3 /opt/brother/scanner/brscan-skey/script/thumbnails.py sweep --pause 0.2' >>/var/log/scanner.log 2>&1 &
    echo "thumbnail sweep started as $NAME (pid: $!)"
  fi

else
  echo "webserver not configured"
fi
echo "-----"

echo "setting up reachability check:"
# Every SCANNER_PING_INTERVAL seconds (0 disables) ask the scanner whether it
# is there and record the result for GET /api/scanner/status ("reachable").
# The question goes over SNMP (`openskey status`: one UDP exchange the device
# answers without side effects). Opening the scan port TCP 54921 instead, as
# the check used to, starts a scan session the device has to tear down, and a
# scan that opens the device in that moment is refused ("open of device ...
# failed: Invalid argument" on an MFC-L2700DW, #193). The TCP probe stays as
# the fallback when openskey is not in the image, and never runs during a scan.
PING_INTERVAL="${SCANNER_PING_INTERVAL:-60}"
if [[ "$PING_INTERVAL" =~ ^[0-9]+$ && "$PING_INTERVAL" -gt 0 ]]; then
  (
    while true; do
      # device_reachable (files/skey.sh): 0 answers, 1 does not, 2 not asked
      # (a scan is running and only the scan-port fallback is available)
      device_reachable "$IPADDRESS" "${SKEY_DEVICE_PORT:-161}"
      case $? in
        0) echo 1 >/tmp/STATUS_REACHABLE; chmod 644 /tmp/STATUS_REACHABLE ;;
        2) : ;;
        *) echo 0 >/tmp/STATUS_REACHABLE; chmod 644 /tmp/STATUS_REACHABLE ;;
      esac
      sleep "$PING_INTERVAL"
    done
  ) &
  if [[ -x /usr/local/bin/openskey ]]; then
    echo "checking that $IPADDRESS answers over SNMP every ${PING_INTERVAL}s"
  else
    echo "checking $IPADDRESS:54921 every ${PING_INTERVAL}s (never during a scan)"
  fi
else
  echo "reachability check disabled"
fi
echo "-----"

echo "capabilities:"
# the registered device (one backend, brother4 or brother5), then its option lists,
# kept for /api/actions (device.capabilities)
scanimage -L 2>&1 | grep -i 'brother' || true
scanimage -A > /tmp/SCANNER_CAPABILITIES 2>&1 || true
chmod 644 /tmp/SCANNER_CAPABILITIES
cat /tmp/SCANNER_CAPABILITIES

echo "startup successful"
keepAliveRegistration &
skey_watchdog &
while true; do
  tail -f /var/log/scanner.log
done
exit 0
