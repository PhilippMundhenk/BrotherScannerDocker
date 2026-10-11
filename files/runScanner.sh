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
    if [[ -n "$(find /tmp -maxdepth 1 \( -name STATUS_SCAN -o -name STATUS_WAITING \) -mmin -10 2>/dev/null)" ]]; then
      echo "keepalive: scan active, skipping registration refresh" >>/var/log/scanner.log
      continue
    fi
    su - "$NAME" -c "/usr/bin/brscan-skey --refresh" >>/var/log/scanner.log 2>&1
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
su - "$NAME" -c "/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS"
su - "$NAME" -c "/usr/bin/brscan-skey"
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
# thumbnail cache for the file list (rendered on first request by the web server user)
mkdir -p /scans/.thumbnails && chmod 777 /scans/.thumbnails
if [ "$WEBSERVER" == "true" ]; then
  echo "www-data ALL=($NAME) NOPASSWD:ALL" >>/etc/sudoers

  echo "starting webserver for API & GUI..."
  {
    echo "<?php"
    echo "\$UID=$USERID;"
    echo "\$MODEL=\"$MODEL\";"
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
      case "$key" in PATH|HOME|HOSTNAME|PWD|SHLVL|TERM|OLDPWD|UID|GID|EUID|PPID|LANG|LC_ALL|_|TZ|MODEL) continue ;; esac
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

else
  echo "webserver not configured"
fi
echo "-----"

echo "setting up reachability check:"
# Every SCANNER_PING_INTERVAL seconds (0 disables) try the scanner's scan port
# and record the result for GET /api/scanner/status (field "reachable").
PING_INTERVAL="${SCANNER_PING_INTERVAL:-60}"
if [[ "$PING_INTERVAL" =~ ^[0-9]+$ && "$PING_INTERVAL" -gt 0 ]]; then
  (
    while true; do
      if timeout 3 bash -c "exec 3<>/dev/tcp/$IPADDRESS/54921" 2>/dev/null; then
        echo 1 >/tmp/STATUS_REACHABLE
      else
        echo 0 >/tmp/STATUS_REACHABLE
      fi
      chmod 644 /tmp/STATUS_REACHABLE
      sleep "$PING_INTERVAL"
    done
  ) &
  echo "checking $IPADDRESS:54921 every ${PING_INTERVAL}s"
else
  echo "reachability check disabled"
fi
echo "-----"

echo "capabilities:"
# kept for /api/actions (device.capabilities): the option lists of the device
scanimage -A > /tmp/SCANNER_CAPABILITIES 2>&1 || true
chmod 644 /tmp/SCANNER_CAPABILITIES
cat /tmp/SCANNER_CAPABILITIES

echo "startup successful"
keepAliveRegistration &
while true; do
  tail -f /var/log/scanner.log
done
exit 0
