#!/usr/bin/env bash
set -e
mkdir -p /run/zabbix /var/spool/rsyslog /var/log/remote
chown -R zabbix:zabbix /run/zabbix || true
(/usr/sbin/zabbix_agent2 -f -c /etc/zabbix/zabbix_agent2.conf &) >/dev/null 2>&1 || true
exec rsyslogd -n -f /etc/rsyslog.conf
