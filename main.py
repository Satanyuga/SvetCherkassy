import os
import json
import time
import threading
import requests
import sys
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# --- ЖЕСТКИЕ ПУТИ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')

ADMIN_ID = 815422710  
TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = "https://svetcherkassy.onrender.com" 

app = Flask(__name__)

def load_json(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def save_json(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush() # Выталкиваем данные на диск немедленно
    except Exception as e:
        print(f"[ERR] Ошибка сохранения {filename}: {e}", flush=True)

# --- ДАЛЬШЕ ЛОГИКА БОТА (БЕЗ ИЗМЕНЕНИЙ, РАЗ ОНА РАБОТАЕТ) ---
bot = TeleBot(TOKEN) if TOKEN else None

def is_admin(m): return m.from_user.id == ADMIN_ID

def get_main_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    notif = "✅ ВКЛ" if u_data.get('notif_15', False) else "❌ ВЫКЛ"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(f"🔔 Уведомления за 15 мин: {notif}")
    return markup

if bot:
    @bot.message_handler(commands=['check'])
    def check_me(message):
        if is_admin(message): bot.reply_to(message, "👑 Хозяин на месте.")
        else: bot.reply_to(message, f"👤 ID: {message.from_user.id}")

    @bot.message_handler(func=is_admin)
    def handle_admin_updates(message):
        text = message.text
        if not text: return
        if "Моя очередь" in text or "Уведомления за 15 мин" in text:
            handle_all_users(message)
            return

        data = load_json(DATA_FILE)
        updated = []
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                g = parts[0].replace(":", "").replace("Группа", "").rstrip(".").strip()
                s = parts[1].strip()
                data[g] = s
                updated.append(g)
        
        if updated:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✅ Обновлено на сервере: {', '.join(updated)}")
            # Рассылка
            users = load_json(USERS_FILE)
            for uid, u_data in users.items():
                if u_data.get('group') in updated:
                    try: bot.send_message(uid, f"⚡ Очередь {u_data['group']}:\n{data[u_data['group']]}")
                    except: pass
        else:
            bot.reply_to(message, "❌ Формат! Пример: 4.1 12:00-15:00")

    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "Адель в строю.", reply_markup=get_main_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def handle_all_users(message):
        uid = str(message.from_user.id)
        text = message.text
        if "Моя очередь" in text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выбирай группу:", reply_markup=markup)
        elif "Уведомления за 15 мин" in text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            bot.send_message(message.chat.id, "Готово.", reply_markup=get_main_menu(uid))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_inline(call):
        group = call.data.replace("set_g_", "")
        users = load_json(USERS_FILE)
        uid = str(call.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.edit_message_text(f"✅ Выбрана группа {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Меню обновлено.", reply_markup=get_main_menu(uid))

# --- FLASK ---
@app.route('/')
def home(): return send_from_directory(BASE_DIR, 'index.html')

@app.route('/data.json')
def get_data(): 
    # Читаем файл ПРЯМО перед отдачей пользователю
    return jsonify(load_json(DATA_FILE))

@app.route('/ping')
def ping(): return "PONG"

if __name__ == '__main__':
    if bot:
        threading.Thread(target=lambda: bot.infinity_polling(timeout=90, skip_pending=True), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
