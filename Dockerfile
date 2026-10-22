# openskey: the open, leak-free reimplementation of Brother's brscan-skey
# Scan-to-PC daemon (SKEY_DAEMON=openskey, doc/setup.md) and its mock device
# for the end-to-end tests, built from a pinned commit of
# https://github.com/PhilippMundhenk/openskey (#188).
FROM rust:1-slim-bookworm AS openskey
ARG OPENSKEY_REPO=https://github.com/PhilippMundhenk/openskey.git
ARG OPENSKEY_REF=29705170cf8e1dd228f791d009a10d54454149c7
RUN <<EOF
apt-get update && \
apt-get -y --no-install-recommends install git ca-certificates && \
rm -rf /var/lib/apt/lists/* && \
git clone "$OPENSKEY_REPO" /src && \
cd /src && git checkout --quiet "$OPENSKEY_REF" && \
cargo build --release --bins
EOF

FROM python:slim-bookworm

RUN <<EOF
apt-get update && \
apt-get -y --no-install-recommends install \
  curl \
  ghostscript \
  graphicsmagick \
  iproute2 \
  lighttpd \
  netbase \
  netpbm \
  pdftk \
  php-cgi \
  php-curl \
  poppler-utils \
  python3 \
  sane \
  sane-utils \
  ssh \
  sshpass \
  sudo \
  tzdata \
  wget \
  x11-common && \
apt-get -y clean && \
rm -rf /var/lib/apt/lists/* && \
pip install --no-cache-dir requests==2.32.3 && \
wget https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb --progress=dot:giga -O /tmp/brscan4.deb && \
wget https://download.brother.com/welcome/dlf104033/brscan5-1.7.0-0.amd64.deb --progress=dot:giga -O /tmp/brscan5.deb && \
wget https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.5-0.amd64.deb --progress=dot:giga -O /tmp/brscan-skey.deb && \
dpkg -i --force-all /tmp/brscan4.deb && \
dpkg -i --force-all /tmp/brscan5.deb && \
dpkg -i --force-all /tmp/brscan-skey.deb && \
rm -f /tmp/brscan4.deb /tmp/brscan5.deb /tmp/brscan-skey.deb
EOF

COPY files/runScanner.sh /opt/brother/runScanner.sh
COPY files/config.sh /opt/brother/config.sh
COPY files/skey.sh /opt/brother/skey.sh
COPY files/brscan-skey.config /opt/brother/scanner/brscan-skey/brscan-skey.config
COPY files/lighttpd-scanner.conf /etc/lighttpd/conf-enabled/99-scanner-rewrite.conf
COPY script /opt/brother/scanner/brscan-skey/script
COPY --from=openskey /src/target/release/openskey /usr/local/bin/openskey
COPY --from=openskey /src/target/release/mock-device /usr/local/bin/openskey-mock-device

RUN <<EOF
cp /etc/lighttpd/conf-available/05-auth.conf /etc/lighttpd/conf-enabled/ && \
cp /etc/lighttpd/conf-available/15-fastcgi-php.conf /etc/lighttpd/conf-enabled/ && \
cp /etc/lighttpd/conf-available/10-fastcgi.conf /etc/lighttpd/conf-enabled/ && \
mkdir -p /var/run/lighttpd && \
touch /var/run/lighttpd/php-fastcgi.socket && \
chown -R www-data /var/run/lighttpd
EOF


# Defaults live in files/runScanner.sh (NAME, MODEL, IPADDRESS, REMOVE_BLANK_THRESHOLD, FTP_PATH),
# so that a configuration file on the volume can set them: an ENV here would
# count as "set by the environment" and win over the file. See README, "Configuration file".

EXPOSE 54925
EXPOSE 54921
EXPOSE 80

# Copy the web files to the web directory
# Version string for /api/actions (the publish workflows pass the tag or branch)
ARG VERSION=dev
RUN echo "$VERSION" > /etc/brotherscanner-version

COPY www /var/www
RUN chown -R www-data /var/www/

#directory for scans:
VOLUME /scans

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl --fail --silent --show-error --max-time 5 \
  "http://127.0.0.1:${PORT:-80}/api/scanner/status" >/dev/null || exit 1

CMD ["bash", "-c", "/opt/brother/runScanner.sh"]
