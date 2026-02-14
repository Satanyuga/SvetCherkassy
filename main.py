import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory, request
from telebot import TeleBot, types
import re
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Украинские месяцы для парсинга
UA_MONTHS = {
    'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4,
    'травня': 5, 'червня': 6, 'липня': 7, 'серпня': 8,
    'вересня': 9, 'жовтня': 10, 'листопада': 11, 'грудня': 12
}

# --- КОНФИГУРАЦИЯ ---
ADMIN_ID = 815422710  
TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GH_TOKEN")
GITHUB_REPO = os.environ.get("GH_REPO", "Satanyuga/SvetCherkassy")
APP_URL = "https://svetcherkassy.onrender.com" 

app = Flask(__name__)
DATA_FILE = 'data.json'
USERS_FILE = 'users.json'
PRIORITY_FILE = 'admin_priority.json'

bot = TeleBot(TOKEN, threaded=False) if TOKEN else None

# --- ПАРСИНГ ДАТЫ ---
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

# --- АВТОПИНГ ---
def keep_alive():
    """Пингует сам себя каждые 5 минут"""
    while True:
        try:
            time.sleep(300)
            requests.get(f"{APP_URL}/ping", timeout=10)
            logger.info("🏓 Автопинг")
        except Exception as e:
            logger.error(f"❌ Автопинг: {e}")

# --- ФАЙЛЫ ---
def load_json(filename):
    if not os.path.exists(filename): 
        return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f: 
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Загрузка {filename}: {e}")
        return {}

def save_json(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Сохранено {filename}")
        return True
    except Exception as e:
        logger.error(f"❌ Сохранение {filename}: {e}")
        return False

def update_github_file(content):
    """Обновляет data.json на GitHub"""
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GH_TOKEN не установлен")
        return False
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        sha = response.json().get("sha") if response.status_code == 200 else None
        
        import base64
        content_bytes = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        content_b64 = base64.b64encode(content_bytes).decode('utf-8')
        
        data = {
            "message": "🔄 Обновление графиков",
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
            logger.error(f"❌ GitHub: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ GitHub: {e}")
        return False

def mark_admin_edit(date_str):
    """Отмечает приоритет админа"""
    priority = load_json(PRIORITY_FILE)
    if 'edited_dates' not in priority:
        priority['edited_dates'] = []
    
    if date_str not in priority['edited_dates']:
        priority['edited_dates'].append(date_str)
        save_json(PRIORITY_FILE, priority)
        logger.info(f"📝 Приоритет админа: {date_str}")

# --- ПАРСИНГ ГРАФИКА ---
def parse_schedule_message(text):
    """Парсит графики"""
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
                logger.info(f"📋 Очередь {group}")
    
    return schedules

# --- МЕНЮ ---
def get_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    is_on = u_data.get('notif_15', False)
    
    notif_text = f"🔔 Уведомлять о изменениях: {'✅ ВКЛ' if is_on else '❌ ВЫКЛ'}"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(notif_text)
    return markup

if bot:
    # --- ПЕРЕСЫЛКА ИЗ КАНАЛА ---
    @bot.message_handler(content_types=['text'], func=lambda m: m.from_user.id == ADMIN_ID and m.forward_from_chat is not None)
    def forward_handler(message):
        """Обработка пересылок из канала"""
        text = message.text
        if not text:
            return
        
        logger.info(f"\n📨 Пересылка из {message.forward_from_chat.title if message.forward_from_chat else 'канала'}")
        
        date_str = parse_date_from_message(text)
        if not date_str:
            bot.reply_to(message, "⚠️ Дата не распознана")
            return
        
        # Проверка приоритета
        priority = load_json(PRIORITY_FILE)
        if date_str in priority.get('edited_dates', []):
            bot.reply_to(message, 
                f"⚠️ График на {date_str} УЖЕ отредактирован вами.\n"
                f"Пересылка игнорируется."
            )
            return
        
        parsed_schedules = parse_schedule_message(text)
        
        if not parsed_schedules:
            bot.reply_to(message, "⚠️ Графики не распознаны")
            return
        
        data = load_json(DATA_FILE)
        
        if not isinstance(data, dict) or 'dates' not in data:
            data = {'dates': {}}
        
        if date_str not in data['dates']:
            data['dates'][date_str] = {}
        
        updated_groups = []
        for group, schedule in parsed_schedules.items():
            data['dates'][date_str][group] = schedule
            updated_groups.append(group)
        
        if save_json(DATA_FILE, data):
            logger.info(f"✅ Из канала: {', '.join(updated_groups)}")
            
            github_success = update_github_file(data)
            
            bot.reply_to(message, 
                f"✅ ИЗ КАНАЛА на {date_str}\n\n"
                f"📋 Очереди: {', '.join(sorted(updated_groups))}\n"
                f"🌐 GitHub: {'✅' if github_success else '❌'}\n\n"
                f"ℹ️ БЕЗ приоритета админа"
            )
            
            # Уведомления
            users = load_json(USERS_FILE)
            notified_count = 0
            
            for uid_str, u_data in users.items():
                user_group = u_data.get('group')
                
                if user_group in updated_groups:
                    try:
                        schedule_text = data['dates'][date_str][user_group]
                        notification = f"🔔 ГРАФИК ОБНОВЛЕН на {date_str}\n\n"
                        notification += f"📍 Очередь: {user_group}\n\n"
                        notification += f"⚡ Отключения:\n{schedule_text}"
                        
                        bot.send_message(int(uid_str), notification)
                        notified_count += 1
                        time.sleep(0.05)
                    except:
                        pass
            
            bot.send_message(ADMIN_ID, f"📊 Уведомлено: {notified_count}")

    # --- АДМИН ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_logic(message):
        text = message.text
        if not text: 
            return

        if "Моя очередь" in text or "Уведомлять о изменениях" in text:
            user_logic(message)
            return

        logger.info(f"\n📨 Админ (ID {ADMIN_ID})")
        
        date_str = parse_date_from_message(text)
        if not date_str:
            logger.warning("⚠️ Дата не распознана")
            bot.reply_to(message, "⚠️ Дата не распознана.\nУкажите: '12 лютого'")
            return
        
        parsed_schedules = parse_schedule_message(text)
        
        if not parsed_schedules:
            bot.reply_to(message, "⚠️ Графики не распознаны.\n\nФормат:\n1.1: 01:00 – 04:30")
            logger.warning("❌ Графики не распознаны")
            return
        
        data = load_json(DATA_FILE)
        
        if not isinstance(data, dict) or 'dates' not in data:
            data = {'dates': {}}
        
        if date_str not in data['dates']:
            data['dates'][date_str] = {}
        
        updated_groups = []
        
        for group, schedule in parsed_schedules.items():
            data['dates'][date_str][group] = schedule
            updated_groups.append(group)
        
        if save_json(DATA_FILE, data):
            logger.info(f"✅ Обновлено: {', '.join(updated_groups)}")
            
            # ПРИОРИТЕТ
            mark_admin_edit(date_str)
            
            github_success = update_github_file(data)
            
            confirmation = f"✅ ГРАФИК ОБНОВЛЕН на {date_str}\n\n"
            confirmation += f"📋 Очереди: {', '.join(sorted(updated_groups))}\n"
            confirmation += f"🌐 GitHub: {'✅' if github_success else '❌'}\n"
            confirmation += f"🎯 Приоритет: АДМИН\n\n"
            
            bot.reply_to(message, confirmation)
            
            users = load_json(USERS_FILE)
            notified_count = 0
            
            for uid_str, u_data in users.items():
                user_group = u_data.get('group')
                
                if user_group in updated_groups:
                    try:
                        schedule_text = data['dates'][date_str][user_group]
                        notification = f"🔔 ГРАФИК ОБНОВЛЕН на {date_str}\n\n"
                        notification += f"📍 Очередь: {user_group}\n\n"
                        notification += f"⚡ Отключения:\n{schedule_text}"
                        
                        bot.send_message(int(uid_str), notification)
                        notified_count += 1
                        logger.info(f"✅ Уведомление {uid_str}")
                        time.sleep(0.05)
                    except Exception as e:
                        logger.error(f"❌ Ошибка {uid_str}: {e}")
            
            report = f"📊 Уведомлено: {notified_count}"
            bot.send_message(ADMIN_ID, report)
            logger.info(f"\n✅ Готово: {notified_count} уведомлений")
        else:
            bot.reply_to(message, "❌ Ошибка сохранения")

    # --- ЮЗЕРЫ ---
    @bot.message_handler(commands=['start'])
    def start(message):
        uid = str(message.from_user.id)
        users = load_json(USERS_FILE)
        
        if uid not in users:
            users[uid] = {'group': None, 'notif_15': False}
            save_json(USERS_FILE, users)
        
        welcome = "⚡ Добро пожаловать!\n\nВыберите очередь через меню."
        bot.send_message(message.chat.id, welcome, reply_markup=get_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def user_logic(message):
        uid = str(message.from_user.id)
        msg_text = message.text

        if "Моя очередь" in msg_text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выберите очередь:", reply_markup=markup)
            
        elif "Уведомлять о изменениях" in msg_text:
            users = load_json(USERS_FILE)
            if uid not in users: 
                users[uid] = {'group': None, 'notif_15': False}
            
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            
            status = "ВКЛЮЧЕНЫ ✅" if users[uid]['notif_15'] else "ВЫКЛЮЧЕНЫ ❌"
            bot.send_message(message.chat.id, f"🔔 Уведомления {status}", reply_markup=get_menu(uid))
        else:
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "⛔ Используйте меню")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_handler(call):
        group = call.data.replace("set_g_", "")
        uid = str(call.from_user.id)
        users = load_json(USERS_FILE)
        
        if uid not in users: 
            users[uid] = {'group': None, 'notif_15': False}
            
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        
        bot.answer_callback_query(call.id, f"✅ Очередь {group}")
        bot.edit_message_text(f"✅ Очередь: {group}", call.message.chat.id, call.message.message_id)
        
        data = load_json(DATA_FILE)
        today = datetime.now().strftime("%d.%m.%Y")
        
        schedule = "График не установлен"
        if isinstance(data, dict) and 'dates' in data:
            if today in data['dates'] and group in data['dates'][today]:
                schedule = data['dates'][today][group]
        
        info = f"📍 Очередь: {group}\n📅 График на {today}\n\n⚡ Отключения:\n{schedule}"
        bot.send_message(call.message.chat.id, info, reply_markup=get_menu(uid))

# --- ЗАПУСК БОТА ---
def setup_webhook():
    """Настройка webhook вместо polling"""
    if not bot:
        logger.error("❌ Бот не создан")
        return
    
    try:
        # Удаляем старый webhook
        bot.remove_webhook()
        time.sleep(1)
        
        # Устанавливаем новый webhook
        webhook_url = f"{APP_URL}/webhook/{TOKEN}"
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}")

# --- WEB ---
@app.route('/')
def index(): 
    return send_from_directory('.', 'index.html')

@app.route('/data.json')
def get_data(): 
    return jsonify(load_json(DATA_FILE))

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js')

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    """Обработчик webhook от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403

@app.route('/ping')
def ping(): 
    return "PONG"

@app.route('/status')
def status():
    data = load_json(DATA_FILE)
    users = load_json(USERS_FILE)
    
    return jsonify({
        "schedules_count": len(data),
        "users_count": len(users),
        "github_token_set": bool(GITHUB_TOKEN),
        "bot_token_set": bool(TOKEN)
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ЗАПУСК")
    print("="*60)
    print(f"✅ BOT_TOKEN: {'Да' if TOKEN else '❌'}")
    print(f"✅ GH_TOKEN: {'Да' if GITHUB_TOKEN else '⚠️'}")
    print(f"✅ ADMIN_ID: {ADMIN_ID}")
    print("="*60 + "\n")
    
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    logger.info("🏓 Автопинг активирован")
    
    # WEBHOOK вместо polling!
    if bot:
        setup_webhook()
    
    logger.info("🌐 Запуск веб-сервера")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
