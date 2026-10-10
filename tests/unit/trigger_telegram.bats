#!/usr/bin/env bats

setup() {
  load '../helpers/common'
  common_setup
}

teardown() {
  common_teardown
}

@test "skips when TELEGRAM_TOKEN is empty" {
  unset TELEGRAM_TOKEN
  export TELEGRAM_CHATID="abc"
  run bash "$SCRIPT_DIR/trigger_telegram.sh" "hello"
  [ "$status" -eq 0 ]
  [[ "$output" == *"skipping Telegram trigger"* ]]
}

@test "skips when TELEGRAM_CHATID is empty" {
  export TELEGRAM_TOKEN="bot:tok"
  unset TELEGRAM_CHATID
  run bash "$SCRIPT_DIR/trigger_telegram.sh" "hello"
  [ "$status" -eq 0 ]
  [[ "$output" == *"skipping Telegram trigger"* ]]
}

@test "invokes wget with token and url-encoded body when both vars set" {
  export TELEGRAM_TOKEN="bot:tok"
  export TELEGRAM_CHATID="42"
  mock_record wget
  # jq is used to URL-encode the message; stub returns a deterministic value.
  mock_command jq 0 "Scanner%3A%20hello%20world"

  run bash "$SCRIPT_DIR/trigger_telegram.sh" "hello world"
  [ "$status" -eq 0 ]
  [ "$(mock_call_count wget)" -eq 1 ]
  # The Telegram API URL must include the token.
  [[ "$(mock_calls wget)" == *"api.telegram.org/bot:tok/sendMessage"* ]]
  # The POST body must include the chat id and encoded text.
  [[ "$(mock_calls wget)" == *"chat_id=42"* ]]
  [[ "$(mock_calls wget)" == *"text=Scanner%3A%20hello%20world"* ]]
}
