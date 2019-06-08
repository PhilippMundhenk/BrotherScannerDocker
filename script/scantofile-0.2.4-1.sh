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
	
	(
		mkdir "/scans/convert_$date"
		mv /scans/*.pnm "/scans/convert_$date"
		cd "/scans/convert_$date"
		gm convert -page A4+0+0 *.pnm /scans/$date.pdf
		cd /scans
		rm -rf "/scans/convert_$date"
		rm /home/$USER/scan_pid
		
		/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
		
		(
			curl -F "userfile=@/scans/$date.pdf" -H "Expect:" -o /scans/$date-ocr.pdf localhost:32800/ocr.php
			/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date-ocr.pdf
		) &
	) &
fi

if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 100000
else
    sleep  0.1
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
(
	if [ "`which usleep  2>/dev/null `" != '' ];then
		usleep 120000000
	else
		sleep  120
	fi
	
	rm /home/$USER/scan_pid
	
	(
		mkdir "/scans/convert_$date"
		mv /scans/*.pnm "/scans/convert_$date"
		cd "/scans/convert_$date"
		echo "converting to PDF..."
		gm convert -page A4+0+0 $filename_base*.pnm /scans/$date.pdf
		cd /scans
		rm -rf "/scans/convert_$date"

		/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
	
		(
			curl -F "userfile=@/scans/$date.pdf" -H "Expect:" -o /scans/$date-ocr.pdf localhost:32800/ocr.php
			/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date-ocr.pdf
		) &
	) &
) &
echo $! > /home/$USER/scan_pid
echo "converting process is running in PID: "$(cat /home/$USER/scan_pid)