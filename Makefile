.PHONY: brotherscanner brotherscanner-slim

build: brotherscanner

brotherscanner:
	docker build --no-cache -t brotherscanner -f Dockerfile .

brotherscanner-slim:
	docker build --no-cache -t brotherscanner-slim -f Dockerfile-slim .