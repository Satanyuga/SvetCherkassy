import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
ADMIN_ID = 815422710  
TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "Satanyuga/SvetCherkassy"
APP_URL = "https://svetcherkassy.onrender.com" 

app = Flask(__name__)
DATA_FILE = 'data.json'
USERS_FILE = 'users.json'

bot = TeleBot(TOKEN, threaded=False) if TOKEN else None

# --- АВТОПИНГ (КАК В ТВОЕМ index.js) ---
def keep_alive():
    """Пингует сам себя каждые 5 минут чтобы Render не уснул"""
    while True:
        try:
            time.sleep(300)  # 5 минут
            requests.get(f"{APP_URL}/ping", timeout=10)
            logger.info("🏓 Автопинг выполнен")
        except Exception as e:
            logger.error(f"❌ Ошибка автопинга: {e}")

# --- ФАЙЛЫ ---
def load_json(filename):
    if not os.path.exists(filename): 
        return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f: 
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки {filename}: {e}")
        return {}

def save_json(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Сохранено в {filename}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения {filename}: {e}")
        return False

def update_github_file(content):
    """Обновляет data.json на GitHub для отображения на сайте"""
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GITHUB_TOKEN не установлен - файл не обновится на сайте!")
        return False
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Получаем SHA текущего файла
        response = requests.get(url, headers=headers, timeout=10)
        sha = response.json().get("sha") if response.status_code == 200 else None
        
        # Кодируем содержимое в base64
        import base64
        content_bytes = json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        content_b64 = base64.b64encode(content_bytes).decode('utf-8')
        
        # Отправляем на GitHub
        data = {
            "message": "🔄 Обновление графиков от бота",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data, timeout=15)
        
        if response.status_code in [200, 201]:
            logger.info("✅ data.json обновлен на GitHub!")
            return True
        else:
            logger.error(f"❌ Ошибка GitHub: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка обновления GitHub: {e}")
        return False

# --- ПАРСИНГ ГРАФИКА ---
def parse_schedule_message(text):
    """
    Парсит сообщение формата:
    1.1: 01:00 – 04:30, 06:30 – 10:30, 13:00 – 16:30, 18:30 – 22:30
    2.1: 00:00 – 01:00, 03:30 – 07:00, ...
    """
    schedules = {}
    
    # Ищем строки вида "X.X: время"
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Паттерн: "1.1:" или "1.1 " в начале строки, затем время
        match = re.match(r'^(\d+\.\d+)\s*:?\s*(.+)$', line)
        
        if match:
            group = match.group(1).strip()
            schedule_text = match.group(2).strip()
            
            # Проверяем, что в расписании есть временные диапазоны
            if re.search(r'\d{1,2}:\d{2}', schedule_text):
                schedules[group] = schedule_text
                logger.info(f"📋 Распознана очередь {group}: {schedule_text[:50]}...")
    
    return schedules

# --- МЕНЮ ---
def get_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    is_on = u_data.get('notif_15', False)
    
    notif_text = f"🔔 Уведомления за 15 мин: {'✅ ВКЛ' if is_on else '❌ ВЫКЛ'}"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(notif_text)
    return markup

if bot:
    # --- АДМИН (ТВОЙ ID) ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_logic(message):
        text = message.text
        if not text: 
            return

        # Если это команды меню - обрабатываем как обычный юзер
        if "Моя очередь" in text or "Уведомления за 15 мин" in text:
            user_logic(message)
            return

        logger.info(f"\n📨 Получено сообщение от админа (ID {ADMIN_ID})")
        
        # Парсинг графика
        parsed_schedules = parse_schedule_message(text)
        
        if not parsed_schedules:
            bot.reply_to(message, "⚠️ Не удалось распознать графики.\n\nФормат:\n1.1: 01:00 – 04:30, 06:30 – 10:30\n2.1: 00:00 – 01:00, 03:30 – 07:00")
            logger.warning("❌ Графики не распознаны")
            return
        
        # Загружаем текущие данные
        data = load_json(DATA_FILE)
        updated_groups = []
        
        # Обновляем только те очереди, которые пришли
        for group, schedule in parsed_schedules.items():
            data[group] = schedule
            updated_groups.append(group)
        
        # Сохраняем локально
        if save_json(DATA_FILE, data):
            logger.info(f"✅ Обновлены очереди: {', '.join(updated_groups)}")
            
            # Обновляем на GitHub
            github_success = update_github_file(data)
            
            # Подтверждение админу
            confirmation = f"✅ ГРАФИКИ ОБНОВЛЕНЫ!\n\n"
            confirmation += f"📋 Очереди: {', '.join(sorted(updated_groups))}\n"
            confirmation += f"🌐 GitHub: {'✅ Обновлен' if github_success else '❌ Ошибка (проверь GITHUB_TOKEN)'}\n\n"
            
            bot.reply_to(message, confirmation)
            
            # УВЕДОМЛЕНИЯ ПОДПИСЧИКАМ
            users = load_json(USERS_FILE)
            notified_count = 0
            
            for uid_str, u_data in users.items():
                user_group = u_data.get('group')
                
                if user_group in updated_groups:
                    try:
                        schedule_text = data[user_group]
                        notification = f"🔔 ГРАФИК ОБНОВЛЕН!\n\n"
                        notification += f"📍 Ваша очередь: {user_group}\n\n"
                        notification += f"⚡ Отключения:\n{schedule_text}"
                        
                        bot.send_message(int(uid_str), notification)
                        notified_count += 1
                        logger.info(f"✅ Уведомление отправлено пользователю {uid_str} (очередь {user_group})")
                        time.sleep(0.05)  # Чтобы не словить лимит Telegram
                        
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить пользователю {uid_str}: {e}")
            
            # Итоговый отчет админу
            report = f"📊 Уведомлено пользователей: {notified_count}"
            bot.send_message(ADMIN_ID, report)
            logger.info(f"\n✅ Обработка завершена: {notified_count} уведомлений отправлено")
        else:
            bot.reply_to(message, "❌ Ошибка сохранения графиков")

    # --- ЮЗЕРЫ ---
    @bot.message_handler(commands=['start'])
    def start(message):
        uid = str(message.from_user.id)
        users = load_json(USERS_FILE)
        
        # Инициализируем нового пользователя
        if uid not in users:
            users[uid] = {'group': None, 'notif_15': False}
            save_json(USERS_FILE, users)
        
        welcome = "⚡ Добро пожаловать в бот мониторинга отключений света!\n\n"
        welcome += "Выберите вашу очередь через меню ниже."
        
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
            
        elif "Уведомления за 15 мин" in msg_text:
            users = load_json(USERS_FILE)
            if uid not in users: 
                users[uid] = {'group': None, 'notif_15': False}
            
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            
            status = "ВКЛЮЧЕНЫ ✅" if users[uid]['notif_15'] else "ВЫКЛЮЧЕНЫ ❌"
            bot.send_message(message.chat.id, f"🔔 Напоминания {status}", reply_markup=get_menu(uid))
        else:
            # Если это не админ и не команда меню
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "⛔ Используйте кнопки меню ниже.")

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
        bot.edit_message_text(f"✅ Выбрана очередь: {group}", call.message.chat.id, call.message.message_id)
        
        # Показываем текущий график для выбранной очереди
        data = load_json(DATA_FILE)
        schedule = data.get(group, "График пока не установлен")
        
        info = f"📍 Ваша очередь: {group}\n\n⚡ Отключения:\n{schedule}"
        bot.send_message(call.message.chat.id, info, reply_markup=get_menu(uid))

# --- ЗАПУСК БОТА ---
def start_bot_polling():
    """Запуск бота с обработкой ошибок и автоперезапуском"""
    if not bot:
        logger.error("❌ Бот не создан - проверь BOT_TOKEN")
        return
    
    retry_delay = 5
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Попытка запуска бота #{attempt + 1}")
            
            # Принудительно удаляем webhook
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(2)
            
            # Запускаем polling
            logger.info("✅ Бот запущен в режиме polling")
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True,
                allowed_updates=['message', 'callback_query']
            )
            
            # Если дошли сюда - polling остановился нормально
            break
            
        except Exception as e:
            logger.error(f"❌ Ошибка бота: {e}")
            
            if "409" in str(e) or "Conflict" in str(e):
                logger.warning("⚠️ Конфликт 409 - другой процесс использует токен")
                logger.info(f"⏳ Жду {retry_delay} сек перед повтором...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Увеличиваем задержку
            else:
                logger.error("❌ Критическая ошибка, перезапуск через 10 сек...")
                time.sleep(10)

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

@app.route('/ping')
def ping(): 
    return "PONG"

@app.route('/status')
def status():
    """Отладочный endpoint для проверки состояния"""
    data = load_json(DATA_FILE)
    users = load_json(USERS_FILE)
    
    return jsonify({
        "schedules_count": len(data),
        "users_count": len(users),
        "github_token_set": bool(GITHUB_TOKEN),
        "bot_token_set": bool(TOKEN),
        "app_url": APP_URL
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ЗАПУСК СЕРВИСА")
    print("="*60)
    print(f"✅ BOT_TOKEN: {'Установлен' if TOKEN else '❌ НЕ УСТАНОВЛЕН'}")
    print(f"✅ GITHUB_TOKEN: {'Установлен' if GITHUB_TOKEN else '⚠️ НЕ УСТАНОВЛЕН'}")
    print(f"✅ ADMIN_ID: {ADMIN_ID}")
    print(f"🌐 URL: {APP_URL}")
    print("="*60 + "\n")
    
    # Запускаем автопинг в отдельном потоке
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    logger.info("🏓 Автопинг активирован (каждые 5 минут)")
    
    # Запускаем бота в отдельном потоке
    if bot:
        bot_thread = threading.Thread(target=start_bot_polling, daemon=True)
        bot_thread.start()
        time.sleep(3)  # Даем боту время на запуск
    
    # Запускаем Flask
    logger.info("🌐 Запуск веб-сервера...")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
