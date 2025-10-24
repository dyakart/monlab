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

LONG_METHODS = {
    "host.create", "host.update", "item.create", "item.update",
    "trigger.create", "trigger.update", "action.create", "action.update",
    "mediatype.create", "mediatype.update", "user.update", "hostinterface.update", "hostinterface.create",
}

ZBX_USER = os.getenv("ZBX_USER")
ZBX_PASS = os.getenv("ZBX_PASS")
ZBX_LANG = os.getenv("ZBX_LANG")

WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", "600"))
WAIT_INTERVAL = int(os.getenv("WAIT_INTERVAL", "5"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver1/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],1m)>0'
    },
    {
        "name": 'Log webserver2',
        "key_": 'logrt["/var/log/remote/webserver2/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip]',
        "delay": "1m",
        "trigger_name": "Trigger for webserver2 logs",
        "trigger_expr": 'count(/log-srv/logrt["/var/log/remote/webserver2/syslog.log","LAB-TEST|ERROR|CRITICAL",,,skip],1m)>0'
    },
]

LOG_TRIGGER_ACTION_NAME = "Send webserver1/2 LOG problems to Telegram"
LOG_TRIGGER_NAMES = [
    "Trigger for webserver1 logs",
    "Trigger for webserver2 logs",
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
            print(f"✅  Успешное подключение к Zabbix API! Версия: {v}")
            return
        except Exception as e:
            last_err = e
            time.sleep(interval)
    raise RuntimeError(f"Zabbix API не поднялся за {timeout}с: {last_err}")


def wait_for_login(user, password, timeout=600, interval=5):
    """Ждет, пока авторизация Zabbix API начнет отвечать (user.login)"""
    print("⌛  Жду ответа от авторизации Zabbix API...")
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            token = login(user, password)
            print("✅  Авторизация Zabbix API готова.")
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
            print("✅  API готов к операциям записи.")
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


def ensure_trigger(token, description, expression, priority=3, manual_close=1):
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
    print('✅  Установлены шаблоны для хоста "Zabbix server": "Zabbix server health".')


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


def ensure_required_items_for_hosts(token, hosts=("webserver1", "webserver2")):
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
        - script: JS-код с POST на `https://api.telegram.org/bot{token}/sendMessage`.
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
        header = (status === 'PROBLEM') ? '⚠️ Событие' : '✅ Восстановление';
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


def ensure_cpu_disk_triggers(token, hosts=("webserver1", "webserver2")):
    """
    Создаёт, если их нет базовые триггеры по CPU и свободному месту на корне для заданных хостов.

    Для каждого хоста добавляет два триггера:
      1) Высокая загрузка CPU: среднее за 5 минут > 85% (`system.cpu.util`).
      2) Мало свободного места на `/`: доля свободного < 10% (`vfs.fs.size[/,pfree]`).

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
        "✅  Элементы данных для контейнера 'monitoring-plugins' для проверки доступности HTTP и размера логов успешно установлены!")


def main():
    """Основная функция запуска для полной настройки Zabbix."""
    wait_for_api(timeout=WAIT_TIMEOUT, interval=WAIT_INTERVAL)  # Ждём, когда API Zabbix будет доступен

    token = wait_for_login(ZBX_USER, ZBX_PASS, timeout=WAIT_TIMEOUT, interval=WAIT_INTERVAL)

    wait_for_write_ready(token, timeout=max(WAIT_TIMEOUT, 900), interval=5)

    # Интерфейс пользователя на русском
    set_user_language(token, ZBX_USER, ZBX_LANG)

    # Создаем хосты webserver1/2/log-srv
    groupid = ensure_group(token, GROUP_NAME)
    for h in HOSTS:
        hid = ensure_host(token, groupid, h["host"], h["dns"], h["port"], h["templates"])
        print(f"✅  Хост создан/обновлён: {h['host']} (id={hid})")

    # Создаем элементы данных и триггеры для логов на хосте log-srv
    provision_logs_and_triggers(token)

    # Для Zabbix server оставляем только шаблон "Zabbix server health"
    ensure_zabbix_server_health_only(token)

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
        print("✅  Telegram (webhook) успешно установлен!")
    else:
        print("⚠️  Пропускаю настройку Telegram: не заданы TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID.")

    print("✅  Готово! Zabbix успешно настроен!")


if __name__ == "__main__":
    main()
