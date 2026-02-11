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
        print(f"[ERR] Ошибка сохранения: {e}", flush=True)

# --- ГЕНЕРАЦИЯ МЕНЮ (ВСЕ ИКОНКИ НА МЕСТЕ) ---
def get_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    is_on = u_data.get('notif_15', False)
    
    # Твои любимые галочки и крестики
    notif_status = "✅ ВКЛ" if is_on else "❌ ВЫКЛ"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(f"🔔 Уведомления за 15 мин: {notif_status}")
    return markup

if bot:
    # --- АДМИНСКАЯ ЛОГИКА ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_handler(message):
        text = message.text
        if not text: return

        # Если нажал кнопку меню
        if "Моя очередь" in text or "Уведомления за 15 мин" in text:
            user_handler(message)
            return

        # Парсинг графика (с поддержкой 4.1. и т.д.)
        data = load_json(DATA_FILE)
        updated = []
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            try:
                parts = line.split(None, 1)
                if len(parts) < 2: continue
                # Очистка группы
                g = parts[0].replace(":", "").replace("Группа", "").rstrip(".").strip()
                s = parts[1].strip()
                data[g] = s
                updated.append(g)
            except: continue

        if updated:
            save_json(DATA_FILE, data)
            bot.reply_to(message, f"✨ Хозяин, я обновила: {', '.join(updated)}")
            
            # Рассылка
            users = load_json(USERS_FILE)
            for uid, u_data in users.items():
                if u_data.get('group') in updated:
                    try:
                        g_name = u_data['group']
                        bot.send_message(uid, f"📢 ВНИМАНИЕ! График обновился!\nОчередь {g_name}:\n{data[g_name]}")
                    except: pass
        else:
            bot.reply_to(message, "⚠️ Формат: 4.1 00:00-18:00")

    # --- ОБЩАЯ ЛОГИКА ---
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "🤖 Бот готов к работе.", reply_markup=get_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def user_handler(message):
        uid = str(message.from_user.id)
        text = message.text

        if "Моя очередь" in text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            gs = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in gs]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выбери свою очередь:", reply_markup=markup)
            
        elif "Уведомления за 15 мин" in text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            
            # Переключаем
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            
            icon = "🔔" if users[uid]['notif_15'] else "🔕"
            word = "ВКЛЮЧЕНЫ ✅" if users[uid]['notif_15'] else "ВЫКЛЮЧЕНЫ ❌"
            bot.send_message(message.chat.id, f"{icon} Уведомления {word}", reply_markup=get_menu(uid))
        else:
            if message.from_user.id != ADMIN_ID:
                bot.send_message(message.chat.id, "⛔ Писать нельзя, пользуйся кнопками.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("set_g_"))
    def callback_set_group(call):
        group = call.data.replace("set_g_", "")
        uid = str(call.from_user.id)
        users = load_json(USERS_FILE)
        if uid not in users: users[uid] = {'group': None, 'notif_15': False}
        users[uid]['group'] = group
        save_json(USERS_FILE, users)
        bot.answer_callback_query(call.id, f"Очередь {group} сохранена")
        bot.edit_message_text(f"✅ Выбрана очередь: {group}", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Меню обновлено", reply_markup=get_menu(uid))

# --- FLASK ---
@app.route('/')
def home(): return send_from_directory('.', 'index.html')

@app.route('/data.json')
def get_data(): return jsonify(load_json(DATA_FILE))

@app.route('/ping')
def ping(): return "PONG"

if __name__ == '__main__':
    if bot:
        try:
            # ПРИНУДИТЕЛЬНЫЙ СБРОС КОНФЛИКТА
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(1)
            # ЗАПУСК
            threading.Thread(target=lambda: bot.infinity_polling(timeout=90, skip_pending=True), daemon=True).start()
            print("[OK] Бот запущен без конфликтов", flush=True)
        except Exception as e:
            print(f"[ERR] Ошибка старта: {e}", flush=True)
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
