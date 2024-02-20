FROM debian:bookworm-slim AS builder

ARG DEBIAN_FRONTEND=noninteractive 

RUN apt-get update && apt-get -y --no-install-recommends install \
		wget \
		ca-certificates

RUN cd /tmp && \
	wget https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb

RUN cd /tmp && \
	wget https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.1-2.amd64.deb

FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive 

RUN apt-get update && apt-get -y --no-install-recommends install \
		sane \
		sane-utils \
		netbase \
		ghostscript \
		netpbm \
		graphicsmagick \
		curl \
		ssh \
		sshpass \
		lighttpd \
        php-cgi \
		iproute2 \
		iputils-ping \
		&& apt-get -y clean

COPY --from=builder /tmp/brscan4-0.4.11-1.amd64.deb /tmp/brscan4-0.4.11-1.amd64.deb
RUN cd /tmp && \
	dpkg -i /tmp/brscan4-0.4.11-1.amd64.deb && \
	rm /tmp/brscan4-0.4.11-1.amd64.deb

COPY --from=builder /tmp/brscan-skey-0.3.1-2.amd64.deb /tmp/brscan-skey-0.3.1-2.amd64.deb
RUN cd /tmp && \
	dpkg -i /tmp/brscan-skey-0.3.1-2.amd64.deb && \
	rm /tmp/brscan-skey-0.3.1-2.amd64.deb

RUN cp /etc/lighttpd/conf-available/05-auth.conf /etc/lighttpd/conf-enabled/
RUN cp /etc/lighttpd/conf-available/15-fastcgi-php.conf /etc/lighttpd/conf-enabled/
RUN cp /etc/lighttpd/conf-available/10-fastcgi.conf /etc/lighttpd/conf-enabled/
RUN mkdir -p /var/run/lighttpd
RUN touch /var/run/lighttpd/php-fastcgi.socket
RUN chown -R www-data /var/run/lighttpd

ENV TZ=Etc/UTC

ENV NAME="Scanner"
ENV MODEL="MFC-L2700DW"
ENV IPADDRESS="192.168.1.123"
ENV USERNAME="NAS"

#only set these variables, if inotify needs to be triggered (e.g., for Synology Drive):
ENV SSH_USER=""
ENV SSH_PASSWORD=""
ENV SSH_HOST=""
ENV SSH_PATH=""

#only set these variables, if you need FTP upload:
ENV FTP_USER=""
ENV FTP_PASSWORD=""
ENV FTP_HOST=""
# Make sure this ends in a slash.
ENV FTP_PATH="/scans/" 


COPY files/gui/ /var/www/html
COPY files/api/ /var/www/html

COPY files/runScanner.sh /opt/brother/runScanner.sh
COPY script /opt/brother/scanner/brscan-skey/script

RUN chown -R www-data /var/www/

#directory for scans:
VOLUME /scans

CMD /opt/brother/runScanner.sh