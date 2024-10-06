docker cp ./www brotherscannerdocker-brother-scanner-1:/var/
docker exec brotherscannerdocker-brother-scanner-1 chown -R www-data:root /var/www/
docker cp ./script brotherscannerdocker-brother-scanner-1:/opt/brother/scanner/brscan-skey/
docker exec brotherscannerdocker-brother-scanner-1 chown -R root:root /opt/brother/scanner/brscan-skey/