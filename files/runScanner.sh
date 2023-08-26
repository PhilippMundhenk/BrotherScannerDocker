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
su - $USERNAME -c "/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS"
su - $USERNAME -c "/usr/bin/brscan-skey"

echo "capabilities:"
scanimage -A

echo "startup successful"
while true;
do
  tail -f /var/log/scanner.log
done
exit 0
