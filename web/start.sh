#!/usr/bin/env bash
set -e
# SSH
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config || true
ssh-keygen -A
/usr/sbin/sshd

AGENT_SERVER="${AGENT_SERVER:-zabbix-server}"
AGENT_SERVER_ACTIVE="${AGENT_SERVER_ACTIVE:-$AGENT_SERVER}"
sed -i "s/^#\?Server=.*/Server=${AGENT_SERVER}/" /etc/zabbix/zabbix_agent2.conf
sed -i "s/^#\?ServerActive=.*/ServerActive=${AGENT_SERVER_ACTIVE}/" /etc/zabbix/zabbix_agent2.conf
sed -i "s/^#\?HostnameItem=.*/HostnameItem=system.hostname/" /etc/zabbix/zabbix_agent2.conf

# SNMPv3
if [ -z "${SNMP_AUTH_PASS:-}" ] || [ -z "${SNMP_PRIV_PASS:-}" ]; then
  echo "[ERROR] SNMP_AUTH_PASS и/или SNMP_PRIV_PASS не заданы"; exit 1
fi
mkdir -p /var/lib/snmp /etc/snmp
envsubst < /etc/snmp/snmpd.conf.template > /etc/snmp/snmpd.conf
chmod 600 /etc/snmp/snmpd.conf
# запустим snmpd в фоне (лог в stdout)
snmpd -Lo -C -c /etc/snmp/snmpd.conf &

# Zabbix Agent2
mkdir -p /run/zabbix
chown -R zabbix:zabbix /run/zabbix
(/usr/sbin/zabbix_agent2 -f -c /etc/zabbix/zabbix_agent2.conf &) >/dev/null 2>&1

# rsyslog
mkdir -p /var/spool/rsyslog /etc/rsyslog/certs
rsyslogd

# Nginx в фоне
exec nginx -g 'daemon off;'
