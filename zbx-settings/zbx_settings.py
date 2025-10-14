import json
import os
import time
import urllib.request
import urllib.error

API_URL = os.getenv("ZBX_API_URL", "http://zbx-web:8080/api_jsonrpc.php")  # путь к API Zabbix Web
ZBX_USER = os.getenv("ZBX_USER")
ZBX_PASS = os.getenv("ZBX_PASS")

WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", "600"))
WAIT_INTERVAL = int(os.getenv("WAIT_INTERVAL", "5"))

GROUP_NAME = "Linux servers"
TEMPLATE_LINUX_AGENT = "Linux by Zabbix agent"
TEMPLATE_SERVER_HEALTH = "Zabbix server health"

HOSTS = [
    {"host": "webserver1", "dns": "webserver1", "port": "10050", "templates": [TEMPLATE_LINUX_AGENT]},
    {"host": "webserver2", "dns": "webserver2", "port": "10050", "templates": [TEMPLATE_LINUX_AGENT]},
    {"host": "log-srv", "dns": "log-srv", "port": "10050", "templates": []},
    {"host": "monitoring-plugins", "dns": "monitoring-plugins", "port": "10050", "templates": []},
]

# На хосте log-srv создаем элементы данных и триггеры для webserver1/2
LOG_ITEMS = [
    {
        "name": 'Log webserver1',
        "key_": 'logrt["/var/log/remote/webserver1/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip]',
        "delay": "1m",
        "trigger_name": "Trigger for webserver1 logs",
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver1/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],5m,,"ne")>0'
    },
    {
        "name": 'Log webserver2',
        "key_": 'logrt["/var/log/remote/webserver2/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip]',
        "delay": "1m",
        "trigger_name": "Trigger for webserver2 logs",
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver2/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],5m,,"ne")>0'
    },
]

# Номера типов в Zabbix API
ITEM_TYPE_ZABBIX_AGENT_ACTIVE = 7
VALUE_TYPE_LOG = 2

ITEM_TYPE_ZABBIX_AGENT = 0
VALUE_TYPE_FLOAT = 0
VALUE_TYPE_UINT = 3

req_id = 0


def wait_for_api(timeout=600, interval=5):
    """Ждём, пока фронтенд Zabbix начнёт отвечать на apiinfo.version."""
    print(f"Жду ответа от Zabbix API по адресу: {API_URL}")
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            v = call_api("apiinfo.version", {})
            print(f"Успешное подключение к Zabbix API! Версия: {v}")
            return
        except Exception as e:
            last_err = e
            time.sleep(interval)
    raise RuntimeError(f"Zabbix API не поднялся за {timeout}с: {last_err}")


def call_api(method, params, token=None):
    """Вызов метода Zabbix API и возврат результата."""
    global req_id
    req_id += 1
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": req_id}
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json-rpc"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API_URL, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='ignore')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL error: {e.reason}")
    if "error" in resp:
        raise RuntimeError(f"API {method} error: {resp['error']}")
    return resp["result"]


def login(user, password):
    """Аутентификация в Zabbix и получение токена."""
    return call_api("user.login", {"username": user, "password": password})


def ensure_group(token, name):
    """Создает группу для хостов, если её нет и возвращает её ID."""
    r = call_api("hostgroup.get", {"filter": {"name": [name]}}, token)
    if r: return r[0]["groupid"]
    return call_api("hostgroup.create", {"name": name}, token)["groupids"][0]


def get_template_ids(token, names):
    """Возвращает ID шаблонов по их именам, падает, если какие-то не найдены."""
    if not names: return []
    r = call_api("template.get", {"filter": {"host": names}}, token)
    found = {t["host"]: t["templateid"] for t in r}
    missing = [n for n in names if n not in found]
    if missing:
        raise RuntimeError(f"Шаблоны не найдены: {missing}")
    return [found[n] for n in names]


def get_host_by_name(token, host):
    """Возвращает объект хоста по имени или None."""
    r = call_api("host.get", {
        "filter": {"host": [host]},
        "selectInterfaces": "extend",
        "selectGroups": "extend",
        "selectParentTemplates": "extend"
    }, token)
    return r[0] if r else None


def ensure_interface(token, hostid, desired):
    """Создаёт или обновляет информацию о хосте."""
    r = call_api("hostinterface.get", {"hostids": hostid}, token)
    agent_if = next((i for i in r if int(i["type"]) == 1), None)
    if agent_if:
        need_update = any([
            agent_if.get("dns") != desired["dns"],
            agent_if.get("port") != desired["port"],
            int(agent_if.get("useip", 0)) != desired["useip"],
            int(agent_if.get("main", 1)) != desired["main"]
        ])
        if need_update:
            call_api("hostinterface.update", {"interfaceid": agent_if["interfaceid"], **desired}, token)
    else:
        call_api("hostinterface.create", {"hostid": hostid, **desired}, token)


def set_templates_exact(token, hostid, templateids_wanted):
    """Устанавливает шаблоны для хоста."""
    cur = call_api("host.get", {"hostids": hostid, "selectParentTemplates": "extend"}, token)[0]
    current = {t["templateid"] for t in cur.get("parentTemplates", [])}
    wanted = set(templateids_wanted)
    call_api("host.update", {
        "hostid": hostid,
        "templates": [{"templateid": tid} for tid in wanted],
        "templates_clear": [{"templateid": tid} for tid in (current - wanted)]
    }, token)


def ensure_host(token, groupid, host, dns, port, template_names):
    """Создаёт хост при его отсутствии и заполняет нужными данными."""
    templateids = get_template_ids(token, template_names)
    desired_if = {"type": 1, "main": 1, "useip": 0, "ip": "", "dns": dns, "port": port}
    existing = get_host_by_name(token, host)
    if not existing:
        params = {
            "host": host, "name": host,
            "groups": [{"groupid": groupid}],
            "interfaces": [desired_if],
        }
        if templateids:
            params["templates"] = [{"templateid": tid} for tid in templateids]
        res = call_api("host.create", params, token)
        return res["hostids"][0]
    else:
        hostid = existing["hostid"]
        cur_groups = {g["groupid"] for g in existing.get("groups", [])}
        if groupid not in cur_groups:
            call_api("host.update", {"hostid": hostid,
                                     "groups": [{"groupid": gid} for gid in sorted(cur_groups | {groupid})]}, token)
        ensure_interface(token, hostid, desired_if)
        set_templates_exact(token, hostid, templateids)
        return hostid


def ensure_log_item(token, hostid, name, key_, delay="1m"):
    """Создаёт или обновляет элемент данных для логов на хосте."""
    r = call_api("item.get", {"hostids": hostid, "filter": {"key_": key_}}, token)
    params = {
        "name": name,
        "key_": key_,
        "type": ITEM_TYPE_ZABBIX_AGENT_ACTIVE,
        "value_type": VALUE_TYPE_LOG,
        "delay": delay,
        "history": "7d",
        "trends": "0"
    }
    if r:
        itemid = r[0]["itemid"]
        call_api("item.update", {"itemid": itemid, **params}, token)
        return itemid
    else:
        res = call_api("item.create", {"hostid": hostid, **params}, token)
        return res["itemids"][0]


def ensure_trigger(token, description, expression, priority=3):
    """Создаёт или обновляет триггер."""
    r = call_api("trigger.get", {"filter": {"description": [description]}}, token)
    if r:
        tid = r[0]["triggerid"]
        call_api("trigger.update", {"triggerid": tid, "expression": expression, "priority": priority}, token)
        return tid
    else:
        res = call_api("trigger.create", {"description": description, "expression": expression, "priority": priority},
                       token)
        return res["triggerids"][0]


def provision_logs_and_triggers(token):
    """Устанавливает элементы данных и триггеры на хосте log-srv."""
    logsrv = get_host_by_name(token, "log-srv")
    if not logsrv:
        raise RuntimeError('Хост "log-srv" не найден; сначала создайте его.')
    logsrv_id = logsrv["hostid"]
    for it in LOG_ITEMS:
        itemid = ensure_log_item(token, logsrv_id, it["name"], it["key_"], it["delay"])
        trig_id = ensure_trigger(token, it["trigger_name"], it["trigger_expr"], priority=3)
        print(
            f"Элемент данных для логов создан/обновлён: {it['name']} (id={itemid})\nТриггер для логов создан/обновлён: {it['trigger_name']} (id={trig_id})")


def set_user_language(token, username, lang="ru_RU"):
    """Устанавливает язык интерфейса пользователя в Zabbix."""
    users = call_api("user.get", {"filter": {"username": [username]}}, token)
    if not users:
        raise RuntimeError(f'Пользователь "{username}" не найден')
    uid = users[0]["userid"]
    call_api("user.update", {"userid": uid, "lang": lang}, token)


def ensure_zabbix_server_health_only(token):
    """Оставляет на хосте "Zabbix server" только шаблон "Zabbix server health"."""
    zbx_host = get_host_by_name(token, "Zabbix server")
    if not zbx_host:
        raise RuntimeError('Хост "Zabbix server" не найден')
    zbx_hostid = zbx_host["hostid"]
    health_tid = get_template_ids(token, [TEMPLATE_SERVER_HEALTH])[0]
    set_templates_exact(token, zbx_hostid, [health_tid])
    print('Установлены шаблоны для хоста "Zabbix server": "Zabbix server health".')


def get_agent_interface_id(token, hostid):
    """Возвращает interfaceid агентского интерфейса хоста (type=1)."""
    ifs = call_api("hostinterface.get", {"hostids": hostid}, token)
    agent_if = next((i for i in ifs if int(i.get("type", 1)) == 1), None)
    if not agent_if:
        raise RuntimeError(f"No Zabbix agent interface on host {hostid}")
    return agent_if["interfaceid"]


def ensure_numeric_item(token, hostid, name, key_, value_type=VALUE_TYPE_UINT, delay="1m", timeout="10s"):
    """Создаёт/обновляет числовой элемент данных (type=Zabbix agent) и возвращает itemid."""
    iface_id = get_agent_interface_id(token, hostid)

    r = call_api("item.get", {"hostids": hostid, "filter": {"key_": key_}}, token)
    common = {
        "name": name,
        "key_": key_,
        "type": ITEM_TYPE_ZABBIX_AGENT,
        "value_type": value_type,
        "delay": delay,
        "timeout": timeout,
        "history": "31d",
        "trends": "90d",
        "interfaceid": iface_id,
    }

    if r:
        iid = r[0]["itemid"]
        call_api("item.update", {"itemid": iid, **common}, token)
        return iid
    else:
        res = call_api("item.create", {"hostid": hostid, **common}, token)
        return res["itemids"][0]


def provision_plugin_items(token):
    """Создаёт элементы данных для контейнера 'monitoring-plugins' (проверка доступности HTTP (1/0) и размер логов в (MB))."""
    host = get_host_by_name(token, "monitoring-plugins")
    if not host:
        raise RuntimeError('Хост "monitoring-plugins" не найден')
    hid = host["hostid"]

    # 1/0 — HTTP состояние
    ensure_numeric_item(token, hid, "HTTP Check webserver1", 'check_http[webserver1]', VALUE_TYPE_UINT, "1m", "10s")
    ensure_numeric_item(token, hid, "HTTP Check webserver2", 'check_http[webserver2]', VALUE_TYPE_UINT, "1m", "10s")

    ensure_numeric_item(token, hid, "HTTP Check webserver1 by custom python plugin",
                        'nginx.check[http,http://webserver1,]', VALUE_TYPE_UINT, "1m", "10s")
    ensure_numeric_item(token, hid, "HTTP Check webserver2 by custom python plugin",
                        'nginx.check[http,http://webserver2,]', VALUE_TYPE_UINT, "1m", "10s")

    # MB — размер логов
    ensure_numeric_item(token, hid, "Webserver1 Logs Size",
                        'nginx.check[log_size,/var/log/remote/webserver1]', VALUE_TYPE_FLOAT, "5m", "10s")
    ensure_numeric_item(token, hid, "Webserver2 Logs Size",
                        'nginx.check[log_size,/var/log/remote/webserver2]', VALUE_TYPE_FLOAT, "5m", "10s")

    print("Элементы данных для контейнера 'monitoring-plugins' для проверки доступности HTTP и размера логов успешно установлены!")


def main():
    """Основная функция запуска для полной настройки Zabbix."""
    wait_for_api(timeout=WAIT_TIMEOUT, interval=WAIT_INTERVAL)  # Ждём, когда API Zabbix будет доступен

    token = login(ZBX_USER, ZBX_PASS)

    # Интерфейс пользователя на русском
    set_user_language(token, ZBX_USER, "ru_RU")

    # Создаем хосты webserver1/2/log-srv
    groupid = ensure_group(token, GROUP_NAME)
    for h in HOSTS:
        hid = ensure_host(token, groupid, h["host"], h["dns"], h["port"], h["templates"])
        print(f"Хост создан/обновлён: {h['host']} (id={hid})")

    # Создаем элементы данных и триггеры для логов на хосте log-srv
    provision_logs_and_triggers(token)

    # Для Zabbix server оставляем только шаблон "Zabbix server health"
    ensure_zabbix_server_health_only(token)

    # Создаём элементы данных для контейнера с плагинами
    provision_plugin_items(token)

    print("Готово! Zabbix успешно настроен!")


if __name__ == "__main__":
    main()
