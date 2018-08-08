#! /bin/bash
# $1 = scanner device
# $2 = friendly name

# Resolution (dpi):
# 100,200,300,400,600
resolution=300
device=$1
mkdir -p ~/brscan
date=$(date +%Y-%m-%d-%H-%M-%S)
output_file=~/brscan/$date"-page%d.pnm"

if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 100000
else
    sleep  0.1
fi
scanadf --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution -o $output_file  2>/dev/null
if [ ! -s $output_file ];then
  if [ "`which usleep  2>/dev/null `" != '' ];then
    usleep 1000000
  else
    sleep  1
  fi
  scanadf --device-name "$device" --source "Automatic Document Feeder(centrally aligned)" --resolution $resolution -o $output_file  2>/dev/null
fi

gm convert ~/brscan/$date-page*.pnm ~/brscan/$date.jpg
rm ~/brscan/$date-page*.pnm
