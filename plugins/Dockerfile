FROM zabbix/zabbix-agent2:alpine-7.0-latest

USER root
RUN apk add --no-cache python3 py3-requests curl \
 && mkdir -p /usr/lib/zabbix/externalscripts \
 && chown -R zabbix:zabbix /usr/lib/zabbix \
 && addgroup -g 999 ping || true \
 && adduser zabbix ping || true

ENV ZBX_PREPAREAGENTCONF=false
COPY zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf
RUN sed -i 's|^PidFile=.*|PidFile=/tmp/zabbix_agent2.pid|' /etc/zabbix/zabbix_agent2.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER zabbix
ENTRYPOINT ["/entrypoint.sh"]
