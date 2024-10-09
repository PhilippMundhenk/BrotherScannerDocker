#!/usr/bin/env python3

import urllib.parse
from typing import Optional, TextIO

import requests


def trigger_telegram(
    log: TextIO, message: str, token: Optional[str], chat_id: Optional[str]
) -> None:
    """Sends a Telegram message using the provided token and chat ID."""

    if not token or not chat_id:
        print(
            "  INFO: TELEGRAM_TOKEN or TELEGRAM_CHATID environment variables not set, skipping Telegram trigger."
        )
        return

    # URL encode the message
    encoded_message = urllib.parse.quote(message, safe="")

    # Build the URL
    url = f"https://api.telegram.org/{token}/sendMessage"

    # Prepare data payload
    payload = {"chat_id": chat_id, "text": encoded_message}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for non-200 response
        print("  Telegram message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: sending Telegram message: {e}")
