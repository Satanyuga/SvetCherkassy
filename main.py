import os
import json
import time
import threading
import requests
import sys
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types, apihelper

# --- КОНФИГУРАЦИЯ ---
ADMIN_ID = 815422710  # Твой проверенный ID
TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = "https://svetcherkassy.onrender.com" 

app = Flask(__name__)
DATA_FILE = 'data.json'
USERS_FILE = 'users.json'

bot = TeleBot(TOKEN) if TOKEN else None

# --- РАБОТА С ФАЙЛАМИ ---
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
        print(f"[ERR] Ошибка записи: {e}", flush=True)

# --- АВТОПИНГ ---
def keep_alive():
    time.sleep(15) 
    while True:
        try:
            requests.get(f"{APP_URL}/ping", timeout=10)
            print("[PING] Сервер жив", flush=True)
        except: pass
        time.sleep(300) 

# --- МЕНЮ ---
def get_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    notif = "ВКЛ" if u_data.get('notif_15', False) else "ВЫКЛ"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(f"🔔 Напоминание за 15 мин: {notif}")
    return markup

if bot:
    # --- ОБРАБОТЧИК ДЛЯ ТЕБЯ (АДМИН) ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_logic(message):
        text = message.text
        if not text: return
        
        # Кнопки меню для админа
        if "Моя очередь" in text or "Напоминание за 15 мин" in text:
            user_logic(message)
            return

        # Парсинг графика
        data = load_json(DATA_FILE)
        updated = []
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            try:
                parts = line.split(None, 1)
                if len(parts) < 2: continue
                # Очистка (4.1. -> 4.1)
                g = parts[0].replace(":", "").replace("Группа", "").rstrip(".").strip()
                s = parts[1].strip()
                data[g] = s
                updated.append(g)
            except: continue

        if updated:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✅ Обновлено: {', '.join(updated)}")
        else:
            bot.reply_to(message, "⚠️ Формат: 4.1 00:00-18:00")

    # --- ОБЩАЯ ЛОГИКА ---
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "🤖 Бот готов. Используй кнопки.", reply_markup=get_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def user_logic(message):
        uid = str(message.from_user.id)
        if "Моя очередь" in message.text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выбери очередь:", reply_markup=markup)
        elif "Напоминание за 15 мин" in text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            bot.send_message(message.chat.id, "🔔 Статус изменен", reply_markup=get_menu(uid))
        else:
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "⛔ Писать нельзя, только кнопки.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_handler(call):
        group = call.data.replace("set_g_", "")
        uid = str(call.from_user.id)
        users = load_json(USERS_FILE)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Очередь {group}")
        bot.edit_message_text(f"✅ Выбрана очередь: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Ок", reply_markup=get_menu(uid))

# --- FLASK ---
@app.route('/')
def index(): return send_from_directory('.', 'index.html')

@app.route('/ping')
def ping(): return "PONG"

@app.route('/data.json')
def get_data(): return jsonify(load_json(DATA_FILE))

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if bot:
        try:
            # ЖЕСТКИЙ СБРОС КОНФЛИКТОВ
            print("[INFO] Сброс старых сессий...", flush=True)
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(1)
            
            # ЗАПУСК В ПОТОКЕ
            print(f"[INFO] Бот стартует для админа {ADMIN_ID}", flush=True)
            t = threading.Thread(target=lambda: bot.infinity_polling(timeout=90, long_polling_timeout=5))
            t.daemon = True
            t.start()
        except Exception as e:
            print(f"[ERROR] Не удалось запустить бота: {e}", flush=True)

    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
