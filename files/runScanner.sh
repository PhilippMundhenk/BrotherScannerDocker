adduser $USERNAME --disabled-password --force-badname --gecos ""
mkdir -p /scans
chmod 777 /scans
env > /opt/brother/scanner/env.txt
su - $USERNAME -c "/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS"
su - $USERNAME -c "/usr/bin/brscan-skey"
while true;
do
  sleep 1000
done
exit 0
