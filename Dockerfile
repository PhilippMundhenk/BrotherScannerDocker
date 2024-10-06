FROM python:slim-bullseye

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
wget https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.2-0.amd64.deb --progress=dot:giga -O /tmp/brscan-skey.deb && \
dpkg -i --force-all /tmp/brscan4.deb && \
dpkg -i --force-all /tmp/brscan-skey.deb && \
rm -f /tmp/brscan4.deb /tmp/brscan-skey.deb
EOF

COPY files/runScanner.sh /opt/brother/runScanner.sh
COPY files/brscan-skey.config /opt/brother/scanner/brscan-skey/brscan-skey.config
COPY script /opt/brother/scanner/brscan-skey/script

RUN <<EOF
cp /etc/lighttpd/conf-available/05-auth.conf /etc/lighttpd/conf-enabled/ && \
cp /etc/lighttpd/conf-available/15-fastcgi-php.conf /etc/lighttpd/conf-enabled/ && \
cp /etc/lighttpd/conf-available/10-fastcgi.conf /etc/lighttpd/conf-enabled/ && \
mkdir -p /var/run/lighttpd && \
touch /var/run/lighttpd/php-fastcgi.socket && \
chown -R www-data /var/run/lighttpd && \
echo 'www-data ALL=(NAS) NOPASSWD:ALL' >> /etc/sudoers
EOF

ENV NAME="Scanner"
ENV MODEL="MFC-L2700DW"
ENV IPADDRESS="192.168.1.123"
ENV USERNAME="NAS"
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

#ADD files/gui/index.php /var/www/html
#ADD files/gui/main.css /var/www/html
#ADD files/api/scan.php /var/www/html
#ADD files/api/active.php /var/www/html
#ADD files/api/list.php /var/www/html
#ADD files/api/download.php /var/www/html
COPY html /var/www/html
RUN chown -R www-data /var/www/

#directory for scans:
VOLUME /scans

CMD ["bash", "-c", "/opt/brother/runScanner.sh"]
