docker run -d -v /home/$USER/scans:/scans -v script:/opt/brother/scanner/brscan-skey/script/ -e "NAME=Scanner" -e "MODEL=MFC-L2700DW" -e "IPADDRESS=192.168.1.123" --net=host brother
