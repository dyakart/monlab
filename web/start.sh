#!/usr/bin/env bash
set -e

# SSH
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
ssh-keygen -A
/usr/sbin/sshd &

# Создаем директории для Zabbix
mkdir -p /run/zabbix
chown -R zabbix:zabbix /run/zabbix

# Запускаем Zabbix Agent2 в фоне
echo "Starting Zabbix Agent2..."
/usr/sbin/zabbix_agent2 -c /etc/zabbix/zabbix_agent2.conf &

# Ждем пока агент запустится
sleep 3

# Проверяем что процесс агента запущен
if ps aux | grep -q "[z]abbix_agent2"; then
    echo "Zabbix Agent2 is running"
else
    echo "ERROR: Zabbix Agent2 failed to start"
    exit 1
fi

# rsyslog
mkdir -p /var/spool/rsyslog /etc/rsyslog/certs
rsyslogd

# Nginx в фоне (основной процесс)
echo "Starting Nginx..."
exec nginx -g 'daemon off;'
