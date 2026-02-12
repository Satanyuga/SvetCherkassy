"""
UserBot для автоматического парсинга графиков из канала
https://t.me/pat_cherkasyoblenergo
"""

import os
import json
import re
import logging
from datetime import datetime
from telethon import TelegramClient, events
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")
CHANNEL_USERNAME = "pat_cherkasyoblenergo"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 815422710
GITHUB_TOKEN = os.environ.get("GH_TOKEN")
GITHUB_REPO = os.environ.get("GH_REPO", "Satanyuga/SvetCherkassy")

DATA_FILE = 'data.json'
PRIORITY_FILE = 'admin_priority.json'  # Отслеживаем что редактировал админ

# Украинские месяцы
UA_MONTHS = {
    'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4,
    'травня': 5, 'червня': 6, 'липня': 7, 'серпня': 8,
    'вересня': 9, 'жовтня': 10, 'листопада': 11, 'грудня': 12
}

client = TelegramClient('userbot_session', API_ID, API_HASH)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")
        return False

def parse_date_from_message(text):
    """Парсит дату из украинского текста"""
    current_year = datetime.now().year
    pattern = r'(\d{1,2})\s+(' + '|'.join(UA_MONTHS.keys()) + r')'
    match = re.search(pattern, text.lower())
    
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        month = UA_MONTHS[month_name]
        date_str = f"{day:02d}.{month:02d}.{current_year}"
        logger.info(f"📅 Распознана дата: {date_str}")
        return date_str
    
    return None

def parse_schedule_message(text):
    """Парсит графики из сообщения"""
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
                logger.info(f"📋 Распознана очередь {group}")
    
    return schedules

def update_github_file(content):
    """Обновляет data.json на GitHub"""
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GH_TOKEN не установлен")
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
            "message": "🤖 Автообновление из канала",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data, timeout=15)
        
        if response.status_code in [200, 201]:
            logger.info("✅ GitHub обновлен")
            return True
        else:
            logger.error(f"❌ Ошибка GitHub: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка GitHub: {e}")
        return False

def check_admin_priority(date_str):
    """Проверяет редактировал ли админ график на эту дату"""
    priority = load_json(PRIORITY_FILE)
    return date_str in priority.get('edited_dates', [])

def mark_admin_edit(date_str):
    """Отмечает что админ редактировал график на эту дату"""
    priority = load_json(PRIORITY_FILE)
    if 'edited_dates' not in priority:
        priority['edited_dates'] = []
    
    if date_str not in priority['edited_dates']:
        priority['edited_dates'].append(date_str)
        save_json(PRIORITY_FILE, priority)
        logger.info(f"📝 Админ отредактировал дату: {date_str}")

def process_channel_message(text):
    """Обрабатывает сообщение из канала"""
    logger.info("\n📨 Получено сообщение из канала")
    
    # Парсим дату
    date_str = parse_date_from_message(text)
    if not date_str:
        logger.warning("⚠️ Дата не распознана")
        return False
    
    # Проверяем приоритет админа
    if check_admin_priority(date_str):
        logger.info(f"⚠️ График на {date_str} отредактирован админом - игнорируем канал")
        return False
    
    # Парсим графики
    schedules = parse_schedule_message(text)
    if not schedules:
        logger.warning("⚠️ Графики не распознаны")
        return False
    
    # Загружаем текущие данные
    data = load_json(DATA_FILE)
    
    if not isinstance(data, dict) or 'dates' not in data:
        data = {'dates': {}}
    
    if date_str not in data['dates']:
        data['dates'][date_str] = {}
    
    # Обновляем графики
    updated_groups = []
    for group, schedule in schedules.items():
        data['dates'][date_str][group] = schedule
        updated_groups.append(group)
    
    # Сохраняем
    if save_json(DATA_FILE, data):
        logger.info(f"✅ Обновлены очереди для {date_str}: {', '.join(updated_groups)}")
        
        # Обновляем GitHub
        update_github_file(data)
        
        return True
    
    return False

# --- ОБРАБОТЧИКИ СОБЫТИЙ ---
@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def channel_handler(event):
    """Обработчик новых сообщений в канале"""
    text = event.message.message
    
    # Проверяем что это похоже на график
    if 'графік' in text.lower() or 'години відсутності' in text.lower():
        logger.info("🔍 Обнаружено сообщение с графиком")
        process_channel_message(text)

@client.on(events.NewMessage(from_users=ADMIN_ID))
async def admin_handler(event):
    """Обработчик сообщений от админа"""
    text = event.message.message
    
    # Парсим дату
    date_str = parse_date_from_message(text)
    if not date_str:
        return
    
    # Парсим графики
    schedules = parse_schedule_message(text)
    if not schedules:
        return
    
    logger.info(f"\n📨 Админ отправил график на {date_str}")
    
    # Отмечаем приоритет
    mark_admin_edit(date_str)
    
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
        logger.info(f"✅ Админ обновил очереди: {', '.join(updated_groups)}")
        update_github_file(data)
        
        # Отправляем подтверждение админу
        await event.reply(
            f"✅ ГРАФИК ОБНОВЛЕН на {date_str}\n\n"
            f"📋 Очереди: {', '.join(sorted(updated_groups))}\n"
            f"🎯 Приоритет: АДМИН (канал будет игнорироваться)"
        )

async def main():
    """Главная функция"""
    logger.info("🚀 Запуск UserBot")
    logger.info(f"📢 Мониторинг канала: {CHANNEL_USERNAME}")
    logger.info(f"👤 Админ ID: {ADMIN_ID}")
    
    await client.start()
    logger.info("✅ UserBot запущен")
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
