docker run \
    -d \
    -v /home/$USER/scans:/scans \
    -v $PWD/script:/opt/brother/scanner/brscan-skey/script/ \
    -e NAME="Scanner" \
    -e MODEL="MFC-L2700DW" \
    -e IPADDRESS="10.0.0.1" \
    --net=host brother-scanner
