#!/usr/bin/env python3

import os
import subprocess
from typing import List, Optional, TextIO


def ftp_insecure_from_env() -> bool:
    """FTP_INSECURE=true selects plain FTP instead of requiring TLS (FTPS)."""
    return os.environ.get("FTP_INSECURE", "").strip().lower() == "true"


def sendtoftps(
    log: TextIO,
    user: Optional[str],
    password: Optional[str],
    address: Optional[str],
    filepath: Optional[str],
    file: Optional[str],
    insecure: Optional[bool] = None,
) -> Optional[bool]:
    """Uploads a file to an FTP(S) server with curl.

    By default the transfer requires TLS (explicit FTPS, curl's --ssl-reqd).
    With insecure=True, or FTP_INSECURE=true in the environment, plain FTP is
    used instead; credentials and the file then travel unencrypted.

    Returns True on success, False on failure and None when the FTP variables
    are not set. Never exits the calling process: the scan pipeline continues
    either way.
    """

    if not all([user, password, address, filepath, file]):
        return None

    if insecure is None:
        insecure = ftp_insecure_from_env()

    command: List[str] = ["curl", "--silent", "--show-error"]
    if not insecure:
        command.append("--ssl-reqd")
    command += [
        "--user",
        f"{user}:{password}",
        "--upload-file",
        str(file),
        f"ftp://{address}{filepath}",
    ]

    try:
        subprocess.run(command, check=True, stdout=log, stderr=log)
        print(f"Uploading to {'FTP' if insecure else 'FTPS'} server {address} successful.")
        return True
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Uploading to FTP failed while using curl: {error}")
        print(f"user: {user}")
        print(f"address: {address}")
        print(f"filepath: {filepath}")
        print(f"file: {file}")
        print(f"insecure: {insecure}")
        return False
