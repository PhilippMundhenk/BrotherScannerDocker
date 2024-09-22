#!/bin/bash
# $1 = scanner device
# $2 = friendly name

{
  #override environment, as brscan is screwing it up:
  export $(grep -v '^#' /opt/brother/scanner/env.txt | xargs)

  resolution="${RESOLUTION:-300}"

  gm_opts=(-page A4+0+0)
  if [ "$USE_JPEG_COMPRESSION" = "true" ]; then
    gm_opts+=(-compress JPEG -quality 80)
  fi

  device="$1"
  date=$(date +%Y-%m-%d-%H-%M-%S)
  script_dir="/opt/brother/scanner/brscan-skey/script"
  tmp_dir="/tmp/$date"
  filename_base="${tmp_dir}/${date}-front-page"
  tmp_output_file="${filename_base}%04d.pnm"
  output_pdf_file="/scans/${date}.pdf"

  set -e # Exit on error

  mkdir -p "$tmp_dir"
  cd "$tmp_dir"
  filename_base="/tmp/${date}/${date}-front-page"
  output_file="${filename_base}%04d.pnm"
  echo "filename: $tmp_output_file"

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

  #only convert when no back pages are being scanned:
  (
    if [ "$(which usleep 2>/dev/null)" != '' ]; then
      usleep 120000000
    else
      sleep 120
    fi

    (
      echo "converting to PDF for $date..."
      gm convert ${gm_opts[@]} "$filename_base"*.pnm "$output_pdf_file"
      ${script_dir}/trigger_inotify.sh "${SSH_USER}" "${SSH_PASSWORD}" "${SSH_HOST}" "${SSH_PATH}" "${output_pdf_file}"
      ${script_dir}/trigger_telegram.sh "${date}.pdf (front) scanned"

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
          ${script_dir}/trigger_telegram.sh "${date}-ocr.pdf (front) OCR finished"
          ${script_dir}/sendtoftps.sh \
            "${FTP_USER}" \
            "${FTP_PASSWORD}" \
            "${FTP_HOST}" \
            "${FTP_PATH}" \
            "${output_pdf_file}"
        ) &
      fi
    ) &
  ) &
  echo $! >scan_pid
  echo "conversion process for $date is running in PID: $(cat scan_pid)"

} >>/var/log/scanner.log 2>&1
