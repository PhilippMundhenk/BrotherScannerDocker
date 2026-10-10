#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name

import sys

LOG_PATH = "/var/log/scanner.log"


def main(argv, log_path=LOG_PATH):
    # Open the log file in append mode and send all output there
    with open(log_path, "a") as log:
        sys.stdout = log
        sys.stderr = log

        print("ERROR!")
        print("This function is not implemented.")
        print("You may implement your own script and mount under $0.")
        print(
            "Check out scripts in same folder or https://github.com/PhilippMundhenk/BrotherScannerDocker for examples."
        )


if __name__ == "__main__":
    main(sys.argv[1:])
