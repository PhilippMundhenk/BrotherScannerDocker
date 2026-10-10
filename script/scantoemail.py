#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name
# API: --job-id <YYYY-MM-DD-HH-MM-SS> to address a specific job waiting for rear pages

import sys

from scanner import parse_entry_args, read_environment, scan_back

if __name__ == "__main__":
    # Open the log file in append mode
    with open("/var/log/scanner.log", "a") as log:
        # Redirect stdout to the log file
        sys.stdout = log
        sys.stderr = log

        read_environment()
        args = parse_entry_args(sys.argv[1:])

        scan_back(log, args.device, job_name=args.job_id)
