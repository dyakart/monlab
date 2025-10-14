#!/usr/bin/env bash
# Наш кастомный плагин check_http

set -e
curl --connect-timeout 3 -s "http://$1" > /dev/null 2>&1
if [ "$?" -ne "0" ]; then
  echo "0"
else
  echo "1"
fi
