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
) -> None:
    """Uploads a file to an FTP server.

    Args:
      user (str): The FTP username.
      password (str): The FTP password.
      address (str): The FTP address.
      filepath (str): The file path on the FTP server.
      file (str): The file to upload.
    """

    if not any([user, password, address, filepath, file]):
        return

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
    except subprocess.CalledProcessError:
        print("Uploading to FTP failed while using curl")
        print(f"user: {user}")
        print(f"address: {address}")
        print(f"filepath: {filepath}")
        print(f"file: {file}")
        exit(1)
