#!/usr/bin/env bash
set -e
mkdir -p /run/zabbix /var/spool/rsyslog /var/log/remote
chown -R zabbix:zabbix /run/zabbix || true
(/usr/sbin/zabbix_agent2 -f -c /etc/zabbix/zabbix_agent2.conf &) >/dev/null 2>&1 || true

# привести существующие пути к группе ping и корректным правам
chgrp -R ping /var/log/remote || true
chmod g+s /var/log/remote || true
find /var/log/remote -type d -exec chmod 2750 {} + || true
find /var/log/remote -type f -name "*.log" -exec chmod 0640 {} + || true


exec rsyslogd -n -f /etc/rsyslog.conf