# Uploads and notifications

[Back to the README](../README.md)

Everything here runs after every finished PDF, and again for the OCR copy when OCR is configured.

## FTPS upload

In addition to the storage on the mounted volume, every scan can be uploaded to an FTP(S) server:

```
- FTP_USER="scanner"
- FTP_PASSWORD="scanner"
- FTP_HOST="ftp.mydomain.com"
- FTP_PATH="/"
```

The upload requires TLS (explicit FTPS, `curl --ssl-reqd`). If your server only speaks plain FTP, add `FTP_INSECURE=true`; the credentials and the scanned files are then sent unencrypted, so only do this on a network you trust.

## inotify over SSH, for synchronization tools

Many synchronization tools, such as Synology CloudStation, are notified about changes in the file system through [inotify](http://man7.org/linux/man-pages/man7/inotify.7.html). As the volume is mounted into Docker, the isolation between host and container means such tools do not see the new file.

To work around this, the scripts run a `sed "" -i` on the file over SSH on the host, which generates an inotify event and starts the synchronization:

```
- SSH_USER="admin"
- SSH_PASSWORD="admin"
- SSH_HOST="localhost"
- SSH_PATH="/path/to/scans/folder/"
```

This requires SSH access to the host. If that is not available, consider the FTPS upload.

## Telegram

With `TELEGRAM_TOKEN` and `TELEGRAM_CHATID` set, a message is sent for every finished scan and every finished OCR copy.

## Secrets

Passwords and tokens can come from files instead of the compose file (Docker secrets); see [Configuration](configuration.md#secrets).
