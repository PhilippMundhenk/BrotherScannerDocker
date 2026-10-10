#!/usr/bin/env bats

setup() {
  load '../helpers/common'
  common_setup
  export OCR_QUEUE_DIR="$test_tmp/queue"
}

teardown() {
  common_teardown
}

@test "exits non-zero when fewer than 3 arguments are given" {
  run bash "$SCRIPT_DIR/ocr_enqueue.sh" /scans/a.pdf 2026-05-17
  [ "$status" -ne 0 ]
  [[ "$output" == *"usage:"* ]]
}

@test "creates pending/ if missing and writes job file with all fields" {
  run bash "$SCRIPT_DIR/ocr_enqueue.sh" /scans/test.pdf 2026-05-17-18-00-00 front
  [ "$status" -eq 0 ]
  [ -d "$OCR_QUEUE_DIR/pending" ]
  # exactly one *.job file
  local jobs
  jobs=("$OCR_QUEUE_DIR"/pending/*.job)
  [ "${#jobs[@]}" -eq 1 ]
  run cat "${jobs[0]}"
  [[ "$output" == *"PDF=/scans/test.pdf"* ]]
  [[ "$output" == *"DATE=2026-05-17-18-00-00"* ]]
  [[ "$output" == *"SUFFIX=front"* ]]
  [[ "$output" == *"ATTEMPTS=0"* ]]
}

@test "leaves no .tmp file behind (atomic rename completed)" {
  run bash "$SCRIPT_DIR/ocr_enqueue.sh" /scans/test.pdf 2026-05-17-18-00-00 front
  [ "$status" -eq 0 ]
  # any hidden .tmp file in pending/ would indicate the stage step failed
  # to atomically rename into place
  local leftovers
  leftovers="$(find "$OCR_QUEUE_DIR/pending" -name '.*.tmp' -print)"
  [ -z "$leftovers" ]
}

@test "filename starts with a sortable numeric timestamp" {
  run bash "$SCRIPT_DIR/ocr_enqueue.sh" /scans/a.pdf 2026-05-17-18-00-00 front
  [ "$status" -eq 0 ]
  local f
  f="$(basename "$(ls "$OCR_QUEUE_DIR"/pending/*.job)")"
  # must start with at least 10 digits (date +%s%N gives 19 in practice)
  [[ "$f" =~ ^[0-9]{10,}- ]]
}

@test "two enqueues in sequence produce two distinct jobs that sort in order" {
  bash "$SCRIPT_DIR/ocr_enqueue.sh" /scans/a.pdf 2026-05-17-18-00-00 front >/dev/null
  bash "$SCRIPT_DIR/ocr_enqueue.sh" /scans/b.pdf 2026-05-17-18-00-01 rear  >/dev/null
  local count
  count=$(find "$OCR_QUEUE_DIR/pending" -name '*.job' | wc -l)
  [ "$count" -eq 2 ]
  # First-by-name (timestamp sort) must be the one we enqueued first.
  local first
  first="$(ls "$OCR_QUEUE_DIR"/pending/*.job | head -n1)"
  grep -q '^PDF=/scans/a.pdf' "$first"
}
