#!/bin/bash
# $1 = scanner device
# $2 = friendly name

SCRIPTPATH="$(
  cd "$(dirname "$0")" || exit
  pwd -P
)"

"$SCRIPTPATH"/scantoemail.py $@
