FROM debian:12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    rsyslog rsyslog-gnutls rsyslog-relp ca-certificates tzdata iproute2 \
 && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Moscow

RUN mkdir -p /var/log/remote /etc/rsyslog/certs /var/spool/rsyslog && chmod 755 /var/log/remote

COPY rsyslog.conf /etc/rsyslog.conf
COPY 10-relp-tls.conf /etc/rsyslog.d/10-relp-tls.conf

EXPOSE 6514/tcp

CMD ["rsyslogd","-n","-f","/etc/rsyslog.conf"]
