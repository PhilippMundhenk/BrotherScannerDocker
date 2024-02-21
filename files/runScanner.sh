#!/bin/bash

mandatory_vars=(NAME MODEL IPADDRESS)
missing=0
for var in "${mandatory_vars[@]}"
do
	if [[ -z "${!var}" ]]; then
		echo "missing mandatory variable: $var"
		missing=1
	fi
done
if [[ $missing -eq 1 ]]; then
	echo "exiting"
	exit 1
fi

echo "setting up logfile"

mkdir -p /scans
chmod 777 /scans
touch /var/log/scanner.log
chmod 777 /var/log/scanner.log
env > /opt/brother/scanner/env.txt
export > /opt/brother/scanner/shell_env.txt
chmod -R 777 /opt/brother
echo "-----"

echo "setting up interface:"
subnet=$(echo $IPADDRESS | sed 's/\([0-9]*\.[0-9]*\.\)[0-9]*\.[0-9]*/\1/')
interface=$(ip addr show | grep -B10 $subnet | grep mtu | tail -1 | sed 's/[0-9]*: \(.*\): .*/\1/')
sed -i 's/^eth=.*//' /opt/brother/scanner/brscan-skey/brscan-skey.config
# if found an interface for scanner subnet. Will use this to contact scanner.
if [[ -z "$interface" ]]; then
	# if scanner subnet (roughly) not found in interfaces, assuming network_mode="host" is not set and using Docker default interface. 
	interface="eth0"
fi
echo "eth=$interface" >> /opt/brother/scanner/brscan-skey/brscan-skey.config
echo "using interface: $interface"
echo "-----"

echo "setting up host IP:"
sed -i 's/^ip_address=.*//' /opt/brother/scanner/brscan-skey/brscan-skey.config
if [[ -z "$HOST_IPADDRESS" ]]; then
	echo "no host IP configured, using default discovery"
else
	echo "using host IP: $HOST_IPADDRESS"
	echo "ip_address=$HOST_IPADDRESS" >> /opt/brother/scanner/brscan-skey/brscan-skey.config
fi
echo "-----"

echo "setting up username:"
sed -i 's/^user=.*//' /opt/brother/scanner/brscan-skey/brscan-skey.config
echo "user=${USERNAME:-docker}" >> /opt/brother/scanner/brscan-skey/brscan-skey.config
echo "using username: ${USERNAME:-docker}"
echo "-----"

echo "whole config:"
cat /opt/brother/scanner/brscan-skey/brscan-skey.config
echo "-----"

echo "starting scanner drivers..."
driver_cmds=("/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS" /usr/bin/brscan-skey)
for cmd in "${driver_cmds[@]}"
do
	#check if failed
	$cmd
	if [ $? -ne 0 ]; then
		echo "failed to start: `$cmd`"
		exit 1
	fi
done
echo "-----"

echo "setting up script permissions..."
#change ownership of scripts to root and setuid
chown root /opt/brother/scanner/brscan-skey/script/*.sh
chmod u+s /opt/brother/scanner/brscan-skey/script/*.sh
chmod o+x /opt/brother/scanner/brscan-skey/script/*.sh

echo "-----"

echo "setting up webserver:"

if [ -n "${WEBSERVER_ENABLE+x}" ]; then

	if [ -n "${WEBSERVER_PING_ENABLE+x}" ]; then
		echo "enabling ping status"
		(
			while true; do
				if /usr/bin/ping -c 1 $IPADDRESS > /dev/null; then
					echo "1" > /var/www/html/reachable.txt
				else
					echo "0" > /var/www/html/reachable.txt
				fi
				sleep 1
			done
		) &
		
	fi

	echo "starting webserver for API & GUI..."
	{
		echo "<?php"
		vars_to_save=(UID GID MODEL WEBSERVER_PING_ENABLE WEBSERVER_LABEL_SCANTOFILE WEBSERVER_LABEL_SCANTOEMAIL WEBSERVER_LABEL_SCANTOIMAGE WEBSERVER_LABEL_SCANTOOCR)
		for var in "${vars_to_save[@]}"
		do
			#escaping quotes
			echo "\$${var} = \"${!var//\"/\\\"}\";"
		done
		echo "?>"
		
	} > /var/www/html/lib/config.php
	chown www-data /var/www/html/lib/config.php
	echo "running on port ${WEBSERVER_PORT:-80}"
	sed -i "s/server.port\W*= 80/server.port = ${WEBSERVER_PORT:-80}/" /etc/lighttpd/lighttpd.conf
	/usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf
	echo "webserver started"
else
	echo "webserver not configured"
fi
echo "-----"

echo "capabilities:"
scanimage -A

echo "startup successful"
tail -f /var/log/scanner.log
exit 0
