FROM python:3.9-alpine

# Установка необходимых пакетов
RUN apk add --no-cache curl bash

# Установка Python зависимостей
RUN pip install requests

CMD ["tail", "-f", "/dev/null"]
