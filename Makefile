.PHONY: brotherscanner

build: brotherscanner

brotherscanner:
	docker build --no-cache -t brotherscanner -f Dockerfile .