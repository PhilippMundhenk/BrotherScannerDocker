#!/usr/bin/python3
# $1 = scanner device
# $2 = friendly name

import sys

from scanner import read_environment, scan_front

if __name__ == "__main__":
    # Open the log file in append mode
    with open("/var/log/scanner.log", "a") as f:
        # Redirect stdout to the log file
        sys.stdout = f

        read_environment()

        device = sys.argv[1]
        scan_front(f, device)
