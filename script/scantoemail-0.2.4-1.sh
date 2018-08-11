#! /bin/bash
# $1 = scanner device
# $2 = friendly name

#override environment, as brscan is screwing it up:
export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)

# Resolution (dpi):
# 100,200,300,400,600
resolution=300
device=$1
date=$(date +%Y-%m-%d-%H-%M-%S)
output_file=/scans/$date"-page%d.pnm"

if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 100000
else
    sleep  0.1
fi
scanadf --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution -o $output_file
if [ ! -s $output_file ];then
  if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 1000000
  else
    sleep  1
  fi
  scanadf --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution -o $output_file
fi

gm convert /scans/$date-page*.pnm /scans/$date.pdf
rm /scans/$date-page*.pnm

if [[ -z "${SSH_USER}" ]]; then
  /opt/brother/scanner/brscan-skey/script/trigger_inotify.sh $SSH_USER $SSH_PASSWORD $SSH_HOST $SSH_PATH $date.pdf
fi

if [[ -z "${FTP_USER}" ]]; then
  curl --ftp-ssl -T "/scans/$date.pdf" -k -u "$FTP_USER:$FTP_PASSWORD" "ftp://$FTP_HOST/$FTP_PATH"
fi
