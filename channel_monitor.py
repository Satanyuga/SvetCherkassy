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

def update_github_file(content):
    if not GITHUB_TOKEN:
        logger.error("❌ GH_TOKEN не установлен!")
        return False
    
    try:
        import base64
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ GitHub GET ошибка: {response.status_code} - {response.text[:200]}")
            return False
        
        sha = response.json().get("sha")
        
        content_bytes = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        content_b64 = base64.b64encode(content_bytes).decode('utf-8')
        
        data = {
            "message": "🤖 Автообновление из Обленерго",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data, timeout=15)
        
        if response.status_code not in [200, 201]:
            logger.error(f"❌ GitHub PUT ошибка: {response.status_code} - {response.text[:200]}")
            return False
        
        logger.info("✅ GitHub обновлен успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ GitHub исключение: {e}")
        return False

def check_admin_priority(date_str):
    """Проверяет приоритет - действует 1 час"""
    priority = load_json(PRIORITY_FILE)
    edited_dates = priority.get('edited_dates', {})
    
    if date_str not in edited_dates:
        return False
    
    import time
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
    if '1.1:' not in text:
        logger.info("⚠️ Это не график (нет '1.1:'), пропускаю")
        return False  # НЕ ПИШЕМ АДМИНУ!
    
    # ТОЛЬКО ТЕПЕРЬ пишем админу
    send_telegram(
        f"📡 <b>НОВЫЙ ГРАФИК ИЗ ОБЛЕНЕРГО</b>\n\n"
        f"ID поста: {post_id}\n"
        f"Парсю график..."
    )
    
    # Парсим дату
    date_str = parse_date_from_message(text)
    if not date_str:
        logger.warning("⚠️ Дата не распознана")
        send_telegram("⚠️ Не могу распознать дату в посте!")
        return False
    
    logger.info(f"📅 Дата: {date_str}")
    
    # Проверяем приоритет
    if check_admin_priority(date_str):
        logger.info(f"⚠️ Приоритет админа - игнорируем Обленерго")
        send_telegram(
            f"⚠️ График на <b>{date_str}</b> УЖЕ установлен ВАМИ.\n\n"
            f"Обленерго игнорируется."
        )
        return False
    
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
        updated_groups.append(group)
    
    if save_json(DATA_FILE, data):
        logger.info(f"✅ ГРАФИКИ ОБНОВЛЕНЫ!")
        
        github_ok = update_github_file(data)
        
        # Получаем очередь админа
        users = load_json('users.json')
        admin_group = users.get(str(ADMIN_ID), {}).get('group', '4.1') or '4.1'
        admin_schedule = data['dates'].get(date_str, {}).get(admin_group, 'График не найден')
        
        # СООБЩЕНИЕ АДМИНУ #2 - График обновлен
        send_telegram(
            f"✅ <b>ГРАФИК ОБНОВЛЕН ИЗ ОБЛЕНЕРГО!</b>\n\n"
            f"📅 Дата: <b>{date_str}</b>\n"
            f"📋 Очереди ({len(updated_groups)}): {', '.join(sorted(updated_groups))}\n"
            f"🌐 GitHub: {'✅ Обновлен' if github_ok else '❌ Ошибка'}\n\n"
            f"📡 Источник: @{CHANNEL_USERNAME}\n"
            f"🆔 Пост: {post_id}\n\n"
            f"<b>⚡ Ваша очередь {admin_group}:</b>\n{admin_schedule}"
        )
        
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
    
    # Берем последний пост
    latest = posts[-1] if posts else None
    if not latest:
        return
    
    # Проверяем не обрабатывали ли
    last_id = get_last_post_id()
    if last_id == latest['id']:
        logger.info("ℹ️ Новых постов нет")
        return
    
    logger.info(f"🆕 НОВЫЙ ПОСТ: {latest['id']}")
    
    # Обрабатываем
    if process_post(latest):
        save_last_post_id(latest['id'])
        logger.info("✅ Обновление применено")
    else:
        # Сохраняем ID чтоб не спамить
        save_last_post_id(latest['id'])

def main():
    logger.info("\n" + "="*60)
    logger.info("🚀 ПАРСЕР КАНАЛА ОБЛЕНЕРГО")
    logger.info("="*60)
    logger.info(f"📢 Канал: @{CHANNEL_USERNAME}")
    logger.info(f"🌐 URL: {CHANNEL_URL}")
    logger.info(f"⏱️ Проверка каждые 3 минуты")
    logger.info("="*60 + "\n")
    
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
