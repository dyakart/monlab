#!/usr/bin/env python3
"""
Кастомный плагин для проверки доступности Nginx и размера логов
"""

import requests
import os
import sys

def check_nginx(url):
    """Проверка доступности Nginx"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print("1")  # ОК
            return 0
        else:
            print("0")  # Ошибка
            return 1
    except:
        print("0")  # Ошибка
        return 1

def get_log_size(log_path):
    """Получение размера логов в MB"""
    try:
        total_size = 0
        file_count = 0

        if not os.path.exists(log_path):
            print("0")  # Путь не найден
            return

        for root, dirs, files in os.walk(log_path):
            for file in files:
                if file.endswith('.log'):
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1

        total_size_mb = total_size / (1024 * 1024)

        # Возвращаем размер в MB
        print(f"{total_size_mb:.2f}")

    except Exception as e:
        print(f"0")  # Ошибка

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: nginx_monitor.py <check> [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "http" and len(sys.argv) > 2:
        url = sys.argv[2]
        sys.exit(check_nginx(url))
    elif command == "log_size" and len(sys.argv) > 2:
        log_path = sys.argv[2]
        get_log_size(log_path)
    else:
        print("0")
        sys.exit(1)
