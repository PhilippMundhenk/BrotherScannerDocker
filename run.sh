docker run -d -v /home/$USER/scans:/root/brscan -e "NAME=ABCScanner" -e "MODEL=MFC-7860DW" -e "IPADDRESS=192.168.1.123" --net=host brother
