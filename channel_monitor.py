"""
ПРЯМОЙ ПАРСИНГ КАНАЛА - БЕЗ АВТОРИЗАЦИИ!
Использует публичный preview API Telegram
100% РАБОТАЕТ!
"""

import os
import json
import re
import logging
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
CHANNEL_USERNAME = "pat_cherkasyoblenergo"
CHANNEL_URL = f"https://t.me/s/{CHANNEL_USERNAME}"
ADMIN_ID = 815422710
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GH_TOKEN")
GITHUB_REPO = os.environ.get("GH_REPO", "Satanyuga/SvetCherkassy")

DATA_FILE = 'data.json'
PRIORITY_FILE = 'admin_priority.json'
USERS_FILE = 'users.json'
LAST_POST_FILE = 'last_post_id.txt'

UA_MONTHS = {
    'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4,
    'травня': 5, 'червня': 6, 'липня': 7, 'серпня': 8,
    'вересня': 9, 'жовтня': 10, 'листопада': 11, 'грудня': 12
}

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def parse_date_from_message(text):
    current_year = datetime.now().year
    pattern = r'(\d{1,2})\s+(' + '|'.join(UA_MONTHS.keys()) + r')'
    match = re.search(pattern, text.lower())
    
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        month = UA_MONTHS[month_name]
        return f"{day:02d}.{month:02d}.{current_year}"
    return None

def parse_schedule_message(text):
    schedules = {}
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        match = re.match(r'^(\d+\.\d+)\s*:?\s*(.+)$', line)
        if match:
            group = match.group(1).strip()
            schedule_text = match.group(2).strip()
            if re.search(r'\d{1,2}:\d{2}', schedule_text):
                schedules[group] = schedule_text
    
    return schedules


import threading

# ============================================================
# СОСТОЯНИЕ В ОТДЕЛЬНОЙ ВЕТКЕ GITHUB (storage)
# Render пересобирает сервис при каждом коммите в main, а при рестарте
# стирает локальные файлы (очередь пользователей, уведомления, графики).
# Коммиты в ветку storage Render НЕ запускают, поэтому всё сохраняется.
# ============================================================
import hashlib
import base64
from datetime import timedelta

GH_BRANCH = os.environ.get("GH_STORAGE_BRANCH", "storage")
GH_BASE = os.environ.get("GH_BASE_BRANCH", "main")
GH_API = f"https://api.github.com/repos/{GITHUB_REPO}"
STATE_FILES = ['data.json', 'users.json', 'admin_priority.json', 'last_post_id.txt']
GH_LAST_ERROR = None
_gh_lock = threading.Lock()
_gh_branch_ok = False
_gh_hash = {}
_gh_last_alert = 0


def kyiv_now():
    """Текущее время Киева (без часового пояса)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Kiev")).replace(tzinfo=None)
    except Exception:
        u = datetime.utcnow()

        def last_sunday(month):
            d = datetime(u.year, month, 31, 1)
            while d.weekday() != 6:
                d -= timedelta(days=1)
            return d

        return u + timedelta(hours=3 if last_sunday(3) <= u < last_sunday(10) else 2)


def fmt_date(dt):
    return dt.strftime("%d.%m.%Y")


def _gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}


def _gh_fail(msg):
    """Запоминает ошибку и (не чаще раза в 30 минут) сообщает админу."""
    global GH_LAST_ERROR, _gh_last_alert
    GH_LAST_ERROR = msg
    logger.error(f"❌ GitHub: {msg}")
    tok = os.environ.get("BOT_TOKEN")
    if tok and time.time() - _gh_last_alert > 1800:
        _gh_last_alert = time.time()
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": ADMIN_ID, "text": f"⚠️ Не удалось сохранить данные в GitHub:\n{msg}"}, timeout=10)
        except Exception:
            pass
    return False


def gh_ensure_branch():
    """Создаёт ветку storage из main, если её ещё нет."""
    global _gh_branch_ok
    if _gh_branch_ok:
        return True
    if not GITHUB_TOKEN:
        return _gh_fail("GH_TOKEN не задан")
    try:
        r = requests.get(f"{GH_API}/branches/{GH_BRANCH}", headers=_gh_headers(), timeout=10)
        if r.status_code == 200:
            _gh_branch_ok = True
            return True
        if r.status_code != 404:
            return _gh_fail(f"ветка {GH_BRANCH}: {r.status_code}")
        b = requests.get(f"{GH_API}/git/ref/heads/{GH_BASE}", headers=_gh_headers(), timeout=10)
        if b.status_code != 200:
            return _gh_fail(f"нет ветки {GH_BASE}: {b.status_code}")
        c = requests.post(f"{GH_API}/git/refs", headers=_gh_headers(), timeout=10,
                          json={"ref": f"refs/heads/{GH_BRANCH}", "sha": b.json()["object"]["sha"]})
        if c.status_code in (200, 201, 422):  # 422 = уже существует
            _gh_branch_ok = True
            logger.info(f"✅ Ветка {GH_BRANCH} создана")
            return True
        return _gh_fail(f"создание ветки: {c.status_code}")
    except Exception as e:
        return _gh_fail(f"ветка: {e}")


def _gh_put(path, text, message, branch):
    """Один файл в одну ветку. Возвращает True/False."""
    for attempt in range(3):
        try:
            g = requests.get(f"{GH_API}/contents/{path}", params={"ref": branch}, headers=_gh_headers(), timeout=10)
            if g.status_code not in (200, 404):
                return _gh_fail(f"{path} GET {g.status_code}")
            body = {"message": message, "branch": branch,
                    "content": base64.b64encode(text.encode('utf-8')).decode('ascii')}
            if g.status_code == 200:
                body["sha"] = g.json().get("sha")
            p = requests.put(f"{GH_API}/contents/{path}", headers=_gh_headers(), json=body, timeout=20)
            if p.status_code in (200, 201):
                return True
            if p.status_code in (409, 422) and attempt < 2:
                time.sleep(1)
                continue
            return _gh_fail(f"{path} PUT {p.status_code}")
        except Exception as e:
            if attempt == 2:
                return _gh_fail(f"{path}: {e}")
            time.sleep(1)
    return False


def gh_push_text(path, text, message="💾 состояние бота", fallback_main=False):
    """Сохраняет файл в ветку storage. Если содержимое не менялось - ничего не делает.
    fallback_main=True (только для data.json): при сбое storage пишет в main как раньше,
    чтобы график точно дошёл до сайта."""
    global GH_LAST_ERROR
    h = hashlib.md5(text.encode('utf-8')).hexdigest()
    if _gh_hash.get(path) == h:
        return True
    with _gh_lock:
        if gh_ensure_branch() and _gh_put(path, text, message, GH_BRANCH):
            _gh_hash[path] = h
            GH_LAST_ERROR = None
            logger.info(f"✅ GitHub: {path} сохранён")
            return True
        if fallback_main and GITHUB_TOKEN and _gh_put(path, text, message, GH_BASE):
            _gh_hash[path] = h
            logger.warning(f"⚠️ {path} записан в {GH_BASE} (storage недоступна)")
            return True
    return False


def gh_push_file_async(path):
    def _run():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                gh_push_text(path, f.read())
        except Exception as e:
            logger.error(f"❌ GitHub {path}: {e}")
    threading.Thread(target=_run, daemon=True).start()


def gh_pull_all():
    """После рестарта возвращает users.json, data.json и т.д. из ветки storage."""
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GH_TOKEN не задан: очереди пользователей не переживут рестарт")
        return
    for path in STATE_FILES:
        try:
            r = requests.get(f"{GH_API}/contents/{path}", params={"ref": GH_BRANCH}, headers=_gh_headers(), timeout=10)
            if r.status_code != 200:
                continue
            text = base64.b64decode(r.json()["content"]).decode('utf-8')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            _gh_hash[path] = hashlib.md5(text.encode('utf-8')).hexdigest()
            logger.info(f"📥 Восстановлен {path}")
        except Exception as e:
            logger.error(f"❌ Восстановление {path}: {e}")


def record_version(data, date_str, group, sched):
    """Запоминает каждую версию графика и минуту суток, когда она опубликована.
    Статистика сайта: прошедшие минуты - по версии, действовавшей тогда, будущие - по последней."""
    versions = data.setdefault('versions', {}).setdefault(date_str, {}).setdefault(group, [])
    if versions and versions[-1].get('s') == sched:
        return False
    try:
        p = int((kyiv_now() - datetime.strptime(date_str, "%d.%m.%Y")).total_seconds() // 60)
    except Exception:
        p = 0
    versions.append({'p': max(0, min(1440, p)), 's': sched})
    return True


def prune_versions(data, keep_days=4):
    """Удаляет версии старых дат, чтобы data.json не разрастался."""
    versions = data.get('versions')
    if not isinstance(versions, dict):
        return
    limit = kyiv_now() - timedelta(days=keep_days)
    for d in list(versions.keys()):
        try:
            if datetime.strptime(d, "%d.%m.%Y") < limit:
                del versions[d]
        except Exception:
            del versions[d]
# ============================================================


def update_github_file(content):
    """Сохраняет data.json (в ветку storage - это НЕ перезапускает Render)"""
    ok = gh_push_text('data.json', json.dumps(content, ensure_ascii=False, indent=2), "🤖 Автообновление из Обленерго", fallback_main=True)
    if not ok:
        logger.error(f"❌ GitHub: {GH_LAST_ERROR}")
    return ok

def check_admin_priority(date_str):
    """Проверяет приоритет - действует 1 час"""
    priority = load_json(PRIORITY_FILE)
    edited_dates = priority.get('edited_dates', {})
    
    if not isinstance(edited_dates, dict) or date_str not in edited_dates:
        return False
    
    edit_time = edited_dates[date_str]
    hours = (time.time() - edit_time) / 3600
    
    if hours > 1:  # Истек
        logger.info(f"⏰ Приоритет истек ({hours:.1f}ч)")
        return False
    
    logger.info(f"🎯 Приоритет активен ({hours:.1f}ч)")
    return True

def send_telegram(message):
    """Отправка сообщения админу"""
    if not BOT_TOKEN:
        logger.warning("⚠️ BOT_TOKEN не установлен")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": ADMIN_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False

def get_last_post_id():
    try:
        with open(LAST_POST_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def save_last_post_id(post_id):
    try:
        with open(LAST_POST_FILE, 'w') as f:
            f.write(str(post_id))
        gh_push_file_async(LAST_POST_FILE)
    except:
        pass

def fetch_channel_posts():
    """Получаем последние посты из канала"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(CHANNEL_URL, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка загрузки канала: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем посты
        messages = soup.find_all('div', class_='tgme_widget_message')
        
        posts = []
        for msg in messages[-5:]:  # Берем последние 5 постов
            # ID поста
            post_link = msg.get('data-post', '')
            post_id = post_link.split('/')[-1] if post_link else ''
            
            # Текст
            text_div = msg.find('div', class_='tgme_widget_message_text')
            text = text_div.get_text('\n', strip=True) if text_div else ''
            
            if text and post_id:
                posts.append({
                    'id': post_id,
                    'text': text
                })
        
        return posts
    
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга: {e}")
        return []

def process_post(post):
    """Обрабатываем один пост"""
    text = post['text']
    post_id = post['id']
    
    logger.info(f"\n📨 Новый пост ID: {post_id}")
    
    # СНАЧАЛА ПРОВЕРЯЕМ - это график?
    if not re.search(r'(?m)^\s*\d\.\d\s*:?\s*\d{1,2}:\d{2}', text):
        logger.info("⚠️ Это не график (нет строк очередей), пропускаю")
        return False  # НЕ ПИШЕМ АДМИНУ!
    
    # Парсим дату
    date_str = parse_date_from_message(text)
    if not date_str:
        logger.warning("⚠️ Дата не распознана")
        send_telegram("⚠️ Не могу распознать дату в посте!")
        return False
    
    logger.info(f"📅 Дата: {date_str}")
    
    # Если такой график уже в data.json - ничего не делаем (рестарт Render стирает last_post_id.txt)
    _new = parse_schedule_message(text)
    _cur = load_json(DATA_FILE).get('dates', {}).get(date_str, {})
    if _new and all(_cur.get(g) == v for g, v in _new.items()):
        logger.info("ℹ️ График не изменился, пропускаю")
        return False
    
    # Проверяем приоритет
    if check_admin_priority(date_str):
        logger.info(f"⚠️ Приоритет админа - игнорируем Обленерго")
        send_telegram(
            f"⚠️ График на <b>{date_str}</b> УЖЕ установлен ВАМИ.\n\n"
            f"Обленерго игнорируется."
        )
        return False
    
    # ТОЛЬКО ТЕПЕРЬ пишем админу
    send_telegram(
        f"📡 <b>НОВЫЙ ГРАФИК ИЗ ОБЛЕНЕРГО</b>\n\n"
        f"ID поста: {post_id}\n"
        f"Парсю график..."
    )
    
    # Парсим графики
    schedules = parse_schedule_message(text)
    if not schedules:
        logger.warning("⚠️ Графики не распознаны")
        send_telegram(f"⚠️ Не могу распознать графики для {date_str}!")
        return False
    
    logger.info(f"📋 Распознано: {len(schedules)} очередей")
    
    # Обновляем данные
    data = load_json(DATA_FILE)
    if not isinstance(data, dict) or 'dates' not in data:
        data = {'dates': {}}
    
    if date_str not in data['dates']:
        data['dates'][date_str] = {}
    
    updated_groups = []
    for group, schedule in schedules.items():
        data['dates'][date_str][group] = schedule
        # версия графика + минута публикации (для статистики за сутки)
        record_version(data, date_str, group, schedule)
        updated_groups.append(group)
    
    prune_versions(data)
    
    if save_json(DATA_FILE, data):
        logger.info(f"✅ ГРАФИКИ ОБНОВЛЕНЫ!")
        
        github_ok = update_github_file(data)
        
        # Получаем очередь админа
        users = load_json('users.json')
        admin_group = users.get(str(ADMIN_ID), {}).get('group', '4.1') or '4.1'
        admin_schedule = data['dates'].get(date_str, {}).get(admin_group, 'График не найден')
        
        # СООБЩЕНИЕ АДМИНУ
        send_telegram(
            f"✅ <b>ГРАФИК ОБНОВЛЕН ИЗ ОБЛЕНЕРГО!</b>\n\n"
            f"📅 Дата: <b>{date_str}</b>\n"
            f"📋 Очереди ({len(updated_groups)}): {', '.join(sorted(updated_groups))}\n"
            f"🌐 GitHub: {'✅ Обновлен' if github_ok else '❌ ' + str(GH_LAST_ERROR)[:150]}\n\n"
            f"📡 Источник: @{CHANNEL_USERNAME}\n"
            f"🆔 Пост: {post_id}\n\n"
            f"<b>⚡ Ваша очередь {admin_group}:</b>\n{admin_schedule}"
        )
        
        # УВЕДОМЛЕНИЯ ВСЕМ ПОЛЬЗОВАТЕЛЯМ
        notified_count = 0
        for uid_str, user_data in users.items():
            user_group = user_data.get('group')
            
            if not user_group or user_group not in updated_groups:
                continue
            
            if int(uid_str) == ADMIN_ID:
                continue  # Админу уже отправили
            
            try:
                user_schedule = data['dates'].get(date_str, {}).get(user_group, 'График не найден')
                
                notification = (
                    f"🔔 <b>ВАШ ГРАФИК ИЗМЕНИЛСЯ!</b>\n\n"
                    f"📍 Очередь: <b>{user_group}</b>\n"
                    f"📅 График на <b>{date_str}</b>\n\n"
                    f"⚡ <b>Отключения:</b>\n{user_schedule}"
                )
                
                # Отправляем через бота
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": int(uid_str),
                    "text": notification,
                    "parse_mode": "HTML"
                }
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    notified_count += 1
                else:
                    logger.error(f"Не доставлено {uid_str}: {resp.status_code}")
                time.sleep(0.05)  # Чтобы не спамить API
                
            except Exception as e:
                logger.error(f"Ошибка отправки {uid_str}: {e}")
        
        logger.info(f"📊 Уведомлено пользователей: {notified_count}")
        send_telegram(f"📊 Уведомлено пользователей: {notified_count}")
        
        return True
    
    return False

def check_updates():
    """Проверяем обновления в канале"""
    logger.info("🔍 Проверка канала...")
    
    posts = fetch_channel_posts()
    if not posts:
        logger.warning("⚠️ Не удалось загрузить посты")
        return
    
    logger.info(f"📰 Найдено постов: {len(posts)}")
    
    last_id = get_last_post_id()
    
    if last_id is None:
        # Первый запуск: берем только самый свежий пост с графиком
        graph = [p for p in posts if re.search(r'(?m)^\s*\d\.\d\s*:?\s*\d{1,2}:\d{2}', p['text'])]
        new_posts = graph[-1:] if graph else []
        if not new_posts:
            save_last_post_id(posts[-1]['id'])
            return
    else:
        new_posts = [p for p in posts if int(p['id']) > int(last_id)]
    
    if not new_posts:
        logger.info("ℹ️ Новых постов нет")
        return
    
    for post in new_posts:
        logger.info(f"🆕 НОВЫЙ ПОСТ: {post['id']}")
        process_post(post)
        save_last_post_id(post['id'])

def main():
    logger.info("\n" + "="*60)
    logger.info("🚀 ПАРСЕР КАНАЛА ОБЛЕНЕРГО")
    logger.info("="*60)
    logger.info(f"📢 Канал: @{CHANNEL_USERNAME}")
    logger.info(f"🌐 URL: {CHANNEL_URL}")
    logger.info(f"⏱️ Проверка каждые 3 минуты")
    logger.info("="*60 + "\n")
    
    # Возвращаем users.json, data.json, last_post_id.txt после рестарта
    gh_pull_all()
    
    # Уведомляем о запуске
    send_telegram(
        f"🚀 <b>ПАРСЕР ЗАПУЩЕН!</b>\n\n"
        f"📡 Канал: @{CHANNEL_USERNAME}\n"
        f"⏱️ Проверка каждые 3 минуты\n\n"
        f"Работает БЕЗ авторизации через публичный API!"
    )
    
    while True:
        try:
            check_updates()
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            send_telegram(f"⚠️ Ошибка парсера: {str(e)[:100]}")
        
        # Проверяем каждые 3 минуты
        logger.info("💤 Ожидание 3 минуты...")
        time.sleep(180)

if __name__ == '__main__':
    main()
