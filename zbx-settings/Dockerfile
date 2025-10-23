FROM python:3.12-alpine
RUN apk add --no-cache ca-certificates curl
WORKDIR /app

COPY zbx_settings.py /app/zbx_settings.py

CMD ["python", "-u", "/app/zbx_settings.py"]
