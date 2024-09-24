#!/usr/bin/python3

import os
import urllib.parse
from typing import TextIO


def trigger_telegram(log: TextIO, token: str, chat_id: str, message: str) -> None:
    """Sends a Telegram message using the provided token and chat ID."""

    if not token or not chat_id:
        print(
            "  INFO: TELEGRAM_TOKEN or TELEGRAM_CHATID environment variables not set, skipping Telegram trigger."
        )
        exit(1)

    # URL encode the message
    encoded_message = urllib.parse.quote(message, safe="")

    # Build the URL
    url = f"https://api.telegram.org/{token}/sendMessage"

    # Prepare data payload
    payload = {"chat_id": chat_id, "text": encoded_message}

    # Use requests library for a more robust solution (install with 'pip install requests')
    try:
        import requests

        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise an exception for non-200 response
        print("  Telegram message sent successfully.")
    except ModuleNotFoundError:
        print("  WARNING: 'requests' library not found. Using wget fallback.")
        # Fallback using wget (not recommended for production due to limited feedback)
        os.system(
            f"wget -qO- --post-data='chat_id={chat_id}&text={encoded_message}' '{url}' >/dev/null"
        )
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: sending Telegram message: {e}")
