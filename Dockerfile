FROM python:slim-bullseye

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get -y install tzdata && apt-get -y clean

RUN apt-get update && apt-get install -y --no-install-recommends apt-utils && apt-get -y clean

RUN apt-get -y update && apt-get -y upgrade && apt-get -y clean
RUN apt-get -y install \
  sane \
  sane-utils \
  ghostscript \
  netpbm \
  x11-common \
  wget \
  graphicsmagick \
  curl \
  ssh \
  sshpass \
  lighttpd \
  php-cgi \
  php-curl \
  sudo \
  iproute2 \
  pdftk \
  poppler-utils \
  && apt-get -y clean && \
  pip install --no-cache-dir requests==2.32.3

RUN wget --progress=dot:giga https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb -O /tmp/brscan4-0.4.11-1.amd64.deb && \
  dpkg -i /tmp/brscan4-0.4.11-1.amd64.deb && \
  rm /tmp/brscan4-0.4.11-1.amd64.deb

RUN wget --progress=dot:giga https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.1-2.amd64.deb -O /tmp/brscan-skey-0.3.1-2.amd64.deb && \
  dpkg -i /tmp/brscan-skey-0.3.1-2.amd64.deb && \
  rm /tmp/brscan-skey-0.3.1-2.amd64.deb

ADD files/runScanner.sh /opt/brother/runScanner.sh
ADD files/brscan-skey.config /opt/brother/scanner/brscan-skey/brscan-skey.config
COPY script /opt/brother/scanner/brscan-skey/script

RUN cp /etc/lighttpd/conf-available/05-auth.conf /etc/lighttpd/conf-enabled/
RUN cp /etc/lighttpd/conf-available/15-fastcgi-php.conf /etc/lighttpd/conf-enabled/
RUN cp /etc/lighttpd/conf-available/10-fastcgi.conf /etc/lighttpd/conf-enabled/
RUN mkdir -p /var/run/lighttpd
RUN touch /var/run/lighttpd/php-fastcgi.socket
RUN chown -R www-data /var/run/lighttpd
RUN echo 'www-data ALL=(NAS) NOPASSWD:ALL' >> /etc/sudoers

ENV NAME="Scanner"
ENV MODEL="MFC-L2700DW"
ENV IPADDRESS="192.168.1.123"
ENV USERNAME="NAS"
ENV REMOVE_BLANK_THRESHOLD="0.3"

#only set these variables in the compose file, if inotify needs to be triggered (e.g., for Synology Drive):
ENV SSH_USER=""
ENV SSH_PASSWORD=""
ENV SSH_HOST=""
ENV SSH_PATH=""

#only set these variables in the compose file, if you need FTP upload:
ENV FTP_USER=""
ENV FTP_PASSWORD=""
ENV FTP_HOST=""

#only set these variables in the compose file, if you need Telegram notifications:
ENV TELEGRAM_TOKEN=""
ENV TELEGRAM_CHATID=""

# Make sure this ends in a slash.
ENV FTP_PATH="/scans/"

EXPOSE 54925
EXPOSE 54921
EXPOSE 80

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


