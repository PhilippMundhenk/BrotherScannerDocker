#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name
# API: --job-id <YYYY-MM-DD-HH-MM-SS> [--resolution N] [--mode M] [--source S]

import sys

from scanner import apply_overrides, entry_overrides, parse_entry_args, read_environment, scan_front

LOG_PATH = "/var/log/scanner.log"


def main(argv, log_path=LOG_PATH):
    # Open the log file in append mode and send all output there
    with open(log_path, "a") as log:
        sys.stdout = log
        sys.stderr = log

        read_environment()
        args = parse_entry_args(argv)
        overrides = entry_overrides(args)
        apply_overrides(overrides)

        scan_front(log, args.device, job_name=args.job_id, action="file", overrides=overrides)


if __name__ == "__main__":
    main(sys.argv[1:])
