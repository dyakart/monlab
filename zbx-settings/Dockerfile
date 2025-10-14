FROM python:3.12-alpine
RUN apk add --no-cache ca-certificates curl
WORKDIR /app

COPY zbx_settings.py /app/zbx_settings.py

ENV PYTHONUNBUFFERED=1 \
    ZBX_API_URL=http://zbx-web:8080/api_jsonrpc.php \
    ZBX_USER=Admin \
    ZBX_PASS=zabbix \
    ZBX_LANG=ru_RU \
    WAIT_TIMEOUT=60 \
    WAIT_INTERVAL=3

CMD ["python", "-u", "/app/zbx_settings.py"]
