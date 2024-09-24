#!/bin/bash
# remove_blank - git.waldenlabs.net/calvinrw/brother-paperless-workflow
# Heavily based on from Anthony Street's (and other contributors')
# StackExchange answer: https://superuser.com/a/1307895

if [ -n "$REMOVE_BLANK_THRESHOLD" ]; then
  IN="$1"
  FILENAME="$(basename "${IN}")"
  FILENAME="${FILENAME%.*}"
  SCRIPTNAME="remove_blank.sh"
  PAGES="$(pdfinfo "$IN" | grep ^Pages: | tr -dc '0-9')"
  echo "$SCRIPTNAME: threshold=$REMOVE_BLANK_THRESHOLD; analyzing $PAGES pages"

  cd "$(dirname "$IN")" || exit
  pwd

  function non_blank() {
    for i in $(seq 1 "$PAGES"); do
      PERCENT=$(gs -o - -dFirstPage="${i}" -dLastPage="${i}" -sDEVICE=ink_cov "$IN" | grep CMYK | nawk 'BEGIN { sum=0; } {sum += $1 + $2 + $3 + $4;} END { printf "%.5f\n", sum } ')
      if [ $(echo "$PERCENT > $REMOVE_BLANK_THRESHOLD" | bc) -eq 1 ]; then
        echo "$i"
        echo "Page $i: keep" 1>&2
      else
        echo "Page $i: delete" 1>&2
      fi
    done | tee "$FILENAME.tmp"
  }

  set +x
  pdftk "${IN}" cat $(non_blank) output "${FILENAME}_noblank.pdf" &&
    mv "${FILENAME}_noblank.pdf" "$IN"
fi
