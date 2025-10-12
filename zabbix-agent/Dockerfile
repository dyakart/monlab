FROM zabbix/zabbix-agent2:alpine-7.0-latest

# Переключаемся на root для установки пакетов
USER root

# Устанавливаем необходимые пакеты через apk
RUN apk add --no-cache curl python3

# Возвращаемся к пользователю zabbix
USER zabbix

# Копируем наш конфиг
COPY zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf

# Используем существующую директорию для PID файла
RUN sed -i 's|^PidFile=.*|PidFile=/tmp/zabbix_agent2.pid|' /etc/zabbix/zabbix_agent2.conf
