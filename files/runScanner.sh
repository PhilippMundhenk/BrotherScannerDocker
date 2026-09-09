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
    su - "$NAME" -c "/usr/bin/brscan-skey --refresh" >>/var/log/scanner.log 2>&1
  done
}

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

echo "setting up webserver:"
if [ "$WEBSERVER" == "true" ]; then
  echo "www-data ALL=($NAME) NOPASSWD:ALL" >>/etc/sudoers

  echo "starting webserver for API & GUI..."
  {
    echo "<?php"
    echo "\$UID=$USERID;"
    echo "\$MODEL=\"$MODEL\";"
    if [[ -n "$RENAME_GUI_SCANTOFILE" ]]; then
      echo "\$RENAME_GUI_SCANTOFILE=$RENAME_GUI_SCANTOFILE;"
    fi
    if [[ -n "$RENAME_GUI_SCANTOEMAIL" ]]; then
      echo "\$RENAME_GUI_SCANTOEMAIL=$RENAME_GUI_SCANTOEMAIL;"
    fi
    if [[ -n "$RENAME_GUI_SCANTOIMAGE" ]]; then
      echo "\$RENAME_GUI_SCANTOIMAGE=$RENAME_GUI_SCANTOIMAGE;"
    fi
    if [[ -n "$RENAME_GUI_SCANTOOCR" ]]; then
      echo "\$RENAME_GUI_SCANTOOCR=$RENAME_GUI_SCANTOOCR;"
    fi
    if [[ -n "$DISABLE_GUI_SCANTOFILE" ]]; then
      echo "\$DISABLE_GUI_SCANTOFILE=$DISABLE_GUI_SCANTOFILE;"
    fi
    if [[ -n "$DISABLE_GUI_SCANTOEMAIL" ]]; then
      echo "\$DISABLE_GUI_SCANTOEMAIL=$DISABLE_GUI_SCANTOEMAIL;"
    fi
    if [[ -n "$DISABLE_GUI_SCANTOIMAGE" ]]; then
      echo "\$DISABLE_GUI_SCANTOIMAGE=$DISABLE_GUI_SCANTOIMAGE;"
    fi
    if [[ -n "$DISABLE_GUI_SCANTOOCR" ]]; then
      echo "\$DISABLE_GUI_SCANTOOCR=$DISABLE_GUI_SCANTOOCR;"
    fi
    if [[ -n "$ALLOW_GUI_FILEOPERATIONS" ]]; then
      echo "\$ALLOW_GUI_FILEOPERATIONS=$ALLOW_GUI_FILEOPERATIONS;"
    fi
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

echo "capabilities:"
scanimage -A

echo "startup successful"
keepAliveRegistration &
while true; do
  tail -f /var/log/scanner.log
done
exit 0
