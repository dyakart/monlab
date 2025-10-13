FROM debian:12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    rsyslog rsyslog-gnutls rsyslog-relp ca-certificates tzdata iproute2 curl \
 && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Moscow

RUN mkdir -p /var/log/remote /etc/rsyslog/certs /var/spool/rsyslog && chmod 755 /var/log/remote

# Установка Zabbix Agent2
RUN curl -fsSL https://repo.zabbix.com/zabbix/7.0/debian/pool/main/z/zabbix-release/zabbix-release_7.0-1+debian12_all.deb -o /tmp/zbx.deb \
 && dpkg -i /tmp/zbx.deb && rm /tmp/zbx.deb \
 && apt-get update && apt-get install -y --no-install-recommends zabbix-agent2 \
 && rm -rf /var/lib/apt/lists/*

# Создаем группу для доступа к логам
RUN groupadd -r logreaders || true
RUN usermod -a -G logreaders zabbix
RUN usermod -a -G logreaders splunk || true

# rsyslog конфиги
COPY rsyslog.conf /etc/rsyslog.conf
COPY 10-relp-tls.conf /etc/rsyslog.d/10-relp-tls.conf

COPY zbx-active.conf /etc/zabbix/zabbix_agent2.d/zbx-active.conf

# стартовый скрипт
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 6514/tcp 10050/tcp
CMD ["/start.sh"]
