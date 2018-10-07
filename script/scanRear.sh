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
filename_base=/scans/$date"-back-page"
output_file=$filename_base"%04d.pnm"

#kill front page conversion process, as we will do conversion later on:
kill -9 `cat /home/$USER/scan_pid`
rm /home/$USER/scan_pid

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

cd /scans

#rename pages:
numberOfPages=$(find . -maxdepth 1  -name "*front-page*" | wc -l)
echo "number of pages scanned: "$numberOfPages

cnt=0
for filename in *front*.pnm; do
        cnt=$((cnt+1))
		if [[ $filename = *"front"* ]]; then
                $(mv $filename index$cnt-1-$filename)
        fi
done
cnt=0
for filename in *back*.pnm; do
        cnt=$((cnt+1))
        if [[ $filename = *"back"* ]]; then
                rearIndex=$((numberOfPages-cnt+1))
                $(mv $filename index$rearIndex-2-$filename)
        fi
done

echo "converting to PDF..."
gm convert -page A4+0+0 /scans/*.pnm /scans/$date.pdf
#TODO: make settings configurable (especially host and port and switch to turn on/off)
curl -F "userfile=@/scans/$date.pdf" -H "Expect:" -o /scans/$date-ocr.pdf localhost:32769/ocr.php
rm /scans/*.pnm

/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
#TODO this is temporary only (final is only one PDF file):
/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date-ocr.pdf
