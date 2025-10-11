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
            print("1")  # OK
            return 0
        else:
            print("0")  # ERROR
            return 1
    except:
        print("0")  # ERROR
        return 1

def check_log_size(log_path, max_size_mb):
    """Проверка размера логов"""
    try:
        total_size = 0
        for root, dirs, files in os.walk(log_path):
            for file in files:
                if file.endswith('.log'):
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
        
        total_size_mb = total_size / (1024 * 1024)
        
        if total_size_mb > max_size_mb:
            print("0")  # ERROR - превышен размер
        else:
            print("1")  # OK
    except:
        print("0")  # ERROR

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: nginx_monitor.py <check> [args...]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "http" and len(sys.argv) > 2:
        url = sys.argv[2]
        sys.exit(check_nginx(url))
    elif command == "log_size" and len(sys.argv) > 3:
        log_path = sys.argv[2]
        max_size = int(sys.argv[3])
        check_log_size(log_path, max_size)
    else:
        print("0")
        sys.exit(1)
