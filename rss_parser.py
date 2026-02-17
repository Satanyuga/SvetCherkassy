import os
import json
import re
import logging
import requests
import time
from datetime import datetime
from xml.etree import ElementTree as ET

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
CHANNEL_USERNAME = "pat_cherkasyoblenergo"
RSS_URL = f"https://rsshub.app/telegram/channel/{CHANNEL_USERNAME}"
ADMIN_ID = 815422710
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GH_TOKEN")
GITHUB_REPO = os.environ.get("GH_REPO", "Satanyuga/SvetCherkassy")

DATA_FILE = 'data.json'
PRIORITY_FILE = 'admin_priority.json'
LAST_CHECK_FILE = 'last_rss_check.txt'

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

def update_github_file(content):
    if not GITHUB_TOKEN:
        return False
    
    try:
        import base64
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        sha = response.json().get("sha") if response.status_code == 200 else None
        
        content_bytes = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        content_b64 = base64.b64encode(content_bytes).decode('utf-8')
        
        data = {
            "message": "🤖 Автообновление из канала (RSS)",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data, timeout=15)
        return response.status_code in [200, 201]
    except:
        return False

def check_admin_priority(date_str):
    priority = load_json(PRIORITY_FILE)
    return date_str in priority.get('edited_dates', [])

def notify_admin(message):
    if not BOT_TOKEN:
        return
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": ADMIN_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=data, timeout=10)
    except:
        pass

def get_last_check_time():
    """Получаем время последней проверки"""
    try:
        with open(LAST_CHECK_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def save_last_check_time(time_str):
    """Сохраняем время последней проверки"""
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(time_str)
    except:
        pass

def fetch_rss():
    """Получаем RSS ленту канала"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(RSS_URL, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"RSS ошибка: {response.status_code}")
            return []
        
        # Парсим XML
        root = ET.fromstring(response.content)
        items = []
        
        for item in root.findall('.//item'):
            title = item.find('title')
            description = item.find('description')
            pubDate = item.find('pubDate')
            
            if description is not None:
                items.append({
                    'text': description.text or '',
                    'date': pubDate.text if pubDate is not None else '',
                    'title': title.text if title is not None else ''
                })
        
        return items
    
    except Exception as e:
        logger.error(f"Ошибка RSS: {e}")
        return []

def process_rss_item(item):
    """Обрабатываем одно сообщение из RSS"""
    text = item['text']
    
    # Убираем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    logger.info(f"\n📨 Новое сообщение")
    logger.info(f"Первые 200 символов: {text[:200]}...")
    
    # Проверяем что это график
    if '1.1:' not in text:
        logger.info("⚠️ Это не график")
        return False
    
    # Парсим дату
    date_str = parse_date_from_message(text)
    if not date_str:
        logger.warning("⚠️ Дата не распознана")
        return False
    
    logger.info(f"📅 Дата: {date_str}")
    
    # Проверяем приоритет
    if check_admin_priority(date_str):
        logger.info(f"⚠️ Приоритет админа - игнорируем")
        return False
    
    # Парсим графики
    schedules = parse_schedule_message(text)
    if not schedules:
        logger.warning("⚠️ Графики не распознаны")
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
        updated_groups.append(group)
    
    if save_json(DATA_FILE, data):
        logger.info(f"✅ Обновлены очереди для {date_str}")
        
        github_ok = update_github_file(data)
        
        notify_admin(
            f"✅ <b>ГРАФИК АВТООБНОВЛЕН</b>\n\n"
            f"📅 Дата: <b>{date_str}</b>\n"
            f"📋 Очереди: {', '.join(sorted(updated_groups))}\n"
            f"🌐 GitHub: {'✅' if github_ok else '❌'}\n"
            f"📡 Источник: RSS канала"
        )
        
        return True
    
    return False

def check_updates():
    """Проверяем обновления в канале"""
    logger.info("🔍 Проверка RSS...")
    
    items = fetch_rss()
    if not items:
        logger.warning("⚠️ RSS пустой или недоступен")
        return
    
    logger.info(f"📰 Получено {len(items)} сообщений")
    
    # Берем только самое новое
    latest = items[0] if items else None
    if not latest:
        return
    
    # Проверяем не обрабатывали ли мы его уже
    last_check = get_last_check_time()
    if last_check == latest['date']:
        logger.info("ℹ️ Новых сообщений нет")
        return
    
    # Обрабатываем
    if process_rss_item(latest):
        save_last_check_time(latest['date'])
        logger.info("✅ Обновление применено")
    else:
        # Даже если не обработали, сохраняем чтоб не спамить
        save_last_check_time(latest['date'])

def main():
    logger.info("\n" + "="*60)
    logger.info("🚀 RSS ПАРСЕР КАНАЛА")
    logger.info("="*60)
    logger.info(f"📢 Канал: {CHANNEL_USERNAME}")
    logger.info(f"📡 RSS: {RSS_URL}")
    logger.info(f"⏱️ Проверка каждые 5 минут")
    logger.info("="*60 + "\n")
    
    notify_admin(
        f"✅ <b>RSS Парсер запущен!</b>\n\n"
        f"📡 Канал: @{CHANNEL_USERNAME}\n"
        f"⏱️ Проверка каждые 5 минут\n\n"
        f"Работает БЕЗ авторизации!"
    )
    
    while True:
        try:
            check_updates()
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
        
        # Проверяем каждые 5 минут
        time.sleep(300)

if __name__ == '__main__':
    main()
