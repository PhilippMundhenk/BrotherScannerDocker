#!/usr/bin/env python3

import subprocess
from typing import List, Optional, TextIO


def sendtoftps(
    log: TextIO,
    user: Optional[str],
    password: Optional[str],
    address: Optional[str],
    filepath: Optional[str],
    file: Optional[str],
) -> Optional[bool]:
    """Uploads a file to an FTP(S) server with curl.

    Returns True on success, False on failure and None when the FTP variables
    are not set. Never exits the calling process: the scan pipeline continues
    either way.
    """

    if not all([user, password, address, filepath, file]):
        return None

    command: List[str] = [
        "curl",
        "--silent",
        "--show-error",
        "--ssl-reqd",
        "--user",
        f"{user}:{password}",
        "--upload-file",
        str(file),
        f"ftp://{address}{filepath}",
    ]

    try:
        subprocess.run(command, check=True, stdout=log, stderr=log)
        print(f"Uploading to FTP server {address} successful.")
        return True
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Uploading to FTP failed while using curl: {error}")
        print(f"user: {user}")
        print(f"address: {address}")
        print(f"filepath: {filepath}")
        print(f"file: {file}")
        return False
