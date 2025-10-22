#!/bin/bash
set -e

# Проверяем что env переменные установлены
if [ -z "$SNMP_AUTH_PASS" ] || [ -z "$SNMP_PRIV_PASS" ]; then
    echo "ERROR: SNMP_AUTH_PASS and SNMP_PRIV_PASS environment variables must be set"
    exit 1
fi

# Генерируем финальный конфиг SNMP с env переменными
echo "Creating SNMPd configuration..."
envsubst < /etc/snmp/snmpd.conf.template > /etc/snmp/snmpd.conf
chown snmp:snmp /etc/snmp/snmpd.conf
chmod 600 /etc/snmp/snmpd.conf

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

# Запускаем SNMPd
echo "Starting SNMP daemon..."
/usr/sbin/snmpd -f -u snmp -g snmp -c /etc/snmp/snmpd.conf &

# Ждем и проверяем процессы
sleep 5

if ps aux | grep -q "[z]abbix_agent2"; then
    echo "✓ Zabbix Agent2 started successfully"
else
    echo "✗ ERROR: Zabbix Agent2 failed to start"
fi

if ps aux | grep -q "[s]nmpd"; then
    echo "✓ SNMPd started successfully"
    echo "SNMPv3 User: zabbix (SHA/AES encrypted)"
else
    echo "✗ ERROR: SNMPd failed to start"
fi

# Rsyslog
mkdir -p /var/spool/rsyslog /etc/rsyslog/certs
rsyslogd
echo "✓ Rsyslog started successfully"

# Nginx в фоне
echo "Starting Nginx..."
exec nginx -g 'daemon off;'
