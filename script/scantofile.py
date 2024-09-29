#!/usr/bin/python3
# $1 = scanner device
# $2 = friendly name

import sys

from scanner import read_environment, scan_front

if __name__ == "__main__":
    # Open the log file in append mode
    with open("/var/log/scanner.log", "a") as log:
        # Redirect stdout to the log file
        sys.stdout = log
        sys.stderr = log

        read_environment()

        device = None
        if len(sys.argv) > 1:
            device = sys.argv[1]
        scan_front(log, device)
