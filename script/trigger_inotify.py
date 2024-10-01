#!/usr/bin/env python3

import subprocess
from typing import Optional, TextIO


def trigger_inotify(
    log: TextIO,
    user: Optional[str],
    password: Optional[str],
    address: Optional[str],
    filepath: Optional[str],
    file: Optional[str],
) -> None:
    """Triggers inotify for a file.

    Args:
        user (str): The SSH username.
        password (str): The SSH password.
        address (str): The SSH address.
        filepath (str): The file path.
        file (str): The file name.
    """

    if not user or not password or not address or not filepath:
        print("  INFO: SSH environment variables not set, skipping inotify trigger.")
        return

    command = [
        "sshpass",
        "-p",
        password,
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        f"{user}@{address}",
        f'sed "" -i {filepath}/{file}',
    ]

    try:
        subprocess.run(command, check=True, stdout=log, stderr=log)
        print("Trigger inotify successful")
    except subprocess.CalledProcessError:
        print("Trigger inotify failed")
        exit(1)
