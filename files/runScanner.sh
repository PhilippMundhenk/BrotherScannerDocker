#!/bin/bash
if [[ -z ${UID} ]]; then
	UID=1000
fi
if [[ -z ${GID} ]]; then
	GID=1000
fi
groupadd --gid $GID NAS
adduser $USERNAME --uid $UID --gid $GID --disabled-password --force-badname --gecos ""
mkdir -p /scans
chmod 777 /scans
touch /var/log/scanner.log
chown $USERNAME /var/log/scanner.log
env > /opt/brother/scanner/env.txt
chmod -R 777 /opt/brother

subnet=$(echo $IPADDRESS | sed 's/\([0-9]*\.[0-9]*\.\)[0-9]*\.[0-9]*/\1/')
interface=$(ip addr show | grep -B10 $subnet | grep mtu | tail -1 | sed 's/[0-9]*: \(.*\): .*/\1/')
echo "eth=$interface" >> /opt/brother/scanner/brscan-skey/brscan-skey.config

su - $USERNAME -c "/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS"
su - $USERNAME -c "/usr/bin/brscan-skey"

if [ "$WEBSERVER" == "true" ]; then
	echo "starting webserver for API & GUI..."
	{
		echo "<?php"
		echo "\$UID=$UID;"
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
		echo "?>"
		
	} > /var/www/html/config.php
	chown www-data /var/www/html/config.php
	if [[ -z ${PORT} ]]; then
		PORT=80
	fi
	echo "running on port $PORT"
	sed -i "s/server.port\W*= 80/server.port = $PORT/" /etc/lighttpd/lighttpd.conf
	/usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf
	echo "webserver started"
fi

echo "capabilities:"
scanimage -A

echo "startup successful"
while true;
do
  tail -f /var/log/scanner.log
done
exit 0
