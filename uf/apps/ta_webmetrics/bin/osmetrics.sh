#!/usr/bin/env bash
set -e
read cpu user nice system idle iowait irq softirq steal guest guest_nice < /proc/stat
PREV_IDLE=$idle; PREV_TOTAL=$((user+nice+system+idle+iowait+irq+softirq+steal))
sleep 1
read cpu user nice system idle iowait irq softirq steal guest guest_nice < /proc/stat
IDLE=$idle; TOTAL=$((user+nice+system+idle+iowait+irq+softirq+steal))
DIFF_IDLE=$((IDLE-PREV_IDLE)); DIFF_TOTAL=$((TOTAL-PREV_TOTAL))
CPU=$(( (100*(DIFF_TOTAL-DIFF_IDLE)) / DIFF_TOTAL ))
FREE_MB=$(free -m | awk '/Mem:/ {print $7}')
HOST="${HOSTNAME:-$(cat /etc/hostname 2>/dev/null || echo unknown)}"
echo "{\"host\":\"$HOST\",\"cpu_percent\":$CPU,\"mem_free_mb\":$FREE_MB}"
