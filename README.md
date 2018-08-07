# Brother Scanner
This is the dockerized scanner setup for Brother scanners. It allows you to run
your scan server in a Docker environment and thus also on devices such as a Synology
DiskStation.

## Requirements
Take note that the Brother scanner drivers require access to the host network, thus
the container needs to be started with --net=host. See run.sh for example.

## Usage
You can configure the tool via environment variables. The following are required:

| Variable | Description |
| ------------- | ------------- |
| NAME  | Arbitrary name to give your scanner  |
| MODEL  | Model of your scanner (see Supported Models)  |
| IPADDRESS | IP Address of your scanner |

You may also want to mount a directory to retrieve your data. Scanned files are stored in /root/brscan.

See run.sh for example how to use environment variables and mounts.

## Supported Models
You can retrieve the supported models by the helper script listModels.sh
