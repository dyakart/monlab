FROM zabbix/zabbix-agent2:alpine-7.0-latest

# Переключаемся на root для установки пакетов
USER root

# Устанавливаем необходимые пакеты через apk
RUN apk add --no-cache curl python3 py3-requests

# Добавляем пользователя zabbix в группу logreaders
#RUN addgroup -g 1001 logreaders || true
#RUN adduser zabbix logreaders || true

# Отключаем автоматическую подготовку конфига ДО копирования конфига
ENV ZBX_PREPAREAGENTCONF=false

# Копируем наш конфиг
COPY zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf

# Используем существующую директорию для PID файла
RUN sed -i 's|^PidFile=.*|PidFile=/tmp/zabbix_agent2.pid|' /etc/zabbix/zabbix_agent2.conf

# Создаем группу ping и добавляем туда пользователя zabbix чтобы у zabbix были права на чтение логов
RUN addgroup -g 999 ping || true
RUN adduser zabbix ping

# Возвращаемся к пользователю zabbix
USER zabbix
