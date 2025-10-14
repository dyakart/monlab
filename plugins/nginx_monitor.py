#!/usr/bin/env python3
"""
Кастомный плагин: проверка доступности HTTP и расчёт размера логов (MB).
Использование:
  http <url>
  log_size <path>
Выводит:
  1/0 для http; число с плавающей точкой для log_size.
"""

import os
import os.path as osp
import sys


def print_err() -> int:
    """Выводит '0' и возвращает код ошибки 1."""
    print("0")
    return 1


def http_check(url: str) -> int:
    """
    Проверяет доступность URL адреса по HTTP.
    """
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=5) as r:
            print("1" if r.status == 200 else "0")
            return 0 if r.status == 200 else 1
    except Exception:
        return print_err()


def log_size(path: str) -> int:
    """
    Считает общий размер *.log в переданном каталоге (рекурсивно), МБ.
    """
    try:
        if not os.path.exists(path):
            print("0")
            return 1
        total = 0
        for root, _, files in os.walk(path):
            for fn in files:
                if fn.endswith(".log"):
                    fp = os.path.join(root, fn)
                    if os.path.isfile(fp):
                        total += osp.getsize(fp)
        mb = total / (1024 * 1024)
        print(f"{mb:.2f}")
        return 0
    except Exception:
        return print_err()


def main(argv) -> int:
    """
    Основная функция запуска для проверки работы HTTP и количества логов.
    """
    if len(argv) < 2:
        return print_err()
    cmd = argv[0]
    arg = argv[1]
    if cmd == "http":
        return http_check(arg)
    elif cmd == "log_size":
        return log_size(arg)
    return print_err()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
