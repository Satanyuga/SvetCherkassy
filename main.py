import os
import json
import time
import threading
import requests
from flask import Flask, jsonify, send_from_directory
from telebot import TeleBot

# --- НАСТРОЙКИ ---
TOKEN = "ТВОЙ_ТОКЕН_ТЕЛЕГРАМ"  # Замени на свой
ADMIN_ID = 12345678  # Твой ID
APP_URL = "https://svetcherkassy.onrender.com" # Твой URL на Render

app = Flask(__name__)
bot = TeleBot(TOKEN)
DATA_FILE = 'data.json'

# Инициализация файла данных
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({"schedule": "Нет данных"}, f)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Я Адель. Присылай график в формате:\nГруппа 4.1: 00:00-03:00, ...")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
def update_schedule(message):
    text = message.text
    # Пример парсинга: "Группа 4.1: 00:00-03:00, 06:00-09:00"
    if ":" in text:
        try:
            parts = text.split(":", 1)
            group_raw = parts[0].replace("Группа", "").strip()
            sched_raw = parts[1].strip()
            
            data = load_data()
            data[group_raw] = sched_raw
            save_data(data)
            bot.reply_to(message, f"✅ Данные для группы {group_raw} обновлены!")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {e}")
    else:
        # Если просто прислал строку — пишем в общий schedule
        data = load_data()
        data["schedule"] = text
        save_data(data)
        bot.reply_to(message, "✅ Общий график обновлен!")

# --- ФУНКЦИЯ САМОПИНГА (АНТИ-СОН) ---
def keep_alive():
    while True:
        try:
            requests.get(APP_URL)
            print("🕒 Пинг сервера: проснулся, работаю.")
        except Exception as e:
            print(f"⚠️ Ошибка пинга: {e}")
        time.sleep(600) # Пинг каждые 10 минут

# --- МАРШРУТЫ FLASK ---
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/data.json')
def get_data():
    return jsonify(load_data())

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('.', 'sw.js')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

# --- ЗАПУСК ---
if __name__ == '__main__':
    # 1. Запускаем самопинг в отдельном потоке
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # 2. Запускаем Телеграм-бота в отдельном потоке
    threading.Thread(target=lambda: bot.infinity_polling(timeout=60), daemon=True).start()
    
    # 3. Запускаем веб-сервер
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
