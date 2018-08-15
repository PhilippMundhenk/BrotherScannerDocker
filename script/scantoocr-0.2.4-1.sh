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
filename_base=/scans/$date"-page"
output_file=$filename_base"%d.pnm"

if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 100000
else
    sleep  0.1
fi
scanadf --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution -o $output_file
if [ ! -s $filename_base"1.pnm" ];then
  if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 1000000
  else
    sleep  1
  fi
  scanadf --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution -o $output_file
fi

gm convert /scans/$date-page*.pnm /scans/$date.pdf
rm /scans/$date-page*.pnm

/opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
