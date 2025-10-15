#!/usr/bin/env bash
# Наш кастомный плагин check_http
# check_http.sh: 1 = OK, 0 = FAIL
set -u

target="${1:-}"
[ -z "$target" ] && { printf '0\n'; exit 0; }

case "$target" in
  http://*|https://*) url="$target" ;;
  *) url="http://$target" ;;
esac

if curl -fs --connect-timeout 3 --max-time 4 -o /dev/null "$url" 2>/dev/null; then
  printf '1\n'
else
  printf '0\n'
fi
