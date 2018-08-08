FROM ubuntu:16.04

RUN apt-get -y update && apt-get -y upgrade && apt-get -y clean
RUN apt-get -y install sane sane-utils ghostscript netpbm x11-common- wget graphicsmagick && apt-get -y clean

RUN cd /tmp && \
    wget http://download.brother.com/welcome/dlf006645/brscan4-0.4.5-1.amd64.deb && \
    dpkg -i /tmp/brscan4-0.4.5-1.amd64.deb && \
    rm /tmp/brscan4-0.4.5-1.amd64.deb

RUN cd /tmp && \
    wget http://download.brother.com/welcome/dlf006652/brscan-skey-0.2.4-1.amd64.deb && \
    dpkg -i /tmp/brscan-skey-0.2.4-1.amd64.deb && \
    rm /tmp/brscan-skey-0.2.4-1.amd64.deb

ADD files/runScanner.sh /opt/brother/runScanner.sh

ENV NAME="Scanner"
ENV MODEL="MFC-7860DW"
ENV IPADDRESS="192.168.1.123"

EXPOSE 54925
EXPOSE 54921

#directory for scans:
VOLUME /root/brscan

#directory for config files:
VOLUME /opt/brother/scanner/brscan-skey

CMD /opt/brother/runScanner.sh
