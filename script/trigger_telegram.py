#!/usr/bin/env python3

from typing import Optional, TextIO

import requests


def trigger_telegram(
    log: TextIO, message: str, token: Optional[str], chat_id: Optional[str]
) -> bool:
    """Sends a Telegram message using the provided bot token and chat ID.

    The token is used as given, so it must include the leading "bot"
    (for example "bot123456:ABC-DEF"). Returns True when the message was
    accepted, False when it was skipped or the API call failed.
    """

    if not token or not chat_id:
        print(
            "  INFO: TELEGRAM_TOKEN or TELEGRAM_CHATID environment variables not set, skipping Telegram trigger."
        )
        return False

    url = f"https://api.telegram.org/{token}/sendMessage"
    # The body is JSON, so the text goes in as-is; URL-encoding it here would
    # make the message arrive percent-encoded.
    payload = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        print("  Telegram message sent successfully.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: sending Telegram message: {e}")
        return False
