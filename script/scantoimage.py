#!/usr/bin/env python3
# $1 = scanner device
# $2 = friendly name

import sys

if __name__ == "__main__":
    # Open the log file in append mode
    with open("/var/log/scanner.log", "a") as log:
        # Redirect stdout to the log file
        sys.stdout = log
        sys.stderr = log

        print("ERROR!")
        print("This function is not implemented.")
        print("You may implement your own script and mount under $0.")
        print(
            "Check out scripts in same folder or https://github.com/PhilippMundhenk/BrotherScannerDocker for examples."
        )
