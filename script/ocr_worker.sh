#!/bin/bash
# OCR queue worker.
#
# Serializes uploads to the OCR microservice so concurrent scans cannot
# saturate the upload bandwidth or overwhelm the OCR backend. One worker
# per container; coordination is done with atomic rename(2) ("mv") so the
# queue works on filesystems that do not support inotify or flock
# (e.g. SMB-mounted /scans).
#
# Queue layout (under $OCR_QUEUE_DIR, default /scans/.ocr_queue):
#   pending/      newly enqueued jobs; oldest first by filename prefix
#   in_progress/  the single job currently being processed
#   failed/       jobs that exceeded $OCR_MAX_ATTEMPTS
#
# Job file (KEY=VALUE text):
#   PDF=/scans/2026-05-17-17-22-59.pdf
#   DATE=2026-05-17-17-22-59
#   SUFFIX=front
#   ATTEMPTS=0

set -u

QUEUE_ROOT="${OCR_QUEUE_DIR:-/scans/.ocr_queue}"
PENDING_DIR="${QUEUE_ROOT}/pending"
IN_PROGRESS_DIR="${QUEUE_ROOT}/in_progress"
FAILED_DIR="${QUEUE_ROOT}/failed"
POLL_INTERVAL="${OCR_QUEUE_POLL_SECONDS:-5}"
MAX_ATTEMPTS="${OCR_MAX_ATTEMPTS:-5}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"

mkdir -p "$PENDING_DIR" "$IN_PROGRESS_DIR" "$FAILED_DIR"

log() {
  echo "[ocr_worker $(date +%Y-%m-%dT%H:%M:%S)] $*"
}

read_field() {
  local file="$1" key="$2"
  grep "^${key}=" "$file" 2>/dev/null | tail -n1 | cut -d= -f2-
}

write_attempts() {
  local file="$1" n="$2"
  local tmp="${file}.rewrite.$$"
  grep -v '^ATTEMPTS=' "$file" >"$tmp"
  echo "ATTEMPTS=$n" >>"$tmp"
  mv "$tmp" "$file"
}

# On startup, return half-processed jobs to the pending queue so a crash
# or container restart does not strand them. ATTEMPTS in the file is
# already incremented (see claim path) so we will not retry forever.
recover() {
  shopt -s nullglob
  for f in "$IN_PROGRESS_DIR"/*.job; do
    name=$(basename "$f")
    if mv "$f" "$PENDING_DIR/$name" 2>/dev/null; then
      log "recovered $name from in_progress"
    fi
  done
  shopt -u nullglob
}

# Upload one PDF and run the post-OCR side effects. Returns 0 on success,
# non-zero on any failure (network, missing file, missing config).
process_job() {
  local jobfile="$1"
  local pdf date suffix
  pdf=$(read_field "$jobfile" PDF)
  date=$(read_field "$jobfile" DATE)
  suffix=$(read_field "$jobfile" SUFFIX)

  if [ -z "${OCR_SERVER:-}" ] || [ -z "${OCR_PORT:-}" ] || [ -z "${OCR_PATH:-}" ]; then
    log "OCR_SERVER/OCR_PORT/OCR_PATH not set; cannot process"
    return 1
  fi
  if [ -z "$pdf" ] || [ -z "$date" ]; then
    log "malformed job $(basename "$jobfile"): PDF or DATE missing"
    return 1
  fi
  if [ ! -f "$pdf" ]; then
    log "input PDF missing: $pdf"
    return 1
  fi

  local out="/scans/${date}-ocr.pdf"
  log "uploading $pdf to ${OCR_SERVER}:${OCR_PORT}/${OCR_PATH}"
  if ! curl --fail --silent --show-error \
        -F "userfile=@${pdf}" -H "Expect:" \
        -o "$out" \
        "${OCR_SERVER}:${OCR_PORT}/${OCR_PATH}"; then
    log "OCR upload failed for $pdf"
    rm -f "$out"
    return 1
  fi

  log "OCR finished -> $out"

  # Best-effort notifications; do not fail the job if any of these error.
  "${SCRIPT_DIR}/trigger_inotify.sh" "${SSH_USER:-}" "${SSH_PASSWORD:-}" "${SSH_HOST:-}" "${SSH_PATH:-}" "${date}-ocr.pdf" || true
  "${SCRIPT_DIR}/trigger_telegram.sh" "${date}-ocr.pdf (${suffix:-?}) OCR finished" || true
  "${SCRIPT_DIR}/sendtoftps.sh" "${FTP_USER:-}" "${FTP_PASSWORD:-}" "${FTP_HOST:-}" "${FTP_PATH:-}" "$out" || true

  if [ "${REMOVE_ORIGINAL_AFTER_OCR:-}" = "true" ] && [ -f "$out" ]; then
    rm -f "$pdf"
  fi
  return 0
}

requeue_or_fail() {
  local jobfile="$1" attempts="$2"
  local name
  name=$(basename "$jobfile")
  if [ "$attempts" -ge "$MAX_ATTEMPTS" ]; then
    mv "$jobfile" "$FAILED_DIR/$name" 2>/dev/null || rm -f "$jobfile"
    log "$name exceeded $MAX_ATTEMPTS attempts; moved to failed/"
    return
  fi
  local backoff=$(( attempts * 30 ))
  log "$name attempt $attempts failed; retrying in ${backoff}s"
  sleep "$backoff"
  mv "$jobfile" "$PENDING_DIR/$name" 2>/dev/null || true
}

recover
log "queue worker started (poll=${POLL_INTERVAL}s, max_attempts=${MAX_ATTEMPTS})"

while true; do
  candidate=$(ls -1 "$PENDING_DIR"/*.job 2>/dev/null | head -n1 || true)
  if [ -z "$candidate" ]; then
    sleep "$POLL_INTERVAL"
    continue
  fi

  name=$(basename "$candidate")
  claim="$IN_PROGRESS_DIR/$name"

  # Atomic claim. If a competing worker (or recovery sweep) won, just retry.
  if ! mv "$candidate" "$claim" 2>/dev/null; then
    continue
  fi

  # Bump ATTEMPTS on disk *before* processing so a crash mid-upload is
  # accounted for and we will not loop forever on a poison job.
  current=$(read_field "$claim" ATTEMPTS)
  [ -z "$current" ] && current=0
  next=$(( current + 1 ))
  write_attempts "$claim" "$next"

  if process_job "$claim"; then
    rm -f "$claim"
  else
    requeue_or_fail "$claim" "$next"
  fi
done
