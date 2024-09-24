#!/bin/bash

# Check if TELEGRAM_TOKEN and TELEGRAM_CHATID are both set
if [ -z "${TELEGRAM_TOKEN}" ] || [ -z "${TELEGRAM_CHATID}" ]; then
  echo "TELEGRAM_TOKEN or TELEGRAM_CHATID environment variables not set, skipping Telegram trigger."
else
  # Use the environment variables TELEGRAM_TOKEN and TELEGRAM_CHATID
  TOKEN="$TELEGRAM_TOKEN"
  CHAT_ID="$TELEGRAM_CHATID"

  # The message is passed as a parameter
  MESSAGE="Scanner: $1"

  # URL encode the message to handle spaces and special characters
  ENCODED_MESSAGE=$(echo "$MESSAGE" | jq -sRr @uri)

  # Send the message using wget
  wget -qO- --post-data="chat_id=$CHAT_ID&text=$ENCODED_MESSAGE" "https://api.telegram.org/$TOKEN/sendMessage" >/dev/null
fi
