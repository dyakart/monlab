#!/usr/bin/env bash
set -e
# SSH
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
ssh-keygen -A
/usr/sbin/sshd

# Zabbix Agent2 (в фоне)
(/usr/sbin/zabbix_agent2 -f -c /etc/zabbix/zabbix_agent2.conf &) >/dev/null 2>&1

# Nginx в фоне
exec nginx -g 'daemon off;'
