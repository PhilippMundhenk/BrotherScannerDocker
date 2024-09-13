#!/bin/bash
# $1 = text

# Check if TELEGRAM_TOKEN and TELEGRAM_CHATID are both set
if [ -z "${TELEGRAM_TOKEN}" ] || [ -z "${TELEGRAM_CHATID}" ]; then
  echo "TELEGRAM_TOKEN or TELEGRAM_CHATID is not set"
  exit 1
fi

TELEGRAM_URL="https://api.telegram.org/${TELEGRAM_TOKEN}/sendMessage"
TELEGRAM_TEXT="Scanner: $1"


# Send message via Telegram API
curl --silent "${TELEGRAM_URL}?chat_id=${TELEGRAM_CHATID}&text=scanner" > /dev/null
echo "${TELEGRAM_URL}?chat_id=${TELEGRAM_CHATID}&text=${TELEGRAM_TEXT}"
echo "Message sent to Telegram chat"
