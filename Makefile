.PHONY: brotherscanner update-container

build: brotherscanner

brotherscanner:
	docker build --no-cache -t brotherscanner -f Dockerfile .

update-container:
	./update-container.sh