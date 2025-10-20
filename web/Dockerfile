FROM debian:12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx openssh-server curl iputils-ping ca-certificates sudo tini gnupg \
    rsyslog rsyslog-relp rsyslog-gnutls \
 && rm -rf /var/lib/apt/lists/*

# пользователь для SSH
RUN useradd -m -s /bin/bash user \
 && echo 'user:1' | chpasswd \
 && mkdir -p /var/run/sshd /etc/sudoers.d \
 && echo 'user ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/user \
 && chmod 440 /etc/sudoers.d/user

# Zabbix repo + agent2
RUN curl -fsSL https://repo.zabbix.com/zabbix/7.0/debian/pool/main/z/zabbix-release/zabbix-release_7.0-1+debian12_all.deb -o /tmp/zbx.deb \
 && dpkg -i /tmp/zbx.deb && rm /tmp/zbx.deb \
 && apt-get update && apt-get install -y --no-install-recommends zabbix-agent2 \
 && rm -rf /var/lib/apt/lists/*

# контент сайта
COPY site/ /usr/share/nginx/html/

# Копируем кастомный конфиг Zabbix Agent2
COPY zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf

COPY start.sh /start.sh
# Конфиг Rsyslog
COPY 20-relp-client.conf /etc/rsyslog.d/20-relp-client.conf

RUN chmod +x /start.sh

EXPOSE 22 80 10050
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/start.sh"]
