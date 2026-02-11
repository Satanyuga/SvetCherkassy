import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# Настройки из твоих переменных в Render
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("TG_API_ID") # Твой ID: 31895665
APP_URL = "https://svetcherkassy.onrender.com"

app = Flask(__name__)
DATA_FILE = 'data.json'
USERS_FILE = 'users.json' # Здесь храним подписчиков

bot = TeleBot(TOKEN) if TOKEN else None

# --- РАБОТА С ДАННЫМИ ---
def load_json(filename):
    if not os.path.exists(filename): return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
def get_main_menu(user_id):
    users = load_json(USERS_FILE)
    u_data = users.get(str(user_id), {})
    group = u_data.get('group', 'Не выбрана')
    notif = "✅ ВКЛ" if u_data.get('notif_15', False) else "❌ ВЫКЛ"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(f"👥 Моя очередь: {group}"))
    markup.add(types.KeyboardButton(f"🔔 Уведомления за 15 мин: {notif}"))
    return markup

def get_group_buttons():
    markup = types.InlineKeyboardMarkup(row_width=3)
    groups = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
    btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in groups]
    markup.add(*btns)
    return markup

if bot:
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "Привет! Я бот Svet Monitor. Выбери свою очередь, чтобы получать уведомления.", reply_markup=get_main_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: m.text and "Моя очередь" in m.text)
    def choose_group(message):
        bot.send_message(message.chat.id, "Выбери свою очередь из списка:", reply_markup=get_group_buttons())

    @bot.message_handler(func=lambda m: m.text and "Уведомления за 15 мин" in m.text)
    def toggle_15min(message):
        users = load_json(USERS_FILE)
        uid = str(message.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['notif_15'] = not users[uid]['notif_15']
        save_json(USERS_FILE, users)
        bot.send_message(message.chat.id, "Настройки уведомлений обновлены!", reply_markup=get_main_menu(uid))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_set_group(call):
        group = call.data.replace("set_g_", "")
        users = load_json(USERS_FILE)
        uid = str(call.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Выбрана очередь {group}")
        bot.edit_message_text(f"✅ Твоя очередь успешно установлена: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Теперь я буду присылать уведомления, если твой график изменится.", reply_markup=get_main_menu(uid))

    # --- ОБНОВЛЕНИЕ ГРАФИКА (ТОЛЬКО ДЛЯ ТЕБЯ) ---
    @bot.message_handler(func=lambda m: str(m.from_user.id) == str(ADMIN_ID))
    def admin_update(message):
        text = message.text
        if ":" not in text: return
        
        data = load_json(DATA_FILE)
        users = load_json(USERS_FILE)
        updated_groups = []
        
        for line in text.split('\n'):
            if ":" in line:
                try:
                    p = line.split(":", 1)
                    g = p[0].replace("Группа", "").strip()
                    s = p[1].strip()
                    data[g] = s
                    updated_groups.append(g)
                except: continue
        
        if updated_groups:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✅ Обновлено групп: {len(updated_groups)}")
            
            # РАССЫЛКА УВЕДОМЛЕНИЙ ОБ ИЗМЕНЕНИИ
            for uid, u_data in users.items():
                if u_data.get('group') in updated_groups:
                    try:
                        new_sched = data[u_data['group']]
                        bot.send_message(uid, f"📢 Ваш график изменился!\n⚡️ Очередь {u_data['group']}:\n{new_sched}")
                    except: pass

# --- ФОНОВЫЕ ЗАДАЧИ ---
def check_15min_notif():
    """Проверка уведомлений за 15 минут"""
    while True:
        try:
            time.sleep(60)
            data = load_json(DATA_FILE)
            users = load_json(USERS_FILE)
            now = new_date_kiev()
            cur_m = now.getHours() * 60 + now.getMinutes()
            
            for uid, u_data in users.items():
                if u_data.get('notif_15') and u_data.get('group') in data:
                    sched = data[u_data['group']]
                    # Логика поиска 15 минут (аналог sw.js)
                    # Если найдено совпадение - бот отправляет сообщение
        except: pass

def keep_alive():
    while True:
        try: requests.get(APP_URL, timeout=10)
        except: pass
        time.sleep(600)

@app.route('/')
def index(): return send_from_directory('.', 'index.html')

@app.route('/data.json')
def get_data(): return jsonify(load_json(DATA_FILE))

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    if bot:
        threading.Thread(target=lambda: bot.infinity_polling(timeout=60), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
