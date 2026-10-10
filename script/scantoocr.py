#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name
# API: --job-id <YYYY-MM-DD-HH-MM-SS> [--resolution N] [--mode M] [--source S]

import os
import sys

from scanner import apply_overrides, entry_overrides, parse_entry_args, read_environment, scan_front

if __name__ == "__main__":
    # Open the log file in append mode
    with open("/var/log/scanner.log", "a") as log:
        # Redirect stdout to the log file
        sys.stdout = log
        sys.stderr = log

        read_environment()
        args = parse_entry_args(sys.argv[1:])
        overrides = entry_overrides(args)
        apply_overrides(overrides)

        # Scan to OCR is gray by default; a per-job --mode or SCAN_MODE wins.
        gray_default = args.mode is None and not os.environ.get("SCAN_MODE", "").strip()
        scanimage_args = ["--mode=True Gray"] if gray_default else []
        scan_front(log, args.device, scanimage_args, job_name=args.job_id, action="ocr", overrides=overrides)
