import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 31895665 # Твой жесткий ID
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
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- АВТОПИНГ В ЛОГИ (КАК ТЫ ПРОСИЛ) ---
def self_ping():
    time.sleep(15)
    while True:
        try:
            res = requests.get(f"{APP_URL}/ping", timeout=10)
            print(f"==> [SELF-PING] Статус: {res.text}, Сервер активен.")
        except Exception as e:
            print(f"==> [SELF-PING] Ошибка: {e}")
        time.sleep(300)

# --- ГЛАВНОЕ МЕНЮ (С БЛОКИРОВКОЙ КЛАВИАТУРЫ) ---
def get_main_menu(user_id):
    users = load_json(USERS_FILE)
    u_data = users.get(str(user_id), {})
    group = u_data.get('group', 'Не выбрана')
    notif = "✅ ВКЛ" if u_data.get('notif_15', False) else "❌ ВЫКЛ"
    
    # input_field_placeholder намекает юзеру, что писать нельзя
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True, 
        input_field_placeholder="Используйте кнопки ниже 👇"
    )
    markup.add(f"👥 Моя очередь: {group}")
    markup.add(f"🔔 Уведомления за 15 мин: {notif}")
    return markup

# --- ЛОГИКА БОТА ---
if bot:
    # 1. СНАЧАЛА ПРОВЕРКА ВЛАДЕЛЬЦА (ПРИОРИТЕТ)
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_handler(message):
        text = message.text
        if text and ":" in text:
            data = load_json(DATA_FILE)
            users = load_json(USERS_FILE)
            updated = []
            
            for line in text.split('\n'):
                if ":" in line:
                    try:
                        g_part, s_part = line.split(":", 1)
                        g = g_part.replace("Группа", "").strip()
                        s = s_part.strip()
                        data[g] = s
                        updated.append(g)
                    except: continue
            
            if updated:
                save_json(DATA_FILE, data)
                bot.reply_to(message, f"✅ Магия сработала. Обновлено групп: {len(updated)}")
                # Рассылка
                for uid, u_data in users.items():
                    if u_data.get('group') in updated:
                        try:
                            bot.send_message(uid, f"📢 ГРАФИК ИЗМЕНИЛСЯ!\nГруппа {u_data['group']}:\n{data[u_data['group']]}")
                        except: pass
        else:
            # Если ты просто нажал на кнопку "Моя очередь"
            if "Моя очередь" in text or "Уведомления за 15 мин" in text:
                handle_buttons(message)
            else:
                bot.reply_to(message, "Йеннифэр слушает. Присылай график (Группа X.X: время).")

    # 2. ЛОГИКА ДЛЯ ЮЗЕРОВ
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "🤖 Охрана Адель активна.\nПисать боту нельзя — только кнопки.", 
                         reply_markup=get_main_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def handle_buttons(message):
        uid = str(message.from_user.id)
        if "Моя очередь" in message.text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            groups = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in groups]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выберите вашу очередь:", reply_markup=markup)
        
        elif "Уведомления за 15 мин" in message.text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            msg = "🔔 Напоминание ВКЛЮЧЕНО" if users[uid]['notif_15'] else "🔕 Напоминание ВЫКЛЮЧЕНО"
            bot.send_message(message.chat.id, msg, reply_markup=get_main_menu(uid))
        
        else:
            # Если это не кнопка и не админ — игнорим или посылаем
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "❌ Ввод текста заблокирован. Пользуйтесь кнопками.", reply_markup=get_main_menu(uid))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_set_group(call):
        group = call.data.replace("set_g_", "")
        users = load_json(USERS_FILE)
        uid = str(call.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Выбрана группа {group}")
        bot.edit_message_text(f"✅ Ваша очередь: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Настройка завершена.", reply_markup=get_main_menu(uid))

# --- FLASK ---
@app.route('/')
def home(): return "🤖 Охрана Адель активна"

@app.route('/ping')
def ping(): return "✅ OK"

@app.route('/data.json')
def get_data(): return jsonify(load_json(DATA_FILE))

@app.route('/index.html')
def index(): return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    threading.Thread(target=self_ping, daemon=True).start()
    if bot:
        threading.Thread(target=lambda: bot.infinity_polling(timeout=60, skip_pending=True), daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
