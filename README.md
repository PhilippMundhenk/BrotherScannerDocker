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

## Customize
As the standard scripts are not working particularly well, you may customize them to your needs.
Have a look in the script/ for ideas. These scripts show some examples on how one might use the buttons
on the printer. If you change these scripts, make sure to leave the filename as is, as the Brother
drivers will call these scripts. Each script corresponds to a shortcut button on the scanner. This way
you can customize the actions running on your scanner. Hint: These scripts don't necessarily need to do
scanning tasks. You can add any shell script here.
You may mount the scripts like this:
-v $PWD/script/:/opt/brother/scanner/brscan-skey/script/

## Supported Models
You can retrieve the supported models by the helper script listModels.sh
