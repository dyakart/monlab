#!/bin/bash
set -e

echo "=== Deploying Simple Monitoring Solution ==="

# Создание каталогов
mkdir -p plugins zabbix/externalscripts/zabbix_agent2.d

# Установка прав доступа
chmod +x plugins/*.sh
chmod +x plugins/*.py

# Сборка и запуск
docker compose build monitoring-plugins
docker compose up -d monitoring-plugins zbx-agent-plugins

# Ждем запуска контейнеров
sleep 10

echo "=== Testing Scripts ==="

echo "1. Проверяем, что скрипты доступны в контейнере:"
docker exec monitoring-plugins ls -la /usr/lib/zabbix/externalscripts/

echo ""
echo "2. Testing check_http.sh:"
docker exec monitoring-plugins /usr/lib/zabbix/externalscripts/check_http.sh webserver1

echo ""
echo "3. Testing nginx_monitor.py HTTP check:"
docker exec monitoring-plugins python3 /usr/lib/zabbix/externalscripts/nginx_monitor.py http http://webserver1

echo ""
echo "4. Testing through Zabbix Agent:"
docker exec zbx-agent-plugins zabbix_agent2 -t "check_http[webserver1]"
docker exec zbx-agent-plugins zabbix_agent2 -t "nginx.check[http,http://webserver1,]"

echo ""
echo "=== INSTRUCTIONS FOR ZABBIX ==="
echo "1. Open Zabbix: http://localhost:8080"
echo "2. Login: Admin / zabbix"
echo ""
echo "3. Add new host 'monitoring-plugins' or use existing web servers"
echo ""
echo "4. Create Items using UserParameters:"
echo "   - Key: check_http[webserver1]"
echo "   - Key: nginx.check[http,http://webserver1,]"
echo "   - Key: nginx.check[log_size,/var/log/nginx,50]"
echo ""
echo "5. Create Triggers when value = 0"
