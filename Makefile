.PHONY: brotherscanner update-container test lint bats

build: brotherscanner

brotherscanner:
	docker build --no-cache -t brotherscanner -f Dockerfile .

update-container:
	./tools/update-container.sh

# Run the bats test suite. Requires bats-core on PATH.
test: bats

bats:
	bats tests/unit

# Static analysis. Requires shellcheck on PATH. --severity=error keeps
# the bar low enough that pre-existing style warnings do not break CI;
# raise to "warning" once those are cleaned up.
lint:
	shellcheck --severity=error \
		files/config.sh \
		files/skey.sh \
		files/runScanner.sh \
		tools/run.sh \
		tools/update-container.sh
