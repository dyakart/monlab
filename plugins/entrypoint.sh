#!/usr/bin/env sh
set -e

SRC="/externalscripts-src"
DST="/usr/lib/zabbix/externalscripts"

mkdir -p "$DST"

# копируем скрипты из примонтированного каталога (ro)
if [ -d "$SRC" ]; then
  cp -a "$SRC"/. "$DST" 2>/dev/null || true
fi

# делаем скрипты исполняемыми
for f in "$DST"/*; do [ -f "$f" ] && chmod +x "$f" || true; done

# запускаем агент
exec /usr/sbin/zabbix_agent2 -f -c /etc/zabbix/zabbix_agent2.conf
