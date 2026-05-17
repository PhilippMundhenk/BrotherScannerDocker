.PHONY: brotherscanner update-container test lint bats

build: brotherscanner

brotherscanner:
	docker build --no-cache -t brotherscanner -f Dockerfile .

update-container:
	./update-container.sh

# Run the bats test suite. Requires bats-core on PATH.
test: bats

bats:
	bats tests/unit

# Static analysis. Requires shellcheck on PATH. --severity=error keeps
# the bar low enough that pre-existing style warnings do not break CI;
# raise to "warning" once those are cleaned up.
lint:
	shellcheck --severity=error \
		script/remove_blank.sh \
		script/scanRear.sh \
		script/scantoemail-0.2.4-1.sh \
		script/scantofile-0.2.4-1.sh \
		script/scantoimage-0.2.4-1.sh \
		script/scantoocr-0.2.4-1.sh \
		script/sendtoftps.sh \
		script/trigger_inotify.sh \
		script/trigger_telegram.sh \
		files/runScanner.sh \
		run.sh \
		update-container.sh