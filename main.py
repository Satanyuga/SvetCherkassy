import os
import json
import time
import threading
import requests
import sys
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot, types

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.environ.get("BOT_TOKEN")
# 🔥 ВОТ ТВОЙ ID. ТЕПЕРЬ ОН ТЕБЯ УЗНАЕТ.
ADMIN_ID = 815422710  
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
        print(f"[ERR] Ошибка сохранения: {e}", flush=True)

# --- АВТОПИНГ ---
def keep_alive():
    time.sleep(10) 
    while True:
        try:
            r = requests.get(f"{APP_URL}/ping", timeout=10)
            print(f"[PING] Я НЕ СПЛЮ. Статус: {r.status_code}", flush=True)
        except Exception as e:
            print(f"[PING] ОШИБКА: {e}", flush=True)
        time.sleep(300) 

# --- МЕНЮ ---
def get_menu(uid):
    users = load_json(USERS_FILE)
    u_data = users.get(str(uid), {})
    grp = u_data.get('group', 'Не выбрана')
    notif = "ВКЛ" if u_data.get('notif_15', False) else "ВЫКЛ"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, input_field_placeholder="Используй кнопки 👇")
    markup.add(f"👥 Моя очередь: {grp}")
    markup.add(f"🔔 Напоминание за 15 мин: {notif}")
    return markup

if bot:
    # --- 1. АДМИНСКАЯ ПАНЕЛЬ (ТВОЙ ID: 815422710) ---
    @bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
    def admin_logic(message):
        text = message.text
        if not text: return

        # Если админ нажимает кнопки меню, работаем как с юзером
        if "Моя очередь" in text or "Напоминание за 15 мин" in text:
            user_logic(message)
            return

        # ПАРСИНГ ГРАФИКА
        print(f"[ADMIN] Принято: {text}", flush=True)
        data = load_json(DATA_FILE)
        updated_groups = []

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            try:
                # Разбиваем по пробелу: "4.1 00-18" -> ["4.1", "00-18"]
                parts = line.split(None, 1)
                if len(parts) < 2: continue
                
                raw_group = parts[0]
                schedule = parts[1]
                
                # ЧИСТКА: убираем двоеточия, слово Группа и ТОЧКУ в конце (4.1. -> 4.1)
                group = raw_group.replace(":", "").replace("Группа", "").rstrip(".").strip()
                
                data[group] = schedule
                updated_groups.append(group)
            except:
                continue

        if updated_groups:
            save_json(DATA_FILE, data)
            # Отвечаем, что всё ок
            bot.reply_to(message, f"✅ ГРАФИК ПРИНЯТ.\nОбновлены: {', '.join(updated_groups)}")
            
            # Рассылка
            users = load_json(USERS_FILE)
            for uid, u_data in users.items():
                if u_data.get('group') in updated_groups:
                    try:
                        g = u_data['group']
                        bot.send_message(uid, f"📢 ГРАФИК ОБНОВИЛСЯ!\nОчередь {g}:\n{data[g]}")
                    except: pass
        else:
            bot.reply_to(message, "⚠️ Не поняла. Пиши так:\n4.1 00:00-18:00")

    # --- 2. ЮЗЕРЫ (БЛОКИРОВКА) ---
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.send_message(message.chat.id, "🤖 Бот активен. Выберите очередь кнопками.", reply_markup=get_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: True)
    def user_logic(message):
        uid = str(message.from_user.id)
        text = message.text
        
        # КНОПКИ
        if "Моя очередь" in text:
            markup = types.InlineKeyboardMarkup(row_width=3)
            groups = ['1.1','1.2','2.1','2.2','3.1','3.2','4.1','4.2','5.1','5.2','6.1','6.2']
            btns = [types.InlineKeyboardButton(g, callback_data=f"set_g_{g}") for g in groups]
            markup.add(*btns)
            bot.send_message(message.chat.id, "Выберите вашу очередь:", reply_markup=markup)
            return
            
        elif "Напоминание за 15 мин" in text:
            users = load_json(USERS_FILE)
            if uid not in users: users[uid] = {'group': None, 'notif_15': False}
            users[uid]['notif_15'] = not users[uid]['notif_15']
            save_json(USERS_FILE, users)
            status = "ВКЛЮЧЕНО" if users[uid]['notif_15'] else "ВЫКЛЮЧЕНО"
            bot.send_message(message.chat.id, f"🔔 Напоминание {status}", reply_markup=get_menu(uid))
            return

        # ЕСЛИ ЭТО НЕ АДМИН ПИШЕТ ТЕКСТ -> БЛОК
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "⛔ Ввод текста отключен. Пользуйтесь меню.")

    # --- 3. ИНЛАЙН КНОПКИ ---
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
        bot.send_message(call.message.chat.id, "Меню обновлено", reply_markup=get_menu(uid))

# --- ВЕБ ---
@app.route('/')
def index(): return send_from_directory('.', 'index.html')

@app.route('/ping')
def ping(): return "Я НЕ СПЛЮ"

@app.route('/data.json')
def data(): return jsonify(load_json(DATA_FILE))

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if bot:
        # Чистим старые сообщения (skip_pending) и запускаем
        print(f"🚀 ЗАПУСК БОТА ДЛЯ ID: {ADMIN_ID}", flush=True)
        threading.Thread(target=lambda: bot.infinity_polling(timeout=90, skip_pending=True), daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
