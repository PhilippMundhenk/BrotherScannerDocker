#!/bin/bash
# $1 = scanner device
# $2 = friendly name

{
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
date=$(date +%Y-%m-%d-%H-%M-%S)

mkdir "/scans/$date"
cd "/scans/$date"
filename_base=/scans/$date/$date"-front-page"
output_file=$filename_base"%04d.pnm"
echo "filename: "$output_file

#sthg is wrong with device name, probably escaping, use default printer:
#scan_cmd="scanimage -l 0 -t 0 -x 215 -y 297 --device-name=$device --resolution=$resolution --batch=$output_file"
scan_cmd="scanimage -l 0 -t 0 -x 215 -y 297 --resolution=$resolution --batch=$output_file"
sleep  0.1
$($scan_cmd)
if [ ! -s $filename_base"0001.pnm" ];then
  sleep 1
  $($scan_cmd)
fi

#only convert when no back pages are being scanned:
(
	sleep  120	
	
	(
		echo "converting to PDF for $date..."
		gm convert -page A4+0+0 $compression_flag $filename_base*.pnm /scans/$date.pdf
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
echo $! > scan_pid
echo "conversion process for $date is running in PID: "$(cat scan_pid)

} >> /var/log/scanner.log 2>&1
