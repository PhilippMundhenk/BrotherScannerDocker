#!/bin/bash
# $1 = scanner device
# $2 = friendly name

{
echo "scantoemail.sh triggered"
#override environment, as brscan is screwing it up:
export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
/bin/bash $SCRIPTPATH/scanRear.sh $@

} >> /var/log/scanner.log 2>&1
