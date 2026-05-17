#!/usr/bin/env bats

# The worker runs an infinite polling loop. Tests use a short
# OCR_QUEUE_POLL_SECONDS, MAX_ATTEMPTS=2 and a copy of the script with
# the linear backoff sed'd down to zero so a full success/failure cycle
# completes in seconds.

setup() {
  load '../helpers/common'
  common_setup

  export OCR_QUEUE_DIR="$test_tmp/queue"
  export OCR_OUTPUT_DIR="$test_tmp/scans"
  export OCR_QUEUE_POLL_SECONDS=1
  export OCR_MAX_ATTEMPTS=2
  mkdir -p "$OCR_OUTPUT_DIR"

  # Trigger scripts must be no-ops; unset every notification env var the
  # worker forwards, so trigger_telegram/trigger_inotify/sendtoftps all
  # take their "skip" branch instead of trying to reach real services.
  unset TELEGRAM_TOKEN TELEGRAM_CHATID
  unset SSH_USER SSH_PASSWORD SSH_HOST SSH_PATH
  unset FTP_USER FTP_PASSWORD FTP_HOST FTP_PATH
  unset REMOVE_ORIGINAL_AFTER_OCR

  # Patched copy of the worker with zero retry backoff. SCRIPT_DIR
  # detection inside the worker uses `dirname "$0"`, so we keep the
  # patched copy alongside the real trigger_*.sh helpers by placing it
  # in script/ via a unique name.
  WORKER="$test_tmp/ocr_worker_test_copy.sh"
  cp "$SCRIPT_DIR/ocr_worker.sh" "$WORKER"
  sed -i 's/local backoff=$(( attempts \* 30 ))/local backoff=0/' "$WORKER"
  # Make the worker resolve trigger_*.sh from the real script dir even
  # though we run our patched copy out of test_tmp.
  sed -i "s|SCRIPT_DIR=\"\$(cd \"\$(dirname \"\$0\")\" && pwd -P)\"|SCRIPT_DIR=\"$SCRIPT_DIR\"|" "$WORKER"
  chmod +x "$WORKER"
}

teardown() {
  common_teardown
}

# Helper: stage a job file in pending/.
stage_pending() {
  local name="$1" pdf="$2" date="$3"
  mkdir -p "$OCR_QUEUE_DIR/pending"
  cat >"$OCR_QUEUE_DIR/pending/$name" <<EOF
PDF=$pdf
DATE=$date
SUFFIX=front
ATTEMPTS=0
EOF
}

@test "recover sweeps orphaned in_progress files back to pending on startup" {
  mkdir -p "$OCR_QUEUE_DIR/in_progress"
  cat >"$OCR_QUEUE_DIR/in_progress/0000000-orphan.job" <<EOF
PDF=/scans/orphan.pdf
DATE=2026-05-17-99-99-99
SUFFIX=front
ATTEMPTS=1
EOF

  # No OCR config, so the recovered job will fail-and-fail again and
  # land in failed/ before timeout fires. We just need to prove the
  # recover step moved the orphan out of in_progress/.
  unset OCR_SERVER OCR_PORT OCR_PATH
  run timeout 6 bash "$WORKER"
  # Worker is killed by timeout (124).
  [ "$status" -eq 124 ] || [ "$status" -eq 0 ]
  [[ "$output" == *"recovered 0000000-orphan.job from in_progress"* ]]
}

@test "successful upload removes the job; output PDF is created" {
  export OCR_SERVER="ocr.local"
  export OCR_PORT="80"
  export OCR_PATH="ocr"

  : >"$test_tmp/source.pdf"
  stage_pending "0000001-job.job" "$test_tmp/source.pdf" "2026-05-17-test"
  # curl is "successful" - the script writes its output via -o, so we
  # also need that path to exist for the REMOVE_ORIGINAL_AFTER_OCR test
  # below; in this test we mock curl to also touch the output file.
  cat >"$MOCK_BIN/curl" <<'EOF'
#!/usr/bin/env bash
# Find the -o argument and touch that file so the post-OCR steps that
# check `[ -f "$out" ]` see a real artefact.
out=""
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then out="$a"; fi
  prev="$a"
done
[ -n "$out" ] && : >"$out"
exit 0
EOF
  chmod +x "$MOCK_BIN/curl"

  run timeout 5 bash "$WORKER"
  [ "$status" -eq 124 ] || [ "$status" -eq 0 ]
  # Job consumed.
  [ -z "$(ls "$OCR_QUEUE_DIR/pending/" 2>/dev/null)" ]
  [ -z "$(ls "$OCR_QUEUE_DIR/in_progress/" 2>/dev/null)" ]
  [ -z "$(ls "$OCR_QUEUE_DIR/failed/" 2>/dev/null)" ]
  # Output PDF created by the curl mock at the path the worker passed.
  [ -f "$OCR_OUTPUT_DIR/2026-05-17-test-ocr.pdf" ]
}

@test "REMOVE_ORIGINAL_AFTER_OCR deletes the source PDF on success" {
  export OCR_SERVER="ocr.local" OCR_PORT="80" OCR_PATH="ocr"
  export REMOVE_ORIGINAL_AFTER_OCR=true

  local src="$test_tmp/source.pdf"
  : >"$src"
  stage_pending "0000001-job.job" "$src" "2026-05-17-rm"

  # curl mock writes the expected -o output (so the [ -f "$out" ] check passes)
  cat >"$MOCK_BIN/curl" <<'EOF'
#!/usr/bin/env bash
out=""
prev=""
for a in "$@"; do
  [ "$prev" = "-o" ] && out="$a"
  prev="$a"
done
[ -n "$out" ] && : >"$out"
exit 0
EOF
  chmod +x "$MOCK_BIN/curl"

  run timeout 5 bash "$WORKER"
  # Source PDF must have been removed by the worker.
  [ ! -f "$src" ]
}

@test "repeated curl failures land the job in failed/ after MAX_ATTEMPTS" {
  export OCR_SERVER="ocr.local" OCR_PORT="80" OCR_PATH="ocr"
  : >"$test_tmp/source.pdf"
  stage_pending "0000001-fail.job" "$test_tmp/source.pdf" "2026-05-17-fail"

  # curl always fails
  mock_command curl 7

  run timeout 6 bash "$WORKER"
  # Should have moved through 2 attempts and ended in failed/.
  [ -z "$(ls "$OCR_QUEUE_DIR/pending/" 2>/dev/null)" ]
  [ -z "$(ls "$OCR_QUEUE_DIR/in_progress/" 2>/dev/null)" ]
  local failed_files
  failed_files=("$OCR_QUEUE_DIR"/failed/*.job)
  [ -f "${failed_files[0]}" ]
  # ATTEMPTS field in the final file is exactly MAX_ATTEMPTS.
  run cat "${failed_files[0]}"
  [[ "$output" == *"ATTEMPTS=2"* ]]
  [[ "$output" == *"PDF=$test_tmp/source.pdf"* ]]
}

@test "missing OCR env vars cause the job to land in failed/ (does not loop forever)" {
  unset OCR_SERVER OCR_PORT OCR_PATH
  : >"$test_tmp/source.pdf"
  stage_pending "0000001-noenv.job" "$test_tmp/source.pdf" "2026-05-17-noenv"

  run timeout 6 bash "$WORKER"
  [ -z "$(ls "$OCR_QUEUE_DIR/pending/" 2>/dev/null)" ]
  local failed_files
  failed_files=("$OCR_QUEUE_DIR"/failed/*.job)
  [ -f "${failed_files[0]}" ]
  [[ "$output" == *"OCR_SERVER/OCR_PORT/OCR_PATH not set"* ]]
}

@test "missing input PDF causes the job to land in failed/" {
  export OCR_SERVER="ocr.local" OCR_PORT="80" OCR_PATH="ocr"
  # PDF path that does not exist
  stage_pending "0000001-missing.job" "$test_tmp/no-such-file.pdf" "2026-05-17-missing"

  run timeout 6 bash "$WORKER"
  local failed_files
  failed_files=("$OCR_QUEUE_DIR"/failed/*.job)
  [ -f "${failed_files[0]}" ]
  [[ "$output" == *"input PDF missing"* ]]
}
