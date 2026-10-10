#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name
# API: --job-id <YYYY-MM-DD-HH-MM-SS> to address a specific job waiting for rear pages

import sys

from scanner import parse_entry_args, read_environment, scan_back

LOG_PATH = "/var/log/scanner.log"


def main(argv, log_path=LOG_PATH):
    # Open the log file in append mode and send all output there
    with open(log_path, "a") as log:
        sys.stdout = log
        sys.stderr = log

        read_environment()
        args = parse_entry_args(argv)

        scan_back(log, args.device, job_name=args.job_id)


if __name__ == "__main__":
    main(sys.argv[1:])
