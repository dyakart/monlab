import json
import os
import socket
import time
import urllib.error
import urllib.request

API_URL = os.getenv("ZBX_API_URL", "http://zbx-web:8080/api_jsonrpc.php")  # путь к API Zabbix Web

HTTP_TIMEOUT = 15
HTTP_TIMEOUT_LONG = 60
API_RETRIES = 8
API_RETRY_DELAY = 3
API_RETRY_BACKOFF = 1.6
socket.setdefaulttimeout(HTTP_TIMEOUT)

ITEM_TYPE_SNMP_AGENT = 20
PREPROC_MULTIPLY = 1
ERRH_IGNORE = 0

LONG_METHODS = {
    "host.create", "host.update", "item.create", "item.update",
    "trigger.create", "trigger.update", "action.create", "action.update",
    "mediatype.create", "mediatype.update", "user.update", "hostinterface.update", "hostinterface.create",
}

ZBX_USER = os.getenv("ZBX_USER")
ZBX_PASS = os.getenv("ZBX_PASS")
ZBX_LANG = os.getenv("ZBX_LANG")

SNMPV3_USER = "zabbix"
SNMP_AUTH_PASS = os.getenv("SNMP_AUTH_PASS", "")
SNMP_PRIV_PASS = os.getenv("SNMP_PRIV_PASS", "")

WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", "600"))
WAIT_INTERVAL = int(os.getenv("WAIT_INTERVAL", "5"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PREPROC_CHANGE_PER_SECOND = 10

GROUP_NAME = "Linux servers"
TEMPLATE_LINUX_AGENT = "Linux by Zabbix agent"
TEMPLATE_SERVER_HEALTH = "Zabbix server health"

PROXY_NAME = os.getenv("ZBX_PROXY_NAME", "zbx-proxy-1")

HOSTS = [
    {"host": "webserver1", "dns": "webserver1", "port": "10050", "templates": [TEMPLATE_LINUX_AGENT]},
    {"host": "webserver2", "dns": "webserver2", "port": "10050", "templates": [TEMPLATE_LINUX_AGENT]},
    {"host": "webserver3", "dns": "webserver3", "port": "10050", "templates": [TEMPLATE_LINUX_AGENT]},
    {"host": "webserver4", "dns": "webserver4", "port": "10050", "templates": [TEMPLATE_LINUX_AGENT]},
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
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver1/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],1m)>0'
    },
    {
        "name": 'Log webserver2',
        "key_": 'logrt["/var/log/remote/webserver2/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip]',
        "delay": "1m",
        "trigger_name": "Trigger for webserver2 logs",
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver2/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],1m)>0'
    },
    {
        "name": 'Log webserver3',
        "key_": 'logrt["/var/log/remote/webserver3/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip]',
        "delay": "1m",
        "trigger_name": "Trigger for webserver3 logs",
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver3/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],1m)>0'
    },
    {
        "name": 'Log webserver4',
        "key_": 'logrt["/var/log/remote/webserver4/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip]',
        "delay": "1m",
        "trigger_name": "Trigger for webserver4 logs",
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver4/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],1m)>0'
    },
]

LOG_TRIGGER_ACTION_NAME = "Send webserver1..4 LOG problems to Telegram"
LOG_TRIGGER_NAMES = [
    "Trigger for webserver1 logs",
    "Trigger for webserver2 logs",
    "Trigger for webserver3 logs",
    "Trigger for webserver4 logs",
]

# Номера типов в Zabbix API
ITEM_TYPE_ZABBIX_AGENT_ACTIVE = 7
VALUE_TYPE_LOG = 2

ITEM_TYPE_ZABBIX_AGENT = 0
VALUE_TYPE_FLOAT = 0
VALUE_TYPE_UINT = 3

req_id = 0


def wait_for_api(timeout=600, interval=5):
    """Ждёт, пока фронтенд Zabbix начнёт отвечать на apiinfo.version."""
    print(f"⌛  Жду ответа от Zabbix API по адресу: {API_URL}")
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            v = call_api("apiinfo.version", {})
            print(f"✅  Успешное подключение к Zabbix API! Версия: {v}\n")
            return
        except Exception as e:
            last_err = e
            time.sleep(interval)
    raise RuntimeError(f"Zabbix API не поднялся за {timeout}с: {last_err}")


def wait_for_login(user, password, timeout=600, interval=5):
    """Ждет, пока авторизация Zabbix API начнет отвечать (user.login)"""
    print("⌛  Жду ответа от сервиса авторизации Zabbix API...")
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            token = login(user, password)
            print("✅  Авторизация Zabbix API готова.\n")
            return token
        except Exception as e:
            last_err = e
            time.sleep(interval)
    raise RuntimeError(f"user.login так и не ответил за {timeout}с: {last_err}")


def wait_for_write_ready(token, timeout=900, interval=5):
    """Ждет готовность Zabbix к записям"""
    print("⌛  Проверяю готовность Zabbix к записям...")
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        probe = f"__probe_{int(time.time())}"
        try:
            res = call_api("hostgroup.create", {"name": probe}, token)
            gid = res["groupids"][0]
            # сразу же удаляем
            call_api("hostgroup.delete", [gid], token)
            print("✅  API готов к операциям записи.\n")
            return
        except Exception as e:
            last_err = e
            time.sleep(interval)
    raise RuntimeError(f"Проверка на запись не прошла за {timeout}с: {last_err}")


def call_api(method, params, token=None):
    """Вызов метода Zabbix API."""
    global req_id
    last_err = None
    timeout = HTTP_TIMEOUT_LONG if method in LONG_METHODS else HTTP_TIMEOUT

    for attempt in range(1, API_RETRIES + 1):
        req_id += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": req_id}
        if token:
            body["auth"] = token
        data = json.dumps(body).encode()
        headers = {
            "Content-Type": "application/json-rpc",
            "Accept": "application/json",
            "Connection": "close",
        }
        req = urllib.request.Request(API_URL, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read().decode())
            if "error" in resp:
                raise RuntimeError(f"API {method} error: {resp['error']}")
            return resp["result"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            sleep = min(API_RETRY_DELAY * (API_RETRY_BACKOFF ** (attempt - 1)), 30)
            print(
                f"⚠️  API метод '{method}' попытка {attempt}/{API_RETRIES} не удалась: {e}. Повтор через {sleep:.1f}s")
            time.sleep(sleep)

    raise RuntimeError(f"API метод '{method}' провалился после {API_RETRIES} попыток: {last_err}")


def login(user, password):
    """Аутентификация в Zabbix и получение токена."""
    return call_api("user.login", {"username": user, "password": password})


def ensure_proxy(token, name, mode=0):
    """Возвращает proxyid по имени или создает прокси."""
    r = call_api("proxy.get", {
        "output": ["proxyid", "name"],
        "filter": {"name": [name]}
    }, token)
    if r:
        return r[0]["proxyid"]

    res = call_api("proxy.create", {
        "name": name,
        "operating_mode": mode  # 0=active, 1=passive
    }, token)
    return res["proxyids"][0]


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


def ensure_host(token, groupid, host, dns, port, template_names, proxy_hostid=None):
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

        if proxy_hostid:
            params["monitored_by"] = 1  # 1 = Proxy
            params["proxyid"] = proxy_hostid

        if templateids:
            params["templates"] = [{"templateid": tid} for tid in templateids]
        res = call_api("host.create", params, token)
        return res["hostids"][0]
    else:
        hostid = existing["hostid"]
        cur_groups = {g["groupid"] for g in existing.get("groups", [])}

        if proxy_hostid:
            call_api("host.update", {
                "hostid": hostid,
                "monitored_by": 1,
                "proxyid": proxy_hostid
            }, token)

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


def ensure_trigger(token, description, expression, priority=3, manual_close=1, recovery_mode=None,
                   recovery_expression=None):
    """
    Создаёт или обновляет триггер.
    - priority=4 -> High
    - manual_close=1 -> Разрешить ручное закрытие
    """
    r = call_api("trigger.get", {"filter": {"description": [description]}}, token)
    obj = {
        "description": description,
        "expression": expression,
        "priority": priority,
        "manual_close": manual_close,
    }

    if recovery_mode is not None:
        obj["recovery_mode"] = recovery_mode
        if recovery_mode in (1, 2) and recovery_expression:
            obj["recovery_expression"] = recovery_expression

    if r:
        tid = r[0]["triggerid"]
        try:
            call_api("trigger.update", {"triggerid": tid, **obj}, token)
            return tid
        except Exception:
            # удаляем и пересоздаем — на случай «битых» старых выражений
            call_api("trigger.delete", [tid], token)

    res = call_api("trigger.create", obj, token)
    return res["triggerids"][0]


def get_trigger_ids_by_descriptions(token, descriptions):
    """
    Возвращает id триггера.
    """
    r = call_api("trigger.get", {
        "filter": {"description": descriptions},
        "output": ["triggerid", "description"]
    }, token)
    found = {t["description"]: t["triggerid"] for t in r}
    missing = [d for d in descriptions if d not in found]
    if missing:
        raise RuntimeError(f"Не найдены триггеры по описанию: {missing}")
    return found


def ensure_trigger_action_for_log_triggers(token, name, mediatypeid, userid, trigger_names):
    """
    Создаёт/обновляет Action, которое реагирует только на заданные триггеры логов.
    """
    ids = get_trigger_ids_by_descriptions(token, trigger_names)

    conditions = [{
        "conditiontype": 2,  # 2 = Trigger
        "operator": 0,
        "value": str(tid)
    } for tid in ids.values()]

    action_obj = {
        "name": name,
        "eventsource": 0,  # Trigger actions
        "status": 0,  # enabled
        "filter": {
            "evaltype": 2,  # OR (A or B)
            "conditions": conditions
        },
        "operations": [{
            "operationtype": 0,  # send message
            "opmessage": {"default_msg": 1, "mediatypeid": mediatypeid},
            "opmessage_usr": [{"userid": userid}]
        }],
        "recovery_operations": [{
            "operationtype": 0,
            "opmessage": {"default_msg": 1, "mediatypeid": mediatypeid},
            "opmessage_usr": [{"userid": userid}]
        }]
    }

    cur = call_api("action.get", {"filter": {"name": [name]}}, token)
    if cur:
        action_obj["actionid"] = cur[0]["actionid"]
        call_api("action.update", action_obj, token)
        return action_obj["actionid"]
    else:
        res = call_api("action.create", action_obj, token)
        return res["actionids"][0]


def provision_logs_and_triggers(token):
    """Устанавливает элементы данных и триггеры на хосте log-srv."""
    logsrv = get_host_by_name(token, "log-srv")
    if not logsrv:
        raise RuntimeError('Хост "log-srv" не найден; сначала создайте его.')
    logsrv_id = logsrv["hostid"]

    for it in LOG_ITEMS:
        itemid = ensure_log_item(token, logsrv_id, it["name"], it["key_"], it["delay"])

        trig_id = ensure_trigger(
            token,
            it["trigger_name"],
            it["trigger_expr"],
            priority=4,
            manual_close=1  # Разрешаем ручное закрытие
        )
        print(
            f"✅  Элемент данных для логов создан/обновлён: {it['name']} (id={itemid})\n✅  Триггер для логов создан/обновлён: {it['trigger_name']} (id={trig_id})"
        )


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
    print('\n✅  Установлены шаблоны для хоста "Zabbix server": "Zabbix server health".\n')


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


def ensure_numeric_item_on_host(token, host_name, name, key_, value_type=VALUE_TYPE_FLOAT, delay="1m", timeout="10s"):
    """Создаёт/обновляет числовой элемент данных на конкретном хосте."""
    host = get_host_by_name(token, host_name)
    if not host:
        raise RuntimeError(f'Хост "{host_name}" не найден')
    hostid = host["hostid"]

    r = call_api("item.get", {"hostids": hostid, "filter": {"key_": key_}, "output": "extend"}, token)
    if r:
        it = r[0]
        if it.get("templateid"):
            return it["itemid"]

        upd = {
            "itemid": it["itemid"],
            "name": name,
            "delay": delay,
            "timeout": timeout,
        }
        call_api("item.update", upd, token)
        return it["itemid"]

    iface_id = get_agent_interface_id(token, hostid)
    create = {
        "hostid": hostid,
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
    res = call_api("item.create", create, token)
    return res["itemids"][0]


def ensure_required_items_for_hosts(token, hosts=("webserver1", "webserver2", "webserver3", "webserver4")):
    """
    Создаёт элементы данных для CPU и свободного места на /.
    """
    for h in hosts:
        ensure_numeric_item_on_host(token, h, "CPU utilization, %", "system.cpu.util", VALUE_TYPE_FLOAT, "1m", "10s")
        ensure_numeric_item_on_host(token, h, "Free space on /, %", "vfs.fs.size[/,pfree]", VALUE_TYPE_FLOAT, "1m",
                                    "10s")


def ensure_telegram_mediatype(token, name="Telegram (Webhook)"):
    """
    Создаёт/обновляет в Zabbix медиа-тип «Telegram (Webhook)».

    Создаёт Webhook-медиа-тип (type=4) с готовым JavaScript-скриптом отправки сообщений
    в Telegram Bot API (sendMessage). Если медиа-тип с таким именем уже существует —
    обновляет его параметры (скрипт, таймаут, шаблоны сообщений и т.п.).

    Параметры:
        token (str): Zabbix API token/или auth-токен для вызова `call_api`.
        name (str): Человекочитаемое имя медиа-типа в Zabbix. По умолчанию "Telegram (Webhook)".

    Возвращает:
        str: Идентификатор медиа-типа (mediatypeid).

    Что настраивается:
        - type=4 (Webhook), status=0 (включен), timeout="30s".
        - parameters: `token`, `chat_id`, `Message`.
        - script: JS-код с GET на `https://api.telegram.org/bot{token}/sendMessage`.
        - message_templates: шаблоны для обычного события и восстановления.
    """
    mt = call_api("mediatype.get", {"filter": {"name": [name]}}, token)

    script = r'''
    try {
      var p = {};
      try { p = JSON.parse(typeof value === 'string' ? value : '{}'); } catch(e){}
    
      function pick(n){
        if (typeof this[n] !== 'undefined' && this[n] !== null && String(this[n]).length) return String(this[n]);
        if (p && typeof p[n] !== 'undefined' && p[n] !== null) return String(p[n]);
        return '';
      }
      function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
      function rxEscape(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }
      function fmtRuDate(d,t){
        var m=d.match(/^(\d{4})\.(\d{2})\.(\d{2})$/);
        return m ? (m[3]+'.'+m[2]+'.'+m[1]+' '+t) : (d+' '+t);
      }
    
      var tgToken = pick.call(this,'token');
      var chatId = pick.call(this,'chat_id');
      var host = pick.call(this,'host');
      var status = pick.call(this,'status');
      var date = pick.call(this,'date');
      var time = pick.call(this,'time');
      var cur = pick.call(this,'value');
      var tname = pick.call(this,'tname');
      var link = pick.call(this,'link');
    
      if (!tgToken) throw 'No token';
      if (!chatId)  throw 'No chat_id';
    
      // Тип события
      var isCpu  = /CPU/i.test(tname);
      var isDisk = /(free space|pfree|disk|свободного места)/i.test(tname);
      var isLog  = /Trigger\s+for\s+webserver\d+\s+logs/i.test(tname) || /Log\s+webserver\d+/i.test(tname);
    
      var webHost = (tname.match(/webserver\d+/i) || [null])[0];
    
      // Сократим имя события (без префикса хоста)
      var tshort = tname.replace(new RegExp('^'+rxEscape(host)+':\\s*'),'').trim();
    
      var originLabel = isLog ? 'Получено с центрального сервера логов' : 'Хост события';
    
      var header, descr;
      
      if (isLog) {
        header = (status === 'PROBLEM')
          ? ('🚨 Обнаружена ошибка на сервере ' + esc(webHost || 'webserver'))
          : ('✅ Ошибка на сервере ' + esc(webHost || 'webserver') + ' устранена');
        descr = (status === 'PROBLEM')
          ? 'На веб-сервере обнаружена запись в логах, соответствующая шаблону (LAB-TEST|ERROR|CRITICAL).'
          : 'Проблема проверена и закрыта. Мониторинг продолжает наблюдение 👀';
      } else if (isCpu) {
        header = (status === 'PROBLEM') ? '⚠️ Высокая загрузка процессора' : '✅ Высокая загрузка процессора устранена';
        descr  = (status === 'PROBLEM') ? 'Зафиксирована повышенная загрузка CPU.' : 'Загрузка CPU вернулась в норму.';
      } else if (isDisk) {
        header = (status === 'PROBLEM') ? '⚠️ Мало свободного места на диске' : '✅ Диск снова в норме';
        descr  = (status === 'PROBLEM') ? 'Свободного места недостаточно.' : 'Свободное место восстановлено.';
      } else {
        header = (status === 'PROBLEM') ? '⚠️ Обнаружена проблема' : '✅ Проблема устранена';
        descr  = 'Мониторинг продолжает наблюдение 👀';
      }
    
      if (!isLog && cur && /[0-9]/.test(cur)) {
        var m = cur.match(/([0-9]+(?:[.,][0-9]+)?)/);
        if (m) cur = (Math.round(parseFloat(m[1].replace(',', '.'))*100)/100) + (/%/.test(cur) ? ' %' : '');
      }
    
      // Текст сообщения
      var text = header + '\n\n' +
                 originLabel + ': <b>' + esc(host) + '</b>\n' +
                 'Событие: ' + esc(tshort) + '\n' +
                 '📅 Дата: ' + esc(fmtRuDate(date,time)) + '\n';
    
      if (isLog) {
        text += 'Шаблон поиска: <code>LAB-TEST|ERROR|CRITICAL</code>\n';
        if (cur && cur !== '-') {
          text += '\n🧾 Последняя запись:\n<code>' + esc(String(cur)).slice(0, 3500) + '</code>\n';
        }
      } else {
        text += '📊 Текущее значение: ' + esc(cur || '-') + '\n';
      }
    
      if (link) text += '\n\n🔗 ' + esc(link);
    
      // Отправка в Telegram
      var url = 'https://api.telegram.org/bot' + tgToken +
                '/sendMessage?chat_id=' + encodeURIComponent(chatId) +
                '&parse_mode=HTML' +
                '&text=' + encodeURIComponent(text);
    
      var req = new HttpRequest();
      var resp = req.get(url);
      Zabbix.log(4, 'TG webhook GET status=' + req.getStatus() + ' resp=' + resp);
      if (req.getStatus() !== 200) throw 'HTTP ' + req.getStatus() + ': ' + resp;
    
      return 'OK';
    } catch (e) {
      Zabbix.log(3, 'TG webhook error: ' + e);
      throw e;
    }
    '''.strip()

    params = [
        {"name": "token", "value": (TELEGRAM_BOT_TOKEN or "")},
        {"name": "chat_id", "value": "{ALERT.SENDTO}"},
        {"name": "host", "value": "{HOST.NAME}"},
        {"name": "status", "value": "{EVENT.STATUS}"},
        {"name": "date", "value": "{EVENT.DATE}"},
        {"name": "time", "value": "{EVENT.TIME}"},
        {"name": "value", "value": "{ITEM.LASTVALUE1}"},
        {"name": "tname", "value": "{TRIGGER.NAME}"},
        {"name": "link", "value": "{TRIGGER.URL}"},
    ]
    msg_templates = [
        {"eventsource": 0, "recovery": 0, "subject": "{EVENT.NAME}", "message": "{ALERT.MESSAGE}"},
        {"eventsource": 0, "recovery": 1, "subject": "RECOVERY: {EVENT.NAME}", "message": "{ALERT.MESSAGE}"},
    ]
    obj = {"name": name, "type": 4, "status": 0, "parameters": params, "script": script,
           "message_templates": msg_templates, "timeout": "30s"}

    if mt:
        obj["mediatypeid"] = mt[0]["mediatypeid"]
        call_api("mediatype.update", obj, token)
        return obj["mediatypeid"]
    else:
        res = call_api("mediatype.create", obj, token)
        return res["mediatypeids"][0]


def ensure_user_media_telegram(token, userid, mediatypeid, chat_id):
    """
    Привязывает Telegram-медиа к пользователю Zabbix (создаёт или обновляет «User media»).

    Если у пользователя уже есть запись медиа данного типа — обновляет её (chat_id, режим, период, уровни).
    Иначе добавляет новую запись в профиль пользователя.

    Параметры:
        token (str): Zabbix API токен.
        userid (str|int): Идентификатор пользователя Zabbix (userid).
        mediatypeid (str|int): Идентификатор медиа-типа (Telegram Webhook).
        chat_id (str): Целевой Telegram chat_id (куда слать уведомления).
    """

    usr = call_api("user.get", {"userids": [userid], "selectMedias": "extend"}, token)[0]
    medias = usr.get("medias", [])
    existing = next((m for m in medias if m["mediatypeid"] == str(mediatypeid)), None)
    media_obj = {
        "mediatypeid": mediatypeid,
        "sendto": chat_id,
        "active": 0,  # 0 - включено
        "severity": 63,  # все уровни
        "period": "1-7,00:00-24:00"
    }
    if existing:
        call_api("user.update", {"userid": userid, "medias": [{
            "mediaid": existing["mediaid"], **media_obj
        }]}, token)
    else:
        call_api("user.update", {"userid": userid, "medias": [media_obj]}, token)


def ensure_trigger_action_telegram(token, name, mediatypeid, userid, groupid):
    """
    Создаёт или обновляет Zabbix Action, отправляющее триггер-уведомления в Telegram.

    Действие срабатывает для триггеров с уровнем «Warning» и выше. Отправляет сообщение пользователю через указанный
    медиа-тип при проблеме.

    Параметры:
        token (str): Zabbix API токен.
        name (str): Имя действия (Action) в Zabbix.
        mediatypeid (str|int): Идентификатор медиа-типа (Telegram Webhook).
        userid (str|int): Пользователь, которому отправлять уведомления.
        groupid (str|int): Идентификатор группы хостов, по которой фильтровать события.
        кроме хоста log-srv

    Возвращает:
        str: Идентификатор действия (actionid).
    """
    log_host = get_host_by_name(token, "log-srv")
    if not log_host:
        raise RuntimeError('Хост "log-srv" не найден для исключения из общего действия.')
    log_hostid = log_host["hostid"]

    cur = call_api("action.get", {"filter": {"name": [name]}}, token)

    action = {
        "name": name,
        "eventsource": 0,  # Trigger actions
        "status": 0,
        "filter": {
            "evaltype": 0,  # AND
            "conditions": [
                {"conditiontype": 0, "operator": 0, "value": str(groupid)},  # Host group = Linux servers
                {"conditiontype": 4, "operator": 5, "value": "2"},  # Severity >= Warning
                {"conditiontype": 1, "operator": 1, "value": str(log_hostid)},  # Host != log-srv
            ]
        },
        "operations": [{
            "operationtype": 0,  # send message
            "opmessage": {"default_msg": 1, "mediatypeid": mediatypeid},
            "opmessage_usr": [{"userid": userid}]
        }],
        "recovery_operations": [{
            "operationtype": 0,
            "opmessage": {"default_msg": 1, "mediatypeid": mediatypeid},
            "opmessage_usr": [{"userid": userid}]
        }]
    }

    if cur:
        action["actionid"] = cur[0]["actionid"]
        call_api("action.update", action, token)
        return action["actionid"]
    else:
        res = call_api("action.create", action, token)
        return res["actionids"][0]


def ensure_cpu_disk_triggers(token, hosts=("webserver1", "webserver2", "webserver3", "webserver4")):
    """
    Создаёт, если их нет базовые триггеры по CPU и свободному месту на корне для заданных хостов.

    Для каждого хоста добавляет два триггера:
      1) Высокая загрузка CPU: среднее за 1 минуту > 50% (`system.cpu.util`).
      2) Мало свободного места на `/`: доля свободного < 40% (`vfs.fs.size[/,pfree]`).

    Параметры:
        token (str): Zabbix API токен.
        hosts (Iterable[str]): Имена хостов в Zabbix.
    """
    for h in hosts:
        cpu_descr = f"{h}: High CPU utilization > 50%"
        cpu_expr = f"avg(/{h}/system.cpu.util,1m)>50"
        ensure_trigger(token, cpu_descr, cpu_expr, priority=4)

        disk_descr = f"{h}: Low free space on / < 40%"
        disk_expr = f"min(/{h}/vfs.fs.size[/,pfree],1m)<40"
        ensure_trigger(token, disk_descr, disk_expr, priority=4)


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

    print(
        "\n✅  Элементы данных для контейнера 'monitoring-plugins' для проверки доступности HTTP и размера логов успешно установлены!\n"
    )


def ensure_templategroup(token, name="Templates"):
    """Возвращает ID группы шаблонов с именем name, создавая её при отсутствии."""
    r = call_api("templategroup.get", {"filter": {"name": [name]}}, token)
    if r: return r[0]["groupid"]
    return call_api("templategroup.create", {"name": name}, token)["groupids"][0]


def ensure_valuemap_ifoperstatus(token, templateid):
    """Создаёт/обновляет valuemap 'ifOperStatus' на шаблоне и возвращает его ID."""
    entries = [
        {"value": "1", "newvalue": "up"},
        {"value": "2", "newvalue": "down"},
        {"value": "3", "newvalue": "testing"},
        {"value": "4", "newvalue": "unknown"},
        {"value": "5", "newvalue": "dormant"},
        {"value": "6", "newvalue": "notPresent"},
        {"value": "7", "newvalue": "lowerLayerDown"},
    ]

    r = call_api("valuemap.get", {
        "filter": {"name": ["ifOperStatus"]},
        "hostids": [templateid]
    }, token)

    if r:
        call_api("valuemap.update", {
            "valuemapid": r[0]["valuemapid"],
            "mappings": entries
        }, token)
        return r[0]["valuemapid"]

    res = call_api("valuemap.create", {
        "name": "ifOperStatus",
        "mappings": entries,
        "hostid": templateid
    }, token)
    return res["valuemapids"][0]


def ensure_template_snmp(token, name="New SNMP"):
    """Возвращает ID SNMP-шаблона с именем name, создавая его в группе Templates при отсутствии."""
    tg_id = ensure_templategroup(token, "Templates")
    t = call_api("template.get", {"filter": {"host": [name]}}, token)
    if t:
        return t[0]["templateid"]
    res = call_api("template.create", {"host": name, "name": name, "groups": [{"groupid": tg_id}]}, token)
    return res["templateids"][0]


def ensure_item_on_template(token, templateid, **kwargs):
    """Создаёт или обновляет item на шаблоне и возвращает его ID."""
    vt = int(kwargs.get("value_type", VALUE_TYPE_FLOAT))
    default_history = "31d"
    default_trends = "0" if vt in (1, 2, 4) else "90d"
    default_timeout = "5s"

    history = kwargs.pop("history", default_history)
    trends = kwargs.pop("trends", default_trends)
    timeout = kwargs.pop("timeout", default_timeout)

    is_snmp = int(kwargs.get("type", ITEM_TYPE_ZABBIX_AGENT)) == ITEM_TYPE_SNMP_AGENT

    # Ищем существующий item по ключу на шаблоне
    r = call_api("item.get", {"hostids": templateid, "filter": {"key_": kwargs["key_"]}}, token)

    if r:
        itemid = r[0]["itemid"]
        update_obj = {
            "itemid": itemid,
            "history": history,
            "trends": trends,
            **kwargs
        }
        if not is_snmp:
            update_obj["timeout"] = timeout
        update_obj.pop("hostid", None)
        call_api("item.update", update_obj, token)
        return itemid
    else:
        create_obj = {
            "hostid": templateid,
            "history": history,
            "trends": trends,
            **kwargs
        }
        if not is_snmp:
            create_obj["timeout"] = timeout
        return call_api("item.create", create_obj, token)["itemids"][0]


def ensure_snmp_items_and_trigger(token, templateid):
    """Добавляет стандартные SNMP-items на шаблон и триггер на падение eth1."""
    vmid = ensure_valuemap_ifoperstatus(token, templateid)

    ensure_item_on_template(
        token, templateid,
        name="SNMP System Uptime (sysUpTime)",
        key_='snmp.get[1.3.6.1.2.1.1.3.0]',
        snmp_oid='1.3.6.1.2.1.1.3.0',
        type=ITEM_TYPE_SNMP_AGENT,
        value_type=0,  # float
        delay="1m",
        timeout="5s",
        preprocessing=[{
            "type": PREPROC_MULTIPLY, "params": "0.01",
            "error_handler": ERRH_IGNORE, "error_handler_params": ""
        }],
        tags=[{"tag": "user", "value": "snmp"}]
    )

    # ifOperStatus eth1
    ensure_item_on_template(
        token, templateid,
        name="SNMP Interface eth1 Status (ifOperStatus)",
        key_='snmp.get[1.3.6.1.2.1.2.2.1.8.{$IFINDEX_ETH1}]',
        snmp_oid='1.3.6.1.2.1.2.2.1.8.{$IFINDEX_ETH1}',
        type=ITEM_TYPE_SNMP_AGENT,
        value_type=3,
        delay="30s",
        timeout="5s",
        valuemapid=vmid,
        tags=[{"tag": "user", "value": "snmp"}]
    )

    # sysDescr
    ensure_item_on_template(
        token, templateid,
        name="SNMP System Description (sysDescr)",
        key_='snmp.get[1.3.6.1.2.1.1.1.0]',
        snmp_oid='1.3.6.1.2.1.1.1.0',
        type=ITEM_TYPE_SNMP_AGENT,
        value_type=4,  # text
        delay="5m",
        timeout="5s",
        trends="0",
        tags=[{"tag": "user", "value": "snmp"}]
    )

    # ssCpuRawUser
    ensure_item_on_template(
        token, templateid,
        name="SNMP CPU User Time (ssCpuRawUser)",
        key_='snmp.get[1.3.6.1.4.1.2021.11.11.0]',
        snmp_oid='1.3.6.1.4.1.2021.11.11.0',
        type=ITEM_TYPE_SNMP_AGENT,
        value_type=0,  # float
        delay="1m",
        timeout="5s",
        preprocessing=[{
            "type": PREPROC_MULTIPLY, "params": "0.01",
            "error_handler": ERRH_IGNORE, "error_handler_params": ""
        }],
        units="%",
        tags=[{"tag": "user", "value": "snmp"}]
    )

    # hrSystemProcesses
    ensure_item_on_template(
        token, templateid,
        name="SNMP System Processes (hrSystemProcesses)",
        key_='snmp.get[1.3.6.1.2.1.25.1.6.0]',
        snmp_oid='1.3.6.1.2.1.25.1.6.0',
        type=ITEM_TYPE_SNMP_AGENT,
        value_type=3,  # uint
        delay="1m",
        timeout="5s",
        tags=[{"tag": "user", "value": "snmp"}]
    )

    # Триггер
    expr_problem = 'last(/New SNMP/snmp.get[1.3.6.1.2.1.2.2.1.8.{$IFINDEX_ETH1}])=2 or {$FORCE_ETH1_PROBLEM}=1'
    expr_recovery = 'last(/New SNMP/snmp.get[1.3.6.1.2.1.2.2.1.8.{$IFINDEX_ETH1}])=1 and {$FORCE_ETH1_PROBLEM}=0'

    ensure_trigger(
        token,
        "Interface eth1 is down on {HOST.NAME}",
        expr_problem,
        priority=4,
        manual_close=0,
        recovery_mode=1,
        recovery_expression=expr_recovery
    )


def ensure_snmpv3_interface(token, host_name):
    """Создаёт или обновляет SNMPv3-интерфейс хоста и задаёт параметры безопасности."""
    if not SNMP_AUTH_PASS or not SNMP_PRIV_PASS:
        raise RuntimeError("SNMP_AUTH_PASS/SNMP_PRIV_PASS не заданы для SNMPv3 интерфейса")
    host = get_host_by_name(token, host_name)
    if not host: raise RuntimeError(f'Хост "{host_name}" не найден')
    hostid = host["hostid"]

    ifs = call_api("hostinterface.get", {"hostids": hostid}, token)
    snmp_if = next((i for i in ifs if int(i.get("type", 2)) == 2), None)

    desired = {
        "hostid": hostid, "type": 2, "main": 1, "useip": 0,
        "ip": "", "dns": host_name, "port": "161",
        "details": {
            "version": 3, "bulk": 1, "maxrepetitions": 10,
            "securityname": SNMPV3_USER, "securitylevel": 2,  # 2=authPriv
            "authprotocol": 1,  # 1=SHA1
            "authpassphrase": SNMP_AUTH_PASS,
            "privprotocol": 1,  # 1=AES128
            "privpassphrase": SNMP_PRIV_PASS,
            "contextname": ""
        }
    }
    if snmp_if:
        call_api("hostinterface.update", {"interfaceid": snmp_if["interfaceid"], **desired}, token)
    else:
        call_api("hostinterface.create", desired, token)


def ensure_host_macro(token, hostid, macro, value):
    """Создаёт/обновляет хост-макрос."""
    r = call_api("usermacro.get", {"hostids": [hostid], "filter": {"macro": [macro]}}, token)
    if r:
        call_api("usermacro.update", {
            "hostmacroid": r[0]["hostmacroid"],
            "value": value
        }, token)
        return r[0]["hostmacroid"]
    else:
        res = call_api("usermacro.create", {
            "hostid": hostid,
            "macro": macro,
            "value": value
        }, token)
        return res["hostmacroids"][0]


def ensure_template_macro(token, templateid, macro, value):
    """Создаёт/обновляет шаблон-макрос."""
    r = call_api("usermacro.get", {"hostids": [templateid], "filter": {"macro": [macro]}}, token)
    if r:
        call_api("usermacro.update", {
            "hostmacroid": r[0]["hostmacroid"],
            "value": value
        }, token)
        return r[0]["hostmacroid"]
    else:
        res = call_api("usermacro.create", {
            "hostid": templateid,
            "macro": macro,
            "value": value
        }, token)
        return res["hostmacroids"][0]


def get_template_itemid_by_key(token, templateid, key_):
    """Возвращает itemid шаблона по key_ или None."""
    r = call_api("item.get", {
        "hostids": [templateid],
        "filter": {"key_": [key_]},
        "output": ["itemid", "name"]
    }, token)
    return r[0]["itemid"] if r else None


def ensure_template_graph(token, templateid, name, itemids):
    """Создает/обновляет граф шаблона по двум itemid."""
    r = call_api("graph.get", {
        "hostids": [templateid],
        "filter": {"name": [name]},
        "output": ["graphid", "flags"]
    }, token)

    g = {
        "name": name,
        "width": "900",
        "height": "200",
        "graphtype": 0,
        "gitems": [
            {"itemid": itemids[0], "color": "0040FF", "sortorder": 0},
            {"itemid": itemids[1], "color": "FF0000", "sortorder": 1},
        ]
    }

    if r:
        gid = r[0]["graphid"]
        call_api("graph.update", {"graphid": gid, **g}, token)
        print(f"✅  График для шаблона успешно обновлен (id={gid}): {name}")
        return gid

    res = call_api("graph.create", g, token)
    gid = res["graphids"][0]
    print(f"✅  График для шаблона успешно создан (id={gid}): {name}")
    return gid


def ensure_eth_inout_items_on_template(token, templateid):
    """Добавляет элементы данных на шаблон SNMP для eth0/eth1."""

    def macro_ref(n):  # вернёт строку вида '{$IFINDEX_ETH0}'
        return '{$' + n + '}'

    def inout(ifmacro, ifname):
        m = macro_ref(ifmacro)

        # IN
        ensure_item_on_template(
            token, templateid,
            name=f"SNMP Interface {ifname} Incoming Traffic (ifHCInOctets)",
            key_=f"snmp.get[1.3.6.1.2.1.31.1.1.1.6.{m}]",
            snmp_oid=f"1.3.6.1.2.1.31.1.1.1.6.{m}",
            type=ITEM_TYPE_SNMP_AGENT,
            value_type=VALUE_TYPE_UINT,
            delay="1m",
            units="bps",
            preprocessing=[
                {"type": PREPROC_CHANGE_PER_SECOND, "params": "", "error_handler": ERRH_IGNORE, "error_handler_params": ""},
                {"type": PREPROC_MULTIPLY, "params": "8", "error_handler": ERRH_IGNORE, "error_handler_params": ""}
            ],
            tags=[{"tag": "net", "value": "snmp"}]
        )

        # OUT
        ensure_item_on_template(
            token, templateid,
            name=f"SNMP Interface {ifname} Outgoing Traffic (ifHCOutOctets)",
            key_=f"snmp.get[1.3.6.1.2.1.31.1.1.1.10.{m}]",
            snmp_oid=f"1.3.6.1.2.1.31.1.1.1.10.{m}",
            type=ITEM_TYPE_SNMP_AGENT,
            value_type=VALUE_TYPE_UINT,
            delay="1m",
            units="bps",
            preprocessing=[
                {"type": PREPROC_CHANGE_PER_SECOND, "params": "", "error_handler": ERRH_IGNORE, "error_handler_params": ""},
                {"type": PREPROC_MULTIPLY, "params": "8", "error_handler": ERRH_IGNORE, "error_handler_params": ""}
            ],
            tags=[{"tag": "net", "value": "snmp"}]
        )

    inout("IFINDEX_ETH0", "eth0")
    inout("IFINDEX_ETH1", "eth1")


def ensure_eth_graphs_on_template(token, templateid):
    """Создает/обновляет графики пропускной способности eth0/eth1."""

    in0 = get_template_itemid_by_key(token, templateid, 'snmp.get[1.3.6.1.2.1.31.1.1.1.6.{$IFINDEX_ETH0}]')
    out0 = get_template_itemid_by_key(token, templateid, 'snmp.get[1.3.6.1.2.1.31.1.1.1.10.{$IFINDEX_ETH0}]')
    in1 = get_template_itemid_by_key(token, templateid, 'snmp.get[1.3.6.1.2.1.31.1.1.1.6.{$IFINDEX_ETH1}]')
    out1 = get_template_itemid_by_key(token, templateid, 'snmp.get[1.3.6.1.2.1.31.1.1.1.10.{$IFINDEX_ETH1}]')

    if in0 and out0:
        ensure_template_graph(token, templateid, "Пропускная способность eth0", [in0, out0])
    else:
        print("⚠️ На шаблоне не найдены items для eth0 (in/out) — график пропущен.")

    if in1 and out1:
        ensure_template_graph(token, templateid, "Пропускная способность eth1", [in1, out1])
    else:
        print("⚠️ На шаблоне не найдены items для eth1 (in/out) — график пропущен.")


def get_host_graph_ids_by_names(token, hostid, names):
    """
    Возвращает словарь {имя_графика: graphid} для заданного хоста.
    """
    r = call_api("graph.get", {
        "hostids": [hostid],
        "filter": {"name": names},
        "output": ["graphid", "name"]
    }, token)
    found = {g["name"]: g["graphid"] for g in r}
    missing = [n for n in names if n not in found]
    if missing:
        print(f"⚠️  На хосте id={hostid} не найдены графики: {missing}")
    return found


def ensure_dashboard_eth_graphs(token, host_name, dash_name=None, time_period=3600):
    """
    Создаёт/обновляет дашборд с графиками 'Пропускная способность eth0/eth1' для указанного хоста.
    """
    host = get_host_by_name(token, host_name)
    if not host:
        print(f"⚠️  Хост {host_name} не найден — пропускаю создание дашборда.")
        return None

    hostid = host["hostid"]
    if not dash_name:
        dash_name = f"Сетевой мониторинг: {host_name}"

    graph_names = ["Пропускная способность eth0", "Пропускная способность eth1"]
    gmap = get_host_graph_ids_by_names(token, hostid, graph_names)

    widgets = []
    x, y = 0, 0
    cols = 12 if len([gid for gid in gmap.values() if gid]) >= 2 else 24

    for name in graph_names:
        gid = gmap.get(name)
        if not gid:
            continue

        widgets.append({
            "type": "graph-classic",
            "name": name,
            "width": cols,
            "height": 8,
            "x": x,
            "y": y,
            "fields": [
                {"type": 0, "name": "graphid", "value": int(gid)},
                {"type": 0, "name": "timePeriod", "value": int(time_period)}
            ]
        })

        # разложим по сетке 24 колонки
        x = 12 if x == 0 and cols == 12 else 0
        if x == 0:
            y += 8

    if not widgets:
        print("⚠️  Нет ни одного графика eth0/eth1 на хосте — дашборд не создан.")
        return None

    page = {"name": "Network", "widgets": widgets}
    obj = {"name": dash_name, "auto_start": 1, "pages": [page]}

    cur = call_api("dashboard.get", {"filter": {"name": [dash_name]}}, token)
    if cur:
        call_api("dashboard.update", {"dashboardid": cur[0]["dashboardid"], **obj}, token)
        print(f"✅  Дашборд «{dash_name}» успешно обновлён.")
        return cur[0]["dashboardid"]
    else:
        res = call_api("dashboard.create", obj, token)
        dashid = res["dashboardids"][0]
        print(f"\n✅  Дашборд «{dash_name}» успешно создан (id={dashid}).")
        return dashid


def ensure_user_can_see_groups(token, username, hostgroup_ids, permission=3):
    """
    Выдаёт пользователю 'username' права на указанные host groups.
    """
    u = call_api("user.get", {"filter": {"username": [username]}, "selectUsrgrps": "extend"}, token)
    if not u:
        raise RuntimeError(f'Пользователь "{username}" не найден')
    usrgrp_ids = [g["usrgrpid"] for g in u[0].get("usrgrps", [])]

    for ugid in usrgrp_ids:
        g = call_api("usergroup.get", {
            "usrgrpids": [ugid],
            "selectRights": "extend",
            "output": "extend"
        }, token)[0]

        rights_by_id = {r["id"]: int(r["permission"]) for r in g.get("rights", [])}
        changed = False
        for hg in map(str, hostgroup_ids):
            if rights_by_id.get(hg, 0) < permission:
                rights_by_id[hg] = permission
                changed = True

        if changed:
            new_rights = [{"permission": p, "id": hid} for hid, p in rights_by_id.items()]
            call_api("usergroup.update", {"usrgrpid": g["usrgrpid"], "rights": new_rights}, token)


def ensure_snmp_spike_triggers_eth0(token, templateid, mb_per_min=1.0):
    """
    Создает триггеры-аномалии на шаблоне 'New SNMP':
      - входящий трафик eth0 за 1 минуту > mb_per_min
      - исходящий трафик eth0 за 1 минуту > mb_per_min
    """
    # 1 МБ (десятичный) в bps, усреднённый за 1 минуту
    threshold_bps = int(mb_per_min * 8_000_000 / 60)

    name_in  = "Резкий скачок входящего трафика на {HOST.NAME}"
    name_out = "Резкий скачок исходящего трафика на {HOST.NAME}"

    expr_in  = f"avg(/New SNMP/snmp.get[1.3.6.1.2.1.31.1.1.1.6.{{$IFINDEX_ETH0}}],1m)>{threshold_bps}"
    expr_out = f"avg(/New SNMP/snmp.get[1.3.6.1.2.1.31.1.1.1.10.{{$IFINDEX_ETH0}}],1m)>{threshold_bps}"

    ensure_trigger(token, name_in,  expr_in,  priority=4, manual_close=1)
    ensure_trigger(token, name_out, expr_out, priority=4, manual_close=1)


def main():
    """Основная функция запуска для полной настройки Zabbix."""
    wait_for_api(timeout=WAIT_TIMEOUT, interval=WAIT_INTERVAL)  # Ждём, когда API Zabbix будет доступен

    token = wait_for_login(ZBX_USER, ZBX_PASS, timeout=WAIT_TIMEOUT, interval=WAIT_INTERVAL)

    wait_for_write_ready(token, timeout=max(WAIT_TIMEOUT, 900), interval=5)

    # Интерфейс пользователя на русском
    set_user_language(token, ZBX_USER, ZBX_LANG)

    # Создаем хосты webserver1/2/log-srv
    proxyid = ensure_proxy(token, PROXY_NAME, mode=0)
    groupid = ensure_group(token, GROUP_NAME)
    ensure_user_can_see_groups(token, ZBX_USER, [groupid], permission=3)

    for h in HOSTS:
        hid = ensure_host(token, groupid, h["host"], h["dns"], h["port"], h["templates"],
                          proxy_hostid=proxyid if h["host"].startswith("webserver") else None)
        print(f"✅  Хост создан/обновлён: {h['host']} (id={hid})")

    # Для Zabbix server оставляем только шаблон "Zabbix server health"
    ensure_zabbix_server_health_only(token)

    # SNMPv3
    snmp_tpl_id = ensure_template_snmp(token, "New SNMP")
    ensure_snmp_items_and_trigger(token, snmp_tpl_id)
    ensure_snmpv3_interface(token, "webserver1")

    # привязываем наш шаблон к webserver1
    h = get_host_by_name(token, "webserver1")
    cur = {t["templateid"] for t in h.get("parentTemplates", [])}
    cur.add(snmp_tpl_id)
    set_templates_exact(token, h["hostid"], list(cur))

    ensure_template_macro(token, snmp_tpl_id, "{$FORCE_ETH1_PROBLEM}", "0")

    ensure_host_macro(token, h["hostid"], "{$IFINDEX_ETH0}", "2")
    ensure_host_macro(token, h["hostid"], "{$IFINDEX_ETH1}", "3")

    ensure_eth_inout_items_on_template(token, snmp_tpl_id)
    ensure_eth_graphs_on_template(token, snmp_tpl_id)
    ensure_snmp_spike_triggers_eth0(token, snmp_tpl_id, mb_per_min=1.0)

    # Дашборд по графикам eth0/eth1 (наследуются на хост webserver1)
    ensure_dashboard_eth_graphs(token, "webserver1", dash_name="Сетевой мониторинг: webserver1", time_period=3600)

    print("\n✅  SNMPv3 успешно настроен!\n")

    # Создаем элементы данных и триггеры для логов на хосте log-srv
    provision_logs_and_triggers(token)

    # Создаём элементы данных для контейнера с плагинами
    provision_plugin_items(token)

    # Создаем элементы данных CPU и DISK на webserver1/2
    ensure_required_items_for_hosts(token)

    # Создаем триггеры на эти элементы данных CPU и DISK
    ensure_cpu_disk_triggers(token)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        mtid = ensure_telegram_mediatype(token)
        admin = call_api("user.get", {"filter": {"username": [ZBX_USER]}}, token)[0]
        ensure_user_media_telegram(token, admin["userid"], mtid, TELEGRAM_CHAT_ID)
        ensure_trigger_action_telegram(token, "Send problems to Telegram (Linux servers ≥ Warning)", mtid,
                                       admin["userid"], groupid)
        ensure_trigger_action_for_log_triggers(
            token,
            LOG_TRIGGER_ACTION_NAME,
            mtid,
            admin["userid"],
            LOG_TRIGGER_NAMES
        )
        print("✅  Telegram (webhook) успешно установлен!\n")
    else:
        print("⚠️  Пропускаю настройку Telegram: не заданы TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID.")

    print("✅  Готово! Zabbix успешно настроен!")


if __name__ == "__main__":
    main()
