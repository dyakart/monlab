FROM zabbix/zabbix-agent2:alpine-7.0-latest

# Копируем наш конфиг
COPY zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf

# Используем существующую директорию для PID файла
RUN sed -i 's|^PidFile=.*|PidFile=/tmp/zabbix_agent2.pid|' /etc/zabbix/zabbix_agent2.conf
