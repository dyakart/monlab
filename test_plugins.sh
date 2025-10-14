#!/bin/bash
set -e

echo "=== Проверка скриптов ==="

echo "1. Проверяем, что скрипты доступны в контейнере:"
docker exec zbx-agent-plugins ls -la /usr/lib/zabbix/externalscripts/

echo ""
echo "2. Проверка check_http.sh:"
docker exec zbx-agent-plugins /usr/lib/zabbix/externalscripts/check_http.sh webserver1
docker exec zbx-agent-plugins /usr/lib/zabbix/externalscripts/check_http.sh webserver2

echo ""
echo "3. Проверка nginx_monitor.py HTTP check:"
docker exec zbx-agent-plugins python3 /usr/lib/zabbix/externalscripts/nginx_monitor.py http http://webserver1
docker exec zbx-agent-plugins python3 /usr/lib/zabbix/externalscripts/nginx_monitor.py http http://webserver2

echo ""
echo "4. Проверка через Zabbix Agent:"
docker exec zbx-agent-plugins zabbix_agent2 -t "check_http[webserver1]"
docker exec zbx-agent-plugins zabbix_agent2 -t "check_http[webserver2]"
docker exec zbx-agent-plugins zabbix_agent2 -t "nginx.check[http,http://webserver1,]"
docker exec zbx-agent-plugins zabbix_agent2 -t "nginx.check[http,http://webserver2,]"
docker exec zbx-agent-plugins zabbix_agent2 -t "nginx.check[log_size,/var/log/remote/webserver1]"
docker exec zbx-agent-plugins zabbix_agent2 -t "nginx.check[log_size,/var/log/remote/webserver2]"
