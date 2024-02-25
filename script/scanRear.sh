#!/bin/bash
# $1 = scanner device
# $2 = friendly name

#override environment, as brscan is screwing it up:
#export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)
source /opt/brother/scanner/shell_env.txt

if [[ $RESOLUTION ]]; then
  resolution=$RESOLUTION
else
  resolution=300
fi

if [ "$USE_JPEG_COMPRESSION" = "true" ]; then
    compression_flag="-compress JPEG -quality 80"
else
    compression_flag=""
fi

device=$1
cd /scans
date=$(ls -rd */ | grep $(date +"%Y-%m-%d") | head -1)
date=${date%/}
filename_base=/scans/$date/$date"-back-page"
output_file=$filename_base"%04d.pnm"

cd /scans/$date

kill -9 `cat scan_pid`
rm scan_pid

#sthg is wrong with device name, probably escaping, use default printer:
#scan_cmd="scanimage -l 0 -t 0 -x 215 -y 297 --device-name=$device --resolution=$resolution --batch=$output_file"
scan_cmd="scanimage -l 0 -t 0 -x 215 -y 297 --resolution=$resolution --batch=$output_file"
sleep  0.1
$($scan_cmd)
if [ ! -s $filename_base"0001.pnm" ];then
	sleep  1
	$($scan_cmd)
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
		gm convert -page A4+0+0 $compression_flag *.pnm /scans/$date.pdf
		#change ownership to target user/group
		chown $UID:$GID /scans/$date.pdf
		/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh "${SSH_USER}" "${SSH_PASSWORD}" "${SSH_HOST}" "${SSH_PATH}" $date.pdf
		
		echo "cleaning up for $date..."
		cd /scans
		rm -rf $date
		
		if [ -z "${OCR_SERVER}" ] || [ -z "${OCR_PORT}" ] || [ -z "${OCR_PATH}" ]; then
			echo "OCR environment variables not set, skipping OCR."
		else
			echo "starting OCR for $date..."
			(
				curl -F "userfile=@/scans/$date.pdf" -H "Expect:" -o /scans/$date-ocr.pdf ${OCR_SERVER}:${OCR_PORT}/${OCR_PATH}
				#change ownership to target user/group
				chown $UID:$GID /scans/$date-ocr.pdf
				/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh "${SSH_USER}" "${SSH_PASSWORD}" "${SSH_HOST}" "${SSH_PATH}" $date-ocr.pdf

				/opt/brother/scanner/brscan-skey/script/sendtoftps.sh \
				  "${FTP_USER}" \
				  "${FTP_PASSWORD}" \
				  "${FTP_HOST}" \
				  "${FTP_PATH}" \
				  "${date}.pdf"
			) &
		fi
	) &
) &
