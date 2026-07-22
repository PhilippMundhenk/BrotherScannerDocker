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
wget https://github.com/EasyNetDev/brscan-skey/releases/download/3.2.0-2/brscan-skey_0.3.2-2_amd64.deb --progress=dot:giga -O /tmp/brscan-skey.deb && \
dpkg -i --force-all /tmp/brscan4.deb && \
dpkg -i --force-all /tmp/brscan-skey.deb && \
rm -f /tmp/brscan4.deb /tmp/brscan-skey.deb
EOF

COPY files/runScanner.sh /opt/brother/runScanner.sh
COPY files/brscan-skey.config /opt/brother/scanner/brscan-skey/brscan-skey.config
COPY files/lighttpd-scanner.conf /etc/lighttpd/conf-enabled/99-scanner-rewrite.conf
COPY script /opt/brother/scanner/brscan-skey/script

RUN <<EOF
cp /etc/lighttpd/conf-available/05-auth.conf /etc/lighttpd/conf-enabled/ && \
cp /etc/lighttpd/conf-available/15-fastcgi-php.conf /etc/lighttpd/conf-enabled/ && \
cp /etc/lighttpd/conf-available/10-fastcgi.conf /etc/lighttpd/conf-enabled/ && \
mkdir -p /var/run/lighttpd && \
touch /var/run/lighttpd/php-fastcgi.socket && \
chown -R www-data /var/run/lighttpd && \
echo 'www-data ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
EOF


ENV NAME="Scanner"
ENV MODEL="MFC-L2700DW"
ENV IPADDRESS="192.168.1.123"
ENV REMOVE_BLANK_THRESHOLD="0.3"

# Only set these variables in the compose file, if inotify needs to be triggered (e.g., for Synology Drive):
ENV SSH_USER=""
ENV SSH_PASSWORD=""
ENV SSH_HOST=""
ENV SSH_PATH=""

# Only set these variables in the compose file, if you need FTP upload:
ENV FTP_USER=""
ENV FTP_PASSWORD=""
ENV FTP_HOST=""

# Only set these variables in the compose file, if you need Telegram notifications:
ENV TELEGRAM_TOKEN=""
ENV TELEGRAM_CHATID=""

# Make sure this ends in a slash.
ENV FTP_PATH="/scans/"

EXPOSE 54925
EXPOSE 54921
EXPOSE 80

# Copy the web files to the web directory
COPY www /var/www
RUN chown -R www-data /var/www/

#directory for scans:
VOLUME /scans

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl --fail --silent --show-error --max-time 5 \
  "http://127.0.0.1:${PORT:-80}/api/scanner/status" >/dev/null || exit 1

CMD ["bash", "-c", "/opt/brother/runScanner.sh"]
