#!/bin/bash
# $1 = scanner device
# $2 = friendly name

#override environment, as brscan is screwing it up:
export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)

# Resolution (dpi):
# 100,200,300,400,600
resolution=300
device=$1
date=$(date +%Y-%m-%d-%H-%M-%S)

#check if a scan is waiting for conversion:
if [ -f "/home/$USER/scan_pid" ]; then
	#kill conversion and do right now:
	kill -9 `cat /home/$USER/scan_pid`
	
	gm convert -page A4+0+0 /scans/*.pnm /scans/$date.pdf
	rm /scans/*.pnm
	rm /home/$USER/scan_pid
	
	/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
fi

date=$(date +%Y-%m-%d-%H-%M-%S)
filename_base=/scans/$date"-front-page"
output_file=$filename_base"%04d.pnm"
echo "filename: "$output_file

if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 100000
else
    sleep  0.1
fi
scanimage -l 0 -t 0 -x 215 -y 297 --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution --batch=$output_file
if [ ! -s $filename_base"0001.pnm" ];then
  if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 1000000
  else
    sleep  1
  fi
  scanimage -l 0 -t 0 -x 215 -y 297 --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution --batch=$output_file
fi

#only convert when no back pages are being scanned:
{
	if [ "`which usleep  2>/dev/null `" != '' ];then
		usleep 120000000
	else
		sleep  120
	fi
	echo "converting to PDF..."
	gm convert -page A4+0+0 $filename_base*.pnm /scans/$date.pdf
	rm $filename_base*.pnm
	rm /home/$USER/scan_pid

	/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
} &
echo $! > /home/$USER/scan_pid
echo "converting process is running in PID: "$(cat /home/$USER/scan_pid)