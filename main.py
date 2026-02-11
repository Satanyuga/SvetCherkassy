import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# --- КОНФИГУРАЦИЯ ---
ADMIN_ID = 815422710  
TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = "https://svetcherkassy.onrender.com" 

app = Flask(__name__)
DATA_FILE = 'data.json'
USERS_FILE = 'users.json'

bot = TeleBot(TOKEN) if TOKEN else None

# --- ФАЙЛЫ ---
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
        print(f"[ERR] Ошибка: {e}", flush=True)

# --- МЕНЮ (С ТВОИМИ ГАЛОЧКАМИ И КОЛОКОЛЬЧИКАМИ) ---
def get_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    
    # Возвращаем визуализацию как ты просил
    is_on = u_data.get('notif_15', False)
    notif_text = f"🔔 Уведомления за 15 мин: {'✅ ВКЛ' if is_on else '❌ ВЫКЛ'}"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(notif_text)
    return markup

if bot:
    # --- АДМИН (ТЫ) ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_logic(message):
        text = message.text
        if not text: return

        # Если ты жмешь на кнопки уведомлений или очереди
        if "Моя очередь" in text or "Уведомления за 15 мин" in text:
            user_logic(message)
            return

        # Обновление графика
        data = load_json(DATA_FILE)
        updated = []
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            try:
                parts = line.split(None, 1)
                if len(parts) < 2: continue
                g = parts[0].replace(":", "").replace("Группа", "").rstrip(".").strip()
                s = parts[1].strip()
                data[g] = s
                updated.append(g)
            except: continue

        if updated:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✅ График обновлен: {', '.join(updated)}")
            
            # Рассылка тем, у кого включены уведомления
            users = load_json(USERS_FILE)
            for uid, u_data in users.items():
                if u_data.get('group') in updated:
                    try:
                        bot.send_message(uid, f"📢 Новый график для группы {u_data['group']}:\n{data[u_data['group']]}")
                    except: pass
        else:
            bot.reply_to(message, "⚠️ Пиши: 4.1 00:00-18:00")

    # --- ЮЗЕРЫ И ОБЩАЯ ЛОГИКА ---
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "👋 Бот активен.", reply_markup=get_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def user_logic(message):
        uid = str(message.from_user.id)
        msg_text = message.text

        if "Моя очередь" in msg_text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выберите вашу очередь:", reply_markup=markup)
            
        elif "Уведомления за 15 мин" in msg_text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            
            # Инвертируем статус
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            
            status_icon = "🔔" if users[uid]['notif_15'] else "🔕"
            status_word = "ВКЛЮЧЕНЫ ✅" if users[uid]['notif_15'] else "ВЫКЛЮЧЕНЫ ❌"
            
            bot.send_message(message.chat.id, f"{status_icon} Напоминания {status_word}", reply_markup=get_menu(uid))
        else:
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "⛔ Пожалуйста, используйте кнопки меню.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_handler(call):
        group = call.data.replace("set_g_", "")
        uid = str(call.from_user.id)
        users = load_json(USERS_FILE)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Выбрана группа {group}")
        bot.edit_message_text(f"✅ Ваша очередь: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Меню обновлено", reply_markup=get_menu(uid))

# --- ВЕБ-ЧАСТЬ (ДЛЯ САЙТА) ---
@app.route('/')
def index(): return send_from_directory('.', 'index.html')

@app.route('/ping')
def ping(): return "PONG"

@app.route('/data.json')
def get_data(): 
    return jsonify(load_json(DATA_FILE))

if __name__ == '__main__':
    # Сброс вебхука для избежания конфликта 409
    if bot:
        bot.delete_webhook(drop_pending_updates=True)
        threading.Thread(target=lambda: bot.infinity_polling(timeout=90, skip_pending=True), daemon=True).start()
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
