import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot

# Берем данные из того, что ТЫ УЖЕ ВПИСАЛ в Render
TOKEN = os.environ.get("BOT_TOKEN")
# Код проверит TG_API_ID, который равен 31895665
ADMIN_ID = os.environ.get("TG_API_ID") 
APP_URL = "https://svetcherkassy.onrender.com"

app = Flask(__name__)
DATA_FILE = 'data.json'

bot = None
if TOKEN:
    try:
        bot = TeleBot(TOKEN)
    except Exception as e:
        print(f"Ошибка инициализации: {e}")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if bot:
    @bot.message_handler(commands=['start'])
    def start(message):
        bot.reply_to(message, "Йеннифэр слушает. Я готова принимать графики.")

    @bot.message_handler(func=lambda m: str(m.from_user.id) == str(ADMIN_ID))
    def update_schedule(message):
        text = message.text
        data = load_data()
        updated = []
        
        # Парсим всё сообщение целиком (как на твоем скрине)
        lines = text.split('\n')
        for line in lines:
            if ":" in line:
                try:
                    parts = line.split(":", 1)
                    group = parts[0].replace("Группа", "").strip()
                    # Убираем лишние пробелы и тире
                    sched = parts[1].strip()
                    data[group] = sched
                    updated.append(group)
                except:
                    continue
        
        if updated:
            save_data(data)
            bot.reply_to(message, f"✅ Обновлено групп: {len(updated)}\nДанные: {', '.join(updated)}")
        else:
            bot.reply_to(message, "⚠️ Пришли график в формате 'Группа 1.1: время'")

def keep_alive():
    """Чтобы Render не засыпал"""
    while True:
        try:
            requests.get(APP_URL, timeout=10)
            print("🕒 Пинг: Сервер в тонусе.")
        except:
            pass
        time.sleep(600)

@app.route('/')
def index(): return send_from_directory('.', 'index.html')

@app.route('/data.json')
def get_data(): return jsonify(load_data())

@app.route('/sw.js')
def serve_sw(): return send_from_directory('.', 'sw.js')

@app.route('/manifest.json')
def serve_manifest(): return send_from_directory('.', 'manifest.json')

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    if bot:
        threading.Thread(target=lambda: bot.infinity_polling(timeout=60), daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
