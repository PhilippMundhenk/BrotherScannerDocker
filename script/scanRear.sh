#!/bin/bash
# $1 = scanner device
# $2 = friendly name

#override environment, as brscan is screwing it up:
export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)

# Resolution (dpi):
# 100,200,300,400,600
resolution=300
device=$1
cd /scans
date=$(ls -rd */ | grep $(date +"%Y-%m-%d") | head -1)
date=${date%/}
filename_base=/scans/$date/$date"-back-page"
output_file=$filename_base"%04d.pnm"

cd /scans/$date

kill -9 `cat scan_pid`
rm scan_pid

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

(
	#rename pages:
	numberOfPages=$(find . -maxdepth 1  -name "*front-page*" | wc -l)
	echo "number of pages scanned: "$numberOfPages
	
	cnt=0
	for filename in *front*.pnm; do
	        cnt=$((cnt+1))
	        cntFormatted=$(printf "%03d" $cnt)
			if [[ $filename = *"front"* ]]; then
	                $(mv $filename index$cntFormatted-1-$filename)
	        fi
	done
	cnt=0
	for filename in *back*.pnm; do
	        cnt=$((cnt+1))
	        if [[ $filename = *"back"* ]]; then
	                rearIndex=$((numberOfPages-cnt+1))
	                rearIndexFormatted=$(printf "%03d" $rearIndex)
	                $(mv $filename index$rearIndexFormatted-2-$filename)
	        fi
	done
	
	(
		echo "converting to PDF for $date..."
		gm convert -page A4+0+0 *.pnm /scans/$date.pdf	
		/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
		
		echo "cleaning up for $date..."
		cd /scans
		rm -rf $date
		
		echo "starting OCR for $date..."
		(
			curl -F "userfile=@/scans/$date.pdf" -H "Expect:" -o /scans/$date-ocr.pdf localhost:32800/ocr.php 
			/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date-ocr.pdf
		) &
	) &
) &