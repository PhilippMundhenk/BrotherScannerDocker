#!/bin/bash
# $1 = scanner device
# $2 = friendly name

#override environment, as brscan is screwing it up:
export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)

resolution="${RESOLUTION:-300}"

gm_opts=(-page A4+0+0)
if [ "$USE_JPEG_COMPRESSION" = "true" ]; then
  gm_opts+=(-compress JPEG -quality 80)
fi

device="$1"
script_dir="/opt/brother/scanner/brscan-skey/script"
remove_blank="${script_dir}/remove_blank.sh"

set -e # Exit on error

mkdir -p /tmp
cd /tmp
date=$(ls -rd */ | grep "$(date +"%Y-%m-%d")" | head -1)
date=${date%/}
tmp_dir="/tmp/${date}"
filename_base="${tmp_dir}/${date}-back-page"
tmp_output_file="${filename_base}%04d.pnm"
tmp_output_pdf_file="${tmp_dir}/${date}.pdf"
output_pdf_file="/scans/${date}.pdf"

cd "$tmp_dir"

kill -9 "$(cat scan_pid)"
rm scan_pid

function scan_cmd() {
  # `brother4:net1;dev0` device name gets passed to scanimage, which it refuses as an invalid device name for some reason.
  # Let's use the default scanner for now
  # scanimage -l 0 -t 0 -x 215 -y 297 --device-name="$1" --resolution="$2" --batch="$3"
  scanimage -l 0 -t 0 -x 215 -y 297 --format=pnm --resolution="$2" --batch="$3"
}

if [ "$(which usleep 2>/dev/null)" != '' ]; then
  usleep 100000
else
  sleep 0.1
fi
scan_cmd "$device" "$resolution" "$tmp_output_file"
if [ ! -s "${filename_base}0001.pnm" ]; then
  if [ "$(which usleep 2>/dev/null)" != '' ]; then
    usleep 1000000
  else
    sleep 1
  fi
  scan_cmd "$device" "$resolution" "$tmp_output_file"
fi

(

  #rename pages:
  numberOfPages=$(find . -maxdepth 1 -name "*front-page*" | wc -l)
  echo "number of pages scanned: $numberOfPages"

  cnt=0
  for filename in *front*.pnm; do
    cnt=$((cnt + 1))
    cntFormatted=$(printf "%03d" $cnt)
    if [[ $filename = *"front"* ]]; then
      mv "$filename" "index${cntFormatted}-1-${filename}"
    fi
  done
  cnt=0
  for filename in *back*.pnm; do
    cnt=$((cnt + 1))
    if [[ $filename = *"back"* ]]; then
      rearIndex=$((numberOfPages - cnt + 1))
      rearIndexFormatted=$(printf "%03d" $rearIndex)
      mv "$filename" "index${rearIndexFormatted}-2-${filename}"
    fi
  done

  (
    echo "converting to PDF for $date..."
    gm convert ${gm_opts[@]} ./*.pnm "$tmp_output_pdf_file"
    ${script_dir}/trigger_inotify.sh "${SSH_USER}" "${SSH_PASSWORD}" "${SSH_HOST}" "${SSH_PATH}" "${output_pdf_file}"
    ${script_dir}/trigger_telegram.sh "${date}.pdf (rear) scanned"
	${script_dir}/sendtoftps.sh \
          "${FTP_USER}" \
          "${FTP_PASSWORD}" \
          "${FTP_HOST}" \
          "${FTP_PATH}" \
          "${output_pdf_file}"

    $remove_blank "$tmp_output_pdf_file"
    mv "$tmp_output_pdf_file" "$output_pdf_file"

    $script_dir/trigger_inotify.sh "${SSH_USER}" "${SSH_PASSWORD}" "${SSH_HOST}" "${SSH_PATH}" "${output_pdf_file}"

    echo "cleaning up for $date..."
    cd /scans || exit
    rm -rf "$tmp_dir"

    if [ -z "${OCR_SERVER}" ] || [ -z "${OCR_PORT}" ] || [ -z "${OCR_PATH}" ]; then
      echo "OCR environment variables not set, skipping OCR."
    else
      echo "starting OCR for $date..."
      (
        curl -F "userfile=@${output_pdf_file}" -H "Expect:" -o "/scans/${date}-ocr.pdf" "${OCR_SERVER}":"${OCR_PORT}"/"${OCR_PATH}"
        ${script_dir}/trigger_inotify.sh "${SSH_USER}" "${SSH_PASSWORD}" "${SSH_HOST}" "${SSH_PATH}" "${date}-ocr.pdf"
        ${script_dir}/trigger_telegram.sh "${date}-ocr.pdf (rear) OCR finished"
        ${script_dir}/sendtoftps.sh \
          "${FTP_USER}" \
          "${FTP_PASSWORD}" \
          "${FTP_HOST}" \
          "${FTP_PATH}" \
          "/scans/${date}-ocr.pdf"

          if [ "${REMOVE_ORIGINAL_AFTER_OCR}" = true ]; then
			if [ -f "/scans/${date}-ocr.pdf" ]; then
				rm ${output_pdf_file}
			fi
          fi
      ) &
    fi
  ) &
) &
