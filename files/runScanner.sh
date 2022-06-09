adduser $USERNAME --disabled-password --force-badname --gecos ""
mkdir -p /scans
chmod 777 /scans
env > /opt/brother/scanner/env.txt
mkdir -p /etc/opt/brother/scanner/brscan4/
chmod -R 777 /etc/opt/brother
rm -rf /etc/opt/brother/scanner/brscan4//brsanenetdevice4.cfg
su - $USERNAME -c "/usr/bin/brsaneconfig4 -a name=$NAME model=$MODEL ip=$IPADDRESS"
su - $USERNAME -c "/usr/bin/brscan-skey"
echo "startup successful"
while true;
do
  sleep 1000
done
exit 0
