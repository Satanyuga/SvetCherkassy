import os
import json
import time
import threading
import requests
import sys
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# --- ЖЕСТКАЯ АВТОРИЗАЦИЯ ---
# Твой ID как константа (Integer)
ADMIN_ID = 815422710  
TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = "https://svetcherkassy.onrender.com" 

app = Flask(__name__)
DATA_FILE = 'data.json'
USERS_FILE = 'users.json'

bot = TeleBot(TOKEN) if TOKEN else None

def load_json(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_json(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[ERROR] Ошибка записи: {e}", flush=True)

# --- АДМИНСКИЙ ФИЛЬТР ---
def is_admin(m):
    return m.from_user.id == ADMIN_ID

# --- МЕНЮ ---
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
    # 1. КОМАНДА ПРОВЕРКИ (Для тебя)
    @bot.message_handler(commands=['check'])
    def check_me(message):
        if is_admin(message):
            bot.reply_to(message, f"👑 Привет, Хозяин. Твой ID ({message.from_user.id}) в белом списке.")
        else:
            bot.reply_to(message, f"👤 Ты обычный смертный. Твой ID: {message.from_user.id}")

    # 2. ЛОГИКА АДМИНА (ОБНОВЛЕНИЕ ГРАФИКА)
    @bot.message_handler(func=is_admin)
    def handle_admin_updates(message):
        text = message.text
        if not text: return
        
        # Если это нажатие кнопки меню - отправляем в логику юзера
        if "Моя очередь" in text or "Уведомления за 15 мин" in text:
            handle_all_users(message)
            return

        print(f"[ADMIN] Обработка данных: {text}", flush=True)
        data = load_json(DATA_FILE)
        updated = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                # Очистка номера группы от мусора (4.1. или Группа 4.1:)
                g = parts[0].replace(":", "").replace("Группа", "").rstrip(".").strip()
                s = parts[1].strip()
                data[g] = s
                updated.append(g)
        
        if updated:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✅ Магия сработала. Обновлено: {', '.join(updated)}")
            # Рассылка
            users = load_json(USERS_FILE)
            for uid, u_data in users.items():
                if u_data.get('group') in updated:
                    try: bot.send_message(uid, f"⚡ ГРАФИК ОБНОВЛЕН!\nОчередь {u_data['group']}:\n{data[u_data['group']]}")
                    except: pass
        else:
            bot.reply_to(message, "❌ Не вижу данных. Пиши: `4.1 12:00-15:00`", parse_mode="Markdown")

    # 3. ОБЩИЕ КОМАНДЫ
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "Адель готова к работе. Используй меню.", reply_markup=get_main_menu(message.from_user.id))

    # 4. ЛОГИКА ЮЗЕРОВ
    @bot.message_handler(func=lambda m: True)
    def handle_all_users(message):
        uid = str(message.from_user.id)
        text = message.text

        if "Моя очередь" in text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выбирай очередь:", reply_markup=markup)
        
        elif "Уведомления за 15 мин" in text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            bot.send_message(message.chat.id, "Настройки изменены.", reply_markup=get_main_menu(uid))
        
        else:
            if not is_admin(message):
                bot.send_message(message.chat.id, "🤫 Тсс... Я не разговариваю с незнакомцами. Пользуйся кнопками.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_inline(call):
        group = call.data.replace("set_g_", "")
        users = load_json(USERS_FILE)
        uid = str(call.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Выбрана группа {group}")
        bot.edit_message_text(f"✅ Твоя очередь: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Меню обновлено.", reply_markup=get_main_menu(uid))

# --- ВЕБ СЕРВЕР ---
@app.route('/')
def home(): return "Бот Адель активен."

@app.route('/ping')
def ping(): return "PONG"

@app.route('/data.json')
def get_data(): return jsonify(load_json(DATA_FILE))

def self_ping():
    while True:
        try: requests.get(f"{APP_URL}/ping", timeout=10)
        except: pass
        time.sleep(600)

if __name__ == '__main__':
    threading.Thread(target=self_ping, daemon=True).start()
    if bot:
        print(f"[START] Запуск бота. Админ ID: {ADMIN_ID}", flush=True)
        threading.Thread(target=lambda: bot.infinity_polling(timeout=90, skip_pending=True), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
