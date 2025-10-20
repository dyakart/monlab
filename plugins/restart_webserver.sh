#!/bin/bash
CONTAINER_NAME="$1"
TRIGGER_MESSAGE="$2"

echo "$(date): Restarting container $CONTAINER_NAME - Reason: $TRIGGER_MESSAGE" >> /var/log/zabbix/actions.log

# Перезапускаем контейнер
docker restart "$CONTAINER_NAME"

if [ $? -eq 0 ]; then
    echo "Container $CONTAINER_NAME restarted successfully"
else
    echo "ERROR: Failed to restart container $CONTAINER_NAME"
    exit 1
fi
