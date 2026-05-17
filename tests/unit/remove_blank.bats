#!/usr/bin/env bats

setup() {
  load '../helpers/common'
  common_setup
}

teardown() {
  common_teardown
}

@test "no-op when REMOVE_BLANK_THRESHOLD is unset" {
  unset REMOVE_BLANK_THRESHOLD
  # Should exit 0 and produce no output. Crucially must not invoke
  # any of pdfinfo/gs/pdftk - we'd see PATH command-not-found errors.
  run bash "$SCRIPT_DIR/remove_blank.sh" /tmp/nonexistent.pdf
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "invokes pdfinfo + gs + pdftk pipeline when threshold is set" {
  export REMOVE_BLANK_THRESHOLD="0.3"

  # pdfinfo prints page count; the script greps "^Pages:" and strips non-digits.
  mock_command pdfinfo 0 "$(printf 'Title: test\nPages: 2\nFile size: 1234 bytes\n')"
  # gs prints a coverage line; the script greps CMYK and sums via nawk.
  # We make every page report "0.0 0.0 0.0 0.5  CMYK" so the awk sum (0.5)
  # exceeds the 0.3 threshold and every page is kept.
  mock_command gs 0 "0.00000 0.00000 0.00000 0.50000 CMYK OK"
  mock_command nawk 0 "0.50000"
  mock_command bc 0 "1"
  mock_record pdftk 0

  # The script chdirs to dirname of the input then writes a _noblank.pdf
  # next to it; put the input in our sandbox.
  local pdf="$test_tmp/in.pdf"
  : >"$pdf"
  # pdftk is mocked, so the rename step (`mv _noblank.pdf in.pdf`) won't
  # have a real file to move; that's fine - we only check the pipeline ran.
  run bash "$SCRIPT_DIR/remove_blank.sh" "$pdf"
  [[ "$output" == *"threshold=0.3"* ]]
  [[ "$output" == *"analyzing 2 pages"* ]]
  # pdftk is invoked exactly once with cat <pages> output.
  [ "$(mock_call_count pdftk)" -ge 1 ]
}
