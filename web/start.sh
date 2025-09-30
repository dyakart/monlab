#!/usr/bin/env bash
set -e
# SSH
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
ssh-keygen -A
/usr/sbin/sshd

# Zabbix Agent2
mkdir -p /run/zabbix
chown -R zabbix:zabbix /run/zabbix
(/usr/sbin/zabbix_agent2 -f -c /etc/zabbix/zabbix_agent2.conf &) >/dev/null 2>&1

# Nginx в фоне
exec nginx -g 'daemon off;'
