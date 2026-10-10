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
) -> bool:
    """Touches a file over SSH so inotify-based watchers (e.g. Synology Drive) notice it.

    Returns True on success, False when skipped (SSH variables not set) or failed.
    Never exits the calling process: the scan pipeline continues either way.
    """

    if not all([user, password, address, filepath]):
        print("  INFO: SSH environment variables not set, skipping inotify trigger.")
        return False

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
        return True
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Trigger inotify failed: {error}")
        return False
