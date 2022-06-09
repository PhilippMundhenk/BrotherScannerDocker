adduser $USERNAME --disabled-password --force-badname --gecos ""
mkdir -p /scans
chmod 777 /scans
env > /opt/brother/scanner/env.txt
chmod -R 777 /opt/brother
su - $USERNAME -c "/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS"
su - $USERNAME -c "/usr/bin/brscan-skey"
echo "startup successful"
while true;
do
  sleep 1000
done
exit 0
