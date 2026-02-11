import os
import json
import time
import threading
import requests
import sys
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 31895665 # Твой ID
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

# --- ЖЕСТКИЙ АВТОПИНГ С ВЫВОДОМ В КОНСОЛЬ ---
def self_ping():
    time.sleep(20)
    while True:
        try:
            res = requests.get(f"{APP_URL}/ping", timeout=10)
            # ПЕЧАТАЕМ В ЛОГИ ЖИРНО И СРАЗУ
            print(f"\n[!!!] Я НЕ СПЛЮ. ОТВЕТ СЕРВЕРА: {res.text}\n", flush=True)
        except Exception as e:
            print(f"\n[!!!] ОШИБКА ПИНГА: {e}\n", flush=True)
        time.sleep(600) # Раз в 10 минут

# --- МЕНЮ БОТА ---
def get_main_menu(user_id):
    users = load_json(USERS_FILE)
    u_data = users.get(str(user_id), {})
    group = u_data.get('group', 'Не выбрана')
    notif = "✅ ВКЛ" if u_data.get('notif_15', False) else "❌ ВЫКЛ"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, input_field_placeholder="Жми кнопки 👇")
    markup.add(f"👥 Моя очередь: {group}")
    markup.add(f"🔔 Уведомления за 15 мин: {notif}")
    return markup

if bot:
    # --- ОБРАБОТЧИК ВЛАДЕЛЬЦА (ПРИОРИТЕТ) ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_handler(message):
        text = message.text
        if not text: return

        # Если нажата кнопка меню, обрабатываем как юзер
        if "Моя очередь" in text or "Уведомления за 15 мин" in text:
            handle_user_logic(message)
            return

        # ПАРСИНГ: ПРОСТО ИЩЕМ ЦИФРЫ В НАЧАЛЕ СТРОКИ
        data = load_json(DATA_FILE)
        users = load_json(USERS_FILE)
        updated = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            
            # Разбиваем строку: первое слово — это очередь (напр. 4.1), остальное — график
            parts = line.split(None, 1) 
            if len(parts) == 2:
                g = parts[0].replace(":", "").replace("Группа", "").strip()
                s = parts[1].strip()
                data[g] = s
                updated.append(g)
        
        if updated:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✅ ПРИНЯТО. ОБНОВЛЕНО: {', '.join(updated)}")
            # РАССЫЛКА
            for uid, u_data in users.items():
                if u_data.get('group') in updated:
                    try: bot.send_message(uid, f"📢 ГРАФИК ИЗМЕНИЛСЯ!\nОчередь {u_data['group']}:\n{data[u_data['group']]}")
                    except: pass
        else:
            bot.reply_to(message, "❌ Не вижу очереди. Напиши например: 4.1 00:00-12:00")

    # --- ОБЩАЯ ЛОГИКА ---
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "🤖 Адель на связи. Используй кнопки.", reply_markup=get_main_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def handle_user_logic(message):
        uid = str(message.from_user.id)
        if "Моя очередь" in message.text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выбери очередь:", reply_markup=markup)
        elif "Уведомления за 15 мин" in message.text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            status = "ВКЛ" if users[uid]['notif_15'] else "ВЫКЛ"
            bot.send_message(message.chat.id, f"🔔 Напоминание {status}", reply_markup=get_main_menu(uid))
        else:
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "❌ Писать нельзя. Только кнопки.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_set_group(call):
        group = call.data.replace("set_g_", "")
        users = load_json(USERS_FILE)
        uid = str(call.from_user.id)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Очередь {group}")
        bot.edit_message_text(f"✅ Твоя очередь: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Настройка завершена.", reply_markup=get_main_menu(uid))

# --- СЕРВЕР ---
@app.route('/')
def home(): return "🤖 Адель активна"

@app.route('/ping')
def ping_status(): 
    print("[!!!] ПОЛУЧЕН ВНЕШНИЙ ПИНГ", flush=True)
    return "Я НЕ СПЛЮ"

@app.route('/data.json')
def get_data(): return jsonify(load_json(DATA_FILE))

@app.route('/index.html')
def index_page(): return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    threading.Thread(target=self_ping, daemon=True).start()
    if bot:
        threading.Thread(target=lambda: bot.infinity_polling(timeout=60, skip_pending=True), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
