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
# Смени этот URL на свой, если он другой!
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

# --- АВТОПИНГ (КАК В ТВОЕМ ПРИМЕРЕ) ---
def self_ping():
    time.sleep(10) # Даем серверу стартануть
    while True:
        try:
            # Пингуем сам себя по сети
            res = requests.get(f"{APP_URL}/ping", timeout=10)
            print(f"==> [SELF-PING] Статус: {res.text}, Сервер активен.")
        except Exception as e:
            print(f"==> [SELF-PING] Ошибка пинга: {e}")
        time.sleep(300) # Раз в 5 минут (300 сек)

# --- ЛОГИКА БОТА ---
if bot:
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "🤖 Охрана Адель активна.\nИспользуйте кнопки для настройки очереди.", 
                         reply_markup=get_main_menu(message.from_user.id))

    # Рассылка 15 минут (кнопка)
    @bot.message_handler(func=lambda m: "Уведомления за 15 мин" in m.text)
    def toggle_15min(message):
        users = load_json(USERS_FILE)
        uid = str(message.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['notif_15'] = not users[uid]['notif_15']
        save_json(USERS_FILE, users)
        msg = "🔔 Напоминание ВКЛЮЧЕНО" if users[uid]['notif_15'] else "🔕 Напоминание ВЫКЛЮЧЕНО"
        bot.send_message(message.chat.id, msg, reply_markup=get_main_menu(uid))

    @bot.message_handler(func=lambda m: "Моя очередь" in m.text)
    def choose_group(message):
        markup = types.InlineKeyboardMarkup(row_width=3)
        groups = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
        btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in groups]
        markup.add(*btns)
        bot.send_message(message.chat.id, "Выберите вашу очередь:", reply_markup=markup)

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

    # --- ОБРАБОТЧИК ВЛАДЕЛЬЦА (ДЛЯ ТЕБЯ) ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_handler(message):
        text = message.text
        if ":" in text:
            data = load_json(DATA_FILE)
            users = load_json(USERS_FILE)
            updated = []
            for line in text.split('\n'):
                if ":" in line:
                    try:
                        g, s = line.split(":", 1)
                        g = g.replace("Группа", "").strip()
                        data[g] = s.strip()
                        updated.append(g)
                    except: continue
            if updated:
                save_json(DATA_FILE, data)
                bot.reply_to(message, f"✅ Обновлено групп: {len(updated)}")
                # Рассылка уведомлений
                for uid, u_data in users.items():
                    if u_data.get('group') in updated:
                        try: bot.send_message(uid, f"📢 ГРАФИК ИЗМЕНИЛСЯ!\nГруппа {u_data['group']}:\n{data[u_data['group']]}")
                        except: pass
        else:
            bot.reply_to(message, "⚠️ Пришли график в формате: 'Группа 4.1: время'")

def get_main_menu(user_id):
    users = load_json(USERS_FILE)
    u_data = users.get(str(user_id), {})
    group = u_data.get('group', 'Не выбрана')
    notif = "✅ ВКЛ" if u_data.get('notif_15', False) else "❌ ВЫКЛ"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {group}")
    markup.add(f"🔔 Уведомления за 15 мин: {notif}")
    return markup

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
    # Запуск пинга
    threading.Thread(target=self_ping, daemon=True).start()
    
    # Запуск бота (с пропуском старых сообщений)
    if bot:
        threading.Thread(target=lambda: bot.infinity_polling(timeout=60, skip_pending=True), daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"==> [START] Сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)
