#!/bin/bash
# Append a job to the OCR worker's pending queue.
#
# Usage: ocr_enqueue.sh <pdf_path> <date> <suffix>
#   pdf_path - absolute path to the PDF to OCR (typically /scans/<date>.pdf)
#   date     - the date stamp used elsewhere in the pipeline; becomes the
#              filename for the OCR output (/scans/<date>-ocr.pdf)
#   suffix   - "front", "rear", or similar; used only for log/notification text

set -eu

PDF="${1:-}"
DATE="${2:-}"
SUFFIX="${3:-}"

if [ -z "$PDF" ] || [ -z "$DATE" ] || [ -z "$SUFFIX" ]; then
  echo "ocr_enqueue.sh: usage: $0 <pdf_path> <date> <suffix>" >&2
  exit 2
fi

QUEUE_ROOT="${OCR_QUEUE_DIR:-/scans/.ocr_queue}"
PENDING_DIR="${QUEUE_ROOT}/pending"
mkdir -p "$PENDING_DIR"

# Write to a hidden temp file first then atomically rename into place so
# the worker can never observe a partially written job. Filename starts
# with a sortable timestamp so the worker drains in roughly FIFO order.
ts=$(date +%s%N)
basename="${ts}-${DATE}-${SUFFIX}.job"
tmpfile="${PENDING_DIR}/.${basename}.tmp"
final="${PENDING_DIR}/${basename}"

{
  echo "PDF=${PDF}"
  echo "DATE=${DATE}"
  echo "SUFFIX=${SUFFIX}"
  echo "ATTEMPTS=0"
} >"$tmpfile"

mv "$tmpfile" "$final"
echo "ocr_enqueue: queued ${basename}"
